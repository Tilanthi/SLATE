/**
 * SLATE Dashboard Application
 * Main application logic for the SLATE trading dashboard.
 */

class SlateDashboard {
    constructor() {
        this.api = window.slateAPI;
        this.utils = window.SlateUtils;
        this.charts = new window.SlateCharts();

        // State
        this.state = {
            stats: null,
            strategies: [],
            filteredStrategies: [],
            currentPage: 1,
            pageSize: 10,
            sortBy: 'total_profit_usdt',
            sortOrder: 'desc',
            filterType: 'all',
            autoRefresh: true,
            autoRefreshInterval: 5000
        };

        // UI elements
        this.elements = {
            status: document.getElementById('status'),
            statusCard: document.getElementById('status-card'),
            totalTests: document.getElementById('total-tests'),
            profitable: document.getElementById('profitable'),
            bestReturn: document.getElementById('best-return'),
            bestSharpe: document.getElementById('best-sharpe'),
            avgWinRate: document.getElementById('avg-win-rate'),
            startBtn: document.getElementById('start-btn'),
            stopBtn: document.getElementById('stop-btn'),
            strategyStatus: document.getElementById('strategy-status'),
            strategiesBody: document.getElementById('strategies-body'),
            typeFilter: document.getElementById('type-filter'),
            pageInfo: document.getElementById('page-info'),
            prevBtn: document.getElementById('prev-btn'),
            nextBtn: document.getElementById('next-btn')
        };

        this.refreshTimer = null;
        this.init();
    }

    async init() {
        console.log('[Dashboard] Initializing...');

        // Load initial data
        await this.refreshData();

        // Setup auto-refresh
        this.setupAutoRefresh();

        // Setup table sort handlers
        this.setupTableSorting();

        console.log('[Dashboard] Initialized successfully');
    }

    async refreshData() {
        console.log('[Dashboard] Refreshing data...');

        try {
            // Fetch data
            const [stats, strategiesData] = await Promise.all([
                this.api.getStatistics(),
                this.api.getTopStrategies(1000) // Get more for filtering
            ]);

            // Update state
            this.state.stats = stats;
            this.state.strategies = strategiesData.strategies || [];
            this.state.filteredStrategies = this.state.strategies;

            // Update UI
            this.updateStatistics(stats);
            this.updateFilterOptions();
            this.applyFiltersAndSort();
            this.updateCharts();

            // Hide loading message
            if (this.elements.strategyStatus) {
                this.elements.strategyStatus.style.display = 'none';
            }

            console.log('[Dashboard] Data refreshed successfully');

        } catch (error) {
            console.error('[Dashboard] Error refreshing data:', error);
            this.showError('Failed to load data: ' + error.message);
        }
    }

    updateStatistics(stats) {
        // Update status
        if (stats.discovery_running) {
            this.elements.status.textContent = '● Running';
            this.elements.status.className = 'value running';
            this.elements.statusCard.classList.add('success');
        } else {
            this.elements.status.textContent = '○ Idle';
            this.elements.status.className = 'value idle';
            this.elements.statusCard.classList.remove('success');
        }

        // Update buttons
        this.elements.startBtn.disabled = stats.discovery_running;
        this.elements.stopBtn.disabled = !stats.discovery_running;

        // Update statistics cards with animation
        this.animateValue(this.elements.totalTests, stats.total_tests || 0);
        this.animateValue(this.elements.profitable, stats.profitable_strategies || 0);

        // Best return
        const bestReturn = stats.best_return || 0;
        this.elements.bestReturn.textContent = this.utils.formatPercentage(bestReturn);
        this.elements.bestReturn.className = 'value ' + (bestReturn >= 0 ? 'positive' : 'negative');

        // Best Sharpe
        const bestSharpe = stats.best_sharpe || 0;
        this.elements.bestSharpe.textContent = this.utils.formatNumber(bestSharpe);

        // Average Win Rate
        const avgWinRate = stats.average_win_rate || 0;
        this.elements.avgWinRate.textContent = this.utils.formatPercentage(avgWinRate);
    }

    animateValue(element, value) {
        const start = 0;
        const end = value;
        const duration = 500;
        const startTime = performance.now();

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + (end - start) * easeProgress);
            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };

        requestAnimationFrame(update);
    }

    updateFilterOptions() {
        const types = this.utils.getUniqueTypes(this.state.strategies);
        const currentFilter = this.elements.typeFilter.value;

        this.elements.typeFilter.innerHTML = '<option value="all">All Types</option>';
        types.forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            if (type === currentFilter) {
                option.selected = true;
            }
            this.elements.typeFilter.appendChild(option);
        });
    }

    applyFiltersAndSort() {
        let filtered = this.state.strategies;

        // Apply type filter
        if (this.state.filterType !== 'all') {
            filtered = this.utils.filterByType(filtered, this.state.filterType);
        }

        // Apply sorting
        filtered = this.utils.sortStrategies(filtered, this.state.sortBy, this.state.sortOrder);

        this.state.filteredStrategies = filtered;
        this.updateTable();
    }

    updateTable() {
        const { filteredStrategies, currentPage, pageSize } = this.state;
        const { elements } = this;

        // Pagination
        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const pageData = filteredStrategies.slice(startIndex, endIndex);
        const totalPages = Math.ceil(filteredStrategies.length / pageSize);

        // Clear table
        elements.strategiesBody.innerHTML = '';

        if (pageData.length === 0) {
            elements.strategiesBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center">
                        ${this.state.strategies.length === 0
                            ? 'No strategies discovered yet. Start discovery to begin.'
                            : 'No strategies match the current filters.'}
                    </td>
                </tr>
            `;
        } else {
            // Populate table
            pageData.forEach((strategy, index) => {
                const row = this.createStrategyRow(strategy, startIndex + index + 1);
                elements.strategiesBody.appendChild(row);
            });
        }

        // Update pagination
        elements.pageInfo.textContent = `Page ${currentPage} of ${totalPages || 1}`;
        elements.prevBtn.disabled = currentPage <= 1;
        elements.nextBtn.disabled = currentPage >= totalPages;
    }

    createStrategyRow(strategy, rank) {
        const row = document.createElement('tr');
        row.className = 'fade-in';

        const returnClass = strategy.total_return_pct >= 0 ? 'positive' : 'negative';

        row.innerHTML = `
            <td>${rank}</td>
            <td><strong>${strategy.edge_type}</strong></td>
            <td>${strategy.edge_description}</td>
            <td class="${returnClass}">${this.utils.formatPercentage(strategy.total_return_pct)}</td>
            <td>${this.utils.formatCurrency(strategy.total_profit_usdt)}</td>
            <td>${this.utils.formatNumber(strategy.sharpe_ratio)}</td>
            <td>${this.utils.formatPercentage(strategy.win_rate)}</td>
            <td class="${strategy.max_drawdown_pct < 0 ? 'negative' : ''}">${this.utils.formatPercentage(strategy.max_drawdown_pct)}</td>
            <td>${this.utils.formatNumber(strategy.profit_factor)}</td>
        `;

        return row;
    }

    updateCharts() {
        if (this.state.strategies.length > 0) {
            this.charts.updateCharts(this.state.strategies);
        }
    }

    setupAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }

        if (this.state.autoRefresh) {
            this.refreshTimer = setInterval(() => {
                this.refreshData();
            }, this.state.autoRefreshInterval);
        }
    }

    setupTableSorting() {
        const headers = document.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const sortBy = header.dataset.sort;

                // Toggle sort order if clicking same column
                if (this.state.sortBy === sortBy) {
                    this.state.sortOrder = this.state.sortOrder === 'desc' ? 'asc' : 'desc';
                } else {
                    this.state.sortBy = sortBy;
                    this.state.sortOrder = 'desc';
                }

                // Update header classes
                headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                header.classList.add(this.state.sortOrder === 'asc' ? 'sort-asc' : 'sort-desc');

                this.applyFiltersAndSort();
            });
        });
    }

    // Public methods for button handlers

    async startDiscovery() {
        console.log('[Dashboard] Starting discovery...');
        try {
            const result = await this.api.startDiscovery();
            this.showMessage(result.message || 'Discovery started');
            setTimeout(() => this.refreshData(), 1000);
        } catch (error) {
            this.showError('Failed to start discovery: ' + error.message);
        }
    }

    async stopDiscovery() {
        console.log('[Dashboard] Stopping discovery...');
        try {
            const result = await this.api.stopDiscovery();
            this.showMessage(result.message || 'Discovery stopped');
            setTimeout(() => this.refreshData(), 1000);
        } catch (error) {
            this.showError('Failed to stop discovery: ' + error.message);
        }
    }

    filterByType(type) {
        this.state.filterType = type;
        this.state.currentPage = 1;
        this.applyFiltersAndSort();
    }

    sortStrategies(sortBy) {
        this.state.sortBy = sortBy;
        this.state.currentPage = 1;
        this.applyFiltersAndSort();
    }

    changePageSize(size) {
        this.state.pageSize = parseInt(size);
        this.state.currentPage = 1;
        this.updateTable();
    }

    previousPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage--;
            this.updateTable();
        }
    }

    nextPage() {
        const totalPages = Math.ceil(this.state.filteredStrategies.length / this.state.pageSize);
        if (this.state.currentPage < totalPages) {
            this.state.currentPage++;
            this.updateTable();
        }
    }

    exportToCSV() {
        console.log('[Dashboard] Exporting to CSV...');
        this.utils.exportToCSV(this.state.strategies, 'slate_strategies.csv');
    }

    showMessage(message) {
        // Simple alert for now, could be enhanced with a toast notification
        alert(message);
    }

    showError(message) {
        console.error('[Dashboard]', message);
        this.showMessage('Error: ' + message);
    }

    // Natural Language Strategy Generation

    async generateNLStrategy() {
        const description = document.getElementById('nl-description').value.trim();
        if (!description) {
            this.showNLResult('Please enter a strategy description', true);
            return;
        }

        this.showNLResult('Generating strategy from description...', false, true);

        try {
            const response = await fetch('/api/discovery/nl/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ description })
            });

            const data = await response.json();

            if (data.status === 'success') {
                const strategy = data.strategy;
                this.showNLResult(`
                    <h4>✅ Strategy Generated Successfully</h4>
                    <p><strong>Type:</strong> ${strategy.edge_type}</p>
                    <p><strong>Description:</strong> ${strategy.description}</p>
                    <p><strong>Confidence:</strong> ${(strategy.confidence * 100).toFixed(1)}%</p>
                    <p><strong>Expected Return:</strong> ${this.utils.formatPercentage(strategy.expected_return)}</p>
                    <details>
                        <summary style="cursor: pointer; color: #3498db;">View Strategy Details</summary>
                        <pre>${JSON.stringify(strategy, null, 2)}</pre>
                    </details>
                    <p style="margin-top: 15px;">
                        <button onclick="app.testNLStrategy()" style="padding: 10px 20px; background: #9b59b6; color: white; border: none; border-radius: 5px; cursor: pointer;">
                            ▶ Test This Strategy
                        </button>
                    </p>
                `);
            } else {
                this.showNLResult(`❌ Failed to generate strategy: ${data.message}`, true);
            }
        } catch (error) {
            console.error('[NL Strategy] Error:', error);
            this.showNLResult(`❌ Error: ${error.message}`, true);
        }
    }

    async testNLStrategy() {
        const description = document.getElementById('nl-description').value.trim();
        if (!description) {
            this.showNLResult('Please enter a strategy description', true);
            return;
        }

        this.showNLResult('Generating and testing strategy...', false, true);

        try {
            const response = await fetch('/api/discovery/nl/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ description })
            });

            const data = await response.json();

            if (data.status === 'success') {
                const results = data.results;
                const passed = results.passed_validation;
                const beatMarket = results.beat_market;

                this.showNLResult(`
                    <h4>✅ Strategy Tested Successfully</h4>
                    <p><strong>Strategy:</strong> ${data.strategy.description}</p>
                    <div style="margin-top: 15px;">
                        <h5>Results:</h5>
                        <p><strong>Profit:</strong> ${this.utils.formatCurrency(results.total_profit_usdt)} (${this.utils.formatPercentage(results.total_return_pct)})</p>
                        <p><strong>Sharpe Ratio:</strong> ${results.sharpe_ratio.toFixed(2)}</p>
                        <p><strong>Win Rate:</strong> ${this.utils.formatPercentage(results.win_rate)}</p>
                        <p><strong>Max Drawdown:</strong> ${this.utils.formatPercentage(results.max_drawdown_pct)}</p>
                        <p><strong>Total Trades:</strong> ${results.total_trades}</p>
                        <p><strong>Beat Market:</strong> ${beatMarket ? '✅ Yes' : '❌ No'}</p>
                        <p><strong>Validation:</strong> ${passed ? '✅ Passed' : '❌ Failed'}</p>
                    </div>
                    <p style="margin-top: 15px;">
                        <em>The strategy has been saved to the database. Refresh the data to see it in the strategies list.</em>
                    </p>
                `);

                // Refresh data to show the new strategy
                setTimeout(() => this.refreshData(), 2000);
            } else {
                this.showNLResult(`❌ Failed to test strategy: ${data.message}`, true);
            }
        } catch (error) {
            console.error('[NL Strategy] Error:', error);
            this.showNLResult(`❌ Error: ${error.message}`, true);
        }
    }

    showNLResult(html, isError = false, isLoading = false) {
        const resultDiv = document.getElementById('nl-result');
        resultDiv.style.display = 'block';
        resultDiv.className = 'nl-result' + (isError ? ' error' : '');

        if (isLoading) {
            resultDiv.innerHTML = '<p style="text-align: center;">⏳ Processing...</p>';
        } else {
            resultDiv.innerHTML = html;
        }
    }
}

// Initialize dashboard when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] DOM loaded, initializing app...');
    app = new SlateDashboard();
    window.app = app; // Make available globally for button handlers
});
