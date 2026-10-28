/**
 * Tri des personnalités influentes. Fichier chargé avant app.js ; testé avec node (tests/js/sort.test.js).
 */

/** Particules rattachées au nom de famille (« Le Gendre » est classé en L). */
const SURNAME_PARTICLES = new Set(['le', 'la', 'les']);

/**
 * Nom de famille pour le classement : le dernier mot, avec « le/la/les » qui le précèdent.
 * « de/du/van » sont ignorées (« Dominique de Villepin » est classé en V).
 * @param {string} name
 * @returns {string}
 */
function surnameOf(name) {
  const words = name.trim().split(/\s+/);
  let i = words.length - 1;
  while (i > 0 && SURNAME_PARTICLES.has(words[i - 1].toLowerCase())) i--;
  return words.slice(i).join(' ');
}

/**
 * Valeur de tri d'une personnalité pour une colonne.
 * @param {{ name: string, party: string, statut: string, followers: number | null, youtube_views: number | null, youtube_subscribers: number | null, youtube_subs_gain_7d: number | null }} i
 * @param {string} key
 * @param {(i: any) => string} partyName
 * @param {(statut: string) => string} statusLabel
 * @returns {string | number | null}
 */
function influencerSortValue(i, key, partyName, statusLabel) {
  switch (key) {
    case 'name': return surnameOf(i.name);
    case 'party': return partyName(i);
    case 'status': return statusLabel(i.statut);
    case 'followers': return i.followers;
    case 'views': return i.youtube_views;
    case 'subs': return i.youtube_subscribers;
    case 'gain': return i.youtube_subs_gain_7d;
    default: return null;
  }
}

/**
 * Comparateur : les valeurs absentes restent en bas, quel que soit le sens du tri.
 * À égalité, les abonnés YouTube sont départagés par leur gain hebdomadaire, puis le nom.
 * @param {any} x
 * @param {any} y
 * @param {{ key: string, dir: 'asc' | 'desc' }} sort
 * @param {string} locale
 * @param {(i: any) => string} partyName
 * @param {(statut: string) => string} statusLabel
 * @returns {number}
 */
function compareInfluencers(x, y, sort, locale, partyName, statusLabel) {
  const a = influencerSortValue(x, sort.key, partyName, statusLabel);
  const b = influencerSortValue(y, sort.key, partyName, statusLabel);
  const sign = sort.dir === 'asc' ? 1 : -1;
  const byName = x.name.localeCompare(y.name, locale);
  if (a == null || b == null) {
    if (a == null && b == null) return byName;
    return a == null ? 1 : -1;
  }
  let cmp;
  if (typeof a === 'string' && typeof b === 'string') {
    cmp = sign * a.localeCompare(b, locale);
  } else {
    cmp = sign * (Number(a) - Number(b));
  }
  if (cmp !== 0) return cmp;
  if (sort.key === 'subs') {
    const ga = x.youtube_subs_gain_7d;
    const gb = y.youtube_subs_gain_7d;
    if (ga != null && gb != null && ga !== gb) return gb - ga;
    if (ga == null && gb != null) return 1;
    if (gb == null && ga != null) return -1;
  }
  return byName;
}
