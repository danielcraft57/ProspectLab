/**
 * Modèle d’ingénierie — cache carte (SQLite sur Android, sans pièges classiques)
 *
 * **Couche A — Données métier (entreprises « proches »)**  
 * - Stockage : table `cache_entry` (existante), `scope = map_nearby`, `payload` = JSON texte.  
 * - Politique : SWR via `STALE_AFTER_MS[MAP_NEARBY]`, LRU via `SCOPE_LRU_MAX[MAP_NEARBY]`, purge TTL au démarrage.  
 * - Clé : grille géographique + rayon + filtres (`buildMapNearbyCacheKey`) pour mutualiser les requêtes proches.
 *
 * **Couche B — Tuiles raster OpenStreetMap**  
 * - Anti-pattern : PNG en BLOB dans SQLite → fichier `.db` énorme, lectures lentes, pression WAL / curseurs.  
 * - Pattern retenu : table `osm_tile_index` (clé z/x/y + chemin relatif + métadonnées) + **octets sur le cache disque**
 *   (`expo-file-system` `cacheDirectory`). SQLite ne fait qu’indexer et appliquer LRU/TTL.
 *
 * **Affichage**  
 * - Les tuiles OSM sont chargées en HTTPS (MapLibre / Leaflet web). Le cache disque sert au **préchargement**
 *   (p.ex. après `onRegionChangeComplete`) et prépare une future couche 100 % offline (MapLibre, `file://`, etc.).
 *
 * @see `osmTileFileCache.ts` — implémentation tuiles
 * @see `repositories.ts` — `readMapNearbyCache` / `writeMapNearbyCache`
 */
/** Version du schéma logique (doc / migrations humaines). */
export const MAP_CACHE_ARCHITECTURE_VERSION = 1 as const;
