/**
 * SLATE API Client
 * Handles all API communication with retry logic, caching, and error handling.
 */
class SlateAPI {
    constructor(config = {}) {
        this.baseURL = config.baseURL || this.detectBaseURL();
        this.cache = new Map();
        this.cacheTimeout = config.cacheTimeout || 2000;
        this.requestTimeout = config.requestTimeout || 30000;  // Increased to 30s
        this.maxRetries = config.maxRetries || 5;  // Increased retries
        this.retryDelay = config.retryDelay || 1500;  // Increased delay
    }

    detectBaseURL() {
        // Force use of 127.0.0.1 instead of localhost to avoid IPv6 issues
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '') {
            return `http://127.0.0.1:${window.location.port}`;
        }
        return window.location.origin;
    }

    async fetch(endpoint, options = {}) {
        const cacheKey = `${options.method || 'GET'}:${endpoint}`;
        const now = Date.now();

        // Check cache for GET requests
        if ((!options.method || options.method === 'GET') && this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (now - cached.timestamp < this.cacheTimeout) {
                console.log(`[API] Cache hit for: ${endpoint}`);
                return cached.data;
            }
        }

        // Perform request with retry logic
        let lastError;
        for (let attempt = 0; attempt < this.maxRetries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);

                const response = await fetch(`${this.baseURL}${endpoint}`, {
                    ...options,
                    signal: controller.signal,
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                // Cache successful GET requests
                if ((!options.method || options.method === 'GET')) {
                    this.cache.set(cacheKey, {
                        data,
                        timestamp: now
                    });
                }

                console.log(`[API] Success: ${endpoint} (attempt ${attempt + 1})`);
                return data;

            } catch (error) {
                lastError = error;
                console.warn(`[API] Attempt ${attempt + 1}/${this.maxRetries} failed for ${endpoint}:`, error.message);

                if (attempt < this.maxRetries - 1) {
                    await this.delay(this.retryDelay * (attempt + 1) * 0.5);
                }
            }
        }

        throw new Error(`API request failed after ${this.maxRetries} attempts: ${lastError.message}`);
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    clearCache() {
        this.cache.clear();
        console.log('[API] Cache cleared');
    }

    // API Methods

    async getStatistics() {
        return this.fetch('/api/discovery/statistics');
    }

    async getTopStrategies(limit = 10, sortBy = 'total_profit_usdt') {
        const params = new URLSearchParams({
            limit: limit.toString(),
            sort_by: sortBy
        });
        return this.fetch(`/api/discovery/top?${params}`);
    }

    async startDiscovery() {
        return this.fetch('/api/discovery/start', { method: 'POST' });
    }

    async stopDiscovery() {
        return this.fetch('/api/discovery/stop', { method: 'POST' });
    }

    async getHealth() {
        return this.fetch('/health');
    }

    async getDiscoveryStatus() {
        return this.fetch('/api/discovery/status');
    }

    // Batch requests
    async getDashboardData() {
        try {
            const [stats, strategies] = await Promise.all([
                this.getStatistics(),
                this.getTopStrategies(50)
            ]);
            return { stats, strategies };
        } catch (error) {
            console.error('[API] Batch request failed:', error);
            throw error;
        }
    }

    // Natural Language Strategy Generation
    async generateNLStrategy(description, provider = 'mock', apiKey = null) {
        return this.fetch('/api/discovery/nl/generate', {
            method: 'POST',
            body: JSON.stringify({
                description,
                provider,
                api_key: apiKey
            })
        });
    }

    async testNLStrategy(description, provider = 'mock', apiKey = null) {
        return this.fetch('/api/discovery/nl/test', {
            method: 'POST',
            body: JSON.stringify({
                description,
                provider,
                api_key: apiKey
            })
        });
    }

    async getBenchmarkComparison() {
        return this.fetch('/api/discovery/benchmark');
    }

    async getStrategyCorrelation() {
        return this.fetch('/api/discovery/correlation');
    }

    async optimizePortfolio(method = 'mean_variance') {
        const params = new URLSearchParams({ method });
        return this.fetch(`/api/discovery/portfolio/optimize?${params}`);
    }
}

// Create singleton instance
window.slateAPI = new SlateAPI();
