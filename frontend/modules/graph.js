/**
 * VR System Monitor - Graph Component
 * Chart.js wrapper for historical data visualization
 */

const Graph = (function() {
    // Store chart instances
    const charts = new Map();
    
    // Chart color configurations
    const COLORS = {
        normal: {
            line: 'rgb(110, 231, 183)',
            fill: 'rgba(110, 231, 183, 0.1)'
        },
        warning: {
            line: 'rgb(251, 191, 36)',
            fill: 'rgba(251, 191, 36, 0.1)'
        },
        alert: {
            line: 'rgb(248, 113, 113)',
            fill: 'rgba(248, 113, 113, 0.1)'
        }
    };
    
    // Metric configurations
    const METRIC_CONFIG = {
        cpu: { label: 'CPU %', min: 0, max: 100, unit: '%' },
        ram: { label: 'RAM GB', min: 0, max: null, unit: 'GB' },
        disk: { label: 'Disk GB', min: 0, max: null, unit: 'GB' },
        temp: { label: 'Temp °C', min: 25, max: 60, unit: '°C' },
        battery: { label: 'Battery %', min: 0, max: 100, unit: '%' }
    };
    
    /**
     * Format timestamp for chart labels
     */
    function formatTime(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false
        });
    }
    
    /**
     * Get chart ID for a device/metric combination
     */
    function getChartId(deviceId, metric) {
        return `${deviceId.replace('_', '-')}-${metric}-chart`;
    }
    
    /**
     * Create a new chart
     */
    function createChart(deviceId, metric, data = []) {
        const chartId = getChartId(deviceId, metric);
        const canvas = document.getElementById(chartId);
        if (!canvas) {
            console.error('Canvas not found:', chartId);
            return null;
        }
        
        // Destroy existing chart if any
        destroyChart(deviceId, metric);
        
        const config = METRIC_CONFIG[metric] || METRIC_CONFIG.cpu;
        const colors = COLORS.normal;
        
        const chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.map(d => formatTime(d.timestamp)),
                datasets: [{
                    label: config.label,
                    data: data.map(d => d.value),
                    borderColor: colors.line,
                    backgroundColor: colors.fill,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 4,
                    pointBackgroundColor: colors.line
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 300
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#2a2a2a',
                        borderColor: '#4a4a4a',
                        borderWidth: 1,
                        titleFont: {
                            family: "'IBM Plex Mono', monospace",
                            size: 10
                        },
                        bodyFont: {
                            family: "'IBM Plex Mono', monospace",
                            size: 10
                        },
                        padding: 8,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return `${context.parsed.y.toFixed(1)}${config.unit}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(42, 42, 42, 0.5)',
                            lineWidth: 1
                        },
                        ticks: {
                            color: '#666666',
                            font: {
                                family: "'IBM Plex Mono', monospace",
                                size: 9
                            },
                            maxTicksLimit: 6
                        }
                    },
                    y: {
                        min: config.min,
                        max: config.max,
                        grid: {
                            color: 'rgba(42, 42, 42, 0.5)',
                            lineWidth: 1
                        },
                        ticks: {
                            color: '#666666',
                            font: {
                                family: "'IBM Plex Mono', monospace",
                                size: 9
                            }
                        }
                    }
                }
            }
        });
        
        charts.set(`${deviceId}_${metric}`, chart);
        return chart;
    }
    
    /**
     * Update chart with new data
     */
    function updateChart(deviceId, metric, data) {
        const key = `${deviceId}_${metric}`;
        let chart = charts.get(key);
        
        if (!chart) {
            chart = createChart(deviceId, metric, data);
            return;
        }
        
        // Update data
        chart.data.labels = data.map(d => formatTime(d.timestamp));
        chart.data.datasets[0].data = data.map(d => d.value);
        chart.update('none');
    }
    
    /**
     * Add a single data point to chart
     */
    function addDataPoint(deviceId, metric, timestamp, value) {
        const key = `${deviceId}_${metric}`;
        const chart = charts.get(key);
        if (!chart) return;
        
        const maxPoints = 240; // 60 minutes at 15s intervals
        
        chart.data.labels.push(formatTime(timestamp));
        chart.data.datasets[0].data.push(value);
        
        // Remove old points if exceeding max
        if (chart.data.labels.length > maxPoints) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }
        
        chart.update('none');
    }
    
    /**
     * Destroy a chart
     */
    function destroyChart(deviceId, metric) {
        const key = `${deviceId}_${metric}`;
        const chart = charts.get(key);
        if (chart) {
            chart.destroy();
            charts.delete(key);
        }
    }
    
    /**
     * Show/hide graph container with animation
     */
    function toggleGraphVisibility(deviceId, metric, visible) {
        const containerId = `${deviceId.replace('_', '-')}-${metric}-graph`;
        const container = document.getElementById(containerId);
        if (!container) return;
        
        if (visible) {
            container.classList.remove('hidden');
            // Trigger reflow before adding visible class
            container.offsetHeight;
            container.classList.add('visible');
        } else {
            container.classList.remove('visible');
            // Wait for animation before hiding
            setTimeout(() => {
                if (!container.classList.contains('visible')) {
                    container.classList.add('hidden');
                }
            }, 200);
        }
    }
    
    /**
     * Destroy all charts
     */
    function destroyAll() {
        charts.forEach((chart, key) => {
            chart.destroy();
        });
        charts.clear();
    }
    
    // Public API
    return {
        createChart,
        updateChart,
        addDataPoint,
        destroyChart,
        destroyAll,
        toggleGraphVisibility
    };
})();
