(function () {
    function formatEuro(number) {
        if (isNaN(number)) return '0,00 €';
        const isNeg = number < 0;
        const abs = Math.abs(Number(number));
        const parts = abs.toFixed(2).split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        return (isNeg ? '-' : '') + parts.join(',') + ' €';
    }

    function getChartPalette() {
        const dark = document.body.classList.contains('dark-theme');
        return {
            text: dark ? '#cbd5e1' : '#475569',
            grid: dark ? 'rgba(148, 163, 184, 0.14)' : '#f1f5f9',
            investito: dark ? '#94a3b8' : '#64748b',
        };
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.fmt-currency').forEach(function (el) {
            let raw = el.getAttribute('data-val');
            if (raw) raw = raw.replace(',', '.');
            const num = parseFloat(raw);
            if (!isNaN(num)) {
                el.textContent = formatEuro(num);
            }
        });

        const chartDataEl = document.getElementById('pac-chart-data');
        const allocDataEl = document.getElementById('pac-alloc-data');
        const rawData = chartDataEl ? JSON.parse(chartDataEl.textContent) : [];
        const allocData = allocDataEl ? JSON.parse(allocDataEl.textContent) : [];

        const labels = rawData.map((d) => d.date);
        const valore = rawData.map((d) => d.valore);
        const valoreLordo = rawData.map((d) => d.valore_lordo);
        const investito = rawData.map((d) => d.investito);
        const picValore = rawData.map((d) => d.pic_valore);
        const drawdown = rawData.map((d) => d.drawdown);

        const toggleLordo = document.getElementById('toggle-lordo');
        const togglePic = document.getElementById('toggle-pic');
        let palette = getChartPalette();

        // 1. Main Portfolio Chart
        let pacChart = null;
        const pacCanvas = document.getElementById('pacChart');
        if (pacCanvas && typeof Chart !== 'undefined') {
            pacChart = new Chart(pacCanvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'PAC Valore Netto (Exit)',
                            data: valore,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.12)',
                            fill: true,
                            tension: 0.25,
                            borderWidth: 2.4,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            hitRadius: 10,
                        },
                        {
                            label: 'Capitale Versato',
                            data: investito,
                            borderColor: palette.investito,
                            borderDash: [5, 5],
                            tension: 0.1,
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            hitRadius: 10,
                        },
                        {
                            label: 'PIC (Lump Sum Netto)',
                            data: picValore,
                            borderColor: '#6366f1',
                            borderWidth: 2,
                            borderDash: [3, 3],
                            tension: 0.25,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            hitRadius: 10,
                            hidden: !(togglePic && togglePic.checked),
                        },
                        {
                            label: 'PAC Valore Lordo',
                            data: valoreLordo,
                            borderColor: '#f59e0b',
                            borderWidth: 1.8,
                            tension: 0.25,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            hitRadius: 10,
                            hidden: !(toggleLordo && toggleLordo.checked),
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    const lbl = ctx.dataset.label ? ctx.dataset.label + ': ' : '';
                                    return ctx.parsed.y !== null ? lbl + formatEuro(ctx.parsed.y) : lbl;
                                },
                            },
                        },
                        legend: {
                            labels: {
                                usePointStyle: true,
                                boxWidth: 10,
                                color: palette.text,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { maxTicksLimit: 8, maxRotation: 0, color: palette.text },
                        },
                        y: {
                            grid: { color: palette.grid },
                            ticks: {
                                color: palette.text,
                                callback: (v) => (Math.abs(v) >= 1000 ? '€' + (v / 1000).toFixed(0) + 'k' : '€' + v),
                            },
                        },
                    },
                },
            });

            if (toggleLordo) {
                toggleLordo.addEventListener('change', function () {
                    pacChart.setDatasetVisibility(3, toggleLordo.checked);
                    pacChart.update();
                });
            }
            if (togglePic) {
                togglePic.addEventListener('change', function () {
                    pacChart.setDatasetVisibility(2, togglePic.checked);
                    pacChart.update();
                });
            }
        }

        // 2. Drawdown Chart
        let ddChart = null;
        const ddCanvas = document.getElementById('drawdownChart');
        if (ddCanvas && typeof Chart !== 'undefined') {
            ddChart = new Chart(ddCanvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Drawdown (%)',
                            data: drawdown,
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.16)',
                            fill: true,
                            tension: 0.2,
                            borderWidth: 1.8,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            hitRadius: 8,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `Drawdown: ${Number(ctx.parsed.y).toFixed(2)}%`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { maxTicksLimit: 8, maxRotation: 0, color: palette.text },
                        },
                        y: {
                            max: 0,
                            grid: { color: palette.grid },
                            ticks: {
                                color: palette.text,
                                callback: (v) => v.toFixed(0) + '%',
                            },
                        },
                    },
                },
            });
        }

        // 3. Allocation Doughnut Chart
        let allocChart = null;
        const allocCanvas = document.getElementById('allocationChart');
        if (allocCanvas && allocData.length > 1 && typeof Chart !== 'undefined') {
            const colors = ['#10b981', '#6366f1', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6'];
            allocChart = new Chart(allocCanvas.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: allocData.map((a) => a.ticker),
                    datasets: [
                        {
                            data: allocData.map((a) => a.valore_netto),
                            backgroundColor: allocData.map((_, i) => colors[i % colors.length]),
                            borderWidth: 2,
                            borderColor: 'transparent',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: palette.text, usePointStyle: true, boxWidth: 10 },
                        },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    const item = allocData[ctx.dataIndex];
                                    return `${item.ticker}: ${formatEuro(item.valore_netto)} (${item.peso_pct}%)`;
                                },
                            },
                        },
                    },
                },
            });
        }

        // Sync Chart colors on theme switch
        window.addEventListener('pacThemeChange', function () {
            const pal = getChartPalette();
            if (pacChart) {
                pacChart.data.datasets[1].borderColor = pal.investito;
                pacChart.options.plugins.legend.labels.color = pal.text;
                pacChart.options.scales.x.ticks.color = pal.text;
                pacChart.options.scales.y.ticks.color = pal.text;
                pacChart.options.scales.y.grid.color = pal.grid;
                pacChart.update();
            }
            if (ddChart) {
                ddChart.options.scales.x.ticks.color = pal.text;
                ddChart.options.scales.y.ticks.color = pal.text;
                ddChart.options.scales.y.grid.color = pal.grid;
                ddChart.update();
            }
            if (allocChart) {
                allocChart.options.plugins.legend.labels.color = pal.text;
                allocChart.update();
            }
        });

        // CSV Export
        const csvBtn = document.getElementById('btn-export-csv');
        if (csvBtn && rawData.length > 0) {
            csvBtn.addEventListener('click', function () {
                const header = 'Data,Capitale_Versato_EUR,Valore_Netto_EUR,Valore_Lordo_EUR,PIC_Netto_EUR,Drawdown_Pct\n';
                const rows = rawData
                    .map((r) => `${r.date},${r.investito},${r.valore},${r.valore_lordo},${r.pic_valore},${r.drawdown}`)
                    .join('\n');
                const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'simulazione_pac_etf.csv';
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(url);
            });
        }

        // Print / PDF
        const printBtn = document.getElementById('btn-print-pdf');
        if (printBtn) {
            printBtn.addEventListener('click', function () {
                window.print();
            });
        }
    });
})();
