/**
 * SLATE Dashboard Charts
 * Chart rendering using Chart.js with responsive design.
 */

class SlateCharts {
    constructor() {
        this.charts = new Map();
        this.colors = {
            primary: '#3498db',
            success: '#27ae60',
            danger: '#e74c3c',
            warning: '#f39c12',
            info: '#9b59b6',
            grid: 'rgba(255, 255, 255, 0.1)',
            text: 'rgba(255, 255, 255, 0.8)'
        };
    }

    // Common chart options for dark theme
    getCommonOptions() {
        return {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: this.colors.text,
                        font: { size: 12 }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: this.colors.grid },
                    ticks: { color: this.colors.text }
                },
                y: {
                    grid: { color: this.colors.grid },
                    ticks: { color: this.colors.text }
                }
            }
        };
    }

    // Create return distribution chart
    createReturnDistribution(strategies, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }

        const returns = strategies.map(s => s.total_return_pct * 100);

        // Create histogram bins
        const min = Math.min(...returns);
        const max = Math.max(...returns);
        const binCount = 20;
        const binSize = (max - min) / binCount;
        const bins = new Array(binCount).fill(0);
        const labels = [];

        for (let i = 0; i < binCount; i++) {
            const binStart = min + (i * binSize);
            const binEnd = binStart + binSize;
            labels.push(`${binStart.toFixed(1)}%`);
            returns.forEach(r => {
                if (r >= binStart && r < binEnd) bins[i]++;
            });
        }

        const chart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Strategy Count',
                    data: bins,
                    backgroundColor: returns.map(r =>
                        r >= 0 ? 'rgba(39, 174, 96, 0.7)' : 'rgba(231, 76, 60, 0.7)'
                    ),
                    borderColor: returns.map(r =>
                        r >= 0 ? '#27ae60' : '#e74c3c'
                    ),
                    borderWidth: 1
                }]
            },
            options: {
                ...this.getCommonOptions(),
                plugins: {
                    ...this.getCommonOptions().plugins,
                    title: {
                        display: true,
                        text: 'Return Distribution',
                        color: this.colors.text,
                        font: { size: 16 }
                    }
                }
            }
        });

        this.charts.set(canvasId, chart);
        console.log(`[Charts] Created return distribution chart`);
    }

    // Create win rate comparison chart
    createWinRateComparison(strategies, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }

        // Group by edge type and calculate average win rate
        const typeGroups = {};
        strategies.forEach(s => {
            if (!typeGroups[s.edge_type]) {
                typeGroups[s.edge_type] = [];
            }
            typeGroups[s.edge_type].push(s.win_rate * 100);
        });

        const labels = Object.keys(typeGroups);
        const data = labels.map(type => {
            const rates = typeGroups[type];
            return rates.reduce((a, b) => a + b, 0) / rates.length;
        });

        const chart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Average Win Rate (%)',
                    data: data,
                    backgroundColor: data.map(v =>
                        v >= 50 ? 'rgba(39, 174, 96, 0.7)' : 'rgba(231, 76, 60, 0.7)'
                    ),
                    borderWidth: 1
                }]
            },
            options: {
                ...this.getCommonOptions(),
                plugins: {
                    ...this.getCommonOptions().plugins,
                    title: {
                        display: true,
                        text: 'Win Rate by Strategy Type',
                        color: this.colors.text,
                        font: { size: 16 }
                    }
                },
                scales: {
                    ...this.getCommonOptions().scales,
                    y: {
                        ...this.getCommonOptions().scales.y,
                        min: 0,
                        max: 100
                    }
                }
            }
        });

        this.charts.set(canvasId, chart);
        console.log(`[Charts] Created win rate comparison chart`);
    }

    // Create top strategies comparison chart
    createTopStrategiesChart(strategies, canvasId, limit = 10) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }

        const topStrategies = strategies
            .sort((a, b) => b.total_profit_usdt - a.total_profit_usdt)
            .slice(0, limit);

        const labels = topStrategies.map(s =>
                s.edge_type.substring(0, 15) + '...'
            );
        const profits = topStrategies.map(s => s.total_profit_usdt);

        const chart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Profit (USDT)',
                    data: profits,
                    backgroundColor: profits.map(p =>
                        p >= 0 ? 'rgba(52, 152, 219, 0.7)' : 'rgba(231, 76, 60, 0.7)'
                    ),
                    borderWidth: 1
                }]
            },
            options: {
                ...this.getCommonOptions(),
                indexAxis: 'y',
                plugins: {
                    ...this.getCommonOptions().plugins,
                    title: {
                        display: true,
                        text: `Top ${limit} Strategies by Profit`,
                        color: this.colors.text,
                        font: { size: 16 }
                    }
                }
            }
        });

        this.charts.set(canvasId, chart);
        console.log(`[Charts] Created top strategies chart`);
    }

    // Create performance metrics chart
    createPerformanceMetrics(strategies, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }

        const topStrategies = strategies
            .sort((a, b) => b.total_profit_usdt - a.total_profit_usdt)
            .slice(0, 10);

        const labels = topStrategies.map((s, i) => `#${i + 1}`);

        const chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Sharpe Ratio',
                        data: topStrategies.map(s => s.sharpe_ratio),
                        borderColor: this.colors.primary,
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        yAxisID: 'y'
                    },
                    {
                        label: 'Win Rate (%)',
                        data: topStrategies.map(s => s.win_rate * 100),
                        borderColor: this.colors.success,
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                ...this.getCommonOptions(),
                plugins: {
                    ...this.getCommonOptions().plugins,
                    title: {
                        display: true,
                        text: 'Performance Metrics Comparison',
                        color: this.colors.text,
                        font: { size: 16 }
                    }
                },
                scales: {
                    x: {
                        ...this.getCommonOptions().scales.x,
                        title: {
                            display: true,
                            text: 'Strategy Rank',
                            color: this.colors.text
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: this.colors.grid },
                        ticks: { color: this.colors.text },
                        title: {
                            display: true,
                            text: 'Sharpe Ratio',
                            color: this.colors.primary
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        min: 0,
                        max: 100,
                        grid: { drawOnChartArea: false },
                        ticks: { color: this.colors.text },
                        title: {
                            display: true,
                            text: 'Win Rate (%)',
                            color: this.colors.success
                        }
                    }
                }
            }
        });

        this.charts.set(canvasId, chart);
        console.log(`[Charts] Created performance metrics chart`);
    }

    // Update all charts with new data
    updateCharts(strategies) {
        if (strategies && strategies.length > 0) {
            this.createReturnDistribution(strategies, 'returnDistributionChart');
            this.createWinRateComparison(strategies, 'winRateChart');
            this.createTopStrategiesChart(strategies, 'topStrategiesChart');
            this.createPerformanceMetrics(strategies, 'performanceMetricsChart');
        }
    }

    // Destroy all charts
    destroyAll() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
        console.log('[Charts] All charts destroyed');
    }
}

// Make available globally
window.SlateCharts = SlateCharts;
