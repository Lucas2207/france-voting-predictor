const candidateConfig = {
  'Marine Le Pen (RN)': { color: '#0F172A', party: 'Rassemblement National', badge: 'RN', team: 'Bardella, Maréchal, Chenu' },
  'Jean-Luc Mélenchon (LFI)': { color: '#E11D48', party: 'La France Insoumise', badge: 'LFI', team: 'Guetté, Bompard, Hassan, Caron, Guiraud' },
  'Édouard Philippe (Horizons)': { color: '#2563EB', party: 'Horizons', badge: 'HORIZONS', team: 'Le Gendre, Naegelen' },
  'Gabriel Attal (Renaissance)': { color: '#0284C7', party: 'Renaissance', badge: 'RENAISSANCE', team: 'Borne, Darmanin, Séjourné' },
  'Raphaël Glucksmann (PP/PS)': { color: '#EC4899', party: 'Place Publique / PS', badge: 'PP-PS', team: 'Faure, Delga' },
  'François Hollande (PS)': { color: '#F43F5E', party: 'Parti Socialiste', badge: 'PS', team: 'Vallaud, Mayer-Rossignol' },
  'Bruno Retailleau (LR)': { color: '#1E3A8A', party: 'Les Républicains', badge: 'LR', team: 'Wauquiez, Pécresse' },
  'Dominique de Villepin (DVD)': { color: '#475569', party: 'Divers Droite', badge: 'DVD', team: 'Gaullistes indépendants' },
  'Éric Zemmour (Reconquête)': { color: '#7C3AED', party: 'Reconquête', badge: 'RECONQUÊTE', team: 'Knafo, Meunier' },
  'David Lisnard (Nouvelle Énergie)': { color: '#0D9488', party: 'Nouvelle Énergie', badge: 'NE', team: 'Collectifs d’élus locaux' }
};

let globalData = null;
let chartVoting = null;
let chartSocial = null;

async function renderDashboard() {
  try {
    const response = await fetch('live_data.json');
    if (!response.ok) throw new Error(`Erreur HTTP : ${response.status}`);
    globalData = await response.json();

    document.getElementById('lastUpdated').innerText = `Mis à jour : ${globalData.last_updated || 'Aujourd\'hui'}`;
    document.getElementById('calculatorTitle').innerText = `📊 Calculateur d'évolution (Du ${globalData.start_date || '01 Oct'} au ${globalData.end_date || 'Aujourd\'hui'})`;

    const select = document.getElementById('candidateSelect');
    select.innerHTML = '<option value="ALL">Tous les candidats (Vue d\'ensemble)</option>';
    Object.keys(candidateConfig).forEach(cand => {
      const cfg = candidateConfig[cand];
      select.innerHTML += `<option value="${cand}">[${cfg.badge}] ${cand}</option>`;
    });

    renderEvents();
    updateCharts('ALL');
  } catch (error) {
    console.error('Erreur :', error);
  }
}

function renderEvents() {
  const container = document.getElementById('eventsContainer');
  if (!globalData.events) return;

  container.innerHTML = Object.entries(globalData.events).map(([date, ev]) => `
    <details class="group p-4 rounded-2xl bg-slate-50 border border-slate-200 cursor-pointer transition hover:border-indigo-300 shadow-sm flex flex-col justify-between">
      <summary class="list-none outline-none">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-extrabold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-lg">${date}</span>
          <span class="text-xs text-indigo-600 font-bold group-open:rotate-180 transition transform">▼ Détails</span>
        </div>
        <h4 class="font-extrabold text-slate-900 text-sm leading-snug">${ev.title}</h4>
      </summary>
      <div class="mt-3 pt-3 border-t border-slate-200 space-y-1">
        <p class="text-[11px] text-slate-600 whitespace-pre-line leading-relaxed">${ev.desc}</p>
      </div>
    </details>
  `).join('');
}

function updateCharts(selectedCandidate) {
  const history = globalData.history || [];
  if (history.length === 0) return;

  const dates = history.map(h => h.date);
  const candidates = selectedCandidate === 'ALL' ? Object.keys(candidateConfig) : [selectedCandidate];

  const firstDay = history[0];
  const lastDay = history[history.length - 1];
  const calcContainer = document.getElementById('calculatorResults');

  calcContainer.innerHTML = candidates.map(cand => {
    const cfg = candidateConfig[cand] || { party: '', badge: '' };
    const vStart = firstDay.voting_intentions[cand] || 0;
    const vEnd = lastDay.voting_intentions[cand] || 0;
    const vDiff = (vEnd - vStart).toFixed(1);

    const fStart = firstDay.social_media_followers_m[cand] || 0;
    const fEnd = lastDay.social_media_followers_m[cand] || 0;
    const fDiff = (fEnd - fStart).toFixed(2);

    const vColor = vDiff >= 0 ? 'text-emerald-600' : 'text-rose-600';
    const fColor = fDiff >= 0 ? 'text-emerald-600' : 'text-rose-600';

    return `
      <div class="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex-1 min-w-[240px] shadow-sm flex items-center justify-between">
        <div>
          <div class="flex items-center gap-1.5 mb-1">
            <span class="px-2 py-0.5 rounded text-[10px] font-extrabold text-white" style="background-color: ${cfg.color}">${cfg.badge}</span>
            <span class="text-[10px] text-slate-400 font-semibold">${cfg.party}</span>
          </div>
          <div class="font-extrabold text-slate-900 text-xs">${cand}</div>
          <div class="text-[11px] text-slate-600 mt-1">Intentions : <span class="font-extrabold ${vColor}">${vDiff > 0 ? '+' : ''}${vDiff}%</span></div>
          <div class="text-[11px] text-slate-600">Followers : <span class="font-extrabold ${fColor}">${fDiff > 0 ? '+' : ''}${fDiff}M</span></div>
        </div>
      </div>
    `;
  }).join('');

  const votingDatasets = candidates.map(cand => ({
    label: cand,
    data: history.map(h => h.voting_intentions[cand] || null),
    borderColor: candidateConfig[cand].color,
    backgroundColor: candidateConfig[cand].color,
    borderWidth: selectedCandidate === 'ALL' ? 2.5 : 4,
    tension: 0.35,
    pointRadius: selectedCandidate === 'ALL' ? 0 : 3,
    pointHoverRadius: 6
  }));

  const socialDatasets = candidates.map(cand => ({
    label: cand,
    data: history.map(h => h.social_media_followers_m[cand] || null),
    borderColor: candidateConfig[cand].color,
    backgroundColor: candidateConfig[cand].color,
    borderWidth: selectedCandidate === 'ALL' ? 2.5 : 4,
    tension: 0.35,
    pointRadius: selectedCandidate === 'ALL' ? 0 : 3,
    pointHoverRadius: 6
  }));

  const getOptions = (unit, isSocial = false) => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: { boxWidth: 14, font: { size: 11, weight: 'bold' }, color: '#334155' }
      },
      tooltip: {
        backgroundColor: '#0F172A',
        titleFont: { size: 12, weight: 'bold' },
        bodyFont: { size: 11 },
        padding: 14,
        cornerRadius: 10,
        usePointStyle: true,
        itemSort: (a, b) => b.raw - a.raw,
        callbacks: {
          afterBody: (items) => {
            return items.map(item => {
              const cfg = candidateConfig[item.dataset.label];
              return cfg ? `   ↳ Équipe / Figures : ${cfg.team}` : '';
            });
          },
          afterTitle: (items) => {
            const date = items[0].label;
            return globalData.events && globalData.events[date] ? `📍 Crise : ${globalData.events[date].title}` : '';
          }
        }
      }
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 10 }, maxTicksLimit: 10 } },
      y: { 
        grid: { color: '#F1F5F9' }, 
        suggestedMin: isSocial ? 0 : undefined,
        ticks: { color: '#64748B', font: { size: 10 }, callback: v => `${v}${unit}` } 
      }
    }
  });

  if (chartVoting) chartVoting.destroy();
  if (chartSocial) chartSocial.destroy();

  chartVoting = new Chart(document.getElementById('votingChart').getContext('2d'), {
    type: 'line',
    data: { labels: dates, datasets: votingDatasets },
    options: getOptions('%', false)
  });

  chartSocial = new Chart(document.getElementById('socialChart').getContext('2d'), {
    type: 'line',
    data: { labels: dates, datasets: socialDatasets },
    options: getOptions('M', true)
  });
}

function filterCandidates() {
  const selected = document.getElementById('candidateSelect').value;
  updateCharts(selected);
}

renderDashboard();
