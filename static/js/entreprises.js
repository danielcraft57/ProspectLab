/**
 * Point d'entrée cohérent pour la page "Entreprises".
 *
 * Objectif: garder un nom homogène (`entreprises.js`) sans casser l'existant.
 * On charge ensuite l'implémentation actuelle (`entreprises.refactored.js`).
 *
 * Note: la refactorisation en modules est déjà en place pour utils/api/analyses,
 * ce wrapper permet de migrer progressivement le reste sans gros bang.
 */

(function () {
    'use strict';

    // Éviter les doubles chargements si plusieurs templates l'incluent.
    if (window.__entreprisesEntryLoaded) return;
    window.__entreprisesEntryLoaded = true;

    const currentSrc = (document.currentScript && document.currentScript.getAttribute('src')) || '';
    const hasQuery = currentSrc.includes('?');
    const query = hasQuery ? currentSrc.slice(currentSrc.indexOf('?')) : '';

    // Si le script est servi depuis /static/js/entreprises.js, on dérive la cible.
    // Sinon fallback sur le chemin attendu.
    let target = '/static/js/entreprises.refactored.js' + query;
    if (currentSrc) {
        target = currentSrc.replace(/entreprises\.js(\?.*)?$/i, 'entreprises.refactored.js$1');
    }

    const s = document.createElement('script');
    s.src = target;
    s.async = false;
    s.defer = true;
    document.head.appendChild(s);
})();

