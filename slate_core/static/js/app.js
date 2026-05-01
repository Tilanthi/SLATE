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

        // Load benchmark data
        await this.refreshBenchmarkData();

        // Load correlation data
        await this.refreshCorrelationData();

        // Load portfolio optimization
        await this.optimizePortfolio();

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

    // Benchmark Comparison Methods

    async refreshBenchmarkData() {
        console.log('[Dashboard] Refreshing benchmark data...');

        try {
            const benchmarkData = await this.api.getBenchmarkComparison();

            if (benchmarkData.status === 'no_data') {
                this.showBenchmarkPlaceholder();
                return;
            }

            if (benchmarkData.status === 'error') {
                console.error('[Dashboard] Benchmark error:', benchmarkData.error);
                this.showBenchmarkError(benchmarkData.error);
                return;
            }

            // Update benchmark summary cards
            this.updateBenchmarkSummary(benchmarkData.summary);

            // Update benchmark chart
            this.charts.createBenchmarkComparison(
                benchmarkData.top_performers,
                benchmarkData.worst_performers,
                'benchmarkChart'
            );

            // Update top and worst performers lists
            this.updateBenchmarkPerformers(benchmarkData.top_performers, benchmarkData.worst_performers);

            // Hide loading message
            const statusElement = document.getElementById('benchmark-status');
            if (statusElement) {
                statusElement.style.display = 'none';
            }

            console.log('[Dashboard] Benchmark data refreshed successfully');

        } catch (error) {
            console.error('[Dashboard] Error loading benchmark data:', error);
            this.showBenchmarkError(error.message);
        }
    }

    updateBenchmarkSummary(summary) {
        // Beat market rate
        const beatMarketRate = document.getElementById('beat-market-rate');
        const beatMarketCount = document.getElementById('beat-market-count');
        if (beatMarketRate) {
            const rate = (summary.beat_market_percentage * 100).toFixed(1);
            beatMarketRate.textContent = `${rate}%`;
            beatMarketRate.className = 'benchmark-value ' + (summary.beat_market_percentage >= 0.5 ? 'positive' : 'negative');
        }
        if (beatMarketCount) {
            beatMarketCount.textContent = `${summary.beat_market_count}/${summary.total_strategies} strategies`;
        }

        // Cumulative excess return
        const cumulativeExcess = document.getElementById('cumulative-excess');
        if (cumulativeExcess) {
            const excess = summary.cumulative_excess_usdt;
            cumulativeExcess.textContent = this.utils.formatCurrency(excess);
            cumulativeExcess.className = 'benchmark-value ' + (excess >= 0 ? 'positive' : 'negative');
        }

        // Information Ratio
        const infoRatio = document.getElementById('information-ratio');
        if (infoRatio) {
            const ir = summary.information_ratio.toFixed(2);
            infoRatio.textContent = ir;
            infoRatio.className = 'benchmark-value ' + (summary.information_ratio >= 1 ? 'positive' : 'negative');
        }

        // Average excess return
        const avgExcess = document.getElementById('avg-excess-return');
        if (avgExcess) {
            const avg = summary.average_excess_return_usdt;
            avgExcess.textContent = this.utils.formatCurrency(avg);
            avgExcess.className = 'benchmark-value ' + (avg >= 0 ? 'positive' : 'negative');
        }
    }

    updateBenchmarkPerformers(topPerformers, worstPerformers) {
        const topList = document.getElementById('top-performers-list');
        const worstList = document.getElementById('worst-performers-list');

        if (topList) {
            topList.innerHTML = topPerformers.map(p => this.createPerformerItem(p, 'positive')).join('');
        }

        if (worstList) {
            worstList.innerHTML = worstPerformers.map(p => this.createPerformerItem(p, 'negative')).join('');
        }
    }

    createPerformerItem(performer, type) {
        const excessClass = performer.excess_return_usdt >= 0 ? 'excess' : 'excess negative';
        const excessSign = performer.excess_return_usdt >= 0 ? '+' : '';

        return `
            <div class="performer-item ${type}">
                <div class="performer-name">${performer.edge_type}</div>
                <div class="performer-metrics">
                    <div class="performer-metric">Profit: <span>${this.utils.formatCurrency(performer.total_profit_usdt)}</span></div>
                    <div class="performer-metric">Buy & Hold: <span>${this.utils.formatCurrency(performer.buy_hold_profit_usdt)}</span></div>
                    <div class="performer-metric ${excessClass}">Excess: <span>${excessSign}${this.utils.formatCurrency(performer.excess_return_usdt)}</span></div>
                    ${performer.sharpe_ratio ? `<div class="performer-metric">Sharpe: <span>${performer.sharpe_ratio.toFixed(2)}</span></div>` : ''}
                    ${performer.win_rate ? `<div class="performer-metric">Win Rate: <span>${this.utils.formatPercentage(performer.win_rate)}</span></div>` : ''}
                </div>
            </div>
        `;
    }

    showBenchmarkPlaceholder() {
        const statusElement = document.getElementById('benchmark-status');
        if (statusElement) {
            statusElement.textContent = 'No benchmark data available yet. Run discovery to generate benchmark comparisons.';
            statusElement.className = 'text-center';
            statusElement.style.display = 'block';
        }
    }

    showBenchmarkError(message) {
        const statusElement = document.getElementById('benchmark-status');
        if (statusElement) {
            statusElement.textContent = `Error loading benchmark data: ${message}`;
            statusElement.className = 'error';
            statusElement.style.display = 'block';
        }
    }

    // Correlation Analysis Methods

    async refreshCorrelationData() {
        console.log('[Dashboard] Refreshing correlation data...');

        try {
            const correlationData = await this.api.getStrategyCorrelation();

            if (correlationData.status === 'insufficient_data') {
                this.showCorrelationPlaceholder(correlationData.message);
                return;
            }

            if (correlationData.status === 'error') {
                console.error('[Dashboard] Correlation error:', correlationData.error);
                this.showCorrelationError(correlationData.error);
                return;
            }

            // Update correlation summary
            this.updateCorrelationSummary(correlationData.summary);

            // Update correlation matrix
            this.updateCorrelationMatrix(correlationData.matrix);

            // Update recommendations
            this.updateCorrelationRecommendations(correlationData.recommendations);

            // Hide loading message
            const statusElement = document.getElementById('correlation-status');
            if (statusElement) {
                statusElement.style.display = 'none';
            }

            console.log('[Dashboard] Correlation data refreshed successfully');

        } catch (error) {
            console.error('[Dashboard] Error loading correlation data:', error);
            this.showCorrelationError(error.message);
        }
    }

    updateCorrelationSummary(summary) {
        const totalTypes = document.getElementById('total-types');
        const highCorrPairs = document.getElementById('high-corr-pairs');
        const lowCorrPairs = document.getElementById('low-corr-pairs');

        if (totalTypes) totalTypes.textContent = summary.total_types;
        if (highCorrPairs) highCorrPairs.textContent = summary.high_correlation_pairs;
        if (lowCorrPairs) lowCorrPairs.textContent = summary.low_correlation_pairs;
    }

    updateCorrelationMatrix(matrixData) {
        const matrixContainer = document.getElementById('correlation-matrix');
        if (!matrixContainer) return;

        const types = matrixData.types;
        const correlations = matrixData.correlations;

        // Create grid with header row
        let html = '<div class="correlation-cell header">Strategy Type</div>';
        types.forEach(type => {
            html += `<div class="correlation-cell header">${type.substring(0, 15)}</div>`;
        });

        // Create data rows
        types.forEach((type, i) => {
            html += `<div class="correlation-cell header">${type.substring(0, 15)}</div>`;
            correlations[i].forEach((corr, j) => {
                const value = corr.toFixed(2);
                let cellClass = '';

                if (i === j) {
                    cellClass = 'diagonal';
                } else if (corr < 0.2) {
                    cellClass = 'corr-very-low';
                } else if (corr < 0.4) {
                    cellClass = 'corr-low';
                } else if (corr < 0.6) {
                    cellClass = 'corr-medium-low';
                } else if (corr < 0.7) {
                    cellClass = 'corr-medium';
                } else if (corr < 0.8) {
                    cellClass = 'corr-medium-high';
                } else if (corr < 0.9) {
                    cellClass = 'corr-high';
                } else {
                    cellClass = 'corr-very-high';
                }

                html += `
                    <div class="correlation-cell ${cellClass}">
                        <div class="correlation-value-text">${value}</div>
                    </div>
                `;
            });
        });

        matrixContainer.innerHTML = html;
    }

    updateCorrelationRecommendations(recommendations) {
        const redundantList = document.getElementById('redundant-strategies-list');
        const opportunitiesList = document.getElementById('diversification-opportunities-list');

        if (redundantList) {
            if (recommendations.redundant_strategies.length === 0) {
                redundantList.innerHTML = '<p style="color: var(--text-secondary);">No highly correlated strategies found.</p>';
            } else {
                redundantList.innerHTML = recommendations.redundant_strategies.map(pair =>
                    this.createCorrelationPairItem(pair, 'redundant')
                ).join('');
            }
        }

        if (opportunitiesList) {
            if (recommendations.diversification_opportunities.length === 0) {
                opportunitiesList.innerHTML = '<p style="color: var(--text-secondary);">No low correlation pairs found yet.</p>';
            } else {
                opportunitiesList.innerHTML = recommendations.diversification_opportunities.map(pair =>
                    this.createCorrelationPairItem(pair, 'diversification')
                ).join('');
            }
        }
    }

    createCorrelationPairItem(pair, type) {
        const badgeClass = pair.correlation > 0.8 ? 'badge-high' : pair.correlation > 0.5 ? 'badge-medium' : 'badge-low';
        const itemClass = type === 'diversification' ? 'diversification' : '';

        return `
            <div class="correlation-pair-item ${itemClass}">
                <div class="correlation-pair-name">${pair.type1} ↔ ${pair.type2}</div>
                <div class="correlation-pair-metric">
                    <span>Correlation: <strong>${pair.correlation.toFixed(2)}</strong></span>
                    <span class="correlation-badge ${badgeClass}">${pair.diversification_benefit} Benefit</span>
                </div>
            </div>
        `;
    }

    showCorrelationPlaceholder(message) {
        const statusElement = document.getElementById('correlation-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = 'text-center';
            statusElement.style.display = 'block';
        }
    }

    showCorrelationError(message) {
        const statusElement = document.getElementById('correlation-status');
        if (statusElement) {
            statusElement.textContent = `Error loading correlation data: ${message}`;
            statusElement.className = 'error';
            statusElement.style.display = 'block';
        }
    }

    // Portfolio Optimization Methods

    async optimizePortfolio(method = 'mean_variance') {
        console.log(`[Dashboard] Optimizing portfolio with method: ${method}...`);

        try {
            const portfolioData = await this.api.optimizePortfolio(method);

            if (portfolioData.status === 'insufficient_strategies') {
                this.showPortfolioPlaceholder(portfolioData.message);
                return;
            }

            if (portfolioData.status === 'error') {
                console.error('[Dashboard] Portfolio optimization error:', portfolioData.error);
                this.showPortfolioError(portfolioData.error);
                return;
            }

            // Update portfolio summary
            this.updatePortfolioSummary(portfolioData.portfolio);

            // Update portfolio allocations
            this.updatePortfolioAllocations(portfolioData.allocations, portfolioData.portfolio.initial_capital);

            // Update portfolio chart
            this.charts.createPortfolioChart(portfolioData.allocations, 'portfolioChart');

            // Update portfolio metrics
            this.updatePortfolioMetrics(portfolioData.metrics, portfolioData.portfolio);

            // Hide loading message
            const statusElement = document.getElementById('portfolio-status');
            if (statusElement) {
                statusElement.style.display = 'none';
            }

            console.log('[Dashboard] Portfolio optimization completed successfully');

        } catch (error) {
            console.error('[Dashboard] Error optimizing portfolio:', error);
            this.showPortfolioError(error.message);
        }
    }

    updatePortfolioSummary(portfolio) {
        const returnEl = document.getElementById('portfolio-return');
        const profitEl = document.getElementById('portfolio-profit');
        const sharpeEl = document.getElementById('portfolio-sharpe');
        const divRatioEl = document.getElementById('diversification-ratio');

        if (returnEl) {
            returnEl.textContent = this.utils.formatPercentage(portfolio.expected_return_pct / 100);
            returnEl.className = 'portfolio-value ' + (portfolio.expected_return_pct >= 0 ? 'positive' : 'negative');
        }

        if (profitEl) {
            profitEl.textContent = this.utils.formatCurrency(portfolio.expected_profit_usdt);
            profitEl.className = 'portfolio-value ' + (portfolio.expected_profit_usdt >= 0 ? 'positive' : 'negative');
        }

        if (sharpeEl) {
            sharpeEl.textContent = portfolio.portfolio_sharpe.toFixed(2);
            sharpeEl.className = 'portfolio-value ' + (portfolio.portfolio_sharpe >= 1 ? 'positive' : 'negative');
        }

        if (divRatioEl) {
            divRatioEl.textContent = portfolio.diversification_ratio.toFixed(2);
            divRatioEl.className = 'portfolio-value ' + (portfolio.diversification_ratio >= 1 ? 'positive' : 'negative');
        }
    }

    updatePortfolioAllocations(allocations, initialCapital) {
        const listElement = document.getElementById('portfolio-allocations-list');
        if (!listElement) return;

        listElement.innerHTML = allocations.map(alloc => {
            const weightPct = alloc.weight_pct;
            return `
                <div class="allocation-item">
                    <div class="allocation-info">
                        <div class="allocation-name">${alloc.edge_type}</div>
                        <div class="allocation-details">
                            ${weightPct.toFixed(1)}% | ${this.utils.formatCurrency(alloc.allocated_usdt)} |
                            Exp. Return: ${alloc.expected_return_pct.toFixed(1)}%
                        </div>
                    </div>
                    <div class="allocation-bar-container">
                        <div class="allocation-bar" style="width: ${weightPct}%">
                            ${weightPct >= 10 ? weightPct.toFixed(1) + '%' : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    updatePortfolioMetrics(metrics, portfolio) {
        const totalStrategies = document.getElementById('total-strategies');
        const effectiveStrategies = document.getElementById('effective-strategies');
        const topAllocation = document.getElementById('top-allocation');
        const portfolioDrawdown = document.getElementById('portfolio-drawdown');

        if (totalStrategies) totalStrategies.textContent = metrics.total_strategies;
        if (effectiveStrategies) effectiveStrategies.textContent = metrics.effective_strategies;
        if (topAllocation) topAllocation.textContent = metrics.top_allocation.toFixed(1) + '%';
        if (portfolioDrawdown) {
            portfolioDrawdown.textContent = this.utils.formatPercentage(portfolio.portfolio_drawdown_pct / 100);
            portfolioDrawdown.className = 'metric-value ' + (portfolio.portfolio_drawdown_pct <= 20 ? 'positive' : 'negative');
        }
    }

    showPortfolioPlaceholder(message) {
        const statusElement = document.getElementById('portfolio-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = 'text-center';
            statusElement.style.display = 'block';
        }
    }

    showPortfolioError(message) {
        const statusElement = document.getElementById('portfolio-status');
        if (statusElement) {
            statusElement.textContent = `Error optimizing portfolio: ${message}`;
            statusElement.className = 'error';
            statusElement.style.display = 'block';
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
