/**
 * Schéma de live_data.json (produit par `python -m pipeline`).
 * @typedef {{ id: string, name: string, wiki: string, party: string, badge: string, color: string, main: boolean, aliases: string[] }} Candidate
 * @typedef {{ id: string, name: string, badge: string, color: string }} Party
 * @typedef {{ articles_7d: number, share_7d: number, tone_7d: number | null, tone_baseline: number | null, adjustment: number, status: 'ok' | 'calibrage' | 'trop_peu_articles' }} MediaSignal
 * @typedef {{ id: string, poll_avg: number, poll_lo: number, poll_hi: number, n_polls: number, change_7d: number | null, media: MediaSignal, projected: number, projected_lo: number, projected_hi: number }} Projection
 * @typedef {{ mean: number, lo: number, hi: number, n_polls: number }} PollAverage
 * @typedef {{ date: string, polls: Record<string, PollAverage> }} HistoryEntry
 * @typedef {{ pollster: string, end_date: string, sample: number | null, url: string | null, scores: Record<string, number>, scenarios: number }} Poll
 * @typedef {{ date: string, candidates: Record<string, { articles: number, tone: number }> }} MediaDay
 * @typedef {{ outlet: string, title: string, url: string }} SourceLink
 * @typedef {{ date: string, title: string, description: string, category: string, candidates: string[], origin: 'presse' | 'wikipedia', sources: SourceLink[] }} CampaignEvent
 * @typedef {{ outlet: string, ok: boolean, lean?: string, items?: number, error?: string }} FeedStatus
 * @typedef {{ polls?: string, polls_fetched?: string, feeds: FeedStatus[], articles_total: number, articles_analysed: number, media_since: string | null }} Sources
 * @typedef {{ id: string, followers: (number | null)[], change: (number | null)[], latest_by_platform: Record<string, number> }} PersonSeries
 * @typedef {{ id: string, members: string[], followers: (number | null)[], change: (number | null)[] }} PartySeries
 * @typedef {{ dates: string[], platforms: string[], candidates: PersonSeries[], parties: PartySeries[], influencers: PersonSeries[] }} Followers
 * @typedef {{ date: string, candidate: string, channel: string, show: string | null, audience_viewers: number | null, audience_share: number | null, source: SourceLink }} Interview
 * @typedef {Record<string, { count: number, avg_viewers: number | null, avg_share: number | null }>} InterviewSummary
 * @typedef {{ id: string, name: string, color: string | null, group?: string | null, views: (number | null)[], change: (number | null)[], subscribers: (number | null)[], latest: { date: string, views: number, subscribers: number | null, videos: number, title: string } | null }} YouTubeSeries
 * @typedef {{ dates: string[], candidates: YouTubeSeries[], media: YouTubeSeries[], influencers: YouTubeSeries[] }} YouTube
 * @typedef {{ id: string, name: string, party: string, statut: 'non_candidat' | 'a_verifier', note: string, followers: number | null, youtube_views: number | null, youtube_subscribers: number | null, youtube_subs_gain_7d: number | null }} Influencer
 * @typedef {{ period: string, fetched: string, total_tv: number | null, shares: Record<string, number> }} TvWeek
 * @typedef {{ video_id: string, title: string, channel: string, published: string, candidates: string[], views: number, url: string }} InterviewVideo
 * @typedef {{ last_updated: string, tv_weekly: TvWeek | null, interview_videos: InterviewVideo[], today: string, candidates: Candidate[], parties: Party[], influencers: Influencer[], youtube: YouTube, projection: Projection[], history: HistoryEntry[], polls: Poll[], media_daily: MediaDay[], media_by_outlet: Record<string, Record<string, { tone: number, n: number }>>, events: CampaignEvent[], followers: Followers, interviews: Interview[], interview_summary: InterviewSummary, sources: Sources, parameters?: Record<string, number> }} LiveData
 */

/** @type {LiveData} */
let data = /** @type {LiveData} */ ({});
/** @type {Record<string, Candidate>} */
let candById = {};
/** @type {Record<string, Party>} */
let partyById = {};
/** @type {Record<string, any>} */
const charts = {};

/** Clés « cand:<id> », « party:<id> » et « media:<id> » des entités cochées. */
/** @type {Set<string>} */
const selected = new Set();
/** @type {'total' | 'change'} */
let followersMode = 'total';
/** @type {'viewers' | 'share'} */
let interviewMetric = 'viewers';
/** @type {'total' | 'change'} */
let youtubeMode = 'total';

const GRID = '#EEF0F3';
const INK = '#334155';
const MUTED = '#64748B';

/**
 * @param {string} id
 * @returns {HTMLElement}
 */
function $(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Élément introuvable : #${id}`);
  return el;
}

/** @type {Record<string, string>} */
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
// Tout texte venant des flux RSS / de Wikipédia est échappé avant insertion.
/** @param {unknown} s */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => HTML_ESCAPES[c]);
/** @param {number | null | undefined} v @param {number} [digits] */
const fmt = (v, digits = 1) => v == null ? '—' : v.toLocaleString(LOCALES[lang], { minimumFractionDigits: digits, maximumFractionDigits: digits });
/** @param {number | null | undefined} v @param {number} [digits] */
const signed = (v, digits = 1) => v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + fmt(Math.abs(v), digits);
/** Abonnés lisibles : 1,23 M, 850 k, 4 210. @param {number | null | undefined} v */
const compact = (v) => {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e6) return `${fmt(v / 1e6, 2)} M`;
  if (a >= 1e3) return `${fmt(v / 1e3, 0)} k`;
  return fmt(v, 0);
};
/** @param {string | null | undefined} u */
const safeUrl = (u) => /^https?:\/\//.test(u || '') ? u : '#';
/** @param {string} hex @param {number} a */
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
/** @param {string} id @returns {HTMLCanvasElement} */
const canvas = (id) => /** @type {HTMLCanvasElement} */ ($(id));
/** Date et heure au format de la langue (fr : 27/10/2026 22:59). @param {string} stamp « AAAA-MM-JJ HH:MM » */
const dateTime = (stamp) => new Date(stamp.replace(' ', 'T')).toLocaleString(LOCALES[lang], { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
/** Date courte ; une date seule est lue à midi pour ne pas glisser d'un jour selon le fuseau. @param {string} iso */
const shortDate = (iso) => new Date(iso.length === 10 ? iso + 'T12:00:00' : iso).toLocaleDateString(LOCALES[lang], { day: '2-digit', month: 'short' });

async function init() {
  applyStatic();
  const sel = document.getElementById('langSelect');
  if (sel) sel.addEventListener('change', () => setLang(/** @type {HTMLSelectElement} */ (sel).value));
  try {
    const res = await fetch('live_data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    $('lastUpdated').textContent = t('header.unavailable', { error: e instanceof Error ? e.message : String(e) });
    return;
  }
  data.candidates.forEach(c => { candById[c.id] = c; });
  (data.parties || []).forEach(p => { partyById[p.id] = p; });

  // Sélection initiale : les candidats principaux et tous les partis
  data.candidates.filter(c => c.main).forEach(c => selected.add(`cand:${c.id}`));
  (data.parties || []).forEach(p => selected.add(`party:${p.id}`));
  buildPicker();
  (data.influencers || []).forEach(i => influencerIncluded.add(i.id));
  wireInfluencerControls();

  renderEverything();
}

/** Appelée par setLang (i18n.js) : redessine tout, textes compris. */
function onLanguageChange() {
  renderEverything();
}

function renderEverything() {
  applyStatic();
  renderHeader();
  renderMethodology();
  renderProjection();
  renderOutlets();
  renderEvents();
  renderInfluencers();
  renderTvWeekly();
  renderInterviewVideos();
  renderAll();
}

function renderHeader() {
  const src = data.sources || {};
  $('lastUpdated').textContent = t('header.updated', { date: dateTime(data.last_updated) });
  const okFeeds = (src.feeds || []).filter(f => f.ok).length;
  $('sourceSummary').textContent = t('header.summary', {
    polls: data.polls.length, feeds: okFeeds, total: (src.feeds || []).length,
    analysed: src.articles_analysed, articles: src.articles_total,
  });
}

/** Méthodologie : générée à partir des traductions, avec les paramètres du modèle. */
function renderMethodology() {
  const src = data.sources || {};
  const p = data.parameters || {};
  const link = `<a class="text-indigo-600 underline" href="${esc(safeUrl(src.polls))}" target="_blank" rel="noopener noreferrer">${t('method.source')}</a>`;
  const paragraphs = ['method.polls', 'method.media', 'method.projection', 'method.followers', 'method.candidates',
    'method.youtube', 'method.interviews', 'method.limits', 'method.emblem'];
  const params = {
    sourceLink: link, beta: fmt(p.MEDIA_BETA ?? 1.5), cap: fmt(p.MEDIA_CAP ?? 2, 0),
  };
  $('methodologyBody').innerHTML = paragraphs.map(k => `<p>${t(k, params)}</p>`).join('');
}

/** Parts d'audience TV de la semaine (Médiamétrie) : chaînes suivies et total. */
function renderTvWeekly() {
  const w = data.tv_weekly;
  if (!w) {
    $('tvWeeklyTable').innerHTML = `<tbody><tr><td class="py-2 text-slate-400">${t('tv.none')}</td></tr></tbody>`;
    return;
  }
  const rows = [['tf1', 'TF1'], ['france2', 'France 2'], ['france3', 'France 3'], ['m6', 'M6'], ['w9', 'W9']]
    .filter(([k]) => w.shares[k] != null)
    .map(([k, label]) => `<tr class="border-b border-slate-100"><td class="px-2 py-1 font-semibold">${label}</td><td class="px-2 py-1 text-right">${fmt(w.shares[k])} %</td></tr>`).join('');
  $('tvWeeklyTable').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${esc(t('tv.week', { period: w.period }))}</th><th class="px-2 py-1 text-right">${t('tv.share')}</th></tr></thead>
    <tbody>${rows}<tr class="font-bold"><td class="px-2 py-1">${t('tv.total')}</td><td class="px-2 py-1 text-right">${w.total_tv == null ? '—' : compact(w.total_tv)}</td></tr></tbody>`;
}

/** Vidéos YouTube d'entretiens citant un candidat (depuis le 1er juillet 2026). */
function renderInterviewVideos() {
  const rows = (data.interview_videos || []).map(v => `<tr class="border-b border-slate-100">
      <td class="px-2 py-1 whitespace-nowrap">${esc(shortDate(v.published))}</td>
      <td class="px-2 py-1 whitespace-nowrap font-semibold">${esc(v.candidates.join(', '))}</td>
      <td class="px-2 py-1 whitespace-nowrap">${esc(v.channel)}</td>
      <td class="px-2 py-1"><a class="text-indigo-700 underline" href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener noreferrer">${esc(v.title)}</a></td>
      <td class="px-2 py-1 text-right">${compact(v.views)}</td></tr>`).join('');
  $('interviewVideosTable').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('yt.th.date')}</th><th class="px-2 py-1 text-left">${t('yt.th.candidate')}</th><th class="px-2 py-1 text-left">${t('yt.th.channel')}</th>
      <th class="px-2 py-1 text-left">${t('yt.th.title')}</th><th class="px-2 py-1 text-right">${t('yt.th.views')}</th></tr></thead>
    <tbody>${rows || `<tr><td class="py-2 text-slate-400" colspan="5">${t('yt.none')}</td></tr>`}</tbody>`;
}

/** Tri et sélection des personnalités influentes (logique dans sort.js). */
/** @type {{ key: string, dir: 'asc' | 'desc' }} */
let influencerSort = { key: 'name', dir: 'asc' };
/** @type {Set<string>} identifiants des personnalités cochées */
const influencerIncluded = new Set();
/** Colonnes triables : clé de tri, et sens initial au premier clic. */
/** @type {Record<string, 'asc' | 'desc'>} */
const SORTABLE = {
  name: 'asc', party: 'asc', status: 'asc',
  followers: 'desc', views: 'desc', subs: 'desc', gain: 'desc',
};

/** @param {Influencer} i */
const partyLabel = (i) => partyById[i.party] ? partyById[i.party].name : i.party;
/** @param {string} statut */
const statusText = (statut) => t('status.' + statut);

/** Personnalités triées selon la colonne et le sens choisis. */
function sortedInfluencers() {
  return [...(data.influencers || [])].sort((x, y) =>
    compareInfluencers(x, y, influencerSort, LOCALES[lang], partyLabel, statusText));
}

/** Flèche indiquant la colonne triée et son sens. */
/** @param {string} key */
const arrow = (key) => influencerSort.key !== key ? '' : (influencerSort.dir === 'asc' ? ' ▲' : ' ▼');

/** Intitulé de colonne cliquable pour trier. */
/** @param {string} key @param {string} label @param {string} [align] */
const sortTh = (key, label, align = 'text-left') =>
  `<th data-sort="${key}" class="px-2 py-1 ${align} cursor-pointer select-none whitespace-nowrap hover:text-slate-900 ${influencerSort.key === key ? 'text-indigo-700' : ''}">${label}${arrow(key)}</th>`;

/** Personnalités influentes non candidates : tableau triable, abonnés, audience YouTube et total par parti. */
function renderInfluencers() {
  const rows = sortedInfluencers();
  $('infCount').textContent = `(${rows.length})`;
  $('influencersTable').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('inf.th.include')}</th>
      ${sortTh('name', t('influencers.th.person'))}${sortTh('party', t('influencers.th.party'))}${sortTh('status', t('influencers.th.status'))}
      ${sortTh('followers', t('influencers.th.followers'), 'text-right')}${sortTh('views', t('influencers.th.views'), 'text-right')}
      ${sortTh('subs', t('influencers.th.subs'), 'text-right')}${sortTh('gain', t('inf.th.gain'), 'text-right')}</tr></thead>
    <tbody>${rows.map(i => `<tr class="border-b border-slate-100 ${influencerIncluded.has(i.id) ? '' : 'opacity-40'}">
      <td class="px-2 py-1"><input type="checkbox" data-inf="${esc(i.id)}" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" ${influencerIncluded.has(i.id) ? 'checked' : ''}></td>
      <td class="px-2 py-1 font-semibold whitespace-nowrap">${esc(i.name)}</td>
      <td class="px-2 py-1 whitespace-nowrap">${esc(partyLabel(i))}</td>
      <td class="px-2 py-1" title="${esc(i.note)}">${esc(statusText(i.statut))}</td>
      <td class="px-2 py-1 text-right">${compact(i.followers)}</td>
      <td class="px-2 py-1 text-right">${compact(i.youtube_views)}</td>
      <td class="px-2 py-1 text-right">${compact(i.youtube_subscribers)}</td>
      <td class="px-2 py-1 text-right ${i.youtube_subs_gain_7d != null && i.youtube_subs_gain_7d < 0 ? 'text-[#c62f2e]' : 'text-[#1d5fb0]'}">${i.youtube_subs_gain_7d == null ? '—' : signed(i.youtube_subs_gain_7d, 0)}</td></tr>`).join('')}</tbody>`;

  // Données manquantes, par critère
  const missing = (/** @type {(i: Influencer) => boolean} */ f) => (data.influencers || []).filter(f).length;
  $('infMissing').textContent = t('inf.missing', {
    followers: missing(i => i.followers == null), views: missing(i => i.youtube_views == null),
  });

  // Total cumulé par parti, uniquement pour les personnalités cochées
  /** @type {Record<string, { count: number, followers: number | null, views: number | null, subs: number | null }>} */
  const byParty = {};
  (data.influencers || []).filter(i => influencerIncluded.has(i.id)).forEach(i => {
    const g = byParty[partyLabel(i)] || (byParty[partyLabel(i)] = { count: 0, followers: null, views: null, subs: null });
    g.count += 1;
    if (i.followers != null) g.followers = (g.followers || 0) + i.followers;
    if (i.youtube_views != null) g.views = (g.views || 0) + i.youtube_views;
    if (i.youtube_subscribers != null) g.subs = (g.subs || 0) + i.youtube_subscribers;
  });
  const totals = Object.entries(byParty).sort((x, y) => (y[1].followers ?? -1) - (x[1].followers ?? -1));
  $('partyTotalsTable').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('influencers.th.party')}</th><th class="px-2 py-1 text-right">${t('inf.th.count')}</th>
      <th class="px-2 py-1 text-right">${t('influencers.th.followers')}</th><th class="px-2 py-1 text-right">${t('influencers.th.views')}</th><th class="px-2 py-1 text-right">${t('influencers.th.subs')}</th></tr></thead>
    <tbody>${totals.map(([party, g]) => `<tr class="border-b border-slate-100">
      <td class="px-2 py-1 font-semibold whitespace-nowrap">${esc(party)}</td><td class="px-2 py-1 text-right">${g.count}</td>
      <td class="px-2 py-1 text-right font-bold">${compact(g.followers)}</td><td class="px-2 py-1 text-right">${compact(g.views)}</td>
      <td class="px-2 py-1 text-right">${compact(g.subs)}</td></tr>`).join('') || `<tr><td class="py-2 text-slate-400" colspan="5">${t('followers.noneChecked')}</td></tr>`}</tbody>`;
}

/** Écouteurs : clic sur un intitulé de colonne (tri), case à cocher (sélection). Installés une fois. */
function wireInfluencerControls() {
  $('influencersTable').addEventListener('click', (ev) => {
    const th = /** @type {HTMLElement} */ (ev.target).closest('th[data-sort]');
    if (!th) return;
    const key = /** @type {HTMLElement} */ (th).dataset.sort || 'name';
    /** @type {'asc' | 'desc'} */
    const first = SORTABLE[key] || 'asc';
    influencerSort = influencerSort.key === key
      ? { key, dir: influencerSort.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: first };
    renderInfluencers();
  });
  $('influencersTable').addEventListener('change', (ev) => {
    const t = /** @type {HTMLInputElement} */ (ev.target);
    if (!t.dataset.inf) return;
    if (t.checked) influencerIncluded.add(t.dataset.inf); else influencerIncluded.delete(t.dataset.inf);
    renderInfluencers();
  });
}

/** @param {string} key @param {string} label @param {string} color @param {string} badge */
function checkbox(key, label, color, badge) {
  const on = selected.has(key) ? 'checked' : '';
  return `<label class="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer hover:text-slate-900">
    <input type="checkbox" data-key="${esc(key)}" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" ${on}>
    <span class="inline-block w-2.5 h-2.5 rounded-full" style="background:${esc(color)}" aria-hidden="true"></span>
    <span>${esc(label)}</span><span class="text-[10px] text-slate-400">${esc(badge)}</span></label>`;
}

function buildPicker() {
  $('pickerCandidates').innerHTML = data.candidates.map(c => checkbox(`cand:${c.id}`, c.name, c.color, c.badge)).join('');
  $('pickerParties').innerHTML = (data.parties || []).map(p => checkbox(`party:${p.id}`, p.name, p.color, p.badge)).join('');
  $('pickerMedia').innerHTML = ((data.youtube && data.youtube.media) || []).map(m => checkbox(`media:${m.id}`, m.name, m.color || '#64748B', 'YT')).join('');
  $('pickerPanel').addEventListener('change', (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLInputElement) || !t.dataset.key) return;
    if (t.checked) selected.add(t.dataset.key); else selected.delete(t.dataset.key);
    renderAll();
  });
  $('pickerPanel').addEventListener('click', (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLButtonElement) || !t.dataset.preset) return;
    /** @type {string[]} */
    let keys = [];
    if (t.dataset.preset === 'all') {
      keys = [...data.candidates.map(c => `cand:${c.id}`), ...(data.parties || []).map(p => `party:${p.id}`),
              ...((data.youtube && data.youtube.media) || []).map(m => `media:${m.id}`)];
    } else if (t.dataset.preset === 'main') {
      keys = [...data.candidates.filter(c => c.main).map(c => `cand:${c.id}`), ...(data.parties || []).map(p => `party:${p.id}`)];
    }
    selected.clear();
    keys.forEach(k => selected.add(k));
    document.querySelectorAll('#pickerPanel input[data-key]').forEach(i => {
      if (i instanceof HTMLInputElement) i.checked = selected.has(i.dataset.key || '');
    });
    renderAll();
  });
  document.querySelectorAll('[data-toggle]').forEach(btn => {
    btn.addEventListener('click', (ev) => {
      const t = /** @type {HTMLButtonElement} */ (ev.currentTarget);
      const [group, value] = (t.dataset.toggle || '').split(':');
      if (group === 'followers') followersMode = /** @type {'total' | 'change'} */ (value);
      if (group === 'interview') interviewMetric = /** @type {'viewers' | 'share'} */ (value);
      if (group === 'youtube') youtubeMode = /** @type {'total' | 'change'} */ (value);
      document.querySelectorAll(`[data-toggle^="${group}:"]`).forEach(b => {
        const on = /** @type {HTMLButtonElement} */ (b).dataset.toggle === t.dataset.toggle;
        b.classList.toggle('bg-indigo-600', on);
        b.classList.toggle('text-white', on);
        b.classList.toggle('bg-slate-100', !on);
        b.classList.toggle('text-slate-700', !on);
      });
      renderAll();
    });
  });
}

function renderAll() {
  renderPollChart();
  renderMediaChart();
  renderFollowers();
  renderYouTube();
  renderInterviews();
}

/** Vues YouTube des candidats et des médias cochés. */
function renderYouTube() {
  const yt = data.youtube;
  const hasData = !!yt && yt.dates.length > 0 && (yt.candidates.length + yt.media.length) > 0;
  const change = youtubeMode === 'change';
  $('youtubeNote').textContent = hasData
    ? t('youtube.note', { date: shortDate(yt.dates[0]) })
    : t('youtube.none');
  const labelFmt = change ? (/** @type {number} */ v) => `${v > 0 ? '+' : ''}${compact(v)}` : compact;
  const tooltip = (/** @type {any} */ item) => ` ${item.dataset.label} : ${change ? signed(item.parsed.y, 0) : fmt(item.parsed.y, 0)}`;

  /**
   * @param {YouTubeSeries[]} series
   * @param {string} prefix
   */
  const sets = (series, prefix) => hasData ? series.filter(s => selected.has(prefix + s.id)).map(s => {
    const color = s.color || (candById[s.id] && candById[s.id].color) || '#64748B';
    return { label: s.name, data: change ? s.change : s.views, borderColor: color, backgroundColor: color,
             borderWidth: 2.5, pointRadius: yt.dates.length < 10 ? 4 : 0, pointHoverRadius: 5, tension: 0.2, spanGaps: true };
  }) : [];

  if (charts.ytCand) charts.ytCand.destroy();
  charts.ytCand = new Chart(canvas('ytCandChart'), { type: 'line',
    data: { labels: hasData ? yt.dates : [], datasets: sets(yt.candidates, 'cand:') },
    options: lineOptions('', { legend: true, tickFormat: labelFmt, tooltipLabel: tooltip }) });
  // Médias : deux graphiques, télévisions et radios (10 couleurs au plus), presse
  const mediaOf = (/** @type {string} */ group) => yt.media.filter(s => s.group === group);
  const tvRadio = [...mediaOf('tv'), ...mediaOf('radio')];
  if (charts.ytMediaTv) charts.ytMediaTv.destroy();
  charts.ytMediaTv = new Chart(canvas('ytMediaTvChart'), { type: 'line',
    data: { labels: hasData ? yt.dates : [], datasets: sets(tvRadio, 'media:') },
    options: lineOptions('', { legend: true, tickFormat: labelFmt, tooltipLabel: tooltip }) });
  if (charts.ytMediaPresse) charts.ytMediaPresse.destroy();
  charts.ytMediaPresse = new Chart(canvas('ytMediaPresseChart'), { type: 'line',
    data: { labels: hasData ? yt.dates : [], datasets: sets(mediaOf('presse'), 'media:') },
    options: lineOptions('', { legend: true, tickFormat: labelFmt, tooltipLabel: tooltip }) });

  /** @type {string[]} */
  const rows = [];
  if (hasData) {
    /** @type {Array<{ prefix: string, s: YouTubeSeries }>} */
    const all = [...yt.candidates.map(s => ({ prefix: 'cand:', s })), ...yt.media.map(s => ({ prefix: 'media:', s }))];
    all.filter(({ prefix, s }) => selected.has(prefix + s.id) && s.latest)
      .forEach(({ s }) => {
        if (!s.latest) return;
        const color = s.color || (candById[s.id] && candById[s.id].color) || '#64748B';
        const delta = s.change[s.change.length - 1];
        rows.push(`<tr class="border-b border-slate-100"><td class="px-2 py-1 font-semibold whitespace-nowrap"><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:${esc(color)}"></span>${esc(s.name)}</td>
          <td class="px-2 py-1 text-right">${compact(s.latest.views)}</td><td class="px-2 py-1 text-right">${delta == null ? '—' : signed(delta, 0)}</td>
          <td class="px-2 py-1 text-right">${s.latest.subscribers == null ? '—' : compact(s.latest.subscribers)}</td></tr>`);
      });
  }
  $('youtubeTable').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('youtube.th.channel')}</th><th class="px-2 py-1 text-right">${t('youtube.th.views')}</th>
      <th class="px-2 py-1 text-right">${t('youtube.th.change')}</th><th class="px-2 py-1 text-right">${t('youtube.th.subs')}</th></tr></thead>
    <tbody>${rows.join('') || `<tr><td class="py-2 text-slate-400" colspan="4">${t('youtube.noneChecked')}</td></tr>`}</tbody>`;
}

function renderProjection() {
  const statuses = new Set(data.projection.map(p => p.media.status));
  const since = data.sources?.media_since;
  $('mediaStatus').textContent = statuses.has('calibrage')
    ? t('proj.calib', { since: since ? shortDate(since) : '—' })
    : t('proj.active');

  $('projectionBody').innerHTML = data.projection.map(p => {
    const c = candById[p.id];
    const m = p.media;
    const ch = p.change_7d;
    const chCls = ch != null && ch > 0.2 ? 'text-[#1d5fb0]' : ch != null && ch < -0.2 ? 'text-[#c62f2e]' : 'text-slate-500';
    const lowN = p.n_polls < 5
      ? ` <span class="block text-[10px] text-amber-700">${t('proj.lowN', { n: p.n_polls })}</span>` : '';
    const adj = m.status === 'ok'
      ? signed(m.adjustment)
      : `0 <span class="text-[10px]">(${m.status === 'calibrage' ? t('proj.adj.calib') : t('proj.adj.few')})</span>`;
    return `<tr class="border-b border-slate-100 hover:bg-slate-50">
      <td class="py-2 pr-3 font-semibold text-slate-900 whitespace-nowrap"><span class="inline-block w-2.5 h-2.5 rounded-full mr-1.5 align-middle" style="background:${c.color}" aria-hidden="true"></span>${esc(c.name)} <span class="text-[11px] font-medium text-slate-400">${esc(c.badge)}</span></td>
      <td class="py-2 px-3 text-right">${fmt(p.poll_avg)} %</td>
      <td class="py-2 px-3 text-right text-slate-500">${fmt(p.poll_lo)} – ${fmt(p.poll_hi)}${lowN}</td>
      <td class="py-2 px-3 text-right ${chCls}">${signed(ch)}</td>
      <td class="py-2 px-3 text-right">${m.articles_7d}</td>
      <td class="py-2 px-3 text-right">${m.articles_7d ? fmt(m.share_7d * 100, 0) + ' %' : '—'}</td>
      <td class="py-2 px-3 text-right">${signed(m.tone_7d, 2)}</td>
      <td class="py-2 px-3 text-right text-slate-500">${adj}</td>
      <td class="py-2 pl-3 text-right font-extrabold text-slate-900">${fmt(p.projected)} %</td>
    </tr>`;
  }).join('');
}

function renderPollChart() {
  const cands = data.candidates.filter(c => selected.has(`cand:${c.id}`));
  const single = cands.length === 1;
  const hist = data.history;
  const labels = hist.map(h => h.date);
  const indexByDate = new Map(labels.map((d, i) => [d, i]));

  /** @type {any[]} */
  const datasets = [];
  cands.forEach(c => {
    if (single) {
      // Intervalle à 95 % : bande entre lo et hi (lavis ~12 %)
      datasets.push({ label: '_hi', data: hist.map(h => h.polls[c.id]?.hi ?? null), borderWidth: 0, pointRadius: 0, fill: false });
      datasets.push({ label: '_lo', data: hist.map(h => h.polls[c.id]?.lo ?? null), borderWidth: 0, pointRadius: 0,
                      fill: '-1', backgroundColor: hexA(c.color, 0.12) });
    }
    datasets.push({
      label: c.name, data: hist.map(h => h.polls[c.id]?.mean ?? null),
      borderColor: c.color, backgroundColor: c.color, borderWidth: single ? 4 : 2.5, pointRadius: 0,
      pointHoverRadius: 5, tension: 0.25, spanGaps: true,
    });
    if (single) {
      // Sondages individuels, moyennés si plusieurs enquêtes tombent le même jour
      /** @type {Map<number, number[]>} */
      const byIndex = new Map();
      data.polls.forEach(p => {
        const i = indexByDate.get(p.end_date);
        const v = p.scores[c.wiki];
        if (i === undefined || v == null) return;
        byIndex.set(i, [...(byIndex.get(i) || []), v]);
      });
      datasets.push({
        label: t('poll.individual'), showLine: false,
        data: labels.map((_, i) => {
          const vs = byIndex.get(i);
          return vs ? vs.reduce((a, b) => a + b, 0) / vs.length : null;
        }),
        borderColor: c.color, backgroundColor: hexA(c.color, 0.45), pointRadius: 4, pointBorderColor: '#FFFFFF',
      });
    }
  });

  if (charts.poll) charts.poll.destroy();
  charts.poll = new Chart(canvas('pollChart'), {
    type: 'line', data: { labels, datasets },
    options: lineOptions('%', { legend: true, tooltipLabel: (/** @type {any} */ item) => ` ${item.dataset.label} : ${fmt(item.parsed.y)} %` }),
  });
}

function renderMediaChart() {
  const cands = data.candidates.filter(c => selected.has(`cand:${c.id}`));
  const md = data.media_daily || [];
  const labels = md.map(d => d.date);
  const datasets = cands.map(c => ({
    label: c.name, data: md.map(d => d.candidates[c.id]?.articles ?? 0),
    borderColor: c.color, backgroundColor: c.color, borderWidth: 2.5, pointRadius: md.length < 10 ? 4 : 0,
    pointHoverRadius: 5, tension: 0.25,
  }));
  $('mediaChartNote').textContent = md.length
    ? t('media.since', { date: shortDate(md[0].date) })
    : t('media.none');
  if (charts.media) charts.media.destroy();
  charts.media = new Chart(canvas('mediaChart'), {
    type: 'line', data: { labels, datasets },
    options: lineOptions('', { legend: true, tooltipLabel: (/** @type {any} */ item) => ` ${item.dataset.label} : ${item.parsed.y} ${t('unit.article', { n: item.parsed.y })}` }),
  });
}

function renderFollowers() {
  const f = data.followers;
  const hasData = f && f.dates.length > 0;
  const change = followersMode === 'change';
  const lastDate = hasData ? f.dates[f.dates.length - 1] : null;
  const ageDays = lastDate ? (Date.parse(data.today) - Date.parse(lastDate)) / 86400000 : 0;
  const stale = hasData && ageDays > 10 ? t('followers.stale') : '';
  const note = hasData
    ? t('followers.range', { from: shortDate(f.dates[0]), to: shortDate(lastDate || '') }) + stale
    : t('followers.none');
  $('followersNote').textContent = note;
  $('followersPartyNote').textContent = hasData ? t('followers.partyNote') : note;

  /** @type {any[]} */
  const candSets = [];
  if (hasData) {
    f.candidates.filter(s => selected.has(`cand:${s.id}`)).forEach(s => {
      const values = change ? s.change : s.followers;
      if (values.every(v => v == null)) return;
      candSets.push({ label: candById[s.id].name, data: values, borderColor: candById[s.id].color,
                      backgroundColor: candById[s.id].color, borderWidth: 2.5, pointRadius: f.dates.length < 10 ? 4 : 0,
                      pointHoverRadius: 5, tension: 0.2, spanGaps: true });
    });
  }
  /** @type {any[]} */
  const partySets = [];
  if (hasData) {
    f.parties.filter(s => selected.has(`party:${s.id}`)).forEach(s => {
      const values = change ? s.change : s.followers;
      if (values.every(v => v == null)) return;
      partySets.push({ label: partyById[s.id].name, data: values, borderColor: partyById[s.id].color,
                       backgroundColor: partyById[s.id].color, borderWidth: 2.5, pointRadius: f.dates.length < 10 ? 4 : 0,
                       pointHoverRadius: 5, tension: 0.2, spanGaps: true });
    });
  }
  const labelFmt = change ? (/** @type {number} */ v) => `${v > 0 ? '+' : ''}${compact(v)}` : compact;
  const tooltip = (/** @type {any} */ item) => ` ${item.dataset.label} : ${change ? signed(item.parsed.y, 0) : fmt(item.parsed.y, 0)}`;
  if (charts.followersCand) charts.followersCand.destroy();
  charts.followersCand = new Chart(canvas('followersCandChart'), { type: 'line', data: { labels: hasData ? f.dates : [], datasets: candSets },
    options: lineOptions('', { legend: true, tickFormat: labelFmt, tooltipLabel: tooltip }) });
  if (charts.followersParty) charts.followersParty.destroy();
  charts.followersParty = new Chart(canvas('followersPartyChart'), { type: 'line', data: { labels: hasData ? f.dates : [], datasets: partySets },
    options: lineOptions('', { legend: true, tickFormat: labelFmt, tooltipLabel: tooltip }) });

  renderFollowersTable();
}

function renderFollowersTable() {
  const f = data.followers;
  const table = $('followersTable');
  if (!f || f.dates.length === 0) {
    table.innerHTML = `<tbody><tr><td class="py-2 text-slate-400">${t('followers.empty')}</td></tr></tbody>`;
    return;
  }
  const platforms = f.platforms;
  const rows = f.candidates.filter(s => selected.has(`cand:${s.id}`)).map(s => {
    const latest = s.followers[s.followers.length - 1];
    const cells = platforms.map(p => `<td class="px-2 py-1 text-right">${compact(s.latest_by_platform[p])}</td>`).join('');
    const delta = s.change[s.change.length - 1];
    return `<tr class="border-b border-slate-100"><td class="px-2 py-1 font-semibold whitespace-nowrap"><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:${candById[s.id].color}"></span>${esc(candById[s.id].name)}</td>${cells}<td class="px-2 py-1 text-right font-bold">${compact(latest)}</td><td class="px-2 py-1 text-right ${delta != null && delta < 0 ? 'text-[#c62f2e]' : 'text-[#1d5fb0]'}">${delta == null ? '—' : signed(delta, 0)}</td></tr>`;
  }).join('');
  table.innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('followers.th.candidate')}</th>${platforms.map(p => `<th class="px-2 py-1 text-right">${esc(p)}</th>`).join('')}
      <th class="px-2 py-1 text-right">${t('followers.th.total')}</th><th class="px-2 py-1 text-right">${t('followers.th.since')}</th></tr></thead>
    <tbody>${rows || `<tr><td class="py-2 text-slate-400" colspan="8">${t('followers.noneChecked')}</td></tr>`}</tbody>`;
}

function renderInterviews() {
  const ids = new Set(data.candidates.filter(c => selected.has(`cand:${c.id}`)).map(c => c.id));
  const share = interviewMetric === 'share';
  const items = (data.interviews || []).filter(i => ids.has(i.candidate) && (share ? i.audience_share != null : i.audience_viewers != null));

  /** @type {any[]} */
  const datasets = [];
  data.candidates.filter(c => ids.has(c.id)).forEach(c => {
    const pts = items.filter(i => i.candidate === c.id).map(i => ({
      x: Date.parse(i.date), y: share ? i.audience_share : i.audience_viewers,
      channel: i.channel, show: i.show, outlet: i.source.outlet, url: i.source.url, title: i.source.title,
    }));
    if (pts.length === 0) return;
    datasets.push({ label: c.name, data: pts, borderColor: c.color, backgroundColor: hexA(c.color, 0.75),
                    pointRadius: 6, pointHoverRadius: 8, pointBorderColor: '#FFFFFF', pointBorderWidth: 1 });
  });

  const n = items.length;
  $('interviewNote').textContent = n ? t('interview.count', { n }) : t('interview.none');

  const opts = /** @type {any} */ (lineOptions(share ? '%' : '', {
    legend: true,
    tickFormat: share ? (/** @type {number} */ v) => `${v}%` : compact,
    tooltipLabel: (/** @type {any} */ item) => ` ${item.dataset.label} : ${share ? fmt(item.parsed.y) + ' %' : fmt(item.parsed.y, 0) + ' ' + t('interview.tooltip')}`,
    tooltipAfter: (/** @type {any} */ item) => `   ${item.raw.channel}${item.raw.show ? ' — ' + item.raw.show : ''}`,
  }));
  opts.scales.x = { type: 'linear', grid: { display: false }, ticks: { color: MUTED, font: { size: 10 },
    callback: (/** @type {number} */ v) => v < 1e11 ? '' : shortDate(new Date(v).toISOString()) } };
  opts.plugins.tooltip.callbacks.afterTitle = undefined;
  if (charts.interview) charts.interview.destroy();
  charts.interview = new Chart(canvas('interviewChart'), { type: 'scatter', data: { datasets }, options: opts });

  renderInterviewSummary(ids);
}

/** @param {Set<string>} ids */
function renderInterviewSummary(ids) {
  const summary = data.interview_summary || {};
  const rows = data.candidates.filter(c => ids.has(c.id)).map(c => {
    const s = summary[c.id] || { count: 0, avg_viewers: null, avg_share: null };
    return `<tr class="border-b border-slate-100"><td class="px-2 py-1 font-semibold whitespace-nowrap"><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:${c.color}"></span>${esc(c.name)}</td>
      <td class="px-2 py-1 text-right">${s.count}</td><td class="px-2 py-1 text-right">${s.avg_viewers == null ? '—' : compact(s.avg_viewers)}</td>
      <td class="px-2 py-1 text-right">${s.avg_share == null ? '—' : fmt(s.avg_share) + ' %'}</td></tr>`;
  }).join('');
  $('interviewSummary').innerHTML = `<thead><tr class="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
      <th class="px-2 py-1 text-left">${t('interview.th.candidate')}</th><th class="px-2 py-1 text-right">${t('interview.th.count')}</th>
      <th class="px-2 py-1 text-right">${t('interview.th.avg')}</th><th class="px-2 py-1 text-right">${t('interview.th.share')}</th></tr></thead>
    <tbody>${rows || `<tr><td class="py-2 text-slate-400" colspan="4">${t('followers.noneChecked')}</td></tr>`}</tbody>`;
}

/**
 * Options communes des graphiques en lignes.
 * @param {string} unit
 * @param {{ legend: boolean, tickFormat?: (v: number) => string, tooltipLabel?: (item: any) => string, tooltipAfter?: (item: any) => string }} opts
 * @returns {any}
 */
function lineOptions(unit, { legend, tickFormat, tooltipLabel, tooltipAfter }) {
  const fmtTick = tickFormat || ((/** @type {number} */ v) => `${v}${unit}`);
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: legend,
        position: 'bottom',
        labels: { boxWidth: 12, boxHeight: 2, font: { size: 11, weight: '600' }, color: INK,
                  filter: (/** @type {any} */ item) => !String(item.text).startsWith('_') },
        onHover: (/** @type {any} */ _e, /** @type {any} */ item, /** @type {any} */ legend) => focusSeries(legend.chart, item.datasetIndex),
        onLeave: (/** @type {any} */ _e, /** @type {any} */ _item, /** @type {any} */ legend) => focusSeries(legend.chart, null),
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.78)', padding: 12, cornerRadius: 8, usePointStyle: true,
        filter: (/** @type {any} */ item) => !String(item.dataset.label).startsWith('_') && item.raw != null,
        itemSort: (/** @type {any} */ a, /** @type {any} */ b) => (b.parsed.y ?? 0) - (a.parsed.y ?? 0),
        callbacks: {
          label: tooltipLabel || ((/** @type {any} */ item) => ` ${item.dataset.label} : ${fmt(item.parsed.y)}${unit}`),
          afterBody: tooltipAfter ? (/** @type {any[]} */ items) => items.map(tooltipAfter) : undefined,
          afterTitle: (/** @type {any[]} */ items) => {
            const date = items[0]?.label;
            const ev = (data.events || []).filter(e => e.date === date);
            return ev.length ? ev.map(e => '📍 ' + e.title.slice(0, 90)).join('\n') : '';
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: MUTED, font: { size: 10 }, maxTicksLimit: 8 } },
      y: { grid: { color: GRID }, border: { display: false }, beginAtZero: true,
           ticks: { color: MUTED, font: { size: 10 }, callback: fmtTick } },
    },
  };
}

/**
 * Met en avant une série survolée dans la légende : les autres s'estompent (saturation réduite).
 * @param {any} chart
 * @param {number | null} index  null = toutes les séries à pleine intensité
 */
function focusSeries(chart, index) {
  chart.data.datasets.forEach((/** @type {any} */ ds, /** @type {number} */ i) => {
    if (!ds._base) {
      if (typeof ds.borderColor !== 'string' || !ds.borderColor.startsWith('#')) return;
      ds._base = ds.borderColor;
    }
    const on = index === null || i === index;
    ds.borderColor = on ? ds._base : hexA(ds._base, 0.2);
    ds.backgroundColor = on ? ds._base : hexA(ds._base, 0.2);
  });
  chart.update('none');
}

// Diverging bleu <-> rouge, milieu gris neutre
/** @param {number} t */
function toneColor(t) {
  /** @param {number} a @param {number} b @param {number} k */
  const lerp = (a, b, k) => Math.round(a + (b - a) * k);
  const mid = [240, 239, 236], neg = [227, 73, 72], pos = [42, 120, 214];
  const k = Math.min(1, Math.abs(t) / 2);
  const end = t < 0 ? neg : pos;
  return `rgb(${lerp(mid[0], end[0], k)}, ${lerp(mid[1], end[1], k)}, ${lerp(mid[2], end[2], k)})`;
}

function renderOutlets() {
  const table = $('outletTable');
  const matrix = data.media_by_outlet || {};
  const outlets = Object.keys(matrix);
  if (!outlets.length) {
    table.innerHTML = `<tr><td class="text-slate-400 py-2">${t('tone.none')}</td></tr>`;
    return;
  }
  const ids = data.projection.map(p => p.id).filter(id => outlets.some(o => matrix[o][id]));
  const leanOf = Object.fromEntries((data.sources.feeds || []).map(f => [f.outlet, f.lean]));
  table.innerHTML = `<thead><tr><th class="text-left pr-3 py-1 text-slate-500">Média</th>${ids.map(id =>
    `<th class="px-1 py-1 text-slate-600 font-semibold whitespace-nowrap">${esc(candById[id].name.split(' ').slice(-1)[0])}</th>`).join('')}</tr></thead>
    <tbody>${outlets.map(o => `<tr><td class="pr-3 py-0.5 font-semibold text-slate-700 whitespace-nowrap">${esc(o)}${leanOf[o] ? ` <span class="font-normal text-[10px] text-slate-400">${esc(t('lean.' + leanOf[o]))}</span>` : ''}</td>${ids.map(id => {
      const v = matrix[o][id];
      if (!v) return '<td class="px-1 py-0.5"><div class="h-8 w-16 rounded bg-white border border-slate-100"></div></td>';
      const dark = Math.abs(v.tone) > 1.1;
      return `<td class="px-1 py-0.5"><div class="h-8 w-16 rounded flex items-center justify-center ${dark ? 'text-white' : 'text-slate-800'}"
        style="background:${toneColor(v.tone)}" title="${esc(t('tone.cell', { outlet: o, name: candById[id].name, tone: signed(v.tone, 2), n: v.n, unit: t('unit.article', { n: v.n }) }))}">${signed(v.tone, 1)} <span class="opacity-70 ml-0.5">(${v.n})</span></div></td>`;
    }).join('')}</tr>`).join('')}</tbody>`;
}

function renderEvents() {
  const container = $('eventsContainer');
  const events = data.events || [];
  if (!events.length) {
    container.innerHTML = `<p class="text-xs text-slate-400">${t('events.none')}</p>`;
    return;
  }
  container.innerHTML = events.slice(0, 16).map(ev => `
    <details class="group p-4 rounded-2xl bg-slate-50 border border-slate-200 transition hover:border-indigo-300">
      <summary class="cursor-pointer outline-none">
        <div class="flex items-center justify-between mb-2 gap-2">
          <span class="text-xs font-extrabold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-lg">${esc(shortDate(ev.date))}</span>
          <span class="text-[10px] font-bold uppercase tracking-wider ${ev.origin === 'presse' ? 'text-amber-800 bg-amber-50' : 'text-slate-600 bg-slate-200'} px-2 py-0.5 rounded">${ev.origin === 'presse' ? t('events.presse') : t('events.wiki')}</span>
        </div>
        <h3 class="font-bold text-slate-900 text-sm leading-snug">${esc(ev.title)}</h3>
      </summary>
      <div class="mt-3 pt-3 border-t border-slate-200 space-y-2">
        ${ev.description ? `<p class="text-[11px] text-slate-600 whitespace-pre-line leading-relaxed">${esc(ev.description)}</p>` : ''}
        ${ev.candidates?.length ? `<p class="text-[11px] text-slate-500">${t('events.concerns', { list: ev.candidates.map(id => esc(candById[id]?.name || id)).join(', ') })}</p>` : ''}
        <ul class="text-[11px] space-y-1">${(ev.sources || []).map(s =>
          `<li><a class="text-indigo-700 underline" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.outlet)}</a>${s.title && ev.origin === 'presse' ? ' — ' + esc(s.title) : ''}</li>`).join('') || `<li class="text-slate-400">${t('events.nosource')}</li>`}</ul>
      </div>
    </details>`).join('') + `<p class="col-span-full text-[11px] text-slate-400">${t('events.language')}</p>`;
}

init();
