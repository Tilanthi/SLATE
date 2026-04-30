/**
 * SLATE Dashboard Utilities
 * Number formatting, CSV export, local storage, and helper functions.
 */

class SlateUtils {
    // Number formatting
    static formatCurrency(value, decimals = 2) {
        if (value === null || value === undefined) return '-';
        return '$' + value.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    static formatPercentage(value, decimals = 2) {
        if (value === null || value === undefined) return '-';
        const pct = value * 100;
        const sign = pct >= 0 ? '+' : '';
        return sign + pct.toFixed(decimals) + '%';
    }

    static formatNumber(value, decimals = 2) {
        if (value === null || value === undefined) return '-';
        return value.toFixed(decimals);
    }

    static formatRatio(value, decimals = 2) {
        if (value === null || value === undefined) return '-';
        return value.toFixed(decimals);
    }

    // Color coding
    static getColorForPercentage(value) {
        if (value > 0) return '#27ae60';
        if (value < 0) return '#e74c3c';
        return '#95a5a6';
    }

    static getColorForValue(value, thresholds = { good: 1, neutral: 0 }) {
        if (value >= thresholds.good) return '#27ae60';
        if (value >= thresholds.neutral) return '#f39c12';
        return '#e74c3c';
    }

    // Date/time formatting
    static formatDate(timestamp) {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    static formatRelativeTime(timestamp) {
        if (!timestamp) return '-';
        const now = new Date();
        const then = new Date(timestamp);
        const diffMs = now - then;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);

        if (diffSecs < 60) return `${diffSecs}s ago`;
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${Math.floor(diffHours / 24)}d ago`;
    }

    // CSV Export
    static exportToCSV(data, filename = 'slate_strategies.csv') {
        if (!data || data.length === 0) {
            alert('No data to export');
            return;
        }

        const headers = Object.keys(data[0]);
        const csvRows = [];

        // Add header row
        csvRows.push(headers.join(','));

        // Add data rows
        for (const row of data) {
            const values = headers.map(header => {
                const value = row[header];
                // Escape quotes and wrap in quotes if contains comma
                if (typeof value === 'string') {
                    return `"${value.replace(/"/g, '""')}"`;
                }
                return value ?? '';
            });
            csvRows.push(values.join(','));
        }

        // Create and download file
        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        console.log(`[Utils] Exported ${data.length} rows to ${filename}`);
    }

    // Local Storage helpers
    static savePreference(key, value) {
        try {
            localStorage.setItem(`slate_${key}`, JSON.stringify(value));
        } catch (e) {
            console.warn('[Utils] Failed to save preference:', e);
        }
    }

    static loadPreference(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(`slate_${key}`);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.warn('[Utils] Failed to load preference:', e);
            return defaultValue;
        }
    }

    static removePreference(key) {
        try {
            localStorage.removeItem(`slate_${key}`);
        } catch (e) {
            console.warn('[Utils] Failed to remove preference:', e);
        }
    }

    // Debounce and throttle
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // Sorting helpers
    static sortStrategies(strategies, sortBy, order = 'desc') {
        return [...strategies].sort((a, b) => {
            let aVal = a[sortBy];
            let bVal = b[sortBy];

            // Handle string comparison
            if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }

            if (order === 'asc') {
                return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
            } else {
                return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
            }
        });
    }

    // Pagination helpers
    static paginate(data, page, pageSize) {
        const startIndex = (page - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        return {
            data: data.slice(startIndex, endIndex),
            totalPages: Math.ceil(data.length / pageSize),
            currentPage: page,
            totalItems: data.length
        };
    }

    // Filter helpers
    static filterByType(strategies, type) {
        if (!type || type === 'all') return strategies;
        return strategies.filter(s => s.edge_type === type);
    }

    static getUniqueTypes(strategies) {
        const types = new Set(strategies.map(s => s.edge_type));
        return Array.from(types).sort();
    }

    // Animation helpers
    static animateValue(element, start, end, duration, formatter = null) {
        const range = end - start;
        const startTime = performance.now();

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function for smooth animation
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const current = start + (range * easeProgress);

            element.textContent = formatter ? formatter(current) : current.toFixed(2);

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };

        requestAnimationFrame(update);
    }

    // Loading state helpers
    static showLoading(element, message = 'Loading...') {
        element.innerHTML = `<span class="loading">${message}</span>`;
    }

    static showError(element, message) {
        element.innerHTML = `<span class="error">${message}</span>`;
    }

    static clearElement(element) {
        element.innerHTML = '';
    }
}

// Make available globally
window.SlateUtils = SlateUtils;
