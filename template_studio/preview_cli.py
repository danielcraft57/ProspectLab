import html
import argparse
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

# Assure que le root du repo est importable quand on lance via `python template_studio/preview_cli.py`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.template_manager import TemplateManager


def _prompt(label: str, default: str = "") -> str:
    suffix = f" (default: {default})" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else default


def _prompt_int(label: str, default: Optional[int] = None) -> Optional[int]:
    raw = input(f"{label}{' [Entrée pour garder vide]' if default is None else f' [default: {default}]'}: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_li_list(raw: str) -> str:
    """
    Convertit une entrée utilisateur en liste HTML <li>...</li>.
    Autorise un format soit :
    - une liste déjà au format <li>...</li>
    - une suite d'items séparés par des retours ligne ou des virgules
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "<li" in raw:
        return raw
    parts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts.extend([p.strip() for p in line.split(",") if p.strip()])
    return "\n".join(f"<li>{p}</li>" for p in parts)


def build_preview_wrapper(rendered_html: str, template_id: str, variables_summary: Dict[str, Any]) -> str:
    escaped_srcdoc = html.escape(rendered_html or "", quote=True)
    summary_items = []
    for k in sorted(variables_summary.keys()):
        v = variables_summary.get(k)
        if v is None or v == "":
            continue
        summary_items.append(f"<div><strong>{html.escape(str(k))}</strong>: {html.escape(str(v))}</div>")
    summary_html = "\n".join(summary_items) if summary_items else "<div>Aucune variable spéciale.</div>"

    ts = int(time.time())
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Template preview - {html.escape(template_id)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 16px auto; padding: 0 12px; max-width: 1120px; }}
    .top {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; background: #fff; }}
    iframe {{ width: 100%; height: 920px; border: 1px solid #e5e7eb; border-radius: 10px; margin-top: 12px; }}
    textarea {{ width: 100%; height: 240px; margin-top: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 12px; }}
    .muted {{ color: #6b7280; font-size: 12px; }}
    .preview-note {{ margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="top">
    <div class="card">
      <h1 style="margin:0 0 8px 0; font-size: 18px;">Preview template: {html.escape(template_id)}</h1>
      <div class="muted">Généré à {ts}</div>
      <div class="preview-note">
        <div class="muted">Note: certains emails HTML sont optimisés pour les clients mail (tables/layout inline). Ici on rend via navigateur pour vérification visuelle rapide.</div>
      </div>
    </div>
    <div class="card">
      <h2 style="margin:0 0 8px 0; font-size: 14px;">Variables spéciales</h2>
      {summary_html}
    </div>
  </div>

  <iframe sandbox="" srcdoc="{escaped_srcdoc}"></iframe>

  <details style="margin-top: 12px;">
    <summary style="cursor: pointer;">Voir le HTML rendu (debug)</summary>
    <textarea readonly>{html.escape(rendered_html or "")}</textarea>
  </details>
</body>
</html>"""


def render_and_preview(
    template_manager: TemplateManager,
    template_id: str,
    nom: str,
    entreprise: str,
    email: str,
    entreprise_id: Optional[int],
    extended_overrides: Dict[str, Any],
    open_browser: bool = True,
) -> str:
    content, is_html = template_manager.render_template(
        template_id=template_id,
        nom=nom,
        entreprise=entreprise,
        email=email,
        entreprise_id=entreprise_id,
        extended_overrides=extended_overrides,
    )
    rendered = content or ""
    if not is_html:
        print("Alerte: le template ne semble pas être du HTML (is_html=False). La preview tentera quand même d'afficher le rendu.")

    preview_dir = ROOT / ".template_studio_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    preview_file = preview_dir / f"preview_{template_id}_{stamp}.html"

    variables_summary = dict(extended_overrides)
    variables_summary["nom"] = nom
    variables_summary["entreprise"] = entreprise
    variables_summary["email"] = email
    variables_summary["entreprise_id"] = entreprise_id

    wrapper = build_preview_wrapper(
        rendered_html=rendered,
        template_id=template_id,
        variables_summary=variables_summary,
    )
    preview_file.write_text(wrapper, encoding="utf-8")

    url = f"file:///{preview_file.as_posix()}"
    if open_browser:
        webbrowser.open_new_tab(url)
    return str(preview_file)


def main() -> int:
    parser = argparse.ArgumentParser(description="Template Studio - preview HTML (render navigateur via srcdoc).")
    parser.add_argument("--defaults", action="store_true", help="Mode non-interactif : valeurs par défaut (sans questions).")
    parser.add_argument("--template-id", default="", help="ID du template à prévisualiser (sinon 1er template HTML).")
    parser.add_argument("--nom", default="Loïc", help="Nom du destinataire (pour la prévisualisation).")
    parser.add_argument("--entreprise", default="DanielCraft", help="Nom de l'entreprise.")
    parser.add_argument("--email", default="", help="Email (pour le tracking/lien analyse si présent).")
    parser.add_argument("--website", default="https://exemple.com", help="Website (pour activer {#if_website} et donc voir les liens analyse/désabonnement).")
    parser.add_argument("--secteur", default="", help="Secteur (pour {#if_secteur}).")
    parser.add_argument("--no-open", action="store_true", help="Ne pas ouvrir le navigateur (utile en CI).")
    args = parser.parse_args()

    tm = TemplateManager()

    templates = [t for t in tm.list_templates() if t.get("is_html") or t.get("category") == "html_email"]
    if not templates:
        print("Aucun template HTML trouvé. Lance d'abord template_studio/generate_cli.py --write-default puis --restore.")
        return 2

    if args.defaults:
        nom = args.nom
        entreprise = args.entreprise
        email = args.email
        entreprise_id = None
        extended_overrides = {
            # Valeurs mock NON-vides pour que les blocs {#if_...} s'affichent.
            "secteur": (args.secteur or "E-commerce") or None,
            "website": args.website or None,  # doit être non vide pour voir les liens analyse/désabonnement
            "framework": "React",
            "cms": "WordPress",
            "hosting_provider": "OVHcloud",
            # Scores volontairement bas (preview “site en difficulté”)
            "performance_score": 34,
            "security_score": 22,
            "pages_scanned": 18,
            "avg_response_time_ms": 1280,
            # Pentest : score surface distinct du score sécurité analyse technique (templates récents)
            "has_pentest": True,
            "has_pentest_surface_score": True,
            "pentest_surface_score": 22,
            "technical_security_score": 31,
            "has_technical_security_score": True,
            "show_technical_security_score": False,
            # Pentest (mock) pour visualiser les blocs du template "score zero"
            "has_security_headers_missing_top": True,
            "security_headers_missing_count": 6,
            "security_headers_missing_top": _normalize_li_list(
                "Strict-Transport-Security, Content-Security-Policy, X-Frame-Options"
            ),
            "vulnerabilities_count": 12,
            "has_vulnerabilities_top": True,
            "vulnerabilities_top": _normalize_li_list(
                "Cookie de session exposé sur une route sensible du tunnel de commande\n"
                "Absence de CSP sur les pages qui affichent des formulaires\n"
                "Bibliothèque JavaScript tierce en fin de vie (CVE connues, mises à jour arrêtées)"
            ),
            "total_emails": 120,
            "total_people": 60,
            "total_social_count": 4,
            "seo_issues": _normalize_li_list(
                "Plusieurs pages sans balise title unique (risque de titres dupliqués dans Google)\n"
                "Meta descriptions absentes ou quasi vides sur les pages produit\n"
                "Core Web Vitals instables (LCP élevé sur mobile, ressources bloquantes)\n"
                "Sitemap incomplet : des URLs importantes ne sont pas déclarées au crawler"
            ),
        }

        if args.template_id:
            template_id = args.template_id
        else:
            template_id = templates[0].get("id")
    else:
        print("\nTemplates HTML disponibles :")
        for idx, t in enumerate(templates, start=1):
            print(f"{idx}. {t.get('id')} — {t.get('name')} — subject: {t.get('subject')}")

        choice = input("\nChoisissez un template (id ou numéro): ").strip()
        if choice.isdigit():
            i = int(choice) - 1
            if i < 0 or i >= len(templates):
                print("Choix invalide.")
                return 2
            template_id = templates[i].get("id")
        else:
            template_id = choice
            if not any(t.get("id") == template_id for t in templates):
                print(f"Template id inconnu: {template_id}")
                return 2

        nom = _prompt("Nom du destinataire", default="Loïc")
        entreprise = _prompt("Nom de l'entreprise", default="DanielCraft")
        # En mode interactif "simple", on évite toutes les questions inutiles :
        # - pas d'email => pas de tracking
        # - website pré-rempli => pour afficher les liens analyse/désabonnement ({#if_website})
        email = ""
        entreprise_id = None
        extended_overrides = {
            # Valeurs mock NON-vides pour afficher une preview la plus complète possible.
            "secteur": "E-commerce",
            "website": "https://exemple.com",
            "framework": "React",
            "cms": "WordPress",
            "hosting_provider": "OVHcloud",
            "performance_score": 34,
            "security_score": 22,
            "pages_scanned": 18,
            "avg_response_time_ms": 1280,
            "has_pentest": True,
            "has_pentest_surface_score": True,
            "pentest_surface_score": 22,
            "technical_security_score": 31,
            "has_technical_security_score": True,
            "show_technical_security_score": False,
            "has_security_headers_missing_top": True,
            "security_headers_missing_count": 6,
            "security_headers_missing_top": _normalize_li_list(
                "Strict-Transport-Security, Content-Security-Policy, X-Frame-Options"
            ),
            "vulnerabilities_count": 12,
            "has_vulnerabilities_top": True,
            "vulnerabilities_top": _normalize_li_list(
                "Cookie de session exposé sur une route sensible du tunnel de commande\n"
                "Absence de CSP sur les pages qui affichent des formulaires\n"
                "Bibliothèque JavaScript tierce en fin de vie (CVE connues, mises à jour arrêtées)"
            ),
            "total_emails": 120,
            "total_people": 60,
            "total_social_count": 4,
            "seo_issues": _normalize_li_list(
                "Plusieurs pages sans balise title unique (risque de titres dupliqués dans Google)\n"
                "Meta descriptions absentes ou quasi vides sur les pages produit\n"
                "Core Web Vitals instables (LCP élevé sur mobile, ressources bloquantes)\n"
                "Sitemap incomplet : des URLs importantes ne sont pas déclarées au crawler"
            ),
        }

    preview_file = render_and_preview(
        template_manager=tm,
        template_id=template_id,
        nom=nom,
        entreprise=entreprise,
        email=email,
        entreprise_id=entreprise_id,
        extended_overrides=extended_overrides,
        open_browser=not args.no_open,
    )

    print(f"\nPreview générée : {preview_file}")
    print("Vous pouvez modifier les valeurs et relancer la commande pour régénérer une nouvelle preview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

