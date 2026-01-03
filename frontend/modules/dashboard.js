/**
 * VR System Monitor - Dashboard
 * UI logic.
 */

const Dashboard = (function() {
    
    function init() {
        Gauge.initializeAll();
        
        setupEventListeners();
        setupStateSubscriptions();
        
        console.log('dashboard init');
    }
    
    function setupEventListeners() {
        // Graph toggle buttons
        document.querySelectorAll('.graph-toggle').forEach(button => {
            button.addEventListener('click', handleGraphToggle);
        });
        
        // Record button
        const recordButton = document.getElementById('recordButton');
        if (recordButton) {
            recordButton.addEventListener('click', handleRecordClick);
        }
        
        // Disk select button
        const diskButton = document.getElementById('diskSelectButton');
        if (diskButton) {
            diskButton.addEventListener('click', openDiskModal);
        }
        
        // Disk modal close
        const modalClose = document.getElementById('diskModalClose');
        if (modalClose) {
            modalClose.addEventListener('click', closeDiskModal);
        }
        
        // Modal backdrop click
        const modal = document.getElementById('diskModal');
        if (modal) {
            modal.querySelector('.modal-backdrop')?.addEventListener('click', closeDiskModal);
        }
    }
    
    function setupStateSubscriptions() {
        // device status
        StateManager.subscribe('devices.pc.status', (status) => {
            updateDeviceStatusUI('pc', status);
        });
        
        StateManager.subscribe('devices.quest_3.status', (status) => {
            updateDeviceStatusUI('quest_3', status);
            updateQuestCardState(status);
        });
        
        // Recording state changes
        StateManager.subscribe('ui.recording', (recording) => {
            updateRecordingUI(recording);
        });
    }
    
    /**
     * toggle graph visibility
     */
    async function handleGraphToggle(event) {
        const button = event.currentTarget;
        const deviceId = button.dataset.device;
        const metric = button.dataset.metric;
        
        const isOpen = StateManager.toggleGraph(deviceId, metric);
        
        button.classList.toggle('active', isOpen);
        Graph.toggleGraphVisibility(deviceId, metric, isOpen);
        
        if (isOpen) {
            button.classList.add('loading');
            
            try {
                const response = await APIClient.getMetricsHistory(deviceId, metric, 60);
                if (response.success && response.data) {
                    Graph.createChart(deviceId, metric, response.data.data);
                    StateManager.updateHistory(deviceId, metric, response.data.data);
                }
            } catch (error) {
                console.error('history fetch failed:', error);
            } finally {
                button.classList.remove('loading');
            }
        } else {
            Graph.destroyChart(deviceId, metric);
        }
    }
    
    /**
     * start/stop recording
     */
    async function handleRecordClick() {
        const recording = StateManager.getState('ui.recording');
        
        try {
            if (recording.active) {
                // Stop recording
                const response = await APIClient.stopRecording();
                if (response.success) {
                    StateManager.updateRecording({
                        active: false,
                        sessionId: null,
                        elapsed: 0,
                        startTime: null
                    });
                }
            } else {
                // Start recording
                const response = await APIClient.startRecording();
                if (response.success && response.data) {
                    StateManager.updateRecording({
                        active: true,
                        sessionId: response.data.session_id,
                        elapsed: 0,
                        startTime: response.data.start_time
                    });
                    startRecordingTimer();
                }
            }
        } catch (error) {
            console.error('Recording error:', error);
        }
    }
    
    /**
     * count up timer
     */
    let recordingInterval = null;
    
    function startRecordingTimer() {
        if (recordingInterval) {
            clearInterval(recordingInterval);
        }
        
        recordingInterval = setInterval(() => {
            const recording = StateManager.getState('ui.recording');
            if (recording.active && recording.startTime) {
                const elapsed = Math.floor(Date.now() / 1000) - recording.startTime;
                StateManager.setState('ui.recording.elapsed', elapsed);
                updateTimerDisplay(elapsed);
            }
        }, 1000);
    }
    
    function stopRecordingTimer() {
        if (recordingInterval) {
            clearInterval(recordingInterval);
            recordingInterval = null;
        }
    }
    
    /**
     * draw timer HH:MM:SS
     */
    function updateTimerDisplay(elapsed) {
        const timer = document.getElementById('recordingTimer');
        if (!timer) return;
        
        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);
        const seconds = elapsed % 60;
        
        timer.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    
    /**
     * toggle record button state
     */
    function updateRecordingUI(recording) {
        const button = document.getElementById('recordButton');
        const timer = document.getElementById('recordingTimer');
        
        if (!button || !timer) return;
        
        if (recording.active) {
            button.classList.add('active');
            timer.classList.add('active');
        } else {
            button.classList.remove('active');
            timer.classList.remove('active');
            timer.textContent = '00:00:00';
            stopRecordingTimer();
        }
    }
    
    /**
     * update red/green dots
     */
    function updateDeviceStatusUI(deviceId, status) {
        const elementId = deviceId === 'pc' ? 'pcStatus' : 'questStatus';
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const indicator = element.querySelector('.status-indicator');
        const text = element.querySelector('.status-text');
        
        if (status === 'connected') {
            indicator?.classList.remove('disconnected');
            indicator?.classList.add('connected');
            text.textContent = deviceId === 'pc' ? 'PC Connected' : 'Quest 3 Connected';
            element.classList.remove('disconnected');
        } else {
            indicator?.classList.remove('connected');
            indicator?.classList.add('disconnected');
            text.textContent = deviceId === 'pc' ? 'PC Disconnected' : 'Quest 3 Disconnected';
            element.classList.add('disconnected');
        }
    }
    
    /**
     * dim quest card if offline
     */
    function updateQuestCardState(status) {
        const card = document.getElementById('questCard');
        const connected = document.getElementById('questConnected');
        const disconnected = document.getElementById('questDisconnected');
        
        if (!card || !connected || !disconnected) return;
        
        if (status === 'connected') {
            card.classList.remove('disconnected');
            connected.classList.remove('hidden');
            disconnected.classList.add('hidden');
        } else {
            card.classList.add('disconnected');
            connected.classList.add('hidden');
            disconnected.classList.remove('hidden');
            
            // Disable Quest gauges
            ['cpu', 'ram', 'temp', 'battery'].forEach(metric => {
                Gauge.disableGauge('quest_3', metric);
            });
        }
    }
    
    /**
     * refresh ui numbers
     */
    function updateMetrics(data) {
        if (!data) return;
        
        // Update PC metrics
        if (data.pc) {
            StateManager.updateDeviceMetrics('pc', data.pc);
            
            Gauge.updateGauge('pc', 'cpu', data.pc.cpu);
            Gauge.updateGauge('pc', 'ram', data.pc.ram, data.pc.ram_total);
            
            // Update open graphs
            updateOpenGraphs('pc', data.pc);
        }
        
        // Update disk metrics separately (fetched dynamically)
        updateDiskMetrics();
        
        // Update Quest metrics
        if (data.quest_3) {
            StateManager.updateDeviceMetrics('quest_3', data.quest_3);
            StateManager.updateDeviceStatus('quest_3', 'connected');
            
            Gauge.updateGauge('quest_3', 'cpu', data.quest_3.cpu);
            Gauge.updateGauge('quest_3', 'ram', data.quest_3.ram, data.quest_3.ram_total);
            Gauge.updateGauge('quest_3', 'temp', data.quest_3.temp);
            Gauge.updateGauge('quest_3', 'battery', data.quest_3.battery);
            
            // Update open graphs
            updateOpenGraphs('quest_3', data.quest_3);
        } else {
            StateManager.updateDeviceStatus('quest_3', 'disconnected');
        }
        
        // Update battery stats (charge rate & ETA)
        if (data.battery_stats) {
            updateBatteryStats(data.battery_stats);
        }
    }
    
    function updateNetworkStats(data) {
        if (!data) return;
        
        const updateDeviceNet = (prefix, stats) => {
            if (!stats) return;
            
            const dlEl = document.getElementById(`${prefix}-net-download`);
            const ulEl = document.getElementById(`${prefix}-net-upload`);
            const avgEl = document.getElementById(`${prefix}-net-avg`);
            
            if (dlEl) {
                dlEl.textContent = `${stats.download_mbps.toFixed(2)} MB/s`;
                dlEl.className = stats.download_mbps > 0.1 ? 'network-value active' : 'network-value idle';
            }
            
            if (ulEl) {
                ulEl.textContent = `${stats.upload_mbps.toFixed(2)} MB/s`;
                ulEl.className = stats.upload_mbps > 0.1 ? 'network-value active' : 'network-value idle';
            }
            
            if (avgEl) {
                avgEl.textContent = `Avg: ${stats.avg_download_5min.toFixed(2)} / ${stats.avg_upload_5min.toFixed(2)} MB/s`;
            }
        };
        
        // Update PC stats
        updateDeviceNet('pc', data.pc);
        
        // Update Quest stats
        updateDeviceNet('quest', data.quest_3);
    }
    
    /**
     * draw storage bar
     */
    function updateQuestStorage(stats) {
        if (!stats) return;
        
        const textEl = document.getElementById('quest-storage-text');
        const barEl = document.getElementById('quest-storage-bar');
        const freeEl = document.getElementById('quest-storage-free');
        const pctEl = document.getElementById('quest-storage-percent');
        
        // Update text: "350.5 / 512.0 GB"
        if (textEl) {
            textEl.textContent = `${stats.used_gb.toFixed(1)} / ${stats.total_gb.toFixed(1)} GB`;
        }
        
        // Update progress bar
        if (barEl) {
            barEl.style.width = `${stats.percent_used}%`;
            
            if (stats.percent_used > 90) {
                barEl.style.backgroundColor = 'var(--status-alert)';
            } else if (stats.percent_used > 75) {
                barEl.style.backgroundColor = 'var(--status-warning)';
            } else {
                barEl.style.backgroundColor = 'var(--accent-primary)';
            }
        }
        
        // Update details
        if (freeEl) freeEl.textContent = `${stats.free_gb.toFixed(1)} GB free`;
        if (pctEl) pctEl.textContent = `${stats.percent_used}% used`;
    }

    /**
     * show battery info
     */
    function updateBatteryStats(stats) {
        const rateEl = document.getElementById('quest-3-battery-rate');
        const etaEl = document.getElementById('quest-3-battery-eta');
        const statusEl = document.getElementById('quest-3-battery-status');
        
        if (!rateEl || !etaEl) return;
        
        // Update charge rate display
        if (stats.charge_rate !== undefined && stats.charge_rate !== null) {
            const rate = stats.charge_rate;
            if (Math.abs(rate) < 0.5) {
                rateEl.textContent = 'Stable';
                rateEl.className = 'battery-rate';
            } else if (rate > 0) {
                rateEl.textContent = `Charging @ ${rate.toFixed(1)}%/hr`;
                rateEl.className = 'battery-rate charging';
            } else {
                rateEl.textContent = `Discharging @ ${Math.abs(rate).toFixed(1)}%/hr`;
                rateEl.className = 'battery-rate discharging';
            }
        } else {
            rateEl.textContent = '—';
            rateEl.className = 'battery-rate';
        }
        
        // Update ETA display
        if (stats.eta_text) {
            etaEl.textContent = stats.eta_text;
            
            // Color code based on urgency
            if (stats.eta_minutes !== null && !stats.is_charging) {
                if (stats.eta_minutes < 15) {
                    etaEl.className = 'battery-eta alert';
                } else if (stats.eta_minutes < 30) {
                    etaEl.className = 'battery-eta warning';
                } else {
                    etaEl.className = 'battery-eta';
                }
            } else {
                etaEl.className = 'battery-eta';
            }
        } else {
            etaEl.textContent = '—';
            etaEl.className = 'battery-eta';
        }
        
        // Update status label
        if (statusEl) {
            if (stats.is_charging) {
                statusEl.textContent = 'charging';
            } else {
                statusEl.textContent = 'remaining';
            }
        }
    }
    
    /**
     * refresh disks
     */
    async function updateDiskMetrics() {
        try {
            const response = await APIClient.getDiskMetrics();
            if (response.success && response.data && response.data.disks) {
                updateDiskRows(response.data.disks);
            }
        } catch (error) {
            console.error('Failed to fetch disk metrics:', error);
        }
    }
    
    /**
     * draw disk rows
     */
    function updateDiskRows(disks) {
        const container = document.getElementById('diskRowsContainer');
        if (!container) return;
        
        // Get current disk rows
        const existingRows = container.querySelectorAll('.disk-metric-row');
        const existingMounts = new Set();
        existingRows.forEach(row => existingMounts.add(row.dataset.mount));
        
        // Track which mounts we still need
        const activeMounts = new Set(disks.map(d => d.mount_point));
        
        // Remove rows for unselected disks
        existingRows.forEach(row => {
            if (!activeMounts.has(row.dataset.mount)) {
                row.remove();
            }
        });
        
        // Add/update rows for selected disks
        disks.forEach(disk => {
            const diskId = sanitizeDiskId(disk.mount_point);
            let row = document.getElementById(`pc-disk-${diskId}-row`);
            
            if (!row) {
                // Create new row
                row = createDiskRow(disk);
                container.appendChild(row);
            }
            
            // Update the gauge
            Gauge.updateGauge('pc', `disk-${diskId}`, disk.used_gb, disk.total_gb);
        });
        
        // Show message if no disks selected
        if (disks.length === 0 && !container.querySelector('.no-disks-message')) {
            container.innerHTML = '<div class="no-disks-message">No disks selected. Click ⚙ to add.</div>';
        } else if (disks.length > 0) {
            const msg = container.querySelector('.no-disks-message');
            if (msg) msg.remove();
        }
    }
    
    /**
     * clean disk name
     */
    function sanitizeDiskId(mountPoint) {
        return mountPoint.replace(/[\\/:]/g, '').toLowerCase();
    }
    
    /**
     * html template for disk row
     */
    function createDiskRow(disk) {
        const diskId = sanitizeDiskId(disk.mount_point);
        const rowId = `pc-disk-${diskId}-row`;
        
        const wrapper = document.createElement('div');
        wrapper.className = 'disk-metric-row';
        wrapper.dataset.mount = disk.mount_point;
        
        wrapper.innerHTML = `
            <div class="metric-row" id="${rowId}">
                <div class="metric-left">
                    <div class="gauge-container" id="pc-disk-${diskId}-gauge">
                        <svg class="gauge" viewBox="0 0 200 200">
                            <circle class="gauge-bg" cx="100" cy="100" r="80" />
                            <circle class="gauge-progress" cx="100" cy="100" r="80" data-value="0" />
                            <circle class="gauge-inner" cx="100" cy="100" r="56" />
                        </svg>
                        <div class="gauge-value">
                            <span class="value-number" id="pc-disk-${diskId}-value">--</span>
                            <span class="value-unit">%</span>
                        </div>
                    </div>
                    <div class="metric-label">
                        <span class="label-primary">${disk.mount_point}</span>
                        <span class="label-secondary" id="pc-disk-${diskId}-detail">-- / -- GB</span>
                    </div>
                </div>
                <div class="metric-right">
                    <span class="status-marker normal">─</span>
                </div>
            </div>
        `;
        
        return wrapper;
    }
    
    /**
     * push new points to graph
     */
    function updateOpenGraphs(deviceId, metrics) {
        const graphsOpen = StateManager.getState('ui.graphsOpen');
        const timestamp = Math.floor(Date.now() / 1000);
        const prefix = deviceId.replace('_', '');
        
        Object.entries(metrics).forEach(([metric, value]) => {
            const key = `${prefix}_${metric}`;
            if (graphsOpen[key] && value !== null) {
                Graph.addDataPoint(deviceId, metric, timestamp, value);
            }
        });
    }
    
    /**
     * show disk picker
     */
    async function openDiskModal() {
        const modal = document.getElementById('diskModal');
        const diskList = document.getElementById('diskList');
        
        if (!modal || !diskList) return;
        
        try {
            const response = await APIClient.getAllDisks();
            if (response.success && response.data) {
                renderDiskList(response.data.disks);
                StateManager.updateDisks(response.data.disks);
            }
        } catch (error) {
            console.error('Failed to fetch disks:', error);
        }
        
        modal.classList.remove('hidden');
    }
    
    /**
     * hide disk picker
     */
    function closeDiskModal() {
        const modal = document.getElementById('diskModal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }
    
    /**
     * draw disk options
     */
    function renderDiskList(disks) {
        const diskList = document.getElementById('diskList');
        if (!diskList) return;
        
        diskList.innerHTML = '';
        
        if (disks.length === 0) {
            diskList.innerHTML = '<div class="disk-item">No disks found</div>';
            return;
        }
        
        disks.forEach(disk => {
            const item = document.createElement('div');
            item.className = 'disk-item';
            
            // Format sizes - convert to TB if > 1000 GB
            const usedDisplay = disk.used_gb > 1000 
                ? `${(disk.used_gb / 1024).toFixed(2)} TB` 
                : `${disk.used_gb.toFixed(1)} GB`;
            const totalDisplay = disk.total_gb > 1000 
                ? `${(disk.total_gb / 1024).toFixed(2)} TB` 
                : `${disk.total_gb.toFixed(1)} GB`;
            
            item.innerHTML = `
                <input type="checkbox" 
                       class="disk-checkbox" 
                       id="disk-${disk.mount_point.replace(/[\\/:]/g, '_')}"
                       data-mount="${disk.mount_point}"
                       ${disk.is_selected ? 'checked' : ''}>
                <div class="disk-info">
                    <div class="disk-name">${disk.mount_point}</div>
                    <div class="disk-details">${usedDisplay} / ${totalDisplay} (${disk.percent_used.toFixed(1)}%)</div>
                </div>
            `;
            
            // Add change listener with proper error handling
            const checkbox = item.querySelector('.disk-checkbox');
            checkbox.addEventListener('change', async (e) => {
                const originalChecked = !e.target.checked;
                checkbox.disabled = true; // Disable while processing
                
                try {
                    const response = await APIClient.setDiskSelection(disk.mount_point, e.target.checked);
                    if (!response.success) {
                        throw new Error(response.error?.message || 'Failed to update');
                    }
                    console.log(`Disk ${disk.mount_point} selection: ${e.target.checked}`);
                } catch (error) {
                    console.error('Failed to update disk selection:', error);
                    e.target.checked = originalChecked; // Revert on error
                } finally {
                    checkbox.disabled = false;
                }
            });
            
            diskList.appendChild(item);
        });
    }
    
    /**
     * backend dead
     */
    function showOfflineState() {
        StateManager.setState('app.online', false);
        // Could show a notification/overlay here
        console.warn('Backend is offline');
    }
    
    /**
     * backend alive
     */
    function showOnlineState() {
        StateManager.setState('app.online', true);
        console.log('Backend is online');
    }
    
    // Public API
    return {
        init,
        updateMetrics,
        updateDiskMetrics,
        updateBatteryStats,
        updateNetworkStats,
        updateQuestStorage,
        showOfflineState,
        showOnlineState,
        updateDeviceStatusUI,
        updateQuestCardState
    };
})();
