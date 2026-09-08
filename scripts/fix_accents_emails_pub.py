#!/usr/bin/env python3
"""Ajoute les accents francais dans les maquettes emails-pub."""
from pathlib import Path

PAIRS = [
    ("incomplete", "incomplète"),
    ("visibilite", "visibilité"),
    ("corrigees", "corrigées"),
    ("affiches", "affichés"),
    ("Des 390", "Dès 390"),
    ("etre clair", "être clair"),
    ("telephone", "téléphone"),
    ("trouve sur", "trouvé sur"),
    ("a mettre", "à mettre"),
    ("recois", "reçois"),
    ("soignes", "soignés"),
    ("annonce des", "annoncé dès"),
    ("securise", "sécurisé"),
    ("Reponse", "Réponse"),
    ("ouvrees", "ouvrées"),
    ("ecrivent", "écrivent"),
    ("ecran d", "écran d"),
    ("casse,", "cassé,"),
    ("Idee", "Idée"),
    ("coherente", "cohérente"),
    ("cote mobile", "côté mobile"),
    ("repondre", "répondre"),
    ("tete", "tête"),
    ("Reponses", "Réponses"),
    ("equipe", "équipe"),
    ("Branche sur", "Branché sur"),
    ("a la demande", "à la demande"),
    ("modele", "modèle"),
    ("metier", "métier"),
    ("Echantillons", "Échantillons"),
    # Slugs / assets / variables : garder echantillons, reputation, etc. sans accent
    ("a quoi", "à quoi"),
    ("a vendre", "à vendre"),
    ("des 390", "dès 390"),
    ("activite", "activité"),
    ("ca marche", "ça marche"),
    ("decisions", "décisions"),
    ("preferes", "préfères"),
    ("plutot", "plutôt"),
    ("qu'a l'unite", "qu'à l'unité"),
    ("a l'unite", "à l'unité"),
    ("Telechargement", "Téléchargement"),
    ("immediat", "immédiat"),
    ("Debutant", "Débutant"),
    ("securite", "sécurité"),
    ("A plus", "À plus"),
    ("Loic", "Loïc"),
]


def main() -> None:
    """Applique les remplacements d'accents sur emails-pub."""
    root = Path(__file__).resolve().parents[1] / "design" / "mockups" / "emails-pub"
    files = list(root.glob("*.html")) + [root / "README.md", root / "index.html"]
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new = text
        for old, rep in PAIRS:
            new = new.replace(old, rep)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            print("ok", path.name)


if __name__ == "__main__":
    main()
