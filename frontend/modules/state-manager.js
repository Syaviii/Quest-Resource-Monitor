/**
 * VR System Monitor - State Manager
 * Centralized state management with pub/sub pattern
 */

const StateManager = (function() {
    // Initial state structure
    const state = {
        app: {
            initialized: false,
            online: false,
            lastUpdate: null,
            error: null
        },
        devices: {
            pc: {
                status: 'disconnected',
                metrics: {
                    cpu: null,
                    ram: null,
                    ram_total: null,
                    disk: null,
                    disk_total: null
                }
            },
            quest_3: {
                status: 'disconnected',
                metrics: {
                    cpu: null,
                    ram: null,
                    ram_total: null,
                    temp: null,
                    battery: null
                }
            }
        },
        ui: {
            graphsOpen: {
                pc_cpu: false,
                pc_ram: false,
                pc_disk: false,
                quest_cpu: false,
                quest_ram: false,
                quest_temp: false,
                quest_battery: false
            },
            recording: {
                active: false,
                sessionId: null,
                elapsed: 0,
                startTime: null
            },
            diskModalOpen: false
        },
        data: {
            histories: {
                pc: { cpu: [], ram: [], disk: [] },
                quest_3: { cpu: [], ram: [], temp: [], battery: [] }
            },
            disks: []
        }
    };
    
    // Subscribers for state changes
    const subscribers = new Map();
    
    /**
     * Get the full state or a specific path
     */
    function getState(path = null) {
        if (!path) return state;
        
        const keys = path.split('.');
        let value = state;
        for (const key of keys) {
            value = value?.[key];
        }
        return value;
    }
    
    /**
     * Set a value in the state by path
     */
    function setState(path, value) {
        const keys = path.split('.');
        let obj = state;
        
        for (let i = 0; i < keys.length - 1; i++) {
            obj = obj[keys[i]];
        }
        
        const lastKey = keys[keys.length - 1];
        const oldValue = obj[lastKey];
        obj[lastKey] = value;
        
        // Broadcast change
        broadcastChange(path, value, oldValue);
    }
    
    /**
     * Subscribe to state changes
     */
    function subscribe(path, callback) {
        if (!subscribers.has(path)) {
            subscribers.set(path, new Set());
        }
        subscribers.get(path).add(callback);
        
        // Return unsubscribe function
        return () => {
            subscribers.get(path)?.delete(callback);
        };
    }
    
    /**
     * Broadcast a state change to subscribers
     */
    function broadcastChange(path, newValue, oldValue) {
        // Exact path subscribers
        if (subscribers.has(path)) {
            subscribers.get(path).forEach(callback => {
                try {
                    callback(newValue, oldValue, path);
                } catch (e) {
                    console.error('Subscriber error:', e);
                }
            });
        }
        
        // Parent path subscribers (for nested updates)
        const parts = path.split('.');
        for (let i = 1; i < parts.length; i++) {
            const parentPath = parts.slice(0, i).join('.');
            if (subscribers.has(parentPath)) {
                const parentValue = getState(parentPath);
                subscribers.get(parentPath).forEach(callback => {
                    try {
                        callback(parentValue, null, path);
                    } catch (e) {
                        console.error('Subscriber error:', e);
                    }
                });
            }
        }
        
        // Wildcard subscribers
        if (subscribers.has('*')) {
            subscribers.get('*').forEach(callback => {
                try {
                    callback(newValue, oldValue, path);
                } catch (e) {
                    console.error('Subscriber error:', e);
                }
            });
        }
    }
    
    /**
     * Update device metrics from API response
     */
    function updateDeviceMetrics(deviceId, metrics) {
        if (!metrics) return;
        
        const path = `devices.${deviceId}.metrics`;
        const current = getState(path);
        
        setState(path, {
            ...current,
            cpu: metrics.cpu ?? current.cpu,
            ram: metrics.ram ?? current.ram,
            ram_total: metrics.ram_total ?? current.ram_total,
            temp: metrics.temp ?? current.temp,
            battery: metrics.battery ?? current.battery,
            disk: metrics.disk ?? current.disk,
            disk_total: metrics.disk_total ?? current.disk_total
        });
        
        setState(`devices.${deviceId}.status`, 'connected');
    }
    
    /**
     * Update device status
     */
    function updateDeviceStatus(deviceId, status) {
        setState(`devices.${deviceId}.status`, status);
    }
    
    /**
     * Toggle graph visibility
     */
    function toggleGraph(deviceId, metric) {
        const key = `${deviceId.replace('_', '')}_${metric}`;
        const path = `ui.graphsOpen.${key}`;
        const current = getState(path);
        setState(path, !current);
        return !current;
    }
    
    /**
     * Update recording state
     */
    function updateRecording(recording) {
        const current = getState('ui.recording');
        setState('ui.recording', { ...current, ...recording });
    }
    
    /**
     * Update metrics history
     */
    function updateHistory(deviceId, metric, data) {
        setState(`data.histories.${deviceId}.${metric}`, data);
    }
    
    /**
     * Update disks list
     */
    function updateDisks(disks) {
        setState('data.disks', disks);
    }
    
    // Public API
    return {
        getState,
        setState,
        subscribe,
        updateDeviceMetrics,
        updateDeviceStatus,
        toggleGraph,
        updateRecording,
        updateHistory,
        updateDisks
    };
})();
