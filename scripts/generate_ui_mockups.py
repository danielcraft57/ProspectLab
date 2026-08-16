# -*- coding: utf-8 -*-
"""Génère le maximum de maquettes HTML Material Design 3 (dossier gitignoré)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'design' / 'mockups'
PAGES = ROOT / 'pages'
ASSETS = ROOT / 'assets'
PAGES.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

# Loi de Hick (@clea_ux) : max 7 intentions niveau 1, action clé en tête
NAV_KEYS = [
    'dash', 'onb', 'ent', 'entd', 'carte', 'graph', 'marche',
    'audit', 'tech', 'osint', 'pentest', 'seo', 'scrap',
    'camp', 'campd', 'send', 'tpl', 'bounce', 'victoire',
    'dom', 'api', 'upload', 'set', 'kit', 'search0',
]

NAV = """
<aside class="md-nav">
  <div class="md-brand">
    <div class="md-brand-mark">P</div>
    <div><strong>ProspectLab</strong><span>Daniel Craft</span></div>
  </div>
  <a class="item md-nav-ctv {dash}" href="dashboard.html">Commencer ici</a>
  <a class="item {onb}" href="onboarding.html">Premiere victoire</a>
  <div class="md-nav-section">Par intention · Hick ≤7</div>
  <a class="item {ent}" href="entreprises.html">Prospection</a>
  <a class="item {audit}" href="analyse-site.html">Analyses</a>
  <a class="item {camp}" href="campagnes.html">Envois email</a>
  <a class="item {bounce}" href="bounces.html">Hygiene listes</a>
  <a class="item {dom}" href="domaines.html">Delivrabilite</a>
  <a class="item {upload}" href="upload.html">Importer</a>
  <a class="item {set}" href="settings.html">Reglages</a>
  <div class="md-nav-section">Sous-pages (maquettes)</div>
  <a class="item {entd}" href="entreprise-detail.html">Fiche entreprise</a>
  <a class="item {carte}" href="carte.html">Carte</a>
  <a class="item {graph}" href="graph.html">Graphe</a>
  <a class="item {marche}" href="concurrence.html">Concurrence</a>
  <a class="item {tech}" href="analyses-tech.html">Tech</a>
  <a class="item {osint}" href="analyses-osint.html">OSINT</a>
  <a class="item {pentest}" href="analyses-pentest.html">Pentest</a>
  <a class="item {seo}" href="analyses-seo.html">SEO</a>
  <a class="item {scrap}" href="scrapers.html">Scrapers</a>
  <a class="item {campd}" href="campagne-detail.html">Campagne detail</a>
  <a class="item {send}" href="envoyer.html">Envoi rapide</a>
  <a class="item {tpl}" href="modeles.html">Modeles</a>
  <a class="item {victoire}" href="victoire.html">Ecran victoire</a>
  <a class="item {api}" href="api.html">API</a>
  <a class="item {kit}" href="composants.html">Kit MD3</a>
  <a class="item {search0}" href="recherche-vide.html">Recherche 0 resultat</a>
</aside>
"""

CSS = (
    '<link rel="stylesheet" href="../assets/md3.css" />'
    '<link rel="stylesheet" href="../assets/md3-extra.css" />'
    '<link rel="stylesheet" href="../assets/charts.css" />'
)

LINE = """
<svg class="md-line-chart" viewBox="0 0 520 180" preserveAspectRatio="none">
  <g class="grid">
    <line x1="40" y1="20" x2="500" y2="20"/><line x1="40" y1="60" x2="500" y2="60"/>
    <line x1="40" y1="100" x2="500" y2="100"/><line x1="40" y1="140" x2="500" y2="140"/>
  </g>
  <path class="area" d="M40,120 L100,100 L160,110 L220,70 L280,85 L340,50 L400,60 L460,35 L500,45 L500,160 L40,160 Z"/>
  <path class="line" d="M40,120 L100,100 L160,110 L220,70 L280,85 L340,50 L400,60 L460,35 L500,45"/>
  <path class="line2" d="M40,130 L100,125 L160,118 L220,105 L280,100 L340,90 L400,88 L460,80 L500,78"/>
  <circle class="dot" cx="500" cy="45" r="4"/>
  <text class="axis-lbl" x="40" y="175">Lun</text>
  <text class="axis-lbl" x="220" y="175">Mer</text>
  <text class="axis-lbl" x="400" y="175">Ven</text>
</svg>
"""

RADAR = """
<svg class="md-radar" viewBox="0 0 200 200">
  <polygon fill="none" stroke="rgba(255,255,255,.08)" points="100,20 168,60 168,140 100,180 32,140 32,60"/>
  <polygon fill="none" stroke="rgba(255,255,255,.08)" points="100,50 145,75 145,125 100,150 55,125 55,75"/>
  <polygon fill="rgba(61,214,140,.25)" stroke="#3dd68c" stroke-width="2" points="100,40 155,70 150,130 100,155 50,120 55,70"/>
</svg>
"""

SLOPE = """
<div class="md-slope">
  <div class="side"><span>1. Atelier</span><span>2. Forge</span><span>3. Lumen</span><span>4. Metz H.</span></div>
  <svg viewBox="0 0 200 120" preserveAspectRatio="none">
    <line x1="10" y1="15" x2="190" y2="40" stroke="#3dd68c" stroke-width="2"/>
    <line x1="10" y1="40" x2="190" y2="20" stroke="#7eb8ff" stroke-width="2"/>
    <line x1="10" y1="70" x2="190" y2="85" stroke="#ffb74d" stroke-width="2"/>
    <line x1="10" y1="95" x2="190" y2="70" stroke="#ff8a80" stroke-width="2"/>
    <circle cx="10" cy="15" r="4" fill="#3dd68c"/><circle cx="190" cy="40" r="4" fill="#3dd68c"/>
    <circle cx="10" cy="40" r="4" fill="#7eb8ff"/><circle cx="190" cy="20" r="4" fill="#7eb8ff"/>
  </svg>
  <div class="side" style="text-align:right"><span>2. Atelier</span><span>1. Forge</span><span>4. Lumen</span><span>3. Metz H.</span></div>
</div>
"""


def spark(cls=''):
    return f'''<svg class="md-spark {cls}" viewBox="0 0 120 40" preserveAspectRatio="none">
  <path class="fill" d="M0,32 L10,28 L20,30 L30,18 L40,22 L50,12 L60,16 L70,8 L80,14 L90,10 L100,6 L110,12 L120,8 L120,40 L0,40 Z"/>
  <path class="line" d="M0,32 L10,28 L20,30 L30,18 L40,22 L50,12 L60,16 L70,8 L80,14 L90,10 L100,6 L110,12 L120,8"/>
</svg>'''


def shell(active, title, sub, body, actions='', fab='+', fab_ext=None):
    nav = NAV.format(**{k: ('is-active' if k == active else '') for k in NAV_KEYS})
    fab_html = (
        f'<button class="md-fab-ext">{fab_ext}</button>'
        if fab_ext else
        f'<button class="md-fab" title="Action">{fab}</button>'
    )
    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} | ProspectLab maquette</title>
  {CSS}
</head>
<body>
<div class="md-app">
{nav}
<main class="md-main">
  <div class="md-topbar">
    <div><h1>{title}</h1><p>{sub}</p></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">{actions}</div>
  </div>
  {body}
</main>
</div>
{fab_html}
</body>
</html>
'''


def bare(title, body):
    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} | ProspectLab maquette</title>
  {CSS.replace('../assets/', 'assets/') if False else CSS}
</head>
<body>{body}</body>
</html>
'''.replace('href="../assets/', 'href="assets/')


def analysis_body(kind, scores):
    bars = ''.join(
        f'<div class="bar {"alt" if i % 2 else ""}{" warn" if v < 50 else ""}">'
        f'<i style="height:{v}%"></i><span class="lbl">{k}</span></div>'
        for i, (k, v) in enumerate(scores.items())
    )
    return f'''
<div class="md-tabs">
  <button class="is-active">Historique</button><button>Comparaison</button>
  <button>Timeline</button><button>Export</button>
</div>
<div class="md-grid md-grid-4 md-anim-in" style="margin-bottom:16px">
  <div class="md-card md-stat"><div class="label">En cours</div><div class="value">3</div></div>
  <div class="md-card md-stat"><div class="label">Terminees</div><div class="value">47</div></div>
  <div class="md-card md-stat"><div class="label">Score moyen</div><div class="value" style="color:var(--md-sys-color-primary)">72</div></div>
  <div class="md-card md-stat"><div class="label">Echecs</div><div class="value" style="color:var(--md-sys-color-error)">2</div></div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad md-anim-in-2">
    <div class="md-chart-title"><h3>Scores {kind}</h3><span class="hint">derniere vague</span></div>
    <div class="md-bars">{bars}</div>
  </div>
  <div class="md-card md-card-pad md-anim-in-2">
    <div class="md-chart-title"><h3>Tendance 30 j</h3></div>{LINE}
  </div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad">
    <div class="md-chart-title"><h3>Bullet cibles</h3></div>
    <div class="md-bullet">
      <div class="row"><span>Perf</span><div class="track"><div class="range" style="width:80%"></div><div class="fill" style="width:65%"></div><div class="marker" style="left:75%"></div></div></div>
      <div class="row"><span>Secu</span><div class="track"><div class="range" style="width:90%"></div><div class="fill" style="width:82%"></div><div class="marker" style="left:85%"></div></div></div>
      <div class="row"><span>SEO</span><div class="track"><div class="range" style="width:70%"></div><div class="fill" style="width:58%"></div><div class="marker" style="left:70%"></div></div></div>
    </div>
  </div>
  <div class="md-card md-card-pad">
    <div class="md-chart-title"><h3>Repartition enjeux</h3></div>
    <div class="md-treemap">
      <div class="a">Critique<span>12 findings</span></div>
      <div class="b">Haut<span>18</span></div>
      <div class="c">Moyen<span>31</span></div>
      <div class="d">Faible<span>44</span></div>
      <div class="e">Info<span>9</span></div>
    </div>
  </div>
</div>
<div class="md-card">
  <table class="md-table dense"><thead><tr><th>Cible</th><th>Statut</th><th>Score</th><th>Detail</th><th>Date</th></tr></thead>
  <tbody>
  <tr><td>exemple-pro.fr</td><td><span class="md-chip ok">OK</span></td><td class="num">78</td>
    <td><div class="md-stack-bar"><i style="width:40%;background:#3dd68c"></i><i style="width:25%;background:#7eb8ff"></i><i style="width:20%;background:#ffb74d"></i><i style="width:15%;background:#ff8a80"></i></div></td><td>16/08</td></tr>
  <tr><td>site-demo.com</td><td><span class="md-chip warn">En cours</span></td><td class="num">-</td>
    <td><div class="md-linear"><i style="width:45%"></i></div></td><td>16/08</td></tr>
  <tr><td>atelier-nord.fr</td><td><span class="md-chip ok">OK</span></td><td class="num">82</td>
    <td><div class="md-stack-bar"><i style="width:50%;background:#3dd68c"></i><i style="width:30%;background:#7eb8ff"></i><i style="width:15%;background:#ffb74d"></i><i style="width:5%;background:#ff8a80"></i></div></td><td>15/08</td></tr>
  </tbody></table>
  <div class="md-pagination"><span>1-50 sur 47</span><div class="md-page-btns">
    <button>‹</button><button class="is-active">1</button><button>2</button><button>›</button>
  </div></div>
</div>
'''


def build_pages():
    out = []

    # Dashboard max
    out.append(('dashboard.html', 'dash', 'Dashboard',
        "Vue d'ensemble · preuve de valeur avant config (@clea_ux TTV)",
        '<div class="md-segmented"><button class="is-active">7 j</button><button>30 j</button><button>90 j</button></div>'
        '<button class="md-btn md-btn-filled">Voir mon 1er envoi reussi</button>',
        f'''
<div class="md-ctv-block md-anim-in">
  <h2>Voir ce que Brevo a delivre aujourd'hui</h2>
  <p>CTV (@clea_ux) : on parle du resultat, pas du bouton. Action cle ProspectLab = premier email delivre + ouvert.</p>
  <div class="actions">
    <a class="md-btn md-btn-filled" href="campagne-detail.html">Ouvrir Presence digitale</a>
    <a class="md-btn md-btn-outlined" href="onboarding.html">Premiere victoire (~2 min)</a>
    <span class="hint">1 CTV + 1 secondaire · loi de Hick</span>
  </div>
</div>
<div class="md-zeigarnik">
  <span><strong>Effet Zeigarnik</strong> — checklist activation 2/4</span>
  <a class="md-btn md-btn-tonal" style="padding:6px 12px;font-size:.75rem" href="onboarding.html">Continuer</a>
</div>
<div class="md-banner md-anim-in" style="margin-bottom:16px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center">
  <span><span class="md-dot-live"></span> Sync Brevo OK · 294 credits · SMTP relay actif</span>
  <button class="md-btn md-btn-outlined" style="padding:6px 12px;font-size:.75rem">Voir quota</button>
</div>
<div class="md-grid md-grid-4" style="margin-bottom:16px">
  <div class="md-card md-card-pad md-kpi-spark md-anim-in"><div style="font-size:.72rem;text-transform:uppercase;color:var(--md-sys-color-on-surface-variant)">Entreprises</div>
    <div style="font-size:1.55rem;font-weight:650">1 248</div><div class="delta up">+12 cette semaine</div>{spark()}</div>
  <div class="md-card md-card-pad md-kpi-spark md-anim-in-2"><div style="font-size:.72rem;text-transform:uppercase;color:var(--md-sys-color-on-surface-variant)">Emails</div>
    <div style="font-size:1.55rem;font-weight:650">412</div><div class="delta up">+6 aujourd'hui</div>{spark("blue")}</div>
  <div class="md-card md-card-pad md-kpi-spark md-anim-in-2"><div style="font-size:.72rem;text-transform:uppercase;color:var(--md-sys-color-on-surface-variant)">Ouverture</div>
    <div style="font-size:1.55rem;font-weight:650;color:var(--md-sys-color-primary)">34%</div><div class="delta up">+2,1 pts</div>{spark()}</div>
  <div class="md-card md-card-pad md-kpi-spark md-anim-in-3"><div style="font-size:.72rem;text-transform:uppercase;color:var(--md-sys-color-on-surface-variant)">Credits</div>
    <div style="font-size:1.55rem;font-weight:650">294</div><div class="delta down">-6 aujourd'hui</div>{spark("amber")}</div>
</div>
<div class="md-metric-row" style="margin-bottom:16px">
  <div class="md-metric-pill">Campagnes actives<strong>2</strong></div>
  <div class="md-metric-pill">Analyses en cours<strong>3</strong></div>
  <div class="md-metric-pill">Bounces a traiter<strong style="color:var(--md-sys-color-error)">15</strong></div>
  <div class="md-metric-pill">Scrapers OK<strong>6/7</strong></div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Volume d'envoi</h3><span class="hint">PL vs Brevo</span></div>{LINE}
    <div class="md-chart-legend"><span><i style="background:#3dd68c"></i>Envoyes</span><span><i style="background:#7eb8ff"></i>Delivres</span></div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Evenements</h3></div>
    <div class="md-donut-wrap">
      <div class="md-donut" data-center="412" style="background:conic-gradient(#3dd68c 0 55%,#7eb8ff 55% 78%,#ffb74d 78% 92%,#ff8a80 92% 100%)"></div>
      <div class="md-legend">
        <div class="item"><span class="dot" style="background:#3dd68c"></span> Delivres</div>
        <div class="item"><span class="dot" style="background:#7eb8ff"></span> Ouverts</div>
        <div class="item"><span class="dot" style="background:#ffb74d"></span> Soft</div>
        <div class="item"><span class="dot" style="background:#ff8a80"></span> Hard</div>
      </div>
    </div>
  </div>
</div>
<div class="md-grid md-grid-3" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Pipeline</h3></div>
    <div class="md-funnel">
      <div class="step"><span>Leads</span><strong>1248</strong></div>
      <div class="step"><span>Qualifies</span><strong>214</strong></div>
      <div class="step"><span>Contactes</span><strong>86</strong></div>
      <div class="step"><span>Reponses</span><strong>11</strong></div>
    </div>
  </div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Activite carte</h3></div>
    <div class="md-heat">
      <div class="lbl"></div><div class="lbl">L</div><div class="lbl">M</div><div class="lbl">M</div><div class="lbl">J</div><div class="lbl">V</div><div class="lbl">S</div><div class="lbl">D</div>
      <div class="lbl">S1</div><div class="cell c1"></div><div class="cell c2"></div><div class="cell c3"></div><div class="cell c2"></div><div class="cell c4"></div><div class="cell"></div><div class="cell"></div>
      <div class="lbl">S2</div><div class="cell c2"></div><div class="cell c3"></div><div class="cell c4"></div><div class="cell c3"></div><div class="cell c2"></div><div class="cell c1"></div><div class="cell"></div>
      <div class="lbl">S3</div><div class="cell c1"></div><div class="cell c2"></div><div class="cell c2"></div><div class="cell c4"></div><div class="cell c3"></div><div class="cell"></div><div class="cell c1"></div>
    </div>
  </div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Calendrier envois</h3></div>
    <div class="md-cal">
      <div class="hd">L</div><div class="hd">M</div><div class="hd">M</div><div class="hd">J</div><div class="hd">V</div><div class="hd">S</div><div class="hd">D</div>
      <div class="d"></div><div class="d"></div><div class="d">1</div><div class="d dot">2</div><div class="d">3</div><div class="d">4</div><div class="d">5</div>
      <div class="d">6</div><div class="d">7</div><div class="d">8</div><div class="d">9</div><div class="d">10</div><div class="d">11</div><div class="d">12</div>
      <div class="d">13</div><div class="d">14</div><div class="d on">15</div><div class="d dot">16</div><div class="d">17</div><div class="d">18</div><div class="d">19</div>
    </div>
  </div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Activite</h3></div>
    <div class="md-timeline">
      <div class="ev"><strong>Campagne Presence digitale terminee</strong><span>il y a 2 h</span></div>
      <div class="ev"><strong>Hard bounce sync Brevo</strong><span>il y a 3 h</span></div>
      <div class="ev"><strong>12 entreprises importees</strong><span>hier</span></div>
      <div class="ev"><strong>Analyse SEO atelier-nord.fr</strong><span>hier · 78</span></div>
    </div>
  </div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Sante</h3><span class="md-chip ok">OK</span></div>
    <div class="md-hbar">
      <div class="row"><span>Open</span><div class="track"><i style="width:34%"></i></div><span class="val">34%</span></div>
      <div class="row"><span>Click</span><div class="track blue"><i style="width:9%"></i></div><span class="val">9%</span></div>
      <div class="row"><span>Bounce</span><div class="track amber"><i style="width:4%"></i></div><span class="val">4%</span></div>
      <div class="row"><span>Spam</span><div class="track red"><i style="width:1%"></i></div><span class="val">0%</span></div>
    </div>
    <div class="md-divider"></div>
    <div class="md-waterfall">
      <div class="w"><span style="width:70px">Quota</span><div class="bar" style="width:8%">6/300</div></div>
      <div class="w"><span style="width:70px">IMAP</span><div class="bar" style="width:100%;background:linear-gradient(90deg,#3b82c4,#7eb8ff)">OK</div></div>
    </div>
  </div>
</div>
''', 'Nouvelle campagne'))

    # Entreprises
    out.append(('entreprises.html', 'ent', 'Entreprises',
        'Liste densifiee, filtres, selection et scores',
        '<button class="md-btn md-btn-outlined">Importer</button><button class="md-btn md-btn-filled">+ Entreprise</button>',
        f'''
<div class="md-toolbar">
  <div class="md-search" style="flex:1;min-width:200px"><span>&#128269;</span><input placeholder="Nom, secteur, email..." /></div>
  <button class="md-filter-chip on">Principaux</button>
  <button class="md-filter-chip">Exclure fictifs</button>
  <button class="md-filter-chip">Priorite &gt; 60</button>
  <button class="md-btn md-btn-tonal">Filtres</button>
</div>
<div class="md-tabs"><button class="is-active">Toutes</button><button>A qualifier</button><button>En campagne</button><button>Archives</button></div>
<div class="md-grid md-grid-3" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Priorites</h3></div>
    <div class="md-bars" style="height:110px">
      <div class="bar"><i style="height:82%"></i><span class="lbl">80+</span></div>
      <div class="bar alt"><i style="height:55%"></i><span class="lbl">60</span></div>
      <div class="bar warn"><i style="height:38%"></i><span class="lbl">40</span></div>
      <div class="bar"><i style="height:22%;opacity:.5"></i><span class="lbl">&lt;40</span></div>
    </div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Secteurs</h3></div>
    <div class="md-lollipop">
      <div class="row"><span>Industrie</span><div class="line" style="--p:72%"><i style="width:72%"></i></div></div>
      <div class="row"><span>Agence</span><div class="line" style="--p:48%"><i style="width:48%"></i></div></div>
      <div class="row"><span>Immo</span><div class="line" style="--p:35%"><i style="width:35%"></i></div></div>
    </div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Selection</h3><span class="md-chip ok">3</span></div>
    <button class="md-btn md-btn-filled" style="width:100%;margin-bottom:10px">Ajouter a campagne</button>
    <div class="md-snackbar" style="width:100%"><span>Filtres actifs</span><button class="act">Reset</button></div>
  </div>
</div>
<div class="md-card">
  <table class="md-table dense"><thead><tr><th></th><th>Entreprise</th><th>Secteur</th><th>Priorite</th><th>Email</th><th>Score</th></tr></thead>
  <tbody>
  <tr><td><span class="md-check on">&#10003;</span></td><td><strong>Atelier Nord</strong><div style="font-size:.75rem;color:var(--md-sys-color-on-surface-variant)">atelier-nord.fr</div></td><td>Industrie</td><td><span class="md-chip ok">82</span></td><td>contact@atelier-nord.fr</td><td><div class="md-progress-circ" style="--p:.82" data-label="82"></div></td></tr>
  <tr><td><span class="md-check"></span></td><td><strong>Studio Lumen</strong></td><td>Agence</td><td><span class="md-chip warn">61</span></td><td>hello@studio-lumen.com</td><td><div class="md-progress-circ" style="--p:.61" data-label="61"></div></td></tr>
  <tr><td><span class="md-check"></span></td><td><strong>Metz Habitat</strong></td><td>Immo</td><td><span class="md-chip neutral">44</span></td><td>info@metz-habitat.fr</td><td><div class="md-progress-circ" style="--p:.44" data-label="44"></div></td></tr>
  <tr><td><span class="md-check on">&#10003;</span></td><td><strong>Forge Digitale</strong></td><td>Tech</td><td><span class="md-chip ok">77</span></td><td>bonjour@forge.digital</td><td><div class="md-progress-circ" style="--p:.77" data-label="77"></div></td></tr>
  </tbody></table>
  <div class="md-pagination"><span>1-50 sur 1248</span><div class="md-page-btns"><button>‹</button><button class="is-active">1</button><button>2</button><button>3</button><button>›</button></div></div>
</div>
'''))

    # Entreprise detail
    out.append(('entreprise-detail.html', 'entd', 'Fiche entreprise',
        'Atelier Nord · vue 360° contacts, analyses, emails',
        '<button class="md-btn md-btn-outlined">Editer</button><button class="md-btn md-btn-filled">Ajouter a campagne</button>',
        f'''
<div class="md-hero-detail md-anim-in">
  <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap">
    <div>
      <h2>Atelier Nord</h2>
      <p class="sub">atelier-nord.fr · Metz · Industrie · Priorite 82</p>
      <div class="md-tags"><span class="md-tag">B2B</span><span class="md-tag">Grand Est</span><span class="md-tag">A qualifier</span></div>
    </div>
    <div class="md-metric-row">
      <div class="md-metric-pill">Score global<strong>82</strong></div>
      <div class="md-metric-pill">Emails<strong>3</strong></div>
      <div class="md-metric-pill">Analyses<strong>5</strong></div>
    </div>
  </div>
</div>
<div class="md-tabs"><button class="is-active">Vue</button><button>Contacts</button><button>Analyses</button><button>Emails</button><button>Notes</button></div>
<div class="md-split">
  <div>
    <div class="md-grid md-grid-2" style="margin-bottom:14px">
      <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Radar qualite</h3></div>{RADAR}</div>
      <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Historique scores</h3></div>{LINE}</div>
    </div>
    <div class="md-card"><table class="md-table dense"><thead><tr><th>Analyse</th><th>Score</th><th>Date</th></tr></thead>
      <tbody>
        <tr><td>SEO</td><td class="num">78</td><td>15/08</td></tr>
        <tr><td>Tech</td><td class="num">84</td><td>14/08</td></tr>
        <tr><td>OSINT</td><td class="num">71</td><td>12/08</td></tr>
      </tbody></table></div>
  </div>
  <div>
    <div class="md-card" style="margin-bottom:14px">
      <div class="md-list">
        <div class="md-list-item"><div class="md-avatar">C</div><div class="meta"><strong>contact@atelier-nord.fr</strong><span>Principal · verifie</span></div><span class="md-chip ok">OK</span></div>
        <div class="md-list-item"><div class="md-avatar blue">I</div><div class="meta"><strong>info@atelier-nord.fr</strong><span>Secondaire</span></div><span class="md-chip neutral">?</span></div>
      </div>
    </div>
    <div class="md-card md-card-pad">
      <h3 style="margin:0 0 10px;font-size:1rem">Timeline</h3>
      <div class="md-timeline">
        <div class="ev"><strong>Email campagne Presence</strong><span>il y a 2 j · ouvert</span></div>
        <div class="ev"><strong>Import CSV</strong><span>il y a 1 sem</span></div>
      </div>
    </div>
  </div>
</div>
'''))

    # Carte
    out.append(('carte.html', 'carte', 'Carte des entreprises',
        'Geo, clusters, densite et drawer fiche',
        '<div class="md-segmented"><button class="is-active">Carte</button><button>Liste</button></div><button class="md-btn md-btn-tonal">Filtres</button>',
        f'''
<div class="md-grid md-grid-4" style="margin-bottom:16px">
  <div class="md-card md-stat"><div class="label">Pins</div><div class="value">186</div></div>
  <div class="md-card md-stat"><div class="label">Clusters</div><div class="value">12</div></div>
  <div class="md-card md-stat"><div class="label">Grand Est</div><div class="value" style="color:var(--md-sys-color-primary)">94</div></div>
  <div class="md-card md-stat"><div class="label">Rayon</div><div class="value">80 km</div></div>
</div>
<div class="md-split">
  <div class="md-card md-map-fake">
    <div class="md-cluster" style="left:28%;top:36%">42</div>
    <div class="md-cluster" style="left:52%;top:48%;background:var(--md-sys-color-primary-container);color:var(--md-sys-color-primary)">18</div>
    <div class="md-pin" style="left:35%;top:42%"></div>
    <div class="md-pin" style="left:48%;top:55%;background:#7eb8ff;box-shadow:0 0 0 4px rgba(126,184,255,.25)"></div>
    <div class="md-pin" style="left:62%;top:38%;background:#ffb74d;box-shadow:0 0 0 4px rgba(255,183,77,.25)"></div>
    <div style="position:absolute;bottom:16px;left:16px;display:flex;gap:8px"><span class="md-chip ok">Industrie</span><span class="md-chip neutral">Agence</span></div>
  </div>
  <div>
    <div class="md-card md-card-pad" style="margin-bottom:14px"><div class="md-chart-title"><h3>Densite</h3></div>
      <div class="md-heat">
        <div class="lbl"></div><div class="lbl">L</div><div class="lbl">M</div><div class="lbl">M</div><div class="lbl">J</div><div class="lbl">V</div><div class="lbl">S</div><div class="lbl">D</div>
        <div class="lbl">S1</div><div class="cell c1"></div><div class="cell c2"></div><div class="cell c3"></div><div class="cell c2"></div><div class="cell c4"></div><div class="cell"></div><div class="cell"></div>
        <div class="lbl">S2</div><div class="cell c2"></div><div class="cell c4"></div><div class="cell c3"></div><div class="cell c3"></div><div class="cell c2"></div><div class="cell c1"></div><div class="cell"></div>
      </div>
    </div>
    <div class="md-sheet-backdrop">
      <div class="md-sheet"><div class="handle"></div>
        <strong>Atelier Nord</strong>
        <p style="margin:6px 0 12px;font-size:.85rem;color:var(--md-sys-color-on-surface-variant)">3,2 km · score 82</p>
        <button class="md-btn md-btn-filled" style="width:100%">Ouvrir fiche</button>
      </div>
    </div>
  </div>
</div>
'''))

    # Graph
    out.append(('graph.html', 'graph', 'Graphe entreprises',
        'Relations, similarite, ranking',
        '<button class="md-btn md-btn-outlined">Reset</button><button class="md-btn md-btn-tonal">Force layout</button>',
        f'''
<div class="md-toolbar">
  <button class="md-filter-chip on">Secteur</button>
  <button class="md-filter-chip">Email</button>
  <button class="md-filter-chip">Campagne</button>
  <input class="md-slider" type="range" value="55" style="max-width:160px;margin-left:auto" />
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-graph-fake">
    <div class="md-edge" style="left:28%;top:42%;width:22%;transform:rotate(12deg)"></div>
    <div class="md-edge" style="left:45%;top:38%;width:18%;transform:rotate(-28deg)"></div>
    <div class="md-edge" style="left:40%;top:52%;width:25%;transform:rotate(35deg)"></div>
    <div class="md-node" style="left:22%;top:35%">Atelier<br/>Nord</div>
    <div class="md-node" style="left:48%;top:28%;background:var(--md-sys-color-secondary-container);color:var(--md-sys-color-secondary)">Studio<br/>Lumen</div>
    <div class="md-node" style="left:62%;top:48%">Forge<br/>Dig.</div>
    <div class="md-node" style="left:38%;top:58%;width:44px;height:44px;font-size:.6rem">Metz H.</div>
  </div>
  <div>
    <div class="md-card md-card-pad" style="margin-bottom:14px"><div class="md-chart-title"><h3>Similarite</h3></div>{RADAR}</div>
    <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Ranking 30 j</h3></div>{SLOPE}</div>
  </div>
</div>
'''))

    # Concurrence
    out.append(('concurrence.html', 'marche', 'Concurrence et marche',
        'Veille, part de voix, matrice, opportunites',
        '<button class="md-btn md-btn-filled">Lancer analyse</button>',
        f'''
<div class="md-grid md-grid-3" style="margin-bottom:16px">
  <div class="md-card md-stat"><div class="label">Segments</div><div class="value">8</div></div>
  <div class="md-card md-stat"><div class="label">Concurrents</div><div class="value">23</div></div>
  <div class="md-card md-stat"><div class="label">Opportunites</div><div class="value" style="color:var(--md-sys-color-primary)">11</div></div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Part de voix</h3></div>
    <div class="md-bars"><div class="bar"><i style="height:70%"></i><span class="lbl">DC</span></div>
      <div class="bar alt"><i style="height:92%"></i><span class="lbl">A</span></div>
      <div class="bar warn"><i style="height:55%"></i><span class="lbl">B</span></div>
      <div class="bar"><i style="height:40%"></i><span class="lbl">C</span></div></div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Positionnement</h3></div>{RADAR}</div>
</div>
<div class="md-card md-card-pad" style="margin-bottom:16px"><div class="md-chart-title"><h3>Treemap segments</h3></div>
  <div class="md-treemap">
    <div class="a">Web agency<span>38%</span></div><div class="b">Dev<span>22%</span></div>
    <div class="c">SEO<span>18%</span></div><div class="d">Design<span>12%</span></div><div class="e">Autre<span>10%</span></div>
  </div>
</div>
<div class="md-card"><table class="md-table dense"><thead><tr><th>Concurrent</th><th>Segment</th><th>Visibilite</th><th>Menace</th></tr></thead>
<tbody>
<tr><td>Agence Pulse</td><td>Web</td><td><div class="md-linear" style="width:100px"><i style="width:78%"></i></div></td><td><span class="md-chip warn">Moyenne</span></td></tr>
<tr><td>Blue Peak</td><td>SEO</td><td><div class="md-linear" style="width:100px"><i style="width:91%"></i></div></td><td><span class="md-chip err">Haute</span></td></tr>
</tbody></table></div>
'''))

    for fname, key, title, sub, kind, scores in [
        ('analyse-site.html', 'audit', 'Analyse site complet', 'Audit technique + SEO + OSINT', 'global',
         {'Tech': 78, 'SEO': 72, 'OSINT': 65, 'Sec': 81, 'Perf': 69}),
        ('analyses-tech.html', 'tech', 'Analyses techniques', 'Stack, perf, surface', 'tech',
         {'Stack': 84, 'Perf': 71, 'TLS': 90, 'Headers': 62, 'CMS': 55}),
        ('analyses-osint.html', 'osint', 'Analyses OSINT', 'Emails, gens, exposition', 'osint',
         {'Emails': 70, 'Social': 48, 'DNS': 82, 'Leak': 35, 'Whois': 76}),
        ('analyses-pentest.html', 'pentest', 'Analyses Pentest', 'Formulaires et controles', 'pentest',
         {'Forms': 88, 'Auth': 74, 'XSS': 91, 'CSRF': 80, 'Upload': 66}),
        ('analyses-seo.html', 'seo', 'Analyses SEO', 'Couverture et scores', 'seo',
         {'Title': 85, 'Meta': 70, 'H1': 78, 'Speed': 64, 'Links': 72}),
    ]:
        out.append((fname, key, title, sub,
                    '<button class="md-btn md-btn-filled">Nouvelle analyse</button>',
                    analysis_body(kind, scores)))

    # Scrapers
    out.append(('scrapers.html', 'scrap', 'Scrapers',
        'Orchestration emails, phones, social, tech, people',
        '<button class="md-btn md-btn-filled">Lancer tout</button>',
        f'''
<div class="md-grid md-grid-4" style="margin-bottom:16px">
  <div class="md-card md-stat"><div class="label">Workers</div><div class="value">7</div></div>
  <div class="md-card md-stat"><div class="label">Files</div><div class="value">3</div></div>
  <div class="md-card md-stat"><div class="label">OK 24h</div><div class="value" style="color:var(--md-sys-color-primary)">128</div></div>
  <div class="md-card md-stat"><div class="label">Erreurs</div><div class="value" style="color:var(--md-sys-color-error)">4</div></div>
</div>
<div class="md-card md-card-pad" style="margin-bottom:16px"><div class="md-chart-title"><h3>Throughput</h3></div>{LINE}</div>
<div class="md-kanban">
  <div class="col"><h4>Idle <span>2</span></h4>
    <div class="card">Phones<small>Dernier: il y a 2 h</small></div>
    <div class="card">Metadata<small>Pret</small></div>
  </div>
  <div class="col"><h4>Running <span>3</span></h4>
    <div class="card">Emails<small><div class="md-linear" style="margin-top:6px"><i style="width:62%"></i></div></small></div>
    <div class="card">Social<small><div class="md-linear" style="margin-top:6px"><i style="width:28%"></i></div></small></div>
    <div class="card">Technologies<small><div class="md-spinner" style="margin-top:8px;width:20px;height:20px;border-width:2px"></div></small></div>
  </div>
  <div class="col"><h4>Done <span>1</span></h4>
    <div class="card">People<small>42 profils</small></div>
  </div>
  <div class="col"><h4>Failed <span>1</span></h4>
    <div class="card">Maps scrape<small><span class="md-chip err">timeout</span></small></div>
  </div>
</div>
'''))

    # Campagnes
    out.append(('campagnes.html', 'camp', 'Campagnes email',
        'Brevo, quota, funnel, board kanban',
        '<button class="md-btn md-btn-filled">+ Nouvelle campagne</button>',
        f'''
<div class="md-card" style="margin-bottom:18px;border-color:rgba(61,214,140,.35)">
  <div style="display:flex;justify-content:space-between;padding:20px 22px 8px;align-items:center">
    <div style="display:flex;gap:14px;align-items:center">
      <div class="md-brand-mark">B</div>
      <div><strong style="font-size:1.1rem">Brevo</strong> <span class="md-chip ok">OK</span>
        <div style="color:var(--md-sys-color-on-surface-variant);font-size:.88rem;margin-top:4px">contact@danielcraft.fr</div></div>
    </div>
    <button class="md-icon-btn">&#8635;</button>
  </div>
  <div style="padding:8px 22px 20px">
    <div style="background:var(--md-sys-color-surface-container-high);border-radius:12px;padding:16px;margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;margin-bottom:10px"><span>Credits</span><strong>294 / ~300</strong></div>
      <div class="md-linear"><i style="width:2%"></i></div>
    </div>
    <div class="md-grid md-grid-4">
      <div class="md-card md-stat" style="background:var(--md-sys-color-surface)"><div class="label">Delivres</div><div class="value" style="color:var(--md-sys-color-primary)">103</div></div>
      <div class="md-card md-stat" style="background:var(--md-sys-color-surface)"><div class="label">Hard</div><div class="value">1</div></div>
      <div class="md-card md-stat" style="background:var(--md-sys-color-surface)"><div class="label">Soft</div><div class="value">14</div></div>
      <div class="md-card md-stat" style="background:var(--md-sys-color-surface)"><div class="label">Spam</div><div class="value">0</div></div>
    </div>
  </div>
</div>
<div class="md-tabs"><button class="is-active">Cartes</button><button>Kanban</button><button>Stats</button></div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Funnel</h3></div>
    <div class="md-funnel">
      <div class="step"><span>Cibles</span><strong>120</strong></div>
      <div class="step"><span>Envoyes</span><strong>42</strong></div>
      <div class="step"><span>Ouverts</span><strong>13</strong></div>
      <div class="step"><span>Clics</span><strong>4</strong></div>
    </div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>PL vs Brevo</h3></div>
    <div class="md-bars" style="height:130px">
      <div class="bar"><i style="height:90%"></i><span class="lbl">Env</span></div>
      <div class="bar alt"><i style="height:85%"></i><span class="lbl">Deliv</span></div>
      <div class="bar"><i style="height:45%"></i><span class="lbl">Open</span></div>
      <div class="bar warn"><i style="height:12%"></i><span class="lbl">Bounce</span></div>
    </div></div>
</div>
<div class="md-kanban">
  <div class="col"><h4>Brouillon</h4><div class="card">Securite<small>0 destinataire</small></div></div>
  <div class="col"><h4>Planifiee</h4><div class="card">Modernisation<small>Demain 9h · 28</small></div></div>
  <div class="col"><h4>En cours</h4></div>
  <div class="col"><h4>Terminee</h4><div class="card">Presence digitale<small>42 · 31% open</small></div></div>
</div>
'''))

    # Campagne detail
    out.append(('campagne-detail.html', 'campd', 'Campagne détail',
        'Presence digitale · comparaison PL / Brevo',
        '<button class="md-btn md-btn-outlined">Pause</button><button class="md-btn md-btn-tonal">Sync Brevo</button>',
        f'''
<div class="md-hero-detail">
  <h2>Presence digitale</h2>
  <p class="sub">Terminee · 42 destinataires · expediteur contact@danielcraft.fr</p>
  <div class="md-metric-row">
    <div class="md-metric-pill">Envoyes<strong>42</strong></div>
    <div class="md-metric-pill">Ouverts PL<strong>13</strong></div>
    <div class="md-metric-pill">Delivres Brevo<strong>41</strong></div>
    <div class="md-metric-pill">Hard bounce<strong style="color:var(--md-sys-color-error)">1</strong></div>
  </div>
</div>
<div class="md-compare" style="margin-bottom:16px">
  <div class="col"><h4>ProspectLab trackers</h4>
    <div class="md-hbar">
      <div class="row"><span>Open</span><div class="track"><i style="width:31%"></i></div><span class="val">31%</span></div>
      <div class="row"><span>Click</span><div class="track blue"><i style="width:10%"></i></div><span class="val">10%</span></div>
    </div>
  </div>
  <div class="col"><h4>Brevo events</h4>
    <div class="md-hbar">
      <div class="row"><span>Open</span><div class="track"><i style="width:28%"></i></div><span class="val">28%</span></div>
      <div class="row"><span>Click</span><div class="track blue"><i style="width:9%"></i></div><span class="val">9%</span></div>
      <div class="row"><span>Bounce</span><div class="track amber"><i style="width:4%"></i></div><span class="val">1</span></div>
    </div>
  </div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Courbe d'ouverture</h3></div>{LINE}</div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Candles journaliers</h3></div>
    <div class="md-candles">
      <div class="c"><div class="wick" style="height:60%;bottom:20%"></div><div class="body" style="height:35%"></div></div>
      <div class="c"><div class="wick" style="height:70%;bottom:10%"></div><div class="body down" style="height:40%"></div></div>
      <div class="c"><div class="wick" style="height:50%;bottom:25%"></div><div class="body" style="height:30%"></div></div>
      <div class="c"><div class="wick" style="height:80%;bottom:5%"></div><div class="body" style="height:55%"></div></div>
      <div class="c"><div class="wick" style="height:45%;bottom:30%"></div><div class="body down" style="height:25%"></div></div>
      <div class="c"><div class="wick" style="height:65%;bottom:15%"></div><div class="body" style="height:45%"></div></div>
    </div>
  </div>
</div>
<div class="md-card"><table class="md-table dense"><thead><tr><th>Destinataire</th><th>PL</th><th>Brevo</th><th>Statut</th></tr></thead>
<tbody>
<tr><td>contact@atelier-nord.fr</td><td>ouvert</td><td>delivered+open</td><td><span class="md-chip ok">OK</span></td></tr>
<tr><td>hello@studio-lumen.com</td><td>-</td><td>softBounce</td><td><span class="md-chip warn">Soft</span></td></tr>
<tr><td>bad@exemple.fr</td><td>-</td><td>hardBounce</td><td><span class="md-chip err">Hard</span></td></tr>
</tbody></table></div>
'''))

    # Envoyer
    out.append(('envoyer.html', 'send', 'Envoyer des emails',
        'Envoi rapide, stepper, quota, confirmation',
        '<button class="md-btn md-btn-outlined">Apercu</button><button class="md-btn md-btn-filled">Envoyer</button>',
        f'''
<div class="md-stepper">
  <div class="md-step done" data-n="1">Destinataire</div>
  <div class="md-step active" data-n="2">Message</div>
  <div class="md-step" data-n="3">Confirmer</div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad">
    <div class="md-grid md-grid-2">
      <div class="md-field"><label>Destinataire</label><input value="paulisanberg@gmail.com" /></div>
      <div class="md-field"><label>Expediteur</label><select><option>contact@danielcraft.fr</option></select></div>
    </div>
    <div class="md-field" style="margin-top:12px"><label>Sujet</label><input value="Presence digitale" /></div>
    <div class="md-field" style="margin-top:12px"><label>Message</label><textarea>Bonjour,\\n\\nJe vous contacte...</textarea></div>
    <div style="display:flex;align-items:center;gap:12px;margin-top:14px">
      <button class="md-switch on"></button><span style="font-size:.88rem">Tracking</span>
    </div>
  </div>
  <div>
    <div class="md-card md-card-pad" style="margin-bottom:14px"><div class="md-chart-title"><h3>Quota</h3></div>
      <div style="display:flex;gap:20px;align-items:center">
        <div class="md-gauge" style="--pct:8deg"><div class="arc"></div><div class="val">6</div></div>
        <div><strong>6 / 300</strong><p style="font-size:.82rem;color:var(--md-sys-color-on-surface-variant);margin:6px 0 0">1 credit Brevo</p></div>
      </div>
    </div>
    <div class="md-dialog"><h3>Pret a envoyer ?</h3>
      <p>1 destinataire · Brevo SMTP · tracking ON</p>
      <div class="actions"><button class="md-btn md-btn-outlined">Annuler</button><button class="md-btn md-btn-filled">Confirmer</button></div>
    </div>
  </div>
</div>
'''))

    # Modeles
    out.append(('modeles.html', 'tpl', 'Modeles email',
        'Templates, variantes A/B, performances',
        '<button class="md-btn md-btn-filled">+ Modele</button>',
        f'''
<div class="md-tabs"><button class="is-active">Tous</button><button>Presence</button><button>Modernisation</button><button>Securite</button></div>
<div class="md-grid md-grid-3" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><strong>Presence digitale</strong>
    <p style="color:var(--md-sys-color-on-surface-variant);font-size:.85rem">HTML · CTA audit</p>{spark()}
    <div style="margin-top:10px"><span class="md-chip ok">31% open</span></div></div>
  <div class="md-card md-card-pad"><strong>Modernisation</strong>
    <p style="color:var(--md-sys-color-on-surface-variant);font-size:.85rem">HTML · perf</p>{spark("blue")}
    <div style="margin-top:10px"><span class="md-chip warn">brouillon</span></div></div>
  <div class="md-card md-card-pad"><strong>Securite</strong>
    <p style="color:var(--md-sys-color-on-surface-variant);font-size:.85rem">HTML · conformite</p>{spark("amber")}
    <div style="margin-top:10px"><span class="md-chip ok">28% open</span></div></div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Open rate</h3></div>
    <div class="md-bars"><div class="bar"><i style="height:62%"></i><span class="lbl">Pres.</span></div>
      <div class="bar alt"><i style="height:48%"></i><span class="lbl">Mod.</span></div>
      <div class="bar warn"><i style="height:56%"></i><span class="lbl">Secu</span></div></div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Apercu HTML</h3></div>
    <div style="height:140px;border:1px dashed var(--md-sys-color-outline);border-radius:12px;display:grid;place-items:center;color:var(--md-sys-color-on-surface-variant)">Preview email</div>
  </div>
</div>
'''))

    # Bounces
    out.append(('bounces.html', 'bounce', 'Bounces & hygiene',
        'Hard/soft, sync Brevo, nettoyage base',
        '<button class="md-btn md-btn-outlined">Exporter</button><button class="md-btn md-btn-filled">Nettoyer selection</button>',
        f'''
<div class="md-grid md-grid-4" style="margin-bottom:16px">
  <div class="md-card md-stat"><div class="label">Hard</div><div class="value" style="color:var(--md-sys-color-error)">12</div></div>
  <div class="md-card md-stat"><div class="label">Soft</div><div class="value" style="color:var(--md-sys-color-tertiary)">41</div></div>
  <div class="md-card md-stat"><div class="label">Spam</div><div class="value">2</div></div>
  <div class="md-card md-stat"><div class="label">A purger</div><div class="value">15</div></div>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Evolution bounces</h3></div>{LINE}</div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Causes</h3></div>
    <div class="md-donut-wrap">
      <div class="md-donut" data-center="55" style="background:conic-gradient(#ff8a80 0 40%,#ffb74d 40% 75%,#7eb8ff 75% 100%)"></div>
      <div class="md-legend">
        <div class="item"><span class="dot" style="background:#ff8a80"></span> Inexistant</div>
        <div class="item"><span class="dot" style="background:#ffb74d"></span> Boite pleine</div>
        <div class="item"><span class="dot" style="background:#7eb8ff"></span> Bloque</div>
      </div>
    </div>
  </div>
</div>
<div class="md-banner err" style="margin-bottom:14px">15 adresses hard bounce candidates a suppression de la base.</div>
<div class="md-card"><table class="md-table dense"><thead><tr><th></th><th>Email</th><th>Type</th><th>Source</th><th>Date</th></tr></thead>
<tbody>
<tr><td><span class="md-check on">&#10003;</span></td><td>bad@exemple.fr</td><td><span class="md-chip err">Hard</span></td><td>Brevo</td><td>16/08</td></tr>
<tr><td><span class="md-check"></span></td><td>full@boite.fr</td><td><span class="md-chip warn">Soft</span></td><td>IMAP</td><td>15/08</td></tr>
</tbody></table>
<div class="md-pagination"><span>1-50 sur 55</span><div class="md-page-btns"><button class="is-active">1</button><button>2</button></div></div>
</div>
'''))

    # Domaines
    out.append(('domaines.html', 'dom', 'Domaines et SMTP',
        'Multi-domaines, DNS, sante',
        '<button class="md-btn md-btn-filled">+ Domaine</button>',
        f'''
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Volume</h3></div>
    <div class="md-donut-wrap">
      <div class="md-donut" data-center="412" style="background:conic-gradient(#3dd68c 0 78%,#7eb8ff 78% 95%,#ffb74d 95% 100%)"></div>
      <div class="md-legend">
        <div class="item"><span class="dot" style="background:#3dd68c"></span> danielcraft.fr</div>
        <div class="item"><span class="dot" style="background:#7eb8ff"></span> jammy.fr</div>
      </div>
    </div></div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>DNS</h3></div>
    <div class="md-list">
      <div class="md-list-item"><div class="md-avatar">SP</div><div class="meta"><strong>SPF</strong><span>include:sendinblue.com</span></div><span class="md-chip ok">OK</span></div>
      <div class="md-list-item"><div class="md-avatar blue">DK</div><div class="meta"><strong>DKIM</strong><span>brevo</span></div><span class="md-chip ok">OK</span></div>
      <div class="md-list-item"><div class="md-avatar">DM</div><div class="meta"><strong>DMARC</strong><span>p=none</span></div><span class="md-chip warn">A renforcer</span></div>
    </div></div>
</div>
<div class="md-card"><table class="md-table dense"><thead><tr><th>Domaine</th><th>SMTP</th><th>DNS</th><th>Quota</th><th>Statut</th></tr></thead>
<tbody>
<tr><td>danielcraft.fr</td><td>Brevo</td><td><span class="md-chip ok">OK</span></td><td><div class="md-linear" style="width:80px"><i style="width:2%"></i></div></td><td>Actif</td></tr>
<tr><td>jammy.fr</td><td>node12</td><td><span class="md-chip warn">?</span></td><td><div class="md-linear" style="width:80px"><i style="width:0%"></i></div></td><td>Inactif</td></tr>
</tbody></table></div>
'''))

    # API
    out.append(('api.html', 'api', 'API publique',
        'Tokens, usage, docs',
        '<button class="md-btn md-btn-filled">Creer un token</button>',
        f'''
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Appels 7 j</h3></div>{LINE}</div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Endpoints</h3></div>
    <div class="md-hbar">
      <div class="row"><span>/entreprises</span><div class="track"><i style="width:80%"></i></div><span class="val">820</span></div>
      <div class="row"><span>/campagnes</span><div class="track blue"><i style="width:45%"></i></div><span class="val">210</span></div>
      <div class="row"><span>/brevo</span><div class="track amber"><i style="width:22%"></i></div><span class="val">64</span></div>
    </div></div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad"><h3 style="margin-top:0">Tokens</h3>
    <table class="md-table dense"><thead><tr><th>Nom</th><th>Droits</th><th>Usage</th></tr></thead>
    <tbody><tr><td>Mobile</td><td>read</td><td><span class="md-badge soft">142</span></td></tr>
    <tr><td>Zapier</td><td>rw campagnes</td><td><span class="md-badge soft">38</span></td></tr></tbody></table></div>
  <div class="md-card md-card-pad"><h3 style="margin-top:0">Exemple</h3>
    <pre class="md-code">curl -H "Authorization: Bearer pl_xxx" \\
  https://api.../v1/entreprises?page=1</pre>
    <button class="md-btn md-btn-tonal" style="margin-top:12px">Doc</button></div>
</div>
'''))

    # Upload
    out.append(('upload.html', 'upload', 'Import donnees',
        'CSV entreprises, mapping colonnes, validation',
        '<button class="md-btn md-btn-filled">Importer</button>',
        f'''
<div class="md-stepper">
  <div class="md-step done" data-n="1">Fichier</div>
  <div class="md-step active" data-n="2">Mapping</div>
  <div class="md-step" data-n="3">Validation</div>
  <div class="md-step" data-n="4">Import</div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad">
    <div style="border:2px dashed var(--md-sys-color-outline);border-radius:16px;padding:40px;text-align:center;margin-bottom:16px">
      <div style="font-size:2rem;margin-bottom:8px">&#128194;</div>
      <strong>entreprises_metz.csv</strong>
      <p style="color:var(--md-sys-color-on-surface-variant);font-size:.85rem">248 lignes · 12 colonnes</p>
    </div>
    <div class="md-field"><label>Separateur</label><select><option>;</option><option>,</option></select></div>
  </div>
  <div class="md-card md-card-pad">
    <h3 style="margin-top:0;font-size:1rem">Mapping</h3>
    <table class="md-table dense"><thead><tr><th>CSV</th><th>Champ PL</th></tr></thead>
    <tbody>
      <tr><td>raison_sociale</td><td><select><option>nom</option></select></td></tr>
      <tr><td>mail</td><td><select><option>email_principal</option></select></td></tr>
      <tr><td>ville</td><td><select><option>ville</option></select></td></tr>
    </tbody></table>
    <div class="md-divider"></div>
    <div class="md-hbar">
      <div class="row"><span>Valides</span><div class="track"><i style="width:92%"></i></div><span class="val">228</span></div>
      <div class="row"><span>Doublons</span><div class="track amber"><i style="width:6%"></i></div><span class="val">14</span></div>
      <div class="row"><span>Erreurs</span><div class="track red"><i style="width:2%"></i></div><span class="val">6</span></div>
    </div>
  </div>
</div>
'''))

    # Settings
    out.append(('settings.html', 'set', 'Reglages',
        'Theme, Brevo, restrictions, notifications',
        '<button class="md-btn md-btn-filled">Enregistrer</button>',
        f'''
<div class="md-tabs"><button class="is-active">General</button><button>Brevo</button><button>Securite</button><button>Notifs</button></div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad">
    <h3 style="margin-top:0">Apparence</h3>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <span>Theme sombre</span><button class="md-switch on"></button>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <span>Animations</span><button class="md-switch on"></button>
    </div>
    <div class="md-field"><label>Densite tableaux</label><select><option>Confortable</option><option>Dense</option></select></div>
    <div class="md-divider"></div>
    <a class="md-btn md-btn-tonal" href="dashboard-light.html">Voir variante light</a>
  </div>
  <div class="md-card md-card-pad">
    <h3 style="margin-top:0">Brevo</h3>
    <div class="md-field"><label>Limite journaliere</label><input value="300" /></div>
    <div class="md-field" style="margin-top:10px"><label>Pause auto si quota 0</label>
      <div style="display:flex;align-items:center;gap:12px;margin-top:8px"><button class="md-switch"></button><span style="font-size:.85rem">Bientot</span></div>
    </div>
    <div class="md-divider"></div>
    <div class="md-field"><label>Restriction reseau</label>
      <div style="display:flex;align-items:center;gap:12px;margin-top:8px"><button class="md-switch on"></button><span style="font-size:.85rem">RESTRICT_TO_LOCAL_NETWORK</span></div>
    </div>
  </div>
</div>
'''))

    # Kit composants MAX
    out.append(('composants.html', 'kit', 'Kit composants MD3',
        'Bibliotheque complete patterns + charts',
        '<span class="md-chip ok">Offline</span><span class="md-chip warn">Charts</span><span class="md-chip neutral">Extra</span>',
        f'''
<div class="md-section-label">Actions</div>
<div class="md-card md-card-pad" style="margin-bottom:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center">
  <button class="md-btn md-btn-filled">Filled</button>
  <button class="md-btn md-btn-tonal">Tonal</button>
  <button class="md-btn md-btn-outlined">Outlined</button>
  <button class="md-icon-btn">&#8635;</button>
  <span class="md-chip ok">OK</span><span class="md-chip warn">Warn</span><span class="md-chip err">Err</span>
  <button class="md-filter-chip on">Filter</button>
  <div class="md-segmented"><button class="is-active">A</button><button>B</button></div>
  <button class="md-switch on"></button>
  <span class="md-badge">3</span>
  <span class="md-dot-live"></span><span class="md-dot-live warn"></span><span class="md-dot-live err"></span>
  <div class="md-spinner"></div>
</div>
<div class="md-section-label">Feedback & overlays</div>
<div class="md-comp-grid" style="margin-bottom:14px">
  <div class="md-card md-card-pad"><div class="md-snackbar" style="width:100%"><span>Enregistre</span><button class="act">Undo</button></div>
    <div class="md-divider"></div><div class="md-tooltip">Tooltip</div>
    <div class="md-divider"></div>
    <div class="md-skeleton lg" style="margin-bottom:8px"></div>
    <div class="md-skeleton" style="width:70%"></div>
  </div>
  <div class="md-dialog"><h3>Dialog</h3><p>Confirmation Material.</p>
    <div class="actions"><button class="md-btn md-btn-outlined">Non</button><button class="md-btn md-btn-filled">Oui</button></div></div>
  <div class="md-sheet-backdrop"><div class="md-sheet"><div class="handle"></div><strong>Bottom sheet</strong>
    <p style="font-size:.85rem;color:var(--md-sys-color-on-surface-variant)">Actions contextuelles</p></div></div>
  <div class="md-menu"><button>Modifier</button><button>Dupliquer</button><button>Archiver</button></div>
</div>
<div class="md-section-label">Charts pack</div>
<div class="md-grid md-grid-2" style="margin-bottom:14px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Line</h3></div>{LINE}</div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Bars + donut</h3></div>
    <div class="md-bars" style="height:90px"><div class="bar"><i style="height:70%"></i><span class="lbl">A</span></div>
      <div class="bar alt"><i style="height:90%"></i><span class="lbl">B</span></div>
      <div class="bar warn"><i style="height:45%"></i><span class="lbl">C</span></div></div>
    <div class="md-donut" data-center="72%" style="background:conic-gradient(#3dd68c 0 72%,rgba(255,255,255,.08) 72%);width:90px;height:90px;margin-top:10px"></div>
  </div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Treemap + funnel</h3></div>
    <div class="md-treemap" style="height:120px;margin-bottom:10px">
      <div class="a">A</div><div class="b">B</div><div class="c">C</div><div class="d">D</div><div class="e">E</div>
    </div>
    <div class="md-funnel"><div class="step"><span>In</span><strong>100</strong></div>
      <div class="step"><span>Mid</span><strong>40</strong></div>
      <div class="step"><span>Out</span><strong>12</strong></div></div>
  </div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Radar / slope / bullet / lollipop</h3></div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start">
      <div>{RADAR}</div>
      <div style="flex:1;min-width:160px">{SLOPE}
        <div class="md-bullet" style="margin-top:10px">
          <div class="row"><span>KPI</span><div class="track"><div class="range" style="width:80%"></div><div class="fill" style="width:60%"></div><div class="marker" style="left:75%"></div></div></div>
        </div>
        <div class="md-lollipop" style="margin-top:10px">
          <div class="row"><span>X</span><div class="line" style="--p:70%"><i style="width:70%"></i></div></div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="md-section-label">Kanban + pagination</div>
<div class="md-kanban" style="margin-bottom:14px">
  <div class="col"><h4>Todo</h4><div class="card">Item A</div></div>
  <div class="col"><h4>Doing</h4><div class="card">Item B</div></div>
  <div class="col"><h4>Done</h4><div class="card">Item C</div></div>
  <div class="col"><h4>Blocked</h4><div class="card">Item D</div></div>
</div>
<div class="md-card"><div class="md-pagination"><span>Demo</span><div class="md-page-btns">
  <button>‹</button><button class="is-active">1</button><button>2</button><button>3</button><button>›</button>
</div></div></div>
''', '+ Nouveau'))

    return out


def write_specials():
    """Pages hors shell nav (login, error, restricted, light)."""
    specials = []

    login = f'''<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Login | ProspectLab maquette</title>{CSS}</head>
<body>
<div class="md-auth">
  <div class="md-auth-card md-anim-in">
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:22px">
      <div class="md-brand-mark">P</div>
      <div><strong>ProspectLab</strong><div style="font-size:.8rem;color:var(--md-sys-color-on-surface-variant)">Daniel Craft</div></div>
    </div>
    <div class="md-field"><label>Email</label><input type="email" placeholder="toi@danielcraft.fr"/></div>
    <div class="md-field" style="margin-top:12px"><label>Mot de passe</label><input type="password" value="********"/></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin:16px 0">
      <span style="font-size:.85rem;display:flex;gap:8px;align-items:center"><button class="md-switch on"></button> Se souvenir</span>
      <a href="#" style="font-size:.85rem">Oublie ?</a>
    </div>
    <button class="md-btn md-btn-filled" style="width:100%">Connexion</button>
    <p style="text-align:center;margin:16px 0 0;font-size:.8rem;color:var(--md-sys-color-on-surface-variant)">Acces restreint reseau local / VPN</p>
  </div>
</div>
</body></html>'''
    (PAGES / 'login.html').write_text(login, encoding='utf-8')
    specials.append(('pages/login.html', 'Login', 'Auth Material'))

    err = f'''<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Erreur | ProspectLab maquette</title>{CSS}</head>
<body>
<div class="md-error-page">
  <div>
    <p class="code">404</p>
    <h1 style="margin:0 0 8px">Page introuvable</h1>
    <p style="color:var(--md-sys-color-on-surface-variant);max-width:36ch;margin:0 auto 20px">La ressource n'existe pas ou tu n'y as pas acces.</p>
    <a class="md-btn md-btn-filled" href="dashboard.html">Retour dashboard</a>
  </div>
</div>
</body></html>'''
    (PAGES / 'error.html').write_text(err, encoding='utf-8')
    specials.append(('pages/error.html', 'Erreur 404', 'Etat erreur'))

    restricted = f'''<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Acces restreint | ProspectLab maquette</title>{CSS}</head>
<body>
<div class="md-error-page">
  <div style="max-width:480px">
    <p class="code" style="font-size:3rem">VPN</p>
    <h1 style="margin:0 0 8px">Reseau non autorise</h1>
    <div class="md-error-guide" style="text-align:left">
      <strong>Pourquoi ca bloque</strong>
      <p>RESTRICT_TO_LOCAL_NETWORK n'accepte que des IP privees. Sans VPN, Flask voit l'IP box publique.</p>
      <ol style="margin:0 0 12px;padding-left:18px;font-size:.88rem;color:#ffc9c4;line-height:1.45;text-align:left">
        <li>Connecte-toi au VPN node13</li>
        <li>Flush DNS : ipconfig /flushdns</li>
        <li>campaigns.danielcraft.fr → 192.168.1.209</li>
      </ol>
      <button class="md-btn md-btn-filled">Reessayer maintenant</button>
    </div>
  </div>
</div>
</body></html>'''
    (PAGES / 'restricted.html').write_text(restricted, encoding='utf-8')
    specials.append(('pages/restricted.html', 'Acces restreint', 'VPN / IP'))

    # Light dashboard variant - reuse shell with data-theme
    light_body = f'''
<div data-theme="light" style="margin:-24px -28px -64px;padding:24px 28px 64px;background:var(--md-sys-color-surface-dim);min-height:100vh;border-radius:0">
  <div class="md-banner" style="margin-bottom:16px">Variante light Material (maquette)</div>
  <div class="md-grid md-grid-4" style="margin-bottom:16px">
    <div class="md-card md-stat"><div class="label">Entreprises</div><div class="value">1 248</div></div>
    <div class="md-card md-stat"><div class="label">Emails</div><div class="value">412</div></div>
    <div class="md-card md-stat"><div class="label">Open</div><div class="value" style="color:var(--md-sys-color-primary)">34%</div></div>
    <div class="md-card md-stat"><div class="label">Credits</div><div class="value">294</div></div>
  </div>
  <div class="md-card md-card-pad">{LINE}</div>
</div>
'''
    (PAGES / 'dashboard-light.html').write_text(
        shell('dash', 'Dashboard light', 'Variante theme clair', light_body,
              '<a class="md-btn md-btn-outlined" href="dashboard.html">Dark</a>'),
        encoding='utf-8',
    )
    specials.append(('pages/dashboard-light.html', 'Dashboard light', 'Theme clair'))

    # Empty states gallery
    empty = shell('kit', 'Etats vides', 'Empty states avec CTA (@clea_ux Ch.9)', f'''
<div class="md-clea-quote">« No Data Yet sans CTA = abandon des la premiere seconde. » — @clea_ux</div>
<div class="md-grid md-grid-3">
  <div class="md-card"><div class="md-empty"><div class="ico">&#9993;</div><div>Aucune campagne</div>
    <p style="font-size:.85rem;margin:8px 0 0">La valeur arrive au 1er envoi delivre.</p>
    <a class="md-btn md-btn-filled" style="margin-top:14px" href="onboarding.html">Recevoir ma 1ere preuve</a></div></div>
  <div class="md-card md-card-pad" style="display:grid;place-items:center;min-height:200px">
    <div style="text-align:center"><div class="md-spinner" style="margin:0 auto 12px"></div>Chargement...</div>
  </div>
  <div class="md-card md-card-pad">
    <div class="md-error-guide">
      <strong>Sync Brevo impossible</strong>
      <p>Timeout API — pas un mur : on explique + on propose une action.</p>
      <button class="md-btn md-btn-filled" style="padding:8px 14px;font-size:.8rem">Reessayer maintenant</button>
    </div>
    <div class="md-skeleton lg" style="margin:16px 0 8px"></div>
    <div class="md-skeleton" style="width:80%;margin-bottom:8px"></div>
  </div>
</div>
''', '')
    (PAGES / 'etats.html').write_text(empty, encoding='utf-8')
    specials.append(('pages/etats.html', 'Etats UI', 'Empty / loading / error guide'))

    # Onboarding @clea_ux
    onb = shell('onb', 'Premiere victoire',
        'Onboarding a rebours depuis l\'action cle · TTV < 2 min',
        f'''
<div class="md-clea-quote">« Un bon onboarding guide vers une preuve de valeur, pas vers des features. »</div>
<div class="md-progress-story">
  <div class="seg on"></div><div class="seg on"></div><div class="seg current"></div><div class="seg"></div>
</div>
<p style="font-size:.85rem;color:var(--md-sys-color-on-surface-variant);margin:-8px 0 18px">Etape 3/4 · ~45 s — choisir le 1er envoi</p>
<div class="md-card md-card-pad" style="margin-bottom:16px">
  <h3 style="margin-top:0">Dans quel contexte tu prospectes ?</h3>
  <p style="font-size:.88rem;color:var(--md-sys-color-on-surface-variant)">UX adaptative (@clea_ux) : 2 entrees, 1 produit.</p>
  <div class="md-persona-pick" style="margin-top:14px">
    <div class="md-persona-card on"><strong>TPE / artisans Lorraine</strong><span>Emails presence digitale, audit site, relances simples</span></div>
    <div class="md-persona-card"><strong>Agence / tech</strong><span>Volumes, multi-domaines, scrapers, API</span></div>
  </div>
</div>
<div class="md-grid md-grid-2">
  <div class="md-card md-card-pad">
    <h3 style="margin-top:0;font-size:1rem">Action cle (a rebours)</h3>
    <div class="md-timeline">
      <div class="ev"><strong>4. Email delivre + ouvert</strong><span>preuve de valeur</span></div>
      <div class="ev"><strong>3. Campagne lancee</strong><span>tu es ici</span></div>
      <div class="ev"><strong>2. Destinataires qualifies</strong><span>fait</span></div>
      <div class="ev"><strong>1. Compte Brevo OK</strong><span>fait</span></div>
    </div>
  </div>
  <div class="md-card md-card-pad">
    <div class="md-chart-title"><h3>Apercu pre-rempli</h3><span class="hint">resultat d'abord</span></div>
    {spark()}
    <p style="font-size:.85rem;color:var(--md-sys-color-on-surface-variant)">On remplace par tes vrais destinataires a l'etape suivante.</p>
    <a class="md-btn md-btn-filled" style="width:100%;margin-top:12px" href="victoire.html">Lancer et voir la preuve</a>
  </div>
</div>
''',
        '<span class="md-chip ok">TTV</span><button class="md-btn md-btn-outlined">Passer</button>')
    (PAGES / 'onboarding.html').write_text(onb, encoding='utf-8')
    specials.append(('pages/onboarding.html', 'Onboarding', 'Action cle + TTV'))

    # Victoire Peak-End
    vic = shell('victoire', 'Ecran victoire',
        'Peak-End Rule · fin nette apres le pic',
        f'''
<div class="md-victory md-anim-in">
  <div class="burst">&#10024;</div>
  <h2>C'est delivre</h2>
  <p>42 emails partis via Brevo. Premiere preuve de valeur : 3 ouvertures en 12 minutes.</p>
  <div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-bottom:22px">
    <div class="md-metric-pill">Delivres<strong>41</strong></div>
    <div class="md-metric-pill">Ouverts<strong style="color:var(--md-sys-color-primary)">3</strong></div>
    <div class="md-metric-pill">Credits<strong>291</strong></div>
  </div>
  <div class="next">
    <div class="step"><span class="n">1</span><div><strong>Regarde qui a ouvert</strong><div style="font-size:.78rem;color:var(--md-sys-color-on-surface-variant)">Comparer PL vs Brevo</div></div></div>
    <div class="step"><span class="n">2</span><div><strong>Nettoie les soft bounces</strong><div style="font-size:.78rem;color:var(--md-sys-color-on-surface-variant)">Hygiene listes</div></div></div>
    <div class="step"><span class="n">3</span><div><strong>Planifie la relance</strong><div style="font-size:.78rem;color:var(--md-sys-color-on-surface-variant)">Demain 9h</div></div></div>
  </div>
  <div style="margin-top:22px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
    <a class="md-btn md-btn-filled" href="campagne-detail.html">Voir le detail</a>
    <a class="md-btn md-btn-outlined" href="dashboard.html">Retour accueil</a>
  </div>
</div>
<div class="md-clea-quote" style="margin-top:18px">Peak-End : on retient le pic (ouvertures) + la fin nette (3 prochaines etapes). Pas de fin floue.</div>
''', '')
    (PAGES / 'victoire.html').write_text(vic, encoding='utf-8')
    specials.append(('pages/victoire.html', 'Victoire Peak-End', 'Post action cle'))

    # Recherche 0 resultat
    search0 = shell('search0', 'Recherche sans resultat',
        'Bestseller + roadmap inversee + correcteur (@clea_ux)',
        f'''
<div class="md-toolbar">
  <div class="md-search" style="flex:1"><span>&#128269;</span><input value="facture automatique" /></div>
</div>
<div class="md-card">
  <div class="md-search-zero">
    <h3>Aucun resultat pour « facture automatique »</h3>
    <p>Momentum fort : on ne laisse pas tomber sur du vide.</p>
    <div class="md-clea-quote" style="text-align:left">1) Bestseller · 2) Vote feature · 3) Correcteur d'intention</div>
    <div class="suggests">
      <a class="md-list-item" href="campagnes.html" style="border:1px solid var(--md-sys-color-outline-variant);border-radius:12px;text-decoration:none;color:inherit">
        <div class="md-avatar">1</div><div class="meta"><strong>Campagnes email</strong><span>Le plus utilise · proche de ta recherche</span></div>
      </a>
      <a class="md-list-item" href="entreprises.html" style="border:1px solid var(--md-sys-color-outline-variant);border-radius:12px;text-decoration:none;color:inherit">
        <div class="md-avatar blue">2</div><div class="meta"><strong>Prospection entreprises</strong><span>Tu cherchais peut-etre ca</span></div>
      </a>
      <div class="md-list-item" style="border:1px dashed var(--md-sys-color-outline);border-radius:12px">
        <div class="md-avatar">?</div><div class="meta"><strong>On n'a pas encore ca</strong><span>Vote pour facturation — etude de marche</span></div>
        <button class="md-btn md-btn-tonal" style="padding:6px 12px;font-size:.75rem">Voter</button>
      </div>
    </div>
  </div>
</div>
''', '')
    (PAGES / 'recherche-vide.html').write_text(search0, encoding='utf-8')
    specials.append(('pages/recherche-vide.html', 'Recherche 0', 'Bestseller + vote'))

    # Playbook snapshot page
    playbook = shell('kit', 'Playbook @clea_ux',
        '164 TikToks → principes appliques a ProspectLab',
        f'''
<div class="md-banner" style="margin-bottom:16px">Source : Videos/tiktokUX · clea-ux-saas-playbook-juillet-2026.md</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad">
    <h3 style="margin-top:0">Action cle ProspectLab</h3>
    <p style="color:var(--md-sys-color-on-surface-variant);font-size:.9rem;line-height:1.45">
      La valeur est comprise quand l'utilisateur a <strong>un email delivre (Brevo) et au moins une ouverture</strong> sur une vraie cible.
    </p>
    <div class="md-clea-quote">TTV cible : &lt; 2 min avec donnees de demo pre-remplies.</div>
  </div>
  <div class="md-card md-card-pad">
    <div class="md-chart-title"><h3>Themes corpus</h3></div>
    <div class="md-bars" style="height:120px">
      <div class="bar"><i style="height:100%"></i><span class="lbl">Onb</span></div>
      <div class="bar alt"><i style="height:87%"></i><span class="lbl">TTV</span></div>
      <div class="bar warn"><i style="height:70%"></i><span class="lbl">Err</span></div>
      <div class="bar"><i style="height:66%"></i><span class="lbl">Ret</span></div>
      <div class="bar alt"><i style="height:58%"></i><span class="lbl">Land</span></div>
    </div>
  </div>
</div>
<div class="md-card"><table class="md-table dense">
<thead><tr><th>#</th><th>Principe</th><th>Dans les maquettes</th></tr></thead>
<tbody>
<tr><td>1</td><td>Action cle + a rebours</td><td><a href="onboarding.html">onboarding.html</a></td></tr>
<tr><td>2</td><td>CTV &gt; CTA</td><td>Dashboard « Voir ce que Brevo a delivre »</td></tr>
<tr><td>3</td><td>Hick ≤7 nav</td><td>Sidebar intentions</td></tr>
<tr><td>4</td><td>Erreur qui guide</td><td><a href="etats.html">etats.html</a> · restricted</td></tr>
<tr><td>5</td><td>Empty + CTA</td><td>etats + campagnes brouillon</td></tr>
<tr><td>6</td><td>Peak-End</td><td><a href="victoire.html">victoire.html</a></td></tr>
<tr><td>7</td><td>Recherche 0</td><td><a href="recherche-vide.html">recherche-vide.html</a></td></tr>
<tr><td>8</td><td>Zeigarnik</td><td>Bandeau checklist dashboard</td></tr>
<tr><td>9</td><td>2 personas</td><td>Choix onboarding</td></tr>
<tr><td>10</td><td>Charts inattendus</td><td>slope, treemap, bullet, candles…</td></tr>
</tbody></table></div>
''', '<span class="md-chip ok">164 videos</span>')
    (PAGES / 'playbook-clea.html').write_text(playbook, encoding='utf-8')
    specials.append(('pages/playbook-clea.html', 'Playbook clea_ux', 'Principes → ecrans'))

    # Rapport audit
    rapport = shell('audit', 'Rapport audit', 'Entreprise · export PDF-like', f'''
<div class="md-hero-detail">
  <h2>Rapport · Atelier Nord</h2>
  <p class="sub">Genere le 16/08/2026 · score global 78</p>
</div>
<div class="md-grid md-grid-2" style="margin-bottom:16px">
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Scores</h3></div>{RADAR}</div>
  <div class="md-card md-card-pad"><div class="md-chart-title"><h3>Findings</h3></div>
    <div class="md-treemap">
      <div class="a">Crit.<span>3</span></div><div class="b">Haut<span>7</span></div>
      <div class="c">Moy.<span>12</span></div><div class="d">Bas<span>20</span></div><div class="e">Info<span>5</span></div>
    </div>
  </div>
</div>
<div class="md-card md-card-pad">
  <div class="md-tree">
    <details open><summary>Technique</summary>
      <div class="leaf">TLS 1.2+ OK</div>
      <div class="leaf">Headers incomplets (CSP manquant)</div>
    </details>
    <details open><summary>SEO</summary>
      <div class="leaf">Title OK · Meta description courte</div>
    </details>
    <details><summary>OSINT</summary>
      <div class="leaf">2 emails publics trouves</div>
    </details>
  </div>
</div>
''', '<button class="md-btn md-btn-filled">Exporter PDF</button>')
    (PAGES / 'rapport-audit.html').write_text(rapport, encoding='utf-8')
    specials.append(('pages/rapport-audit.html', 'Rapport audit', 'Export findings'))

    # Preview email
    preview = shell('tpl', 'Preview email', 'Rendu HTML desktop / mobile', f'''
<div class="md-segmented" style="margin-bottom:16px"><button class="is-active">Desktop</button><button>Mobile</button></div>
<div class="md-grid md-grid-2">
  <div class="md-card" style="padding:20px;background:#fff;color:#222;min-height:360px">
    <div style="font-family:Georgia,serif">
      <h2 style="color:#0d8f56;margin-top:0">Presence digitale</h2>
      <p>Bonjour,</p>
      <p>Je vous contacte au sujet de votre site atelier-nord.fr...</p>
      <a style="display:inline-block;background:#0d8f56;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Voir l'audit</a>
    </div>
  </div>
  <div class="md-card md-card-pad">
    <div class="md-chart-title"><h3>Stats modele</h3></div>{spark()}
    <div class="md-hbar" style="margin-top:12px">
      <div class="row"><span>Open</span><div class="track"><i style="width:31%"></i></div><span class="val">31%</span></div>
      <div class="row"><span>Click</span><div class="track blue"><i style="width:10%"></i></div><span class="val">10%</span></div>
    </div>
  </div>
</div>
''', '')
    (PAGES / 'preview-email.html').write_text(preview, encoding='utf-8')
    specials.append(('pages/preview-email.html', 'Preview email', 'Desktop/mobile'))

    return specials


def main():
    pages = build_pages()
    for item in pages:
        fname, active, title, sub, actions, body = item[:6]
        fab_ext = item[6] if len(item) > 6 else None
        kwargs = {}
        text = shell(active, title, sub, body, actions, fab_ext=fab_ext)
        (PAGES / fname).write_text(text, encoding='utf-8')
        print('wrote', fname)

    specials = write_specials()
    print('specials', len(specials))

    sections = [
        ('@clea_ux · TikTok UX', [
            ('pages/playbook-clea.html', 'Playbook clea_ux', '164 videos → principes'),
            ('pages/onboarding.html', 'Onboarding TTV', 'Action cle a rebours'),
            ('pages/victoire.html', 'Victoire Peak-End', 'Fin nette post-envoi'),
            ('pages/recherche-vide.html', 'Recherche 0', 'Bestseller + vote'),
            ('pages/etats.html', 'Etats qui guident', 'Empty / erreur + CTA'),
        ]),
        ('Design system', [
            ('pages/composants.html', 'Kit composants', 'MD3 + charts pack'),
            ('pages/dashboard-light.html', 'Theme light', 'Variante claire'),
        ]),
        ('Auth & systeme', [
            ('pages/login.html', 'Login', 'Ecran connexion'),
            ('pages/restricted.html', 'Acces restreint', 'Erreur qui guide'),
            ('pages/error.html', 'Erreur 404', 'Page erreur'),
            ('pages/settings.html', 'Reglages', 'Theme, Brevo, secu'),
        ]),
        ('Principal', [
            ('pages/dashboard.html', 'Dashboard CTV', 'Commence par ca'),
            ('pages/entreprises.html', 'Entreprises', 'Liste + filtres'),
            ('pages/entreprise-detail.html', 'Fiche entreprise', 'Vue 360'),
            ('pages/carte.html', 'Carte', 'Pins + sheet'),
            ('pages/graph.html', 'Graphe', 'Network + slope'),
            ('pages/concurrence.html', 'Concurrence', 'Marche + treemap'),
        ]),
        ('Analyses', [
            ('pages/analyse-site.html', 'Analyse site', 'Scores + bullet'),
            ('pages/analyses-tech.html', 'Techniques', 'Stack / perf'),
            ('pages/analyses-osint.html', 'OSINT', 'Exposition'),
            ('pages/analyses-pentest.html', 'Pentest', 'Controles'),
            ('pages/analyses-seo.html', 'SEO', 'Scores'),
            ('pages/scrapers.html', 'Scrapers', 'Kanban workers'),
            ('pages/rapport-audit.html', 'Rapport audit', 'Findings tree'),
        ]),
        ('Emails', [
            ('pages/campagnes.html', 'Campagnes', 'Brevo + kanban'),
            ('pages/campagne-detail.html', 'Campagne detail', 'PL vs Brevo'),
            ('pages/envoyer.html', 'Envoyer', 'Stepper'),
            ('pages/modeles.html', 'Modeles', 'Templates'),
            ('pages/preview-email.html', 'Preview email', 'Rendu HTML'),
            ('pages/bounces.html', 'Bounces', 'Hygiene'),
        ]),
        ('Data & API', [
            ('pages/domaines.html', 'Domaines', 'SMTP / DNS'),
            ('pages/api.html', 'API', 'Tokens + usage'),
            ('pages/upload.html', 'Import CSV', 'Mapping'),
            ('campagnes-brevo/index.html', 'Variantes Brevo', 'Screenshots'),
        ]),
    ]

    hub_parts = []
    total = 0
    for title, cards in sections:
        hub_parts.append(f'<div class="hub-section">{title}</div><div class="hub-grid">')
        for href, name, desc in cards:
            hub_parts.append(
                f'<a class="hub-card" href="{href}"><h3>{name}</h3><p>{desc}</p>'
                f'<span class="tag">Ouvrir →</span></a>'
            )
            total += 1
        hub_parts.append('</div>')

    index = f'''<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Maquettes UX/UI | ProspectLab</title>
  <link rel="stylesheet" href="assets/md3.css" />
  <link rel="stylesheet" href="assets/md3-extra.css" />
  <style>
    body {{ padding: 32px 24px 80px; background: linear-gradient(160deg,#0a0e14,#121a24 45%,#0f1419); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1 style="margin:0 0 8px;font-size:1.85rem;letter-spacing:-.02em">Maquettes ProspectLab</h1>
    <p style="color:var(--md-sys-color-on-surface-variant);margin:0 0 10px;max-width:62ch;line-height:1.5">
      Kit MD3 dark + light, graphiques SVG/CSS offline, pages metier densifiees.
      Dossier gitignore : <code>design/mockups/</code>.
    </p>
    <p style="margin:0 0 8px">
      <span class="md-chip ok">MD3</span>
      <span class="md-chip warn">Charts</span>
      <span class="md-chip neutral">Kanban</span>
      <span class="md-chip ok">{total} ecrans</span>
    </p>
    {''.join(hub_parts)}
  </div>
</body>
</html>
'''
    (ROOT / 'index.html').write_text(index, encoding='utf-8')
    (ROOT / 'README.md').write_text(
        '# Maquettes locales (gitignorees)\n\n'
        'Ouvrir `index.html`.\n\n'
        '```powershell\npython scripts/generate_ui_mockups.py\n```\n\n'
        'Assets: md3.css, md3-extra.css, charts.css\n',
        encoding='utf-8',
    )
    print('hub ok', total, 'screens ->', ROOT)


if __name__ == '__main__':
    main()
