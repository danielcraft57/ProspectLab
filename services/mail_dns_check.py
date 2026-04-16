"""
Vérifications DNS utiles pour l'email (MX, enregistrement SPF approximatif).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def check_domain_mail_dns(domain: str) -> Dict[str, Any]:
    """
    Retourne les enregistrements MX et les TXT contenant v=spf1 pour le domaine.

    Args:
        domain: Nom de domaine (ex. danielcraft.fr)

    Returns:
        dict avec success, domain, mx_records, spf_txt, errors
    """
    domain = (domain or "").strip().lower().rstrip(".")
    out: Dict[str, Any] = {
        "success": True,
        "domain": domain,
        "mx_records": [],
        "spf_txt": [],
        "errors": [],
    }
    if not domain:
        out["success"] = False
        out["errors"].append("Domaine vide.")
        return out

    try:
        import dns.resolver
    except ImportError as e:
        out["success"] = False
        out["errors"].append(f"dnspython indisponible: {e}")
        return out

    try:
        answers = dns.resolver.resolve(domain, "MX")
        for r in answers:
            try:
                out["mx_records"].append(
                    {
                        "preference": int(r.preference),
                        "exchange": str(r.exchange).rstrip("."),
                    }
                )
            except Exception:
                out["mx_records"].append({"preference": None, "exchange": str(r)})
        out["mx_records"].sort(key=lambda x: (x.get("preference") is None, x.get("preference") or 999))
    except dns.resolver.NXDOMAIN:
        out["errors"].append("NXDOMAIN : le domaine n'existe pas dans le DNS.")
        out["success"] = False
    except dns.resolver.NoAnswer:
        out["errors"].append("Aucun enregistrement MX pour ce domaine.")
    except Exception as e:
        out["errors"].append(f"Erreur lecture MX: {e}")
        out["success"] = False

    try:
        txt_answers = dns.resolver.resolve(domain, "TXT")
        for rrset in txt_answers:
            for txt in rrset.strings:
                try:
                    s = txt.decode("utf-8", errors="replace")
                except Exception:
                    s = str(txt)
                if "v=spf1" in s.lower():
                    out["spf_txt"].append(s)
    except Exception:
        pass

    return out
