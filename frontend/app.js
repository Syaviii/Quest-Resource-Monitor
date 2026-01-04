/**
 * VR System Monitor - Main App
 * Entry point.
 */

const App = (function() {
    const POLL_INTERVAL = 10000;
    const DEVICE_POLL_INTERVAL = 2000;
    
    let pollTimer = null;
    let devicePollTimer = null;
    let isPolling = false;
    let pollCounter = 0;
    
    async function init() {
        console.log('booting...');
        showLoadingOverlay('CONNECTING...');
        
        Dashboard.init();
        
        const online = await checkBackendHealth();
        
        if (online) {
            updateLoadingText('LOADING METRICS...');
            await fetchInitialData();
            hideLoadingOverlay();
            
            startPolling();
            setupVisibilityHandler();
            setupConnectionTooltip();
            setupSwitchButton();
            
            StateManager.setState('app.initialized', true);
            console.log('we are live');
        } else {
            updateLoadingText('OFFLINE - RETRYING...');
            console.error('backend is dead');
            setTimeout(init, 5000);
        }
    }
    
    async function checkBackendHealth() {
        // is backend alive?
        try {
            const response = await APIClient.getHealth();
            if (response.success) {
                Dashboard.showOnlineState();
                return true;
            }
        } catch (error) {
            console.error('Backend health check failed:', error);
        }
        return false;
    }
    
    async function fetchInitialData() {
        // grab first batch of data
        try {
            const devicesResponse = await APIClient.getDevices();
            if (devicesResponse.success && devicesResponse.data) {
                devicesResponse.data.devices.forEach(device => {
                    StateManager.updateDeviceStatus(device.id, device.status);
                    Dashboard.updateDeviceStatusUI(device.id, device.status);
                    if (device.id === 'quest_3') {
                        Dashboard.updateQuestCardState(device.status);
                    }
                });
            }
            
            await pollConnectionStatus();
            await pollMetrics();
            await pollNetworkStats();
            await pollQuestStorage();
            
            const recordingResponse = await APIClient.getRecordingStatus();
            if (recordingResponse.success && recordingResponse.data) {
                StateManager.updateRecording({
                    active: recordingResponse.data.recording,
                    sessionId: recordingResponse.data.session_id,
                    elapsed: recordingResponse.data.elapsed_seconds || 0,
                    startTime: recordingResponse.data.start_time
                });
            }
            
        } catch (error) {
            console.error('init fetch failed:', error);
        }
    }
    
    function startPolling() {
        // start update loops
        if (isPolling) return;
        
        isPolling = true;
        console.log('starting loops...');
        
        // metrics
        pollTimer = setInterval(async () => {
            await pollMetrics();
            await pollNetworkStats();
            
            // storage (every 60s)
            pollCounter++;
            if (pollCounter % 6 === 0) {
                await pollQuestStorage();
            }
        }, POLL_INTERVAL);
        
        // device status (fast)
        devicePollTimer = setInterval(async () => {
            await pollDeviceStatus();
        }, DEVICE_POLL_INTERVAL);
    }
    
    function stopPolling() {
        // kill loops
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        if (devicePollTimer) {
            clearInterval(devicePollTimer);
            devicePollTimer = null;
        }
        isPolling = false;
        console.log('stopping loops');
    }
    
    async function pollDeviceStatus() {
        // fast poll for connection changes
        try {
            // Poll device status
            const response = await APIClient.getDevices();
            if (response.success && response.data && response.data.devices) {
                response.data.devices.forEach(device => {
                    const currentStatus = StateManager.getState(`devices.${device.id}.status`);
                    if (currentStatus !== device.status) {
                        StateManager.updateDeviceStatus(device.id, device.status);
                        Dashboard.updateDeviceStatusUI(device.id, device.status);
                        if (device.id === 'quest_3') {
                            Dashboard.updateQuestCardState(device.status);
                        }
                    }
                });
            }
            
            // Also poll connection status to update USB/WiFi icons
            await pollConnectionStatus();
        } catch (error) {
            // Silently fail - metrics poll will handle reconnection
        }
    }
    
    async function pollConnectionStatus() {
        // update connection badges
        try {
            const response = await APIClient.getConnectionStatus();
            if (response.success && response.data) {
                updateConnectionIconsEnhanced(response.data);
            }
            
            // Also poll connection events for notifications
            await pollConnectionEvents();
        } catch (error) {
            // Silently fail
        }
    }
    
    async function pollMetrics() {
        // get numbers
        try {
            const response = await APIClient.getCurrentMetrics();
            if (response.success && response.data) {
                Dashboard.updateMetrics(response.data);
                StateManager.setState('app.lastUpdate', Date.now());
                StateManager.setState('app.error', null);
            }
        } catch (error) {
            console.error('Polling error:', error);
            StateManager.setState('app.error', error.message);
            
            // Check if backend is still alive
            const online = await checkBackendHealth();
            if (!online) {
                Dashboard.showOfflineState();
                showConnectionBanner();
                stopPolling();
                
                // Retry connection
                setTimeout(async () => {
                    const reconnected = await checkBackendHealth();
                    if (reconnected) {
                        hideConnectionBanner();
                        startPolling();
                    }
                }, 5000);
            }
        }
    }
    
    async function pollNetworkStats() {
        // bandwidth check
        try {
            const response = await APIClient.getNetworkStats();
            if (response.success && response.data) {
                Dashboard.updateNetworkStats(response.data);
            }
        } catch (error) {
            // Silently fail
            console.warn('Network stats poll failed');
        }
    }
    
    async function pollQuestStorage() {
        // Quest storage check
        try {
            const response = await APIClient.getQuestStorage();
            if (response.success && response.data) {
                Dashboard.updateQuestStorage(response.data);
            }
        } catch (error) {
            // Silently fail
            console.warn('Quest storage poll failed');
        }
    }
    
    const PAUSE_WHEN_HIDDEN = false;
    
    function setupVisibilityHandler() {
        // pause if tab hidden (maybe)
        if (!PAUSE_WHEN_HIDDEN) return;
        
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                stopPolling();
            } else {
                startPolling();
                pollMetrics();
            }
        });
    }
    
    function shutdown() {
        // cleanup time
        console.log('bye');
        stopPolling();
        Graph.destroyAll();
    }
    
    // Set up shutdown handler
    window.addEventListener('beforeunload', shutdown);
    
    // ========== Loading State Controls ==========
    
    function showLoadingOverlay(text = 'LOADING...') {
        const overlay = document.getElementById('loadingOverlay');
        const textEl = overlay?.querySelector('.loading-text');
        if (overlay) {
            overlay.classList.remove('hidden', 'fade-out');
        }
        if (textEl) {
            textEl.textContent = text;
        }
    }
    
    function updateLoadingText(text) {
        const textEl = document.querySelector('#loadingOverlay .loading-text');
        if (textEl) {
            textEl.textContent = text;
        }
    }
    
    function hideLoadingOverlay() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.classList.add('fade-out');
            setTimeout(() => {
                overlay.classList.add('hidden');
            }, 300);
        }
    }
    
    function showConnectionBanner() {
        const banner = document.getElementById('connectionBanner');
        if (banner) {
            banner.classList.remove('hidden');
        }
    }
    
    function hideConnectionBanner() {
        const banner = document.getElementById('connectionBanner');
        if (banner) {
            banner.classList.add('hidden');
        }
    }
    
    // ========== Notification Toast System ==========
    
    function showToast(title, message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const icons = {
            success: '✓',
            warning: '⚠',
            error: '✗',
            info: '●'
        };
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || '●'}</span>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">×</button>
        `;
        
        // Close button handler
        toast.querySelector('.toast-close').addEventListener('click', () => {
            removeToast(toast);
        });
        
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => removeToast(toast), 5000);
    }
    
    function removeToast(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.add('exiting');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }
    
    // ========== Connection Tooltip ==========
    
    let lastConnectionStatus = null;
    
    function setupConnectionTooltip() {
        const badgesArea = document.getElementById('connectionBadges');
        const tooltip = document.getElementById('connectionTooltip');
        
        if (!badgesArea || !tooltip) return;
        
        let hideTimeout = null;
        
        const showTooltip = () => {
            if (hideTimeout) {
                clearTimeout(hideTimeout);
                hideTimeout = null;
            }
            if (lastConnectionStatus) {
                updateTooltipContent(lastConnectionStatus);
                tooltip.classList.remove('hidden');
            }
        };
        
        const hideTooltip = () => {
            hideTimeout = setTimeout(() => {
                tooltip.classList.add('hidden');
            }, 150); // Small delay to allow moving to tooltip
        };
        
        badgesArea.addEventListener('mouseenter', showTooltip);
        badgesArea.addEventListener('mouseleave', hideTooltip);
        
        // Keep tooltip visible when hovering over it
        tooltip.addEventListener('mouseenter', showTooltip);
        tooltip.addEventListener('mouseleave', hideTooltip);
    }
    
    function updateTooltipContent(status) {
        const primary = document.getElementById('tooltipPrimary');
        const backup = document.getElementById('tooltipBackup');
        const usb = document.getElementById('tooltipUsb');
        const wireless = document.getElementById('tooltipWireless');
        const latency = document.getElementById('tooltipLatency');
        const quality = document.getElementById('tooltipQuality');
        const actions = document.getElementById('tooltipActions');
        const switchBtn = document.getElementById('tooltipSwitchBtn');
        
        // Primary mode
        if (primary) {
            primary.textContent = status.mode ? status.mode.toUpperCase() : '--';
            if (status.mode && status.mode !== 'disconnected') {
                primary.className = 'tooltip-value success';
            } else {
                primary.className = 'tooltip-value';
            }
        }
        
        // Backup connection
        if (backup) {
            if (status.state === 'connected_both') {
                // Show which is the backup
                if (status.mode === 'usb' && status.wireless_ip) {
                    backup.textContent = `Wireless (${status.wireless_ip})`;
                    backup.className = 'tooltip-value tooltip-backup';
                } else if (status.mode === 'wireless' && status.usb_serial) {
                    backup.textContent = `USB (${status.usb_serial})`;
                    backup.className = 'tooltip-value tooltip-backup';
                } else {
                    backup.textContent = 'None';
                    backup.className = 'tooltip-value tooltip-backup';
                }
            } else {
                backup.textContent = 'None';
                backup.className = 'tooltip-value tooltip-backup';
            }
        }
        
        // USB status
        if (usb) {
            if (status.usb_connected && status.usb_serial) {
                usb.textContent = `✓ ${status.usb_serial}`;
                usb.className = 'tooltip-value success';
            } else {
                usb.textContent = 'Not connected';
                usb.className = 'tooltip-value';
            }
        }
        
        // Wireless status
        if (wireless) {
            if (status.wireless_connected && status.wireless_ip) {
                wireless.textContent = `✓ ${status.wireless_ip}:${status.wireless_port}`;
                wireless.className = 'tooltip-value success';
            } else if (status.wireless_ip) {
                wireless.textContent = `○ ${status.wireless_ip} (standby)`;
                wireless.className = 'tooltip-value';
            } else {
                wireless.textContent = 'Not connected';
                wireless.className = 'tooltip-value';
            }
        }
        
        // Latency
        if (latency) {
            if (status.latency_ms) {
                latency.textContent = `${status.latency_ms}ms`;
                if (status.latency_ms < 50) {
                    latency.className = 'tooltip-value success';
                } else if (status.latency_ms < 200) {
                    latency.className = 'tooltip-value';
                } else {
                    latency.className = 'tooltip-value warning';
                }
            } else {
                latency.textContent = '--';
                latency.className = 'tooltip-value';
            }
        }
        
        // Quality
        if (quality) {
            if (status.quality && status.quality !== 'unknown') {
                quality.textContent = status.quality.charAt(0).toUpperCase() + status.quality.slice(1);
                if (status.quality === 'excellent' || status.quality === 'good') {
                    quality.className = 'tooltip-value success';
                } else if (status.quality === 'fair') {
                    quality.className = 'tooltip-value warning';
                } else {
                    quality.className = 'tooltip-value error';
                }
            } else {
                quality.textContent = '--';
                quality.className = 'tooltip-value';
            }
        }
        
        // Switch button - only show if can switch
        if (actions && switchBtn) {
            if (status.can_switch_to && status.can_switch_to.length > 0) {
                const switchTarget = status.can_switch_to[0];
                switchBtn.textContent = `Switch to ${switchTarget.toUpperCase()}`;
                switchBtn.dataset.target = switchTarget;
                actions.classList.remove('hidden');
            } else {
                actions.classList.add('hidden');
            }
        }
    }
    
    // Setup switch button click handler
    function setupSwitchButton() {
        const switchBtn = document.getElementById('tooltipSwitchBtn');
        if (!switchBtn) return;
        
        switchBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const target = switchBtn.dataset.target;
            if (!target) return;
            
            switchBtn.textContent = 'Switching...';
            switchBtn.disabled = true;
            
            try {
                const response = await APIClient.switchConnection(target);
                if (response.success) {
                    showToast('SWITCHED', `Now using ${target.toUpperCase()}`, 'success');
                } else {
                    showToast('ERROR', response.error || 'Switch failed', 'error');
                }
            } catch (err) {
                showToast('ERROR', 'Failed to switch connection', 'error');
            }
            
            switchBtn.disabled = false;
            // Tooltip will update on next poll
        });
    }
    
    // ========== Connection Events Polling ==========
    
    async function pollConnectionEvents() {
        try {
            const response = await APIClient.getConnectionEvents(true);
            if (response.success && response.data && response.data.events) {
                response.data.events.forEach(event => {
                    handleConnectionEvent(event);
                });
            }
        } catch (error) {
            // Silently fail
        }
    }
    
    function handleConnectionEvent(event) {
        const typeMap = {
            'connected': 'success',
            'disconnected': 'error',
            'switched': 'info',
            'degraded': 'warning',
            'recovered': 'success'
        };
        
        const titleMap = {
            'connected': 'CONNECTED',
            'disconnected': 'DISCONNECTED',
            'switched': 'CONNECTION SWITCHED',
            'degraded': 'CONNECTION DEGRADED',
            'recovered': 'CONNECTION RECOVERED'
        };
        
        const type = typeMap[event.type] || 'info';
        const title = titleMap[event.type] || 'CONNECTION';
        
        showToast(title, event.message, type);
    }
    
    // Enhanced updateConnectionIcons with primary/standby indicators
    function updateConnectionIconsEnhanced(status) {
        const usbIcon = document.getElementById('connUsb');
        const wifiIcon = document.getElementById('connWifi');
        
        if (!usbIcon || !wifiIcon) return;
        
        // Reset all classes
        usbIcon.classList.remove('active', 'connecting', 'primary', 'standby');
        wifiIcon.classList.remove('active', 'connecting', 'primary', 'standby');
        
        if (status.state === 'disconnected') {
            // Both inactive - default dim state
        } else if (status.state === 'connecting') {
            usbIcon.classList.add('connecting');
            wifiIcon.classList.add('connecting');
        } else if (status.state === 'connected_usb') {
            // Only USB connected - show it as active primary
            usbIcon.classList.add('active', 'primary');
            // Wireless is not connected - leave it dim
        } else if (status.state === 'connected_wireless') {
            // Only wireless connected - show it as active primary
            wifiIcon.classList.add('active', 'primary');
            // USB is not connected - leave it dim
        } else if (status.state === 'connected_both') {
            // both available - show primary active, other standby
            if (status.mode === 'usb') {
                usbIcon.classList.add('active', 'primary');
                wifiIcon.classList.add('standby');
            } else {
                wifiIcon.classList.add('active', 'primary');
                usbIcon.classList.add('standby');
            }
        }
        
        // Update tooltips with details
        if (status.usb_connected && status.usb_serial) {
            usbIcon.title = `USB: ${status.usb_serial}`;
        } else {
            usbIcon.title = 'USB: Not connected';
        }
        
        if (status.wireless_connected && status.wireless_ip) {
            wifiIcon.title = `Wireless: ${status.wireless_ip}:${status.wireless_port}`;
            if (status.latency_ms) {
                wifiIcon.title += ` (${status.latency_ms}ms)`;
            }
        } else {
            wifiIcon.title = 'Wireless: Not connected';
        }
        
        // Store for tooltip
        lastConnectionStatus = status;
        
        // Update diagnostics in settings panel
        if (typeof Settings !== 'undefined' && Settings.updateDiagnostics) {
            Settings.updateDiagnostics(status);
        }
    }
    
    // Public API
    return {
        init,
        startPolling,
        stopPolling,
        shutdown,
        showLoadingOverlay,
        hideLoadingOverlay,
        showConnectionBanner,
        hideConnectionBanner,
        showToast,
        setupConnectionTooltip
    };
})();

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}

