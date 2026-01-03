/**
 * VR System Monitor - Settings UI
 */

const Settings = (function() {
    let isOpen = false;
    
    function init() {
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
        
        // Poll interval change
        document.querySelectorAll('input[name="pollInterval"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                saveSetting('poll_interval_seconds', parseInt(e.target.value));
            });
        });
        
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
        
        // Poll interval
        const interval = settings.poll_interval_seconds || 10;
        const intervalRadio = document.querySelector(`input[name="pollInterval"][value="${interval}"]`);
        if (intervalRadio) intervalRadio.checked = true;
        
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
