/**
 * Schéma de live_data.json (produit par `python -m pipeline`).
 * @typedef {{ id: string, name: string, wiki: string, party: string, badge: string, color: string, main: boolean, aliases: string[] }} Candidate
 * @typedef {{ articles_7d: number, share_7d: number, tone_7d: number | null, tone_baseline: number | null, adjustment: number, status: 'ok' | 'calibrage' | 'trop_peu_articles' }} MediaSignal
 * @typedef {{ id: string, poll_avg: number, poll_lo: number, poll_hi: number, n_polls: number, change_7d: number | null, media: MediaSignal, projected: number, projected_lo: number, projected_hi: number }} Projection
 * @typedef {{ mean: number, lo: number, hi: number, n_polls: number }} PollAverage
 * @typedef {{ date: string, polls: Record<string, PollAverage> }} HistoryEntry
 * @typedef {{ pollster: string, end_date: string, sample: number | null, url: string | null, scores: Record<string, number>, scenarios: number }} Poll
 * @typedef {{ date: string, candidates: Record<string, { articles: number, tone: number }> }} MediaDay
 * @typedef {{ outlet: string, title: string, url: string }} SourceLink
 * @typedef {{ date: string, title: string, description: string, category: string, candidates: string[], origin: 'presse' | 'wikipedia', sources: SourceLink[] }} CampaignEvent
 * Sous-ensemble des objets Chart.js utilisés dans les callbacks d'infobulle.
 * @typedef {{ dataset: { label: string }, parsed: { y: number }, raw: any, label: string }} TooltipItem
 * @typedef {{ text: string }} LegendItem
 * @typedef {{ outlet: string, ok: boolean, lean?: string, items?: number, error?: string }} FeedStatus
 * @typedef {{ polls?: string, polls_fetched?: string, feeds: FeedStatus[], articles_total: number, articles_analysed: number, media_since: string | null }} Sources
 * @typedef {{ last_updated: string, today: string, candidates: Candidate[], projection: Projection[], history: HistoryEntry[], polls: Poll[], media_daily: MediaDay[], media_by_outlet: Record<string, Record<string, { tone: number, n: number }>>, events: CampaignEvent[], sources: Sources, parameters?: Record<string, number> }} LiveData
 */

/** @type {LiveData} */
let data = /** @type {LiveData} */ ({});
/** @type {Record<string, Candidate>} */
let candById = {};
/** @type {Chart | null} */
let pollChart = null;
/** @type {Chart | null} */
let mediaChart = null;

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
const fmt = (v, digits = 1) => v == null ? '—' : v.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
/** @param {number | null | undefined} v @param {number} [digits] */
const signed = (v, digits = 1) => v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + fmt(Math.abs(v), digits);
/** @param {string | null | undefined} u */
const safeUrl = (u) => /^https?:\/\//.test(u || '') ? u : '#';

/** @param {Candidate} c */
function badge(c) {
  return `<span class="inline-block w-2.5 h-2.5 rounded-full mr-1.5 align-middle" style="background:${c.color}" aria-hidden="true"></span>`;
}

async function init() {
  try {
    const res = await fetch('live_data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    $('lastUpdated').textContent = `Données indisponibles (${e instanceof Error ? e.message : e})`;
    return;
  }
  data.candidates.forEach(c => { candById[c.id] = c; });

  const src = data.sources || {};
  $('lastUpdated').textContent = `Mis à jour : ${data.last_updated}`;
  const okFeeds = (src.feeds || []).filter(f => f.ok).length;
  $('sourceSummary').textContent =
    `${data.polls.length} sondages • ${okFeeds}/${(src.feeds || []).length} flux presse • ${src.articles_analysed}/${src.articles_total} articles analysés`;
  if (src.polls) /** @type {HTMLAnchorElement} */ ($('pollSourceLink')).href = src.polls;
  if (data.parameters) {
    $('paramBeta').textContent = fmt(data.parameters.MEDIA_BETA);
    $('paramCap').textContent = fmt(data.parameters.MEDIA_CAP, 0);
  }

  const select = /** @type {HTMLSelectElement} */ ($('candidateSelect'));
  const shown = data.projection.map(p => candById[p.id]);
  select.innerHTML = '<option value="MAIN">Principaux candidats</option>' +
    shown.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.badge)})</option>`).join('');
  select.addEventListener('change', () => renderCharts(select.value));

  renderProjection();
  renderCharts('MAIN');
  renderOutlets();
  renderEvents();
}

function renderProjection() {
  const statuses = new Set(data.projection.map(p => p.media.status));
  const since = data.sources?.media_since;
  $('mediaStatus').textContent = statuses.has('calibrage')
    ? `Ajustement média en calibrage : collecte de presse depuis le ${since || '—'}, 14 jours nécessaires.`
    : 'Ajustement média actif (hypothèse non calibrée, voir méthodologie).';

  $('projectionBody').innerHTML = data.projection.map(p => {
    const c = candById[p.id];
    const m = p.media;
    const ch = p.change_7d;
    const chCls = ch != null && ch > 0.2 ? 'text-emerald-700' : ch != null && ch < -0.2 ? 'text-rose-700' : 'text-slate-500';
    return `<tr class="border-b border-slate-100 hover:bg-slate-50">
      <td class="py-2 pr-3 font-semibold text-slate-900 whitespace-nowrap">${badge(c)}${esc(c.name)} <span class="text-[11px] font-medium text-slate-400">${esc(c.badge)}</span></td>
      <td class="py-2 px-3 text-right">${fmt(p.poll_avg)} %</td>
      <td class="py-2 px-3 text-right text-slate-500">${fmt(p.poll_lo)} – ${fmt(p.poll_hi)}${p.n_polls < 5 ? ` <span class="block text-[10px] text-amber-700">testé dans ${p.n_polls} sondage(s) seulement</span>` : ''}</td>
      <td class="py-2 px-3 text-right ${chCls}">${signed(ch)}</td>
      <td class="py-2 px-3 text-right">${m.articles_7d}</td>
      <td class="py-2 px-3 text-right">${m.articles_7d ? fmt(m.share_7d * 100, 0) + ' %' : '—'}</td>
      <td class="py-2 px-3 text-right">${signed(m.tone_7d, 2)}</td>
      <td class="py-2 px-3 text-right text-slate-500">${m.status === 'ok' ? signed(m.adjustment) : '0 <span class="text-[10px]">(' + (m.status === 'calibrage' ? 'calibrage' : 'peu d\'articles') + ')</span>'}</td>
      <td class="py-2 pl-3 text-right font-extrabold text-slate-900">${fmt(p.projected)} %</td>
    </tr>`;
  }).join('');
}

/** @param {string} sel */
function selectedIds(sel) {
  if (sel !== 'MAIN') return [sel];
  return data.projection.map(p => p.id).filter(id => candById[id].main);
}

/**
 * @param {string} unit
 * @param {{ legend: boolean }} opts
 * @returns {any} options Chart.js
 */
function chartOptions(unit, { legend }) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: legend,
        position: 'bottom',
        labels: { boxWidth: 12, boxHeight: 2, font: { size: 11, weight: '600' }, color: INK,
                  filter: (/** @type {LegendItem} */ item) => !item.text.startsWith('_') },
      },
      tooltip: {
        backgroundColor: '#0F172A', padding: 12, cornerRadius: 8, usePointStyle: true,
        filter: (/** @type {TooltipItem} */ item) => !item.dataset.label.startsWith('_') && item.raw != null,
        itemSort: (/** @type {TooltipItem} */ a, /** @type {TooltipItem} */ b) => (b.parsed.y ?? 0) - (a.parsed.y ?? 0),
        callbacks: {
          label: (/** @type {TooltipItem} */ item) => ` ${item.dataset.label} : ${fmt(item.parsed.y)}${unit}`,
          afterTitle: (/** @type {TooltipItem[]} */ items) => {
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
           ticks: { color: MUTED, font: { size: 10 }, callback: (/** @type {number} */ v) => `${v}${unit}` } },
    },
  };
}

/** @param {string} hex @param {number} a */
function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

/** @param {string} sel */
function renderCharts(sel) {
  const ids = selectedIds(sel);
  const single = ids.length === 1;
  const hist = data.history;
  const dates = hist.map(h => h.date);

  /** @type {any[]} datasets Chart.js */
  const datasets = [];
  ids.forEach(id => {
    const c = candById[id];
    if (single) {
      // Intervalle à 95 % : bande entre hi et lo (lavis ~10 %)
      datasets.push({ label: '_hi', data: hist.map(h => h.polls[id]?.hi ?? null), borderWidth: 0, pointRadius: 0, fill: false });
      datasets.push({ label: '_lo', data: hist.map(h => h.polls[id]?.lo ?? null), borderWidth: 0, pointRadius: 0,
                      fill: '-1', backgroundColor: hexA(c.color, 0.12) });
    }
    datasets.push({
      label: c.name, data: hist.map(h => h.polls[id]?.mean ?? null),
      borderColor: c.color, backgroundColor: c.color, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5,
      tension: 0.25, spanGaps: true, borderCapStyle: 'round', borderJoinStyle: 'round',
    });
    if (single) {
      const pts = data.polls.filter(p => p.scores[c.wiki] != null);
      datasets.push({
        type: 'scatter', label: 'Sondage individuel',
        data: pts.map(p => ({ x: p.end_date, y: p.scores[c.wiki], pollster: p.pollster })),
        backgroundColor: hexA(c.color, 0.35), borderColor: '#FFFFFF', borderWidth: 1, pointRadius: 4,
      });
    }
  });

  if (pollChart) pollChart.destroy();
  const pollOpts = chartOptions('%', { legend: true });
  pollOpts.scales.x.type = 'category';
  pollOpts.plugins.tooltip.callbacks.label = (/** @type {TooltipItem} */ item) => item.raw?.pollster
    ? ` ${item.raw.pollster} : ${fmt(item.parsed.y)} %`
    : ` ${item.dataset.label} : ${fmt(item.parsed.y)} %`;
  pollChart = new Chart(/** @type {HTMLCanvasElement} */ ($('pollChart')), { type: 'line', data: { labels: dates, datasets }, options: pollOpts });

  // Couverture médiatique : articles par jour
  const md = data.media_daily || [];
  const mDates = md.map(d => d.date);
  const mSets = ids.map(id => {
    const c = candById[id];
    return {
      label: c.name, data: md.map(d => d.candidates[id]?.articles ?? 0),
      borderColor: c.color, backgroundColor: c.color, borderWidth: 2, pointRadius: md.length < 10 ? 4 : 0,
      pointHoverRadius: 5, tension: 0.25,
    };
  });
  $('mediaChartNote').textContent = md.length
    ? `Articles qui traitent du candidat, selon l'analyse de Claude. Collecte depuis le ${md[0].date}.`
    : "Aucun article analysé pour l'instant : la courbe apparaîtra après la première analyse quotidienne.";
  if (mediaChart) mediaChart.destroy();
  const mOpts = chartOptions('', { legend: true });
  mOpts.plugins.tooltip.callbacks.label = (/** @type {TooltipItem} */ item) => ` ${item.dataset.label} : ${item.parsed.y} article(s)`;
  mediaChart = new Chart(/** @type {HTMLCanvasElement} */ ($('mediaChart')), { type: 'line', data: { labels: mDates, datasets: mSets }, options: mOpts });
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
    table.innerHTML = '<tr><td class="text-slate-400 py-2">Pas encore d\'articles analysés.</td></tr>';
    return;
  }
  const ids = data.projection.map(p => p.id).filter(id => outlets.some(o => matrix[o][id]));
  const leanOf = Object.fromEntries((data.sources.feeds || []).map(f => [f.outlet, f.lean]));
  table.innerHTML = `<thead><tr><th class="text-left pr-3 py-1 text-slate-500">Média</th>${ids.map(id =>
    `<th class="px-1 py-1 text-slate-600 font-semibold whitespace-nowrap">${esc(candById[id].name.split(' ').slice(-1)[0])}</th>`).join('')}</tr></thead>
    <tbody>${outlets.map(o => `<tr><td class="pr-3 py-0.5 font-semibold text-slate-700 whitespace-nowrap">${esc(o)}${leanOf[o] ? ` <span class="font-normal text-[10px] text-slate-400">${esc(leanOf[o])}</span>` : ''}</td>${ids.map(id => {
      const v = matrix[o][id];
      if (!v) return '<td class="px-1 py-0.5"><div class="h-8 w-16 rounded bg-white border border-slate-100"></div></td>';
      const dark = Math.abs(v.tone) > 1.1;
      return `<td class="px-1 py-0.5"><div class="h-8 w-16 rounded flex items-center justify-center ${dark ? 'text-white' : 'text-slate-800'}"
        style="background:${toneColor(v.tone)}" title="${esc(o)} — ${esc(candById[id].name)} : ${signed(v.tone, 2)} sur ${v.n} article(s)">${signed(v.tone, 1)} <span class="opacity-70 ml-0.5">(${v.n})</span></div></td>`;
    }).join('')}</tr>`).join('')}</tbody>`;
}

function renderEvents() {
  const container = $('eventsContainer');
  const events = data.events || [];
  if (!events.length) {
    container.innerHTML = '<p class="text-xs text-slate-400">Aucun événement pour l\'instant.</p>';
    return;
  }
  container.innerHTML = events.slice(0, 16).map(ev => `
    <details class="group p-4 rounded-2xl bg-slate-50 border border-slate-200 transition hover:border-indigo-300">
      <summary class="cursor-pointer outline-none">
        <div class="flex items-center justify-between mb-2 gap-2">
          <span class="text-xs font-extrabold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-lg">${esc(ev.date)}</span>
          <span class="text-[10px] font-bold uppercase tracking-wider ${ev.origin === 'presse' ? 'text-amber-800 bg-amber-50' : 'text-slate-600 bg-slate-200'} px-2 py-0.5 rounded">${ev.origin === 'presse' ? 'Presse' : 'Wikipédia'}</span>
        </div>
        <h3 class="font-bold text-slate-900 text-sm leading-snug">${esc(ev.title)}</h3>
      </summary>
      <div class="mt-3 pt-3 border-t border-slate-200 space-y-2">
        ${ev.description ? `<p class="text-[11px] text-slate-600 whitespace-pre-line leading-relaxed">${esc(ev.description)}</p>` : ''}
        ${ev.candidates?.length ? `<p class="text-[11px] text-slate-500">Concerne : ${ev.candidates.map(id => esc(candById[id]?.name || id)).join(', ')}</p>` : ''}
        <ul class="text-[11px] space-y-1">${(ev.sources || []).map(s =>
          `<li><a class="text-indigo-700 underline" href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.outlet)}</a>${s.title && ev.origin === 'presse' ? ' — ' + esc(s.title) : ''}</li>`).join('') || '<li class="text-slate-400">Pas de lien source</li>'}</ul>
      </div>
    </details>`).join('');
}

init();
