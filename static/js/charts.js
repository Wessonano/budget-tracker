/**
 * Chart.js initialization for Budget Tracker dashboard.
 */

function initCategoryDonut(canvasId, categories) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Filter categories with actual spending
    const data = categories
        .filter(c => c.total_debit > 0)
        .sort((a, b) => b.total_debit - a.total_debit);

    if (data.length === 0) {
        canvas.parentElement.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">Aucune depense</p>';
        return;
    }

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.map(c => c.icon + ' ' + c.name),
            datasets: [{
                data: data.map(c => c.total_debit),
                backgroundColor: data.map(c => c.color),
                borderWidth: 0,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '55%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#e0e0e0',
                        padding: 12,
                        usePointStyle: true,
                        pointStyleWidth: 10,
                        font: { size: 12 },
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = ((ctx.raw / total) * 100).toFixed(1);
                            return ctx.label + ': ' + ctx.raw.toFixed(2) + ' \u20ac (' + pct + '%)';
                        }
                    }
                }
            }
        }
    });
}


function initBalanceLine(canvasId, dailyBalances) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (!dailyBalances || dailyBalances.length === 0) {
        canvas.parentElement.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">Pas de donnees</p>';
        return;
    }

    // Format dates for display (YYYY-MM-DD -> DD/MM)
    const labels = dailyBalances.map(d => {
        const parts = d.date.split('-');
        return parts[2] + '/' + parts[1];
    });

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Solde',
                data: dailyBalances.map(d => d.balance),
                borderColor: '#e94560',
                backgroundColor: 'rgba(233, 69, 96, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    ticks: { color: '#888', maxTicksLimit: 10 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    ticks: {
                        color: '#888',
                        callback: function(v) { return v.toFixed(0) + ' \u20ac'; }
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) { return 'Solde: ' + ctx.raw.toFixed(2) + ' \u20ac'; }
                    }
                }
            }
        }
    });
}
