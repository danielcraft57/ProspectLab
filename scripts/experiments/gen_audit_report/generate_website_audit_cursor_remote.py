#!/usr/bin/env python3
"""Génère un rapport d'audit web (HTML + PDF) via agent Cursor distant."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_OUTPUT_FILES = ("audit_report.html", "audit_report.pdf")
LOGGER = logging.getLogger("cursor_remote_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rapport d'audit PDF via agent Cursor distant."
    )
    parser.add_argument(
        "--local-baseline-pdf",
        default="",
        help="PDF ReportLab de référence à combiner dans le livrable final",
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--audit-json", required=True, help="Fichier JSON des données d'audit")
    parser.add_argument("--company", default="")
    parser.add_argument("--recipient-email", default="")
    parser.add_argument("--remote-host", default="loicDaniel@serv1.lan")
    parser.add_argument("--remote-workspace", default="")
    parser.add_argument("--remote-cursor-command", default="agent.cmd")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--remote-temp-root", default="C:\\Temp\\cursor_prompt_runner")
    parser.add_argument("--remote-output-root", default="C:\\Temp\\cursor_generated_audit_reports")
    parser.add_argument("--ssh-key-path", default="")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument(
        "--output-dir",
        default="scripts/experiments/gen_audit_report/generated_audit_reports",
    )
    parser.add_argument("--prompts-dir", default="scripts/experiments/gen_audit_report/prompts_cursor_remote")
    parser.add_argument("--extra-instructions", default="")
    return parser.parse_args()


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def website_slug_from_url(url: str) -> str:
    host = urlparse(url).netloc or "site"
    return re.sub(r"[^\w.\-]", "_", host) or "site"


_SSH_BIN: str | None = None
_SCP_BIN: str | None = None


def _resolve_executable(env_key: str, name: str, fallbacks: tuple[str, ...]) -> str:
    explicit = (os.environ.get(env_key) or '').strip()
    if explicit and Path(explicit).is_file():
        return explicit
    found = shutil.which(name)
    if found:
        return found
    for candidate in fallbacks:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        f"Commande « {name} » introuvable (variable {env_key} ou PATH). "
        f'Sur Debian/Raspberry Pi : sudo apt install -y openssh-client'
    )


def ssh_bin() -> str:
    global _SSH_BIN
    if _SSH_BIN is None:
        _SSH_BIN = _resolve_executable('SSH_BIN', 'ssh', ('/usr/bin/ssh', '/bin/ssh'))
    return _SSH_BIN


def scp_bin() -> str:
    global _SCP_BIN
    if _SCP_BIN is None:
        _SCP_BIN = _resolve_executable('SCP_BIN', 'scp', ('/usr/bin/scp', '/bin/scp'))
    return _SCP_BIN


def run_command(
    command: list[str],
    timeout_seconds: int,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    """
    Exécute une commande. Retourne (CompletedProcess, timed_out).
    En cas de timeout, ne lève pas : returncode=124 et timed_out=True.
    """
    LOGGER.debug("Commande: %s | timeout=%ss", " ".join(command), timeout_seconds)
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
        return proc, False
    except FileNotFoundError as exc:
        LOGGER.error('Binaire introuvable: %s', exc)
        proc = subprocess.CompletedProcess(
            command,
            returncode=127,
            stdout='',
            stderr=str(exc),
        )
        return proc, False
    except subprocess.TimeoutExpired as exc:
        LOGGER.warning("Timeout commande (%ss): %s", timeout_seconds, " ".join(command[:4]))
        partial_out = exc.output if isinstance(exc.output, str) else (exc.stdout or "")
        partial_err = exc.stderr if isinstance(exc.stderr, str) else ""
        proc = subprocess.CompletedProcess(
            command,
            returncode=124,
            stdout=partial_out or "",
            stderr=(partial_err or f"TIMEOUT after {timeout_seconds}s"),
        )
        return proc, True


def format_scp_remote_path(windows_path: str) -> str:
    """
    Chemin Windows pour OpenSSH scp (évite que C: soit lu comme un hostname).
    Ex. C:\\Temp\\foo.pdf -> /C:/Temp/foo.pdf
    """
    p = (windows_path or "").strip().replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        return f"/{p}"
    return p


def scp_target(remote_host: str, windows_path: str) -> str:
    return f"{remote_host}:{format_scp_remote_path(windows_path)}"


def _powershell_escape_single(value: str) -> str:
    """Échappe les apostrophes pour littéraux PowerShell entre quotes simples."""
    return (value or '').replace("'", "''")


def _build_remote_agent_command(
    *,
    remote_cursor_command: str,
    model: str,
    workspace_arg: str,
    set_location_stmt: str,
    prompt_instruction: str,
    remote_stdout: str,
    remote_stderr: str,
) -> str:
    """
    Lance agent.cmd sans redirection shell 1>/2> (évite « out-file : processus ne peut pas
    accéder au fichier » quand le fichier est verrouillé ou réutilisé).
    """
    cursor = _powershell_escape_single(remote_cursor_command.strip() or 'agent.cmd')
    model_esc = _powershell_escape_single(model)
    prompt_esc = _powershell_escape_single(prompt_instruction)
    out_esc = _powershell_escape_single(remote_stdout)
    err_esc = _powershell_escape_single(remote_stderr)
    ps = (
        f"{set_location_stmt} "
        f"Remove-Item -LiteralPath '{out_esc}','{err_esc}' -Force -ErrorAction SilentlyContinue; "
        f"$agentOut = & '{cursor}' --print --trust --force --output-format text "
        f"--workspace {workspace_arg} --model '{model_esc}' '{prompt_esc}' 2>&1; "
        f"$exit = $LASTEXITCODE; "
        f"$text = ($agentOut | Out-String); "
        f"[IO.File]::WriteAllText('{out_esc}', $text, [Text.UTF8Encoding]::new($false)); "
        f"if ($exit -ne 0) {{ [IO.File]::WriteAllText('{err_esc}', $text, [Text.UTF8Encoding]::new($false)) }}; "
        f"exit $exit"
    )
    return f'powershell -NoProfile -Command "{ps}"'


_SSH_OPTS = [
    '-o',
    'ConnectTimeout=20',
    '-o',
    'BatchMode=yes',
    '-o',
    'StrictHostKeyChecking=accept-new',
]


def with_ssh_key(command: list[str], ssh_key_path: str) -> list[str]:
    """ssh/scp sans TTY (Celery) : échec immédiat si clé absente."""
    tool = command[0]
    rest = command[1:]
    out = [tool, *_SSH_OPTS]
    key = (ssh_key_path or '').strip().strip('\r')
    if key and Path(key).is_file():
        out.extend(['-i', key])
    out.extend(rest)
    return out


def verify_ssh_connectivity(remote_host: str, ssh_key_path: str) -> tuple[bool, str]:
    try:
        ssh_bin()
        scp_bin()
    except FileNotFoundError as exc:
        return False, f'[ssh] {exc}'

    proc, _ = run_command(
        with_ssh_key(
            [ssh_bin(), remote_host, 'powershell', '-NoProfile', '-Command', 'echo OK'],
            ssh_key_path,
        ),
        timeout_seconds=30,
    )
    if proc.returncode == 0 and 'OK' in (proc.stdout or ''):
        return True, 'ok'
    err = (proc.stderr or proc.stdout or '').strip()
    hint = (
        f'Vérifiez : {ssh_bin()} {remote_host} — clé LANDING_VARIANTS_SSH_KEY_PATH '
        '(ex. /home/pi/.ssh/id_rsa).'
    )
    return False, f'[ssh] connexion serv1 impossible: {err or "code " + str(proc.returncode)}. {hint}'


def fetch_remote_file(remote_host: str, remote_path: str, local_path: Path, ssh_key_path: str) -> bool:
    """Rapatrie un fichier texte via SCP (plus fiable que Get-Content SSH sur Windows)."""
    return fetch_remote_binary(remote_host, remote_path, local_path, ssh_key_path)


def fetch_remote_binary(
    remote_host: str,
    remote_path: str,
    local_path: Path,
    ssh_key_path: str,
    *,
    retries: int = 3,
    retry_delay_sec: float = 2.0,
) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    last_err = ''
    for attempt in range(1, max(1, retries) + 1):
        scp, _ = run_command(
            with_ssh_key([scp_bin(), scp_target(remote_host, remote_path), str(local_path)], ssh_key_path),
            timeout_seconds=180,
        )
        if scp.returncode == 0 and local_path.is_file() and local_path.stat().st_size > 0:
            return True
        last_err = (scp.stderr or scp.stdout or '').strip()
        if attempt < retries:
            LOGGER.info(
                "SCP tentative %s/%s échouée pour %s (%s) — nouvel essai dans %ss",
                attempt,
                retries,
                remote_path,
                last_err[:120] or 'fichier absent',
                retry_delay_sec,
            )
            time.sleep(retry_delay_sec)
    LOGGER.warning("SCP binaire echoue %s: %s", remote_path, last_err)
    return False


def remote_file_size(
    remote_host: str,
    remote_path: str,
    ssh_key_path: str,
    *,
    min_bytes: int = 512,
) -> int:
    """Taille du fichier distant (0 si absent ou trop petit)."""
    ps = (
        f"if (Test-Path '{remote_path}') "
        f"{{ $s=(Get-Item '{remote_path}').Length; if ($s -ge {min_bytes}) {{ $s }} else {{ 0 }} }} "
        f"else {{ 0 }}"
    )
    proc, _ = run_command(
        with_ssh_key([ssh_bin(), remote_host, 'powershell', '-NoProfile', '-Command', ps], ssh_key_path),
        timeout_seconds=30,
    )
    if proc.returncode != 0:
        return 0
    try:
        return int((proc.stdout or "").strip().split()[-1])
    except (ValueError, IndexError):
        return 0


def _pull_agent_logs(
    remote_host: str,
    remote_stdout: str,
    remote_stderr: str,
    local_output_dir: Path,
    ssh_key_path: str,
) -> tuple[str, str]:
    local_stdout = local_output_dir / "agent_stdout.txt"
    local_stderr = local_output_dir / "agent_stderr.txt"
    fetch_remote_file(remote_host, remote_stdout, local_stdout, ssh_key_path)
    fetch_remote_file(remote_host, remote_stderr, local_stderr, ssh_key_path)
    stdout_content = local_stdout.read_text(encoding="utf-8", errors="ignore") if local_stdout.exists() else ""
    stderr_content = local_stderr.read_text(encoding="utf-8", errors="ignore") if local_stderr.exists() else ""
    return stdout_content, stderr_content


def _extract_pdf_paths_from_text(text: str) -> list[str]:
    """Chemins Windows audit_report.pdf mentionnés par l'agent dans sa sortie."""
    if not text.strip():
        return []
    pattern = r'[A-Za-z]:\\(?:[^\\\r\n<>"|]+\\)*audit_report\.pdf'
    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        path = match.group(0).strip()
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(path)
    return found


def discover_remote_audit_pdfs(
    remote_host: str,
    remote_output_root: str,
    ssh_key_path: str,
    *,
    min_bytes: int = 30_000,
) -> list[str]:
    """Recherche récursive audit_report.pdf sous le dossier de sortie serv1."""
    root = (remote_output_root or '').rstrip('\\')
    if not root:
        return []
    root_esc = _powershell_escape_single(root)
    ps = (
        f"Get-ChildItem -LiteralPath '{root_esc}' -Recurse -Filter 'audit_report.pdf' -File "
        f"-ErrorAction SilentlyContinue | Where-Object {{ $_.Length -ge {min_bytes} }} | "
        f"Sort-Object LastWriteTime -Descending | Select-Object -First 10 -ExpandProperty FullName"
    )
    proc, _ = run_command(
        with_ssh_key([ssh_bin(), remote_host, 'powershell', '-NoProfile', '-Command', ps], ssh_key_path),
        timeout_seconds=90,
    )
    if proc.returncode != 0:
        LOGGER.warning('Découverte PDF distante échouée: %s', (proc.stderr or proc.stdout or '')[:200])
        return []
    lines = [ln.strip() for ln in (proc.stdout or '').splitlines() if ln.strip()]
    return lines


def _fetch_deliverable_pdf(
    *,
    remote_host: str,
    remote_output_dir: str,
    remote_output_root: str,
    local_output_dir: Path,
    ssh_key_path: str,
    stdout_content: str,
) -> tuple[bool, str]:
    local_pdf = local_output_dir / 'audit_report.pdf'
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        p = (path or '').strip()
        if not p or p.lower() in seen:
            return
        seen.add(p.lower())
        candidates.append(p)

    _add(f'{remote_output_dir}\\audit_report.pdf')
    for path in _extract_pdf_paths_from_text(stdout_content):
        _add(path)
    for path in discover_remote_audit_pdfs(
        remote_host,
        remote_output_root,
        ssh_key_path,
    ):
        _add(path)

    LOGGER.info('Chemins PDF distants à tenter (%s): %s', len(candidates), candidates[:5])

    for remote_pdf in candidates:
        if fetch_remote_binary(remote_host, remote_pdf, local_pdf, ssh_key_path):
            remote_dir = remote_pdf.rsplit('\\', 1)[0]
            if not fetch_remote_file(
                remote_host,
                f'{remote_dir}\\audit_report.html',
                local_output_dir / 'audit_report.html',
                ssh_key_path,
            ):
                LOGGER.warning('audit_report.html non rapatrié (PDF OK depuis %s)', remote_pdf)
            return True, f'ok ({remote_pdf})'

    hint = ''
    if stdout_content.strip():
        hint = f' stdout={len(stdout_content)} car.'
        snippet = stdout_content.replace('\r', '')[-800:].strip()
        if snippet:
            LOGGER.info('Extrait stdout agent (fin): %s', snippet)
    discovered = discover_remote_audit_pdfs(
        remote_host,
        remote_output_root,
        ssh_key_path,
        min_bytes=1024,
    )
    extra = f' détectés sous {remote_output_root}: {discovered[:5]}' if discovered else ''
    return False, (
        f'[fetch] audit_report.pdf introuvable ou SCP échoué '
        f'(candidats={len(candidates)}).{hint}{extra}'
    )


def _stdout_mentions_remote_pdf(stdout_content: str, remote_output_dir: str) -> bool:
    """Détecte si l'agent a indiqué avoir produit audit_report.pdf sur le serveur distant."""
    if not stdout_content.strip():
        return False
    norm = stdout_content.replace('\\', '/').lower()
    if 'audit_report.pdf' not in norm:
        return False
    if _extract_pdf_paths_from_text(stdout_content):
        return True
    out = remote_output_dir.replace('\\', '/').lower()
    return not out or out in norm or 'cursor_generated_audit_reports' in norm


def extract_first_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _prospectlab_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_audit_agent(
    *,
    args: argparse.Namespace,
    prompt_file: Path,
    audit_json_local: Path,
    local_baseline_pdf: Path | None,
    remote_prompt_dir: str,
    remote_output_dir: str,
    local_output_dir: Path,
) -> tuple[bool, str]:
    remote_output_root = (args.remote_output_root or '').rstrip('\\')
    ok_ssh, ssh_detail = verify_ssh_connectivity(args.remote_host, args.ssh_key_path)
    if not ok_ssh:
        return False, ssh_detail

    run_tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    remote_prompt_path = f"{remote_prompt_dir}\\{prompt_file.name}"
    remote_audit_json = f"{remote_prompt_dir}\\audit_data.json"
    remote_stdout = f"{remote_prompt_dir}\\agent_stdout_{run_tag}.txt"
    remote_stderr = f"{remote_prompt_dir}\\agent_stderr_{run_tag}.txt"
    remote_prompt_esc = _powershell_escape_single(remote_prompt_dir)
    remote_output_esc = _powershell_escape_single(remote_output_dir)

    prep_cmd = (
        "powershell -NoProfile -Command "
        f"\"New-Item -ItemType Directory -Path '{remote_prompt_esc}' -Force | Out-Null; "
        f"New-Item -ItemType Directory -Path '{remote_output_esc}' -Force | Out-Null; "
        f"Remove-Item -LiteralPath '{remote_prompt_esc}\\agent_stdout_*.txt','{remote_prompt_esc}\\agent_stderr_*.txt' "
        f"-Force -ErrorAction SilentlyContinue\""
    )
    prep, _ = run_command(
        with_ssh_key([ssh_bin(), args.remote_host, prep_cmd], args.ssh_key_path),
        timeout_seconds=60,
    )
    if prep.returncode != 0:
        return False, f"[prepare] {(prep.stderr or '').strip()}"

    remote_pdf_path = f"{remote_output_dir}\\audit_report.pdf"
    existing_bytes = remote_file_size(
        args.remote_host, remote_pdf_path, args.ssh_key_path, min_bytes=50_000,
    )
    if existing_bytes >= 50_000:
        LOGGER.info(
            "PDF agent déjà présent sur le serveur distant (%s octets) — import direct.",
            existing_bytes,
        )
        stdout_content, _ = _pull_agent_logs(
            args.remote_host,
            remote_stdout,
            remote_stderr,
            local_output_dir,
            args.ssh_key_path,
        )
        ok, detail = _fetch_deliverable_pdf(
            remote_host=args.remote_host,
            remote_output_dir=remote_output_dir,
            remote_output_root=remote_output_root,
            local_output_dir=local_output_dir,
            ssh_key_path=args.ssh_key_path,
            stdout_content=stdout_content,
        )
        if ok:
            return True, f"ok (remote pdf {existing_bytes} B)"
        LOGGER.warning("PDF distant signalé mais SCP échoué (%s) — relance agent.", detail)

    uploads: list[tuple[Path, str]] = [
        (prompt_file, remote_prompt_path),
        (audit_json_local, remote_audit_json),
    ]
    remote_baseline_name = ""
    if local_baseline_pdf and local_baseline_pdf.is_file():
        remote_baseline = f"{remote_output_dir}\\audit_report_reference_baseline.pdf"
        uploads.append((local_baseline_pdf, remote_baseline))
        remote_baseline_name = remote_baseline

    for local_src, remote_dst in uploads:
        local_abs = Path(local_src).resolve()
        if not local_abs.is_file():
            return False, f"[upload] fichier local introuvable: {local_abs}"
        dest = scp_target(args.remote_host, remote_dst)
        up, _ = run_command(
            with_ssh_key([scp_bin(), str(local_abs), dest], args.ssh_key_path),
            timeout_seconds=180 if local_abs.suffix.lower() == '.pdf' else 90,
        )
        if up.returncode != 0:
            err = (up.stderr or up.stdout or "").strip()
            return False, f"[upload] {local_src.name} -> {dest}: {err}"

    prompt_instruction = (
        f"Lis {remote_prompt_path} et le fichier {remote_audit_json} ; applique exactement les instructions."
    )
    if remote_baseline_name:
        prompt_instruction += (
            f" Le PDF de référence est {remote_baseline_name} : combine et réagence "
            "ses données dans audit_report.html et audit_report.pdf."
        )
    if args.remote_workspace.strip():
        set_location_stmt = f"Set-Location -Path '{args.remote_workspace.strip()}';"
        workspace_arg = f"'{args.remote_workspace.strip()}'"
    else:
        set_location_stmt = "Set-Location -Path $env:USERPROFILE;"
        workspace_arg = "$env:USERPROFILE"

    remote_cmd = _build_remote_agent_command(
        remote_cursor_command=args.remote_cursor_command,
        model=args.model,
        workspace_arg=workspace_arg,
        set_location_stmt=set_location_stmt,
        prompt_instruction=prompt_instruction,
        remote_stdout=remote_stdout,
        remote_stderr=remote_stderr,
    )
    result, ssh_timed_out = run_command(
        with_ssh_key([ssh_bin(), args.remote_host, remote_cmd], args.ssh_key_path),
        timeout_seconds=args.agent_timeout,
    )

    stdout_content, stderr_content = _pull_agent_logs(
        args.remote_host,
        remote_stdout,
        remote_stderr,
        local_output_dir,
        args.ssh_key_path,
    )

    if ssh_timed_out:
        LOGGER.warning(
            "SSH agent timeout (%ss) — tentative récupération du PDF déjà généré sur serv1.",
            args.agent_timeout,
        )
        ok, detail = _fetch_deliverable_pdf(
            remote_host=args.remote_host,
            remote_output_dir=remote_output_dir,
            remote_output_root=remote_output_root,
            local_output_dir=local_output_dir,
            ssh_key_path=args.ssh_key_path,
            stdout_content=stdout_content,
        )
        if ok:
            return True, f"ok (recovered after ssh timeout {args.agent_timeout}s)"
        return False, (
            f"[run] timeout SSH agent ({args.agent_timeout}s). "
            f"stdout={len(stdout_content)} car. stderr={stderr_content[-300:]}"
        )

    if result.returncode != 0:
        ok, detail = _fetch_deliverable_pdf(
            remote_host=args.remote_host,
            remote_output_dir=remote_output_dir,
            remote_output_root=remote_output_root,
            local_output_dir=local_output_dir,
            ssh_key_path=args.ssh_key_path,
            stdout_content=stdout_content,
        )
        if ok:
            LOGGER.info("PDF récupéré malgré returncode SSH %s", result.returncode)
            return True, detail
        run_err = (result.stderr or result.stdout or '').strip()
        return False, detail if detail.startswith('[fetch]') else f'[run] {run_err or "code " + str(result.returncode)}'

    payload = extract_first_json_object(stdout_content)
    agent_confirmed = bool(payload and payload.get("status") == "done")
    if not agent_confirmed and not _stdout_mentions_remote_pdf(stdout_content, remote_output_dir):
        ok, detail = _fetch_deliverable_pdf(
            remote_host=args.remote_host,
            remote_output_dir=remote_output_dir,
            remote_output_root=remote_output_root,
            local_output_dir=local_output_dir,
            ssh_key_path=args.ssh_key_path,
            stdout_content=stdout_content,
        )
        if ok:
            LOGGER.info("PDF récupéré sans JSON de confirmation agent.")
            return True, detail
        return False, (
            detail
            if detail.startswith('[fetch]')
            else (
                "[run] JSON de confirmation agent introuvable ou status != done "
                f"(stdout {len(stdout_content)} car.). {stderr_content[-400:]}".strip()
            )
        )
    if not agent_confirmed:
        LOGGER.info(
            "Pas de JSON status=done ; tentative SCP du PDF distant (stdout texte agent)."
        )

    return _fetch_deliverable_pdf(
        remote_host=args.remote_host,
        remote_output_dir=remote_output_dir,
        remote_output_root=remote_output_root,
        local_output_dir=local_output_dir,
        ssh_key_path=args.ssh_key_path,
        stdout_content=stdout_content,
    )


def main() -> int:
    args = parse_args()
    args.remote_host = (args.remote_host or '').strip().strip('\r')
    args.ssh_key_path = (args.ssh_key_path or '').strip().strip('\r')
    configure_logging(args.log_level)

    root = _prospectlab_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    audit_json_path = Path(args.audit_json)
    if not audit_json_path.is_file():
        LOGGER.error("Fichier audit JSON introuvable: %s", audit_json_path)
        return 1

    try:
        audit_payload = json.loads(audit_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.error("JSON invalide: %s", exc)
        return 1

    from services.website_audit_prompt import build_audit_report_prompt

    site_slug = website_slug_from_url(args.url.strip())
    output_root = Path(args.output_dir) / site_slug
    prompts_root = Path(args.prompts_dir) / site_slug
    output_root.mkdir(parents=True, exist_ok=True)
    prompts_root.mkdir(parents=True, exist_ok=True)

    remote_temp = args.remote_temp_root.rstrip("\\")
    remote_out = args.remote_output_root.rstrip("\\")
    remote_prompt_dir = f"{remote_temp}\\audit_{site_slug}"
    remote_output_dir = f"{remote_out}\\audit_{site_slug}"

    extra = (args.extra_instructions or "").strip()
    prompt_text = build_audit_report_prompt(
        website=args.url.strip(),
        company_name=(args.company or site_slug).strip(),
        recipient_email=(args.recipient_email or "").strip(),
        audit_payload=audit_payload if isinstance(audit_payload, dict) else {},
        remote_output_dir=remote_output_dir,
    )
    if extra:
        prompt_text += f"\n\nInstructions supplementaires:\n{extra}\n"

    prompt_file = prompts_root / "audit_report.prompt.md"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    LOGGER.info("Prompt: %s", prompt_file.as_posix())
    LOGGER.info("Sortie locale: %s", output_root.as_posix())

    baseline_path: Path | None = None
    baseline_raw = (args.local_baseline_pdf or "").strip()
    if baseline_raw:
        candidate = Path(baseline_raw)
        if candidate.is_file():
            baseline_path = candidate
            LOGGER.info("PDF de référence: %s", candidate.as_posix())
        else:
            LOGGER.warning("PDF de référence introuvable: %s", baseline_raw)

    ok, detail = run_audit_agent(
        args=args,
        prompt_file=prompt_file,
        audit_json_local=audit_json_path,
        local_baseline_pdf=baseline_path,
        remote_prompt_dir=remote_prompt_dir,
        remote_output_dir=remote_output_dir,
        local_output_dir=output_root,
    )
    if not ok:
        LOGGER.error("Echec génération audit agent: %s", detail)
        print(f'AGENT_FAILURE: {detail}', flush=True)
        return 1

    pdf_path = output_root / "audit_report.pdf"
    LOGGER.info("Rapport PDF OK: %s (%s octets)", pdf_path.as_posix(), pdf_path.stat().st_size)
    print(json.dumps({"success": True, "pdf_path": str(pdf_path.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
