// Universal Candidate Matrix across all 6 Societal Themes
const candidates = [
    { 
        id: 'rn', name: 'Marine Le Pen (RN)', color: '#f43f5e', baseVote: 32.0, 
        ownership: { sec_imm: 0.95, econ_tax: 0.35, purch_inc: 0.85, health_care: 0.50, pen_soc: 0.65, cohes_dem: 0.20 } 
    },
    { 
        id: 'lfi', name: 'Jean-Luc Mélenchon (LFI)', color: '#10b981', baseVote: 17.5, 
        ownership: { sec_imm: 0.10, econ_tax: 0.20, purch_inc: 0.80, health_care: 0.85, pen_soc: 0.95, cohes_dem: 0.85 } 
    },
    { 
        id: 'philippe', name: 'Édouard Philippe (Horizons)', color: '#3b82f6', baseVote: 16.0, 
        ownership: { sec_imm: 0.50, econ_tax: 0.85, purch_inc: 0.40, health_care: 0.45, pen_soc: 0.30, cohes_dem: 0.50 } 
    },
    { 
        id: 'glucksmann', name: 'Raphaël Glucksmann (PS)', color: '#ec4899', baseVote: 12.0, 
        ownership: { sec_imm: 0.25, econ_tax: 0.45, purch_inc: 0.65, health_care: 0.80, pen_soc: 0.80, cohes_dem: 0.90 } 
    },
    { 
        id: 'lr', name: 'Bruno Retailleau (LR)', color: '#8b5cf6', baseVote: 6.5, 
        ownership: { sec_imm: 0.80, econ_tax: 0.70, purch_inc: 0.30, health_care: 0.40, pen_soc: 0.25, cohes_dem: 0.30 } 
    },
    { 
        id: 'lisnard', name: 'David Lisnard (NE)', color: '#a855f7', baseVote: 5.5, 
        ownership: { sec_imm: 0.70, econ_tax: 0.80, purch_inc: 0.35, health_care: 0.35, pen_soc: 0.20, cohes_dem: 0.40 } 
    },
    { 
        id: 'abs', name: 'Abstention / Undecided', color: '#64748b', baseVote: 10.5, 
        ownership: { sec_imm: 0.00, econ_tax: 0.00, purch_inc: 0.00, health_care: 0.00, pen_soc: 0.00, cohes_dem: 0.00 } 
    }
];

let chartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
    setupSliders();
    initChart();
    runSimulation();
    document.getElementById("run-simulation").addEventListener("click", runSimulation);
});

function setupSliders() {
    ['sec', 'econ', 'soc', 'imm'].forEach(key => {
        const slider = document.getElementById(`frame-${key}`);
        const label = document.getElementById(`val-${key}`);
        slider?.addEventListener('input', (e) => {
            if (label) label.innerText = `${e.target.value}%`;
        });
    });
}

function runSimulation() {
    // 1. Map 4 HTML Sliders to 6 Core Societal Vector Dimensions
    const s_sec = parseFloat(document.getElementById('frame-sec').value) || 0;
    const s_econ = parseFloat(document.getElementById('frame-econ').value) || 0;
    const s_soc = parseFloat(document.getElementById('frame-soc').value) || 0;
    const s_imm = parseFloat(document.getElementById('frame-imm').value) || 0;

    const grandTotal = s_sec + s_econ + s_soc + s_imm || 1;

    // Normalizing media weights into 6 thematic dimensions
    const F_e = {
        sec_imm: ((s_sec * 0.6) + (s_imm * 0.4)) / grandTotal,
        econ_tax: (s_econ * 0.5) / grandTotal,
        purch_inc: ((s_econ * 0.5) + (s_soc * 0.3)) / grandTotal,
        health_care: (s_soc * 0.3) / grandTotal,
        pen_soc: (s_soc * 0.4) / grandTotal,
        cohes_dem: ((s_sec * 0.1) + (s_imm * 0.1) + (s_soc * 0.3)) / grandTotal
    };

    // 2. Compute Non-Linear Impulse for Each Candidate
    const k = 2.0; // Decreasing share power factor
    const rawImpulses = {};

    candidates.forEach(c => {
        if (c.id === 'abs') {
            // Abstention increases during severe security/immigration polarization
            rawImpulses[c.id] = (F_e.sec_imm * 0.4);
        } else {
            // Calculate weighted sum across ALL 6 society themes
            let score = (F_e.sec_imm * c.ownership.sec_imm) +
                        (F_e.econ_tax * c.ownership.econ_tax) +
                        (F_e.purch_inc * c.ownership.purch_inc) +
                        (F_e.health_care * c.ownership.health_care) +
                        (F_e.pen_soc * c.ownership.pen_soc) +
                        (F_e.cohes_dem * c.ownership.cohes_dem);

            rawImpulses[c.id] = Math.pow(score, k); // Power rule for decreasing part dispatch
        }
    });

    // 3. Dispatch Voting Intention Shifts
    const totalImpulse = Object.values(rawImpulses).reduce((a, b) => a + b, 0) || 1;
    const elasticityMultiplier = 4.5;

    const deltas = candidates.map(c => {
        const share = rawImpulses[c.id] / totalImpulse;
        const netShift = (share - (1 / candidates.length)) * elasticityMultiplier;
        return netShift;
    });

    // Normalize final vote share to 100%
    const adjustedVotes = candidates.map((c, i) => Math.max(0.5, c.baseVote + deltas[i]));
    const totalAdjusted = adjustedVotes.reduce((a, b) => a + b, 0);
    const finalPredictedVotes = adjustedVotes.map(v => (v / totalAdjusted) * 100);

    updateChart(finalPredictedVotes);
    renderTransferList(finalPredictedVotes);
}

function initChart() {
    const ctx = document.getElementById('pollsChart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: candidates.map(c => c.name),
            datasets: [
                {
                    label: 'Baseline Polls (%)',
                    data: candidates.map(c => c.baseVote),
                    backgroundColor: 'rgba(100, 116, 139, 0.4)',
                    borderColor: 'rgba(100, 116, 139, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Predicted Voting Intention (%)',
                    data: [],
                    backgroundColor: candidates.map(c => c.color),
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: {
                legend: { labels: { color: '#cbd5e1' } }
            }
        }
    });
}

function updateChart(predictedVotes) {
    chartInstance.data.datasets[1].data = predictedVotes.map(v => v.toFixed(1));
    chartInstance.update();
}

function renderTransferList(predictedVotes) {
    const listContainer = document.getElementById('transfer-list');
    listContainer.innerHTML = '';

    candidates.forEach((c, i) => {
        const diff = (predictedVotes[i] - c.baseVote).toFixed(1);
        const isPositive = diff >= 0;
        
        const card = document.createElement('div');
        card.className = `p-3 rounded-lg border bg-slate-900 ${isPositive ? 'border-emerald-500/30' : 'border-rose-500/30'}`;
        
        card.innerHTML = `
            <div class="text-xs text-slate-400 font-medium truncate">${c.name}</div>
            <div class="flex justify-between items-baseline mt-1">
                <span class="text-sm font-bold text-slate-100">${predictedVotes[i].toFixed(1)}%</span>
                <span class="text-xs font-semibold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}">
                    ${isPositive ? '+' : ''}${diff}%
                </span>
            </div>
        `;
        listContainer.appendChild(card);
    });
}
