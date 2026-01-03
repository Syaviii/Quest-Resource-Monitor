```javascript
/**
 * VR System Monitor - API Client
 * talks to the python backend.
 */

const APIClient = (function() { // api url
    const API_BASE = 'http://localhost:5000/api';
    const TIMEOUT_MS = 5000;
    const MAX_RETRIES = 3;
    
    // fetch wrapper
    async function request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
        
        const config = {
            ...options,
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };
        
        let lastError;
        
        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
            try {
                const response = await fetch(url, config);
                clearTimeout(timeout);
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error?.message || `HTTP error ${response.status}`);
                }
                
                return data;
            } catch (error) {
                lastError = error;
                
                // don't retry on client errors
                if (error.message.includes('HTTP error 4')) {
                    break;
                }
                
                // abort error
                if (error.name === 'AbortError') {
                    lastError = new Error('Request timeout');
                    break;
                }
                
                // retry with backoff
                if (attempt < MAX_RETRIES) {
                    await new Promise(resolve => 
                        setTimeout(resolve, Math.pow(2, attempt) * 100)
                    );
                }
            }
        }
        
        clearTimeout(timeout);
        throw lastError;
    }
    
    // ========== Health & Status ==========
    
    async function getHealth() {
        // pulse check
        return request('/health');
    }
    
    // devices
    
    async function getDevices() {
        // get device list
        return request('/devices');
    }
    
    async function getDevice(deviceId) {
        return request(`/devices/${deviceId}`);
    }
    
    // metrics
    
    async function getCurrentMetrics(fresh = false) {
        // fetch stats
        return request('/metrics/current');
    }
    
    async function getMetricsHistory(device, metric, minutes = 60) {
        // graph data
        return request(`/metrics/history?device=${device}&metric=${metric}&minutes=${minutes}`);
    }
    
    async function getNetworkStats() {
        return request('/metrics/network');
    }
    
    async function getQuestStorage() {
        return request('/quest/storage');
    }
    
    // disks
    
    async function getAllDisks() {
        return request('/disks');
    }
    
    async function setDiskSelection(mountPoint, isSelected) {
        return request('/disks/select', {
            method: 'POST',
            body: JSON.stringify({ mount_point: mountPoint, is_selected: isSelected })
        });
    }
    
    async function getDiskMetrics() {
        return request('/disks/metrics');
    }
    
    // recording
    
    async function startRecording(name = null) {
        return request('/recording/start', {
            method: 'POST',
            body: JSON.stringify({ name })
        });
    }
    
    async function stopRecording() {
        return request('/recording/stop', {
            method: 'POST'
        });
    }
    
    async function getRecordingStatus() {
        return request('/recording/status');
    }
    
    async function exportSession(sessionId, format = 'json') {
        return request(`/recording/export?session_id=${sessionId}&format=${format}`);
    }
    
    // debug
    
    async function getDbInfo() {
        return request('/debug/db-info');
    }
    
    // connection
    
    async function getConnectionStatus() {
        // connection info
        return request('/connection/status');
    }
    
    async function switchConnection(mode) {
        // toggle mode (usb/wireless)
        return request('/connection/switch', {
            method: 'POST',
            body: JSON.stringify({ mode })
        });
    }
    
    async function enableWireless() {
        // turn on wireless
        return request('/connection/enable-wireless', {
            method: 'POST'
        });
    }
    
    async function setConnectionPriority(priority) {
        return request('/connection/priority', {
            method: 'POST',
            body: JSON.stringify({ priority })
        });
    }
    
    async function measureLatency() {
        return request('/connection/latency');
    }
    
    async function discoverWireless() {
        return request('/connection/discover', { method: 'POST' });
    }
    
    async function scanNetwork() {
        return request('/connection/scan', { method: 'POST' });
    }
    
    async function getConnectionEvents(clear = true) {
        return request(`/connection/events?clear=${clear}`);
    }
    
    // settings
    
    async function getSettings() {
        return request('/settings');
    }
    
    async function updateSettings(settings) {
        return request('/settings', {
            method: 'POST',
            body: JSON.stringify(settings)
        });
    }
    
    // Public API
    return {
        getHealth,
        getDevices,
        getDevice,
        getCurrentMetrics,
        getMetricsHistory,
        getNetworkStats,
        getQuestStorage,
        getAllDisks,
        setDiskSelection,
        getDiskMetrics,
        startRecording,
        stopRecording,
        getRecordingStatus,
        exportSession,
        getDbInfo,
        getConnectionStatus,
        switchConnection,
        enableWireless,
        setConnectionPriority,
        measureLatency,
        discoverWireless,
        scanNetwork,
        getConnectionEvents,
        getSettings,
        updateSettings
    };
})();
