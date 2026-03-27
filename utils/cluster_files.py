from __future__ import annotations

import os
import subprocess
from pathlib import Path


def is_windows_path(p: str) -> bool:
    if not p:
        return False
    return bool(len(p) >= 3 and p[1] == ":" and (p[2] == "\\" or p[2] == "/"))


def cluster_copy_upload_to_workers(local_filepath: str, remote_filename: str | None = None) -> str:
    """
    Copie un fichier upload (Windows) vers tous les workers Linux du cluster via scp.

    Paramètres via variables d'environnement (typiquement dans .env.cluster):
    - CLUSTER_WORKER_NODES: "node13.lan,node14.lan"
    - CLUSTER_WORKER_USER: "pi" (défaut)
    - CLUSTER_REMOTE_PATH: "/opt/prospectlab" (défaut)

    Retourne le chemin Linux à utiliser dans la tâche Celery, ex:
    /opt/prospectlab/uploads/mon_fichier.xlsx
    """
    nodes_raw = (os.environ.get("CLUSTER_WORKER_NODES") or "").strip()
    if not nodes_raw:
        raise RuntimeError("CLUSTER_WORKER_NODES manquant (ex: node13.lan,node14.lan)")

    user = (os.environ.get("CLUSTER_WORKER_USER") or "pi").strip()
    remote_root = (os.environ.get("CLUSTER_REMOTE_PATH") or "/opt/prospectlab").strip().rstrip("/")
    remote_upload_dir = f"{remote_root}/uploads"

    local_path = str(Path(local_filepath).resolve())
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)

    remote_name = remote_filename or Path(local_path).name
    remote_path = f"{remote_upload_dir}/{remote_name}"

    nodes = [n.strip() for n in nodes_raw.split(",") if n.strip()]
    if not nodes:
        raise RuntimeError("CLUSTER_WORKER_NODES vide")

    # mkdir uploads/ sur chaque noeud, puis scp le fichier
    for node in nodes:
        target = f"{user}@{node}"

        mkdir_cmd = ["ssh", "-o", "ConnectTimeout=8", target, "mkdir", "-p", remote_upload_dir]
        r1 = subprocess.run(mkdir_cmd, capture_output=True, text=True)
        if r1.returncode != 0:
            raise RuntimeError(f"SSH mkdir échoué sur {node}: {r1.stderr or r1.stdout}".strip())

        scp_cmd = ["scp", local_path, f"{target}:{remote_path}"]
        r2 = subprocess.run(scp_cmd, capture_output=True, text=True)
        if r2.returncode != 0:
            raise RuntimeError(f"SCP échoué vers {node}: {r2.stderr or r2.stdout}".strip())

    return remote_path

