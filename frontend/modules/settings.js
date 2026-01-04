/**
 * VR System Monitor - Settings UI
 */

const Settings = (function() {
    let isOpen = false;
    
    // Configuration for metrics (could come from backend eventually)
    const METRIC_CONFIG = {
        pc: {label: 'PC', metrics: [
            {id: 'cpu', label: 'CPU Usage'},
            {id: 'ram', label: 'RAM Usage'},
            {id: 'disk', label: 'Disk Usage'}
        ]},
        quest_3: {label: 'Meta Quest 3', metrics: [
            {id: 'cpu', label: 'CPU Usage'},
            {id: 'ram', label: 'RAM Usage'},
            {id: 'temp', label: 'Temperature'},
            {id: 'battery', label: 'Battery'}
        ]}
    };

    function init() {
        setupPollingButtons();
        setupGraphPeriodButtons();
        setupMetricToggles(); // Initialize toggles
        setupEventListeners();
        loadSettings();
        loadLocalSettings();
    }
    
    /**
     * restore ui prefs
     */
    function loadLocalSettings() {
        // Layout mode
        const layoutMode = loadSettingLocal('layout_mode', 'side-by-side');
        const layoutRadio = document.querySelector(`input[name="layoutMode"][value="${layoutMode}"]`);
        if (layoutRadio) layoutRadio.checked = true;
        applyLayoutMode(layoutMode);
        
        // Compact mode
        const compactMode = loadSettingLocal('compact_mode', false);
        const compactCheckbox = document.getElementById('compactMode');
        if (compactCheckbox) compactCheckbox.checked = compactMode;
        document.body.classList.toggle('compact-mode', compactMode);
        
        // Auto-collapse disconnected
        const autoCollapse = loadSettingLocal('auto_collapse_disconnected', true);
        const autoCollapseCheckbox = document.getElementById('autoCollapseDisconnected');
        if (autoCollapseCheckbox) autoCollapseCheckbox.checked = autoCollapse;
    }
    
    /**
     * Setup Poll Interval Buttons
     */
    function setupPollingButtons() {
        const intervals = [5, 10, 15, 30];
        const container = document.getElementById('pollingButtons');
        if (!container) return;
        
        container.innerHTML = '';
        
        intervals.forEach(secs => {
            const btn = document.createElement('button');
            btn.className = 'interval-button';
            btn.textContent = `${secs}s`;
            btn.dataset.seconds = secs;
            
            btn.addEventListener('click', () => {
                changePollingInterval(secs);
                updatePollingButtons(secs);
            });
            
            container.appendChild(btn);
        });
    }

    function changePollingInterval(seconds) {
        saveSetting('poll_interval_seconds', seconds);
        const display = document.getElementById('currentPolling');
        if (display) display.textContent = seconds;
        
        // Reload to apply polling change (simplest way)
        setTimeout(() => location.reload(), 500);
    }

    function updatePollingButtons(active) {
        document.querySelectorAll('.interval-button').forEach(btn => {
            if (btn.dataset.seconds == active) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        const display = document.getElementById('currentPolling');
        if (display) display.textContent = active;
    }

    /**
     * Setup Graph Period Buttons
     */
    function setupGraphPeriodButtons() {
        const periods = [15, 30, 60, 120, 180, 1440];
        const container = document.getElementById('graphPeriodButtons');
        if (!container) return;
        
        container.innerHTML = '';
        
        periods.forEach(mins => {
            const label = mins === 1440 ? '24h' : 
                         mins >= 60 ? `${mins/60}h` : 
                         `${mins}m`;
            
            const btn = document.createElement('button');
            btn.className = 'period-button';
            btn.textContent = label;
            btn.dataset.minutes = mins;
            
            btn.addEventListener('click', () => {
                changeGraphPeriod(mins);
                updatePeriodButtons(mins);
            });
            
            container.appendChild(btn);
        });
    }

    function changeGraphPeriod(minutes) {
        saveSetting('graph_history_minutes', minutes);
        
        // Trigger graph refresh
        const openGraphs = StateManager.getState('ui.graphsOpen');
        if (openGraphs) {
            Object.entries(openGraphs).forEach(([key, isOpen]) => {
                if (isOpen) {
                    const [device, metric] = key.split('_');
                    // This assumes APIClient and Graph are available
                    APIClient.getMetricsHistory(device, metric, minutes)
                        .then(response => {
                            if (response.success) {
                                Graph.updateChart(device, metric, response.data.data);
                            }
                        });
                }
            });
        }
        
        const display = document.getElementById('currentPeriod');
        if (display) display.textContent = minutes;
    }

    function updatePeriodButtons(active) {
        document.querySelectorAll('.period-button').forEach(btn => {
            if (btn.dataset.minutes == active) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        const display = document.getElementById('currentPeriod');
        if (display) display.textContent = active;
    }

    /**
     * Setup Metric Visibility Toggles
     */
    function setupMetricToggles() {
        createToggleList('pc', 'pcMetricToggles');
        createToggleList('quest_3', 'questMetricToggles');
    }

    function createToggleList(deviceId, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = '';
        const config = METRIC_CONFIG[deviceId];
        if (!config) return;

        config.metrics.forEach(metric => {
            const label = document.createElement('label');
            label.className = 'settings-checkbox';
            
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = true; // Default to checked
            input.dataset.device = deviceId;
            input.dataset.metric = metric.id;
            
            input.addEventListener('change', (e) => {
                toggleMetricVisibility(deviceId, metric.id, e.target.checked);
            });
            
            const span = document.createElement('span');
            span.textContent = metric.label;
            
            label.appendChild(input);
            label.appendChild(span);
            container.appendChild(label);
        });
    }

    function toggleMetricVisibility(deviceId, metric, isVisible) {
        // Update local state and UI immediately
        // We need to fetch current settings, update visible_metrics, and save
        
        // This is tricky because we don't want to re-fetch settings every click
        // But for now let's assume valid state.
        
        // Apply visual change (hide/show elements)
        applyVisibilityToUI(deviceId, metric, isVisible);
        
        // Save to backend
        APIClient.getSettings().then(res => {
            if (res.success && res.data) {
                const current = res.data.visible_metrics || JSON.parse(JSON.stringify(SettingsStorage.DEFAULTS.visible_metrics));
                
                if (!current[deviceId]) current[deviceId] = [];
                
                if (isVisible) {
                    if (!current[deviceId].includes(metric)) {
                        current[deviceId].push(metric);
                    }
                } else {
                    current[deviceId] = current[deviceId].filter(m => m !== metric);
                }
                
                saveSetting('visible_metrics', current);
            }
        });
    }

    function applyVisibilityToUI(deviceId, metric, isVisible) {
        // Logic to hide/show gauges and graph toggles
        // Selector logic:
        // Gauge container ID: {device}-{metric}-gauge (usually)
        // Except for PC/Quest replacement logic in dashboard.js
        
        // Let's rely on dashboard.js having a way to handle this, 
        // OR we directly manipulate DOM here.
        // Direct DOM manipulation is fastest.
        
        // Gauge ID pattern: pc-cpu-gauge, quest-3-network-gauge (complex)
        // Actually looking at dashboard.js or index.html:
        // IDs like: pc_cpu_gauge, quest_3_battery_gauge ? No, let's check index.html again.
        // I will implement a generic hider based on finding the container.
        
        const safeDeviceId = deviceId.replace('_', '-'); // quest_3 -> quest-3
        
        // Try various ID patterns used in the app
        const selectors = [
            `#${safeDeviceId}-${metric}-gauge`,      // Gauge container
            `#${safeDeviceId}-${metric}-row`,        // Metric row
            `#${safeDeviceId}-disk-list`,            // Disk list special case
            `#${safeDeviceId}-storage-section`       // Storage section
        ];
        
        if (metric === 'disk' && deviceId === 'pc') {
             // PC Disk specific
             const el = document.getElementById('pc-disk-list')?.parentElement; // The disk section
             // Actually, PC disks are dynamically added rows. 
             // We need to hide the whole "Disk Usage" section or rows.
             // For now let's target specific generic IDs if they exist
             const section = document.querySelector(`.card[data-device="${deviceId}"] .section-title:contains("STORAGE")`)?.closest('.section');
             // This is getting complex.
             // Simpler: Just toggle class on known IDs.
             const diskRow = document.getElementById('pc-disk-row'); // If exists
        }

        // Generic Gauge Hiding
        const gaugeId = `${safeDeviceId}-${metric}-gauge`;
        const gaugeEl = document.getElementById(gaugeId);
        if (gaugeEl) {
            gaugeEl.classList.toggle('gauge-hidden', !isVisible);
        }
        
        // Also hide the graph toggle button if it exists
        // Graph toggle ID: toggle-{device}-{metric} (need to check app.js)
    }
    
    /**
     * click handlers
     */
    function setupEventListeners() {
        const trigger = document.getElementById('settingsTrigger');
        const menu = document.getElementById('settingsMenu');
        const discoverBtn = document.getElementById('discoverBtn');
        
        // Toggle dropdown
        if (trigger) {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleDropdown();
            });
        }
        
        // Close on outside click
        document.addEventListener('click', (e) => {
            if (isOpen && !e.target.closest('.settings-dropdown')) {
                closeDropdown();
            }
        });
        
        // Connection priority change
        document.querySelectorAll('input[name="connPriority"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                saveSetting('connection_priority', e.target.value);
                APIClient.setConnectionPriority(e.target.value);
            });
        });
        
        // Poll interval change - REMOVED (Handled by setupPollingButtons)
        
        if (discoverBtn) {
            discoverBtn.addEventListener('click', handleDiscover);
        }
        
        // manual ip
        const ipInput = document.getElementById('wirelessIpInput');
        if (ipInput) {
            ipInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    saveWirelessIP(ipInput.value);
                }
            });
            ipInput.addEventListener('blur', () => {
                if (ipInput.value) {
                    saveWirelessIP(ipInput.value);
                }
            });
        }
        
        // Auto-connection checkboxes
        const autoEnableWireless = document.getElementById('autoEnableWireless');
        if (autoEnableWireless) {
            autoEnableWireless.addEventListener('change', (e) => {
                saveSetting('auto_enable_wireless', e.target.checked);
            });
        }
        
        const autoFallback = document.getElementById('autoFallback');
        if (autoFallback) {
            autoFallback.addEventListener('change', (e) => {
                saveSetting('auto_fallback', e.target.checked);
            });
        }
        
        // Layout mode change
        document.querySelectorAll('input[name="layoutMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                applyLayoutMode(e.target.value);
                saveSettingLocal('layout_mode', e.target.value);
            });
        });
        
        // Compact mode toggle
        const compactMode = document.getElementById('compactMode');
        if (compactMode) {
            compactMode.addEventListener('change', (e) => {
                document.body.classList.toggle('compact-mode', e.target.checked);
                saveSettingLocal('compact_mode', e.target.checked);
            });
        }
        
        // Auto-collapse disconnected toggle
        const autoCollapse = document.getElementById('autoCollapseDisconnected');
        if (autoCollapse) {
            autoCollapse.addEventListener('change', (e) => {
                saveSettingLocal('auto_collapse_disconnected', e.target.checked);
            });
        }
    }
    
    function applyLayoutMode(mode) {
        const content = document.getElementById('content');
        if (!content) return;
        
        // switch layout css
        content.classList.remove('layout-stacked', 'layout-quest-only', 'layout-pc-only');
        
        // Apply new layout
        if (mode === 'stacked') {
            content.classList.add('layout-stacked');
        } else if (mode === 'quest-only') {
            content.classList.add('layout-quest-only');
        } else if (mode === 'pc-only') {
            content.classList.add('layout-pc-only');
        }
        // 'side-by-side' is the default (no class needed)
    }
    
    function saveSettingLocal(key, value) {
        try {
            localStorage.setItem(`vr_monitor_${key}`, JSON.stringify(value));
        } catch (e) {
            console.error('local save failed:', e);
        }
    }
    
    function loadSettingLocal(key, defaultValue) {
        try {
            const value = localStorage.getItem(`vr_monitor_${key}`);
            return value !== null ? JSON.parse(value) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    }
    
    function toggleDropdown() {
        const menu = document.getElementById('settingsMenu');
        if (isOpen) {
            closeDropdown();
        } else {
            menu.classList.remove('hidden');
            isOpen = true;
        }
    }
    
    /**
     * Close the dropdown
     */
    function closeDropdown() {
        const menu = document.getElementById('settingsMenu');
        menu.classList.add('hidden');
        isOpen = false;
    }
    
    /**
     * load from backend
     */
    async function loadSettings() {
        try {
            const response = await APIClient.getSettings();
            if (response.success && response.data) {
                applySettings(response.data);
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
    }
    
    /**
     * update ui form
     */
    function applySettings(settings) {
        // Connection priority
        const priority = settings.connection_priority || 'usb_first';
        const priorityRadio = document.querySelector(`input[name="connPriority"][value="${priority}"]`);
        if (priorityRadio) priorityRadio.checked = true;
        
        // Poll interval (Update buttons)
        const interval = settings.poll_interval_seconds || 10;
        updatePollingButtons(interval);
        
        // Graph history (Update buttons)
        const historyMinutes = settings.graph_history_minutes || 60;
        updatePeriodButtons(historyMinutes);
        
        // Visible Metrics
        if (settings.visible_metrics) {
            applyVisibleMetricsToUI(settings.visible_metrics);
        }
        
        // Wireless IP
        const ipInput = document.getElementById('wirelessIpInput');
        if (ipInput && settings.wireless_ip) {
            ipInput.value = settings.wireless_ip;
        }
        
        // Auto-connection checkboxes
        const autoEnableWireless = document.getElementById('autoEnableWireless');
        if (autoEnableWireless) {
            autoEnableWireless.checked = settings.auto_enable_wireless !== false; // Default true
        }
        
        const autoFallback = document.getElementById('autoFallback');
        if (autoFallback) {
            autoFallback.checked = settings.auto_fallback !== false; // Default true
        }
    }

    function applyVisibleMetricsToUI(visibleMetrics) {
        Object.keys(visibleMetrics).forEach(deviceId => {
            const metrics = visibleMetrics[deviceId];
            const config = METRIC_CONFIG[deviceId];
            if (!config) return;

            // Update checkboxes
            config.metrics.forEach(metric => {
                const isVisible = metrics.includes(metric.id);
                const checkbox = document.querySelector(`input[type="checkbox"][data-device="${deviceId}"][data-metric="${metric.id}"]`);
                if (checkbox) checkbox.checked = isVisible;
                
                // Update specific visibility elements
                applyVisibilityToUI(deviceId, metric.id, isVisible);
            });
        });
    }
    
    /**
     * save to backend
     */
    async function saveSetting(key, value) {
        try {
            await APIClient.updateSettings({ [key]: value });
            console.log(`setting saved: ${key} = ${value}`);
        } catch (error) {
            console.error('save failed:', error);
        }
    }
    
    /**
     * save ip
     */
    async function saveWirelessIP(ip) {
        if (!ip || !ip.match(/^\d+\.\d+\.\d+\.\d+$/)) {
            console.error('Invalid IP format');
            return;
        }
        await saveSetting('wireless_ip', ip);
    }
    
    /**
     * handle discover button
     */
    async function handleDiscover() {
        const discoverBtn = document.getElementById('discoverBtn');
        const ipInput = document.getElementById('wirelessIpInput');
        
        discoverBtn.textContent = '...';
        discoverBtn.disabled = true;
        
        try {
            const response = await APIClient.discoverWireless();
            if (response.success && response.data && response.data.ip) {
                ipInput.value = response.data.ip;
                discoverBtn.textContent = '✓';
                setTimeout(() => {
                    discoverBtn.textContent = 'DISCOVER';
                    discoverBtn.disabled = false;
                }, 2000);
            } else {
                throw new Error('No IP found');
            }
        } catch (error) {
            console.error('Discovery failed:', error);
            discoverBtn.textContent = '✗';
            setTimeout(() => {
                discoverBtn.textContent = 'DISCOVER';
                discoverBtn.disabled = false;
            }, 2000);
        }
    }
    
    function updateDiagnostics(status) {
        const diagUsb = document.getElementById('diagUsb');
        const diagWireless = document.getElementById('diagWireless');
        const diagLatency = document.getElementById('diagLatency');
        const diagQuality = document.getElementById('diagQuality');
        
        if (diagUsb) {
            if (status.usb_connected) {
                diagUsb.textContent = `✓ ${status.usb_serial || 'Connected'}`;
                diagUsb.className = 'diag-value success';
            } else {
                diagUsb.textContent = 'Not connected';
                diagUsb.className = 'diag-value';
            }
        }
        
        if (diagWireless) {
            if (status.wireless_connected) {
                diagWireless.textContent = `✓ ${status.wireless_ip || 'Connected'}`;
                diagWireless.className = 'diag-value success';
            } else if (status.wireless_ip) {
                diagWireless.textContent = `○ ${status.wireless_ip} (standby)`;
                diagWireless.className = 'diag-value';
            } else {
                diagWireless.textContent = 'Not connected';
                diagWireless.className = 'diag-value';
            }
        }
        
        if (diagLatency) {
            if (status.latency_ms) {
                diagLatency.textContent = `${status.latency_ms}ms`;
                if (status.latency_ms < 50) {
                    diagLatency.className = 'diag-value success';
                } else if (status.latency_ms < 200) {
                    diagLatency.className = 'diag-value';
                } else {
                    diagLatency.className = 'diag-value warning';
                }
            } else {
                diagLatency.textContent = '--';
                diagLatency.className = 'diag-value';
            }
        }
        
        if (diagQuality) {
            if (status.quality && status.quality !== 'unknown') {
                diagQuality.textContent = status.quality.charAt(0).toUpperCase() + status.quality.slice(1);
                if (status.quality === 'excellent' || status.quality === 'good') {
                    diagQuality.className = 'diag-value success';
                } else if (status.quality === 'fair') {
                    diagQuality.className = 'diag-value warning';
                } else {
                    diagQuality.className = 'diag-value error';
                }
            } else {
                diagQuality.textContent = '--';
                diagQuality.className = 'diag-value';
            }
        }
    }
    
    // Public API
    return {
        init,
        loadSettings,
        closeDropdown,
        updateDiagnostics
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Settings.init();
});
