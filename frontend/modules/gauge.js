/**
 * VR System Monitor - Gauge Component
 * Draws circles.
 */

const Gauge = (function() {
    const CIRCUMFERENCE = 2 * Math.PI * 80; // radius = 80
    
    // Threshold configurations
    const THRESHOLDS = {
        cpu: { warning: 60, alert: 80, min: 0, max: 100 },
        ram: { warning: 60, alert: 80, min: 0, max: 100 },
        disk: { warning: 70, alert: 90, min: 0, max: 100 },
        temp: { warning: 50, alert: 55, min: 25, max: 60 },
        battery: { warning: 50, alert: 20, min: 0, max: 100, inverted: true }
    };
    
    /**
     * math for circle
     */
    function calculatePercentage(value, metric, total = null) {
        if (value === null || value === undefined) return 0;
        
        // Normalize metric name (disk-c, disk-d, etc. -> disk)
        const normalizedMetric = metric.startsWith('disk') ? 'disk' : metric;
        const config = THRESHOLDS[normalizedMetric] || THRESHOLDS.cpu;
        
        // For RAM and disk, calculate percentage from used/total
        if ((normalizedMetric === 'ram' || normalizedMetric === 'disk') && total) {
            return Math.min(100, Math.max(0, (value / total) * 100));
        }
        
        // For temp, scale to 0-100 based on min/max
        if (metric === 'temp') {
            const range = config.max - config.min;
            return Math.min(100, Math.max(0, ((value - config.min) / range) * 100));
        }
        
        return Math.min(100, Math.max(0, value));
    }
    
    /**
     * pick color (green/yellow/red)
     */
    function getColorClass(value, metric) {
        if (value === null || value === undefined) return 'disabled';
        
        // Normalize metric name (disk-c, disk-d, etc. -> disk)
        const normalizedMetric = metric.startsWith('disk') ? 'disk' : metric;
        const config = THRESHOLDS[normalizedMetric] || THRESHOLDS.cpu;
        
        // Battery is inverted (lower is worse)
        if (config.inverted) {
            if (value <= config.alert) return 'alert';
            if (value <= config.warning) return 'warning';
            return 'normal';
        }
        
        // For temp, use actual value not percentage
        const checkValue = (metric === 'temp') ? value : calculatePercentage(value, metric);
        
        if (checkValue >= config.alert) return 'alert';
        if (checkValue >= config.warning) return 'warning';
        return 'normal';
    }
    
    /**
     * get symbol
     */
    function getStatusMarker(colorClass) {
        switch (colorClass) {
            case 'alert': return '●';
            case 'warning': return '◆';
            default: return '─';
        }
    }
    
    /**
     * animate the circle
     */
    function updateGauge(deviceId, metric, value, total = null) {
        const gaugeId = `${deviceId.replace('_', '-')}-${metric}-gauge`;
        const container = document.getElementById(gaugeId);
        if (!container) return;
        
        const progressCircle = container.querySelector('.gauge-progress');
        const valueElement = document.getElementById(`${deviceId.replace('_', '-')}-${metric}-value`);
        const detailElement = document.getElementById(`${deviceId.replace('_', '-')}-${metric}-detail`);
        const row = document.getElementById(`${deviceId.replace('_', '-')}-${metric}-row`);
        const statusMarker = row?.querySelector('.status-marker');
        
        // Calculate percentage for arc
        const percentage = calculatePercentage(value, metric, total);
        const dashArray = (percentage / 100) * CIRCUMFERENCE;
        
        // Get color class based on percentage
        const colorClass = getColorClass(percentage, metric);
        
        // Update arc
        if (progressCircle) {
            progressCircle.style.strokeDasharray = `${dashArray} ${CIRCUMFERENCE}`;
            progressCircle.classList.remove('normal', 'warning', 'alert', 'disabled');
            progressCircle.classList.add(colorClass);
        }
        
        // Display value in gauge
        // Temperature shows actual °C, everything else shows percentage
        if (valueElement) {
            let displayValue = '--';
            
            if (value !== null && value !== undefined) {
                if (metric === 'temp') {
                    // Temperature shows actual value (°C)
                    displayValue = Math.round(value);
                } else {
                    // Everything else shows percentage
                    displayValue = Math.round(percentage);
                }
            }
            
            // Fade transition
            valueElement.style.opacity = '0';
            setTimeout(() => {
                valueElement.textContent = displayValue;
                valueElement.style.opacity = '1';
            }, 100);
        }
        
        // Update detail label for RAM/disk (shows actual GB/TB values)
        const normalizedMetric = metric.startsWith('disk') ? 'disk' : metric;
        if (detailElement && (normalizedMetric === 'ram' || normalizedMetric === 'disk') && value !== null && total !== null) {
            let usedStr, totalStr;
            
            // Convert to TB if > 1000 GB for readability
            if (total > 1000) {
                usedStr = `${(value / 1024).toFixed(1)} TB`;
                totalStr = `${(total / 1024).toFixed(1)} TB`;
            } else {
                usedStr = `${value.toFixed(1)} GB`;
                totalStr = `${total.toFixed(0)} GB`;
            }
            
            detailElement.textContent = `${usedStr} / ${totalStr}`;
        }
        
        // Update status marker
        if (statusMarker) {
            statusMarker.textContent = getStatusMarker(colorClass);
            statusMarker.classList.remove('normal', 'warning', 'alert');
            statusMarker.classList.add(colorClass);
        }
    }
    
    /**
     * grey it out
     */
    function disableGauge(deviceId, metric) {
        const gaugeId = `${deviceId.replace('_', '-')}-${metric}-gauge`;
        const container = document.getElementById(gaugeId);
        if (!container) return;
        
        const progressCircle = container.querySelector('.gauge-progress');
        const valueElement = document.getElementById(`${deviceId.replace('_', '-')}-${metric}-value`);
        
        if (progressCircle) {
            progressCircle.style.strokeDasharray = `0 ${CIRCUMFERENCE}`;
            progressCircle.classList.remove('normal', 'warning', 'alert');
            progressCircle.classList.add('disabled');
        }
        
        if (valueElement) {
            valueElement.textContent = '--';
        }
    }
    
    /**
     * reset everything
     */
    function initializeAll() {
        const metrics = ['cpu', 'ram', 'disk'];
        metrics.forEach(metric => disableGauge('pc', metric));
        
        const questMetrics = ['cpu', 'ram', 'temp', 'battery'];
        questMetrics.forEach(metric => disableGauge('quest_3', metric));
    }
    
    // Public API
    return {
        updateGauge,
        disableGauge,
        initializeAll,
        calculatePercentage,
        getColorClass,
        getStatusMarker
    };
})();
