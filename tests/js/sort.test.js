// node tests/js/sort.test.js
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

vm.runInThisContext(fs.readFileSync(path.join(__dirname, '..', '..', 'sort.js'), 'utf8'));

const P = { rn: 'Rassemblement national', lfi: 'La France insoumise' };
const partyName = (i) => P[i.party] || i.party;
const statusLabel = (s) => (s === 'a_verifier' ? 'À vérifier' : 'Non déclaré');
const mk = (name, party, extra = {}) => ({
  name, party, statut: 'non_candidat', followers: null, youtube_views: null,
  youtube_subscribers: null, youtube_subs_gain_7d: null, ...extra,
});
const cmp = (sort) => (x, y) => compareInfluencers(x, y, sort, 'fr', partyName, statusLabel);
const names = (rows) => rows.map((r) => r.name);

const rows = [
  mk('Dominique de Villepin', 'rn', { youtube_subscribers: 52800, youtube_subs_gain_7d: 10 }),
  mk('Marion Maréchal', 'rn', { youtube_subscribers: 127000, youtube_subs_gain_7d: 5 }),
  mk('Gilles Le Gendre', 'lfi', { youtube_subscribers: null }),
  mk('Rima Hassan', 'lfi', { youtube_subscribers: 60400, youtube_subs_gain_7d: 3 }),
  mk('Clémence Guetté', 'lfi', { youtube_subscribers: 60400, youtube_subs_gain_7d: 9 }),
  mk('Jordan Bardella', 'rn', { youtube_subscribers: 231000, youtube_subs_gain_7d: null }),
];

// Nom : A-Z puis Z-A, par nom de famille (Villepin en V, Maréchal en M)
assert.deepStrictEqual(names([...rows].sort(cmp({ key: 'name', dir: 'asc' }))),
  ['Jordan Bardella', 'Clémence Guetté', 'Rima Hassan', 'Gilles Le Gendre', 'Marion Maréchal', 'Dominique de Villepin']);
assert.deepStrictEqual(names([...rows].sort(cmp({ key: 'name', dir: 'desc' }))).slice(0, 2),
  ['Dominique de Villepin', 'Marion Maréchal']);

// Parti : A-Z, sans rupture
const byParty = [...rows].sort(cmp({ key: 'party', dir: 'asc' }));
assert.deepStrictEqual(byParty.map((r) => r.party).slice(0, 3), ['lfi', 'lfi', 'lfi']);

// Abonnés YouTube : décroissant, valeurs absentes en bas quel que soit le sens
const subsDesc = [...rows].sort(cmp({ key: 'subs', dir: 'desc' }));
assert.strictEqual(subsDesc[0].name, 'Jordan Bardella');
assert.strictEqual(subsDesc[subsDesc.length - 1].name, 'Gilles Le Gendre');
const subsAsc = [...rows].sort(cmp({ key: 'subs', dir: 'asc' }));
assert.strictEqual(subsAsc[subsAsc.length - 1].name, 'Gilles Le Gendre');
assert.strictEqual(subsAsc[0].name, 'Dominique de Villepin');
// À 60 400 abonnés chacun, le gain hebdomadaire départage (9 avant 3)
const idx = (n) => subsAsc.findIndex((r) => r.name === n);
assert.ok(idx('Clémence Guetté') < idx('Rima Hassan'), 'gain hebdo départage à égalité');

// Gain 7 j : nulls en bas, croissant puis décroissant
assert.deepStrictEqual(names([...rows].sort(cmp({ key: 'gain', dir: 'desc' }))).slice(0, 2),
  ['Dominique de Villepin', 'Clémence Guetté']);
assert.strictEqual([...rows].sort(cmp({ key: 'gain', dir: 'asc' }))[0].name, 'Rima Hassan');

// Statut : texte, pas de rupture
assert.strictEqual(compareInfluencers(mk('A B', 'rn'), mk('C D', 'rn'), { key: 'status', dir: 'asc' }, 'fr', partyName, statusLabel) <= 0, true);

console.log('sort tests OK');
