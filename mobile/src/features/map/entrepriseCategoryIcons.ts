/**
 * Associe le libellé secteur (données libres) à une paire d’icônes :
 * - MaterialCommunityIcons (natif / cohérence app)
 * - Font Awesome 6 solid (web / Leaflet via CDN)
 */

export type EntrepriseCategoryIcons = {
  /** Nom d’icône MaterialCommunityIcons (@expo/vector-icons) */
  material: string;
  /** Suffixe classe FA6 : fa-solid fa-{faSolid} */
  faSolid: string;
};

function normalizeSecteur(raw: string | null | undefined): string {
  if (!raw || typeof raw !== 'string') return '';
  return raw
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .trim();
}

const UNKNOWN_POOL: EntrepriseCategoryIcons[] = [
  { material: 'briefcase', faSolid: 'briefcase' },
  { material: 'domain', faSolid: 'building' },
  { material: 'account-tie', faSolid: 'user-tie' },
  { material: 'tag-multiple', faSolid: 'tags' },
  { material: 'star-four-points', faSolid: 'certificate' },
  { material: 'hexagon-multiple', faSolid: 'cubes' },
];

function iconForUnknown(normalized: string): EntrepriseCategoryIcons {
  if (!normalized) return { material: 'office-building', faSolid: 'building' };
  let h = 0;
  for (let i = 0; i < normalized.length; i++) h = (h * 31 + normalized.charCodeAt(i)) | 0;
  return UNKNOWN_POOL[Math.abs(h) % UNKNOWN_POOL.length]!;
}

const RULES: { test: RegExp; icon: EntrepriseCategoryIcons }[] = [
  {
    test: /restaurant|restauration|brasserie|cafe|café|bar\b|pub\b|traiteur|catering|food truck|snack|boulanger|patisser|pâtisser|boucher|fromager|cuisine|traiteur/i,
    icon: { material: 'silverware-fork-knife', faSolid: 'utensils' },
  },
  {
    test: /hotel|hôtel|hebergement|hébergement|chambre d|gite|gîte|auberge|residence tourisme|tourisme.*heberg/i,
    icon: { material: 'bed', faSolid: 'bed' },
  },
  {
    test: /sante|santé|medical|médical|dentaire|pharmacie|hopital|hôpital|clinique|kinesith|kinésith|osteopat|ostéopat|veterinaire|vétérinaire|optique|laboratoire.*bio|soins|nursing|infirmier/i,
    icon: { material: 'hospital-building', faSolid: 'hospital' },
  },
  {
    test: /btp|construction|macon|maçon|plombier|electricien|électricien|couvreur|charpent|menuis|carreleur|peintre\b|demolition|démolition|gros oeuvre|ingenieur.*civil|étanche|isolation|chauffagiste|climatisation|vitrier|serrur/i,
    icon: { material: 'hard-hat', faSolid: 'helmet-safety' },
  },
  {
    test: /auto|garage|mecanique|mécanique|carrosserie|pneu|station service|lavage auto|concession|motocycle|scooter.*rep/i,
    icon: { material: 'car-wrench', faSolid: 'car' },
  },
  {
    test: /informatique|logiciel|developpeur|développeur|saas|cyber|web\b|digital|data\b|cloud|hebergement web|hébergement web|telecom|télécom|reseau|réseau|it\b|esi|ssi\b/i,
    icon: { material: 'laptop', faSolid: 'laptop-code' },
  },
  {
    test: /commerce|retail|magasin|boutique|pret a porter|prêt-à-porter|superette|supérette|epicer|épicer|supermarche|supermarché|grande distribution|cash and carry/i,
    icon: { material: 'storefront', faSolid: 'shop' },
  },
  {
    test: /coiff|esthetique|esthétique|beauté|beaute|ongler|spa\b|institut|barbier|tatou|maquill/i,
    icon: { material: 'content-cut', faSolid: 'scissors' },
  },
  {
    test: /sport|fitness|salle de musculation|crossfit|yoga|pilates|club.*sport/i,
    icon: { material: 'dumbbell', faSolid: 'dumbbell' },
  },
  {
    test: /juridique|avocat|notaire|huissier|conseil.*jurid|legal\b/i,
    icon: { material: 'gavel', faSolid: 'scale-balanced' },
  },
  {
    test: /finance|assurance|banque|credit\b|crédit|courtier|gestion.*patrim|comptabil|expert compt|audit financier/i,
    icon: { material: 'bank', faSolid: 'landmark' },
  },
  {
    test: /immobilier|agence immo|promoteur|syndic|gestion locative|transaction.*immo/i,
    icon: { material: 'home-city', faSolid: 'building' },
  },
  {
    test: /transport|logistique|messagerie|demenagement|déménagement|livraison|fret|entreposage|warehouse|stockage|3pl/i,
    icon: { material: 'truck', faSolid: 'truck' },
  },
  {
    test: /education|éducation|formation|ecole|école|lycee|lycée|college|collège|universite|université|cours particulier|organisme.*formation|cfa\b/i,
    icon: { material: 'school', faSolid: 'graduation-cap' },
  },
  {
    test: /agriculture|agricole|elevage|élevage|viticult|maraicher|maraîcher|serre\b|cooperative agricole|céréale/i,
    icon: { material: 'tractor', faSolid: 'tractor' },
  },
  {
    test: /industrie|fabrication|usine|production|manufactur|chimie\b|metallurg|métallurg|plastique|textile|mecano|électronique.*fab/i,
    icon: { material: 'factory', faSolid: 'industry' },
  },
  {
    test: /energie|énergie|solaire|photovolt|eolien|éolien|electricite.*prod|électricité.*prod|gaz\b|petrole|pétrole/i,
    icon: { material: 'lightning-bolt', faSolid: 'bolt' },
  },
  {
    test: /environnement|dechets|déchets|recycl|eau\b.*trait|assainissement|ecologie|écologie|biodiversite|biodiversité/i,
    icon: { material: 'leaf', faSolid: 'leaf' },
  },
  {
    test: /nettoyage|proprete|propreté|hygiene|hygiène|desinfect|désinfect|facilit|multi.*service.*propre/i,
    icon: { material: 'spray', faSolid: 'broom' },
  },
  {
    test: /securite|sécurité|gardiennage|surveillance|alarme|videosurveillance|vidéosurveillance|cctv/i,
    icon: { material: 'shield-account', faSolid: 'shield-halved' },
  },
  {
    test: /conseil|consulting|strategie|stratégie|cabinet.*gestion|organisme.*conseil/i,
    icon: { material: 'chart-line', faSolid: 'chart-line' },
  },
  {
    test: /marketing|communication|agence pub|publicité|media|média|evenementiel|événementiel|influenceur|graphisme|design\b/i,
    icon: { material: 'bullhorn', faSolid: 'bullhorn' },
  },
  {
    test: /rh\b|ressources humaines|recrutement|interim|intérim|portage salarial|cabinet.*emploi/i,
    icon: { material: 'account-group', faSolid: 'users' },
  },
  {
    test: /import|export|commerce international|douane/i,
    icon: { material: 'ship-wheel', faSolid: 'ship' },
  },
  {
    test: /aviation|aeroport|aéroport|aeronautique|aéronautique/i,
    icon: { material: 'airplane', faSolid: 'plane' },
  },
  {
    test: /photo|video|vidéo|cinema|cinéma|production audiovis|studio.*(photo|vid)/i,
    icon: { material: 'video', faSolid: 'video' },
  },
  {
    test: /musique|sonorisation|dj\b|instrument|orchestre/i,
    icon: { material: 'music', faSolid: 'music' },
  },
  {
    test: /art\b|galerie|antiquaire|decorateur|décorateur|tapissier/i,
    icon: { material: 'palette', faSolid: 'palette' },
  },
  {
    test: /edition|édition|librairie|imprimerie|presse\b|journal|maison d.*edition/i,
    icon: { material: 'book-open-page-variant', faSolid: 'book-open' },
  },
  {
    test: /telephon|téléphon|call center|centre d.*appel/i,
    icon: { material: 'phone', faSolid: 'phone' },
  },
  {
    test: /association|ong\b|fondation|culturel|social\b.*action|benevolat|bénévolat/i,
    icon: { material: 'hand-heart', faSolid: 'hand-holding-heart' },
  },
  {
    test: /religieu|eglise|église|paroisse|mosquee|mosquée|temple\b/i,
    icon: { material: 'church', faSolid: 'place-of-worship' },
  },
  {
    test: /animal|toilettage|pension.*animal|cynoph|felin|félin/i,
    icon: { material: 'paw', faSolid: 'paw' },
  },
  {
    test: /sport.*equipement|equipement.*sport|velo.*vente|vélo.*vente/i,
    icon: { material: 'bicycle', faSolid: 'bicycle' },
  },
  {
    test: /jardin|paysag|pépini|pepini|espaces verts|foret|forêt/i,
    icon: { material: 'tree', faSolid: 'tree' },
  },
  {
    test: /hotel.*affaire|cowork|espace.*cowork|domiciliation|centre.*affaire/i,
    icon: { material: 'desk', faSolid: 'building-user' },
  },
];

/**
 * Icônes carte à partir du secteur affiché en base.
 */
export function categoryIconsFromSecteur(secteur: string | null | undefined): EntrepriseCategoryIcons {
  const s = normalizeSecteur(secteur);
  if (!s) return { material: 'office-building', faSolid: 'building' };
  for (const r of RULES) {
    if (r.test.test(s)) return r.icon;
  }
  return iconForUnknown(s);
}
