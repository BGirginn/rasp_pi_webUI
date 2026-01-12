import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { api } from '../services/api';

const DashboardContext = createContext(undefined);

const defaultWidgets = [
    { id: 'cpu-1', type: 'cpu', width: 1, height: 1, variant: 'graphic', position: { row: 0, col: 0 } },
    { id: 'memory-1', type: 'memory', width: 1, height: 1, variant: 'graphic', position: { row: 0, col: 1 } },
    { id: 'disk-1', type: 'disk', width: 1, height: 1, variant: 'graphic', position: { row: 0, col: 2 } },
    { id: 'temp-1', type: 'temperature', width: 1, height: 1, variant: 'graphic', position: { row: 0, col: 3 } },
    { id: 'perf-1', type: 'performance', width: 2, height: 2, variant: 'graphic', position: { row: 1, col: 0 } },
    { id: 'network-1', type: 'network', width: 2, height: 2, variant: 'graphic', position: { row: 1, col: 2 } },
    { id: 'processes-1', type: 'processes', width: 2, height: 2, variant: 'list', position: { row: 3, col: 0 } },
    { id: 'system-1', type: 'system-info', width: 2, height: 2, variant: 'list', position: { row: 3, col: 2 } },
];

export function DashboardProvider({ children }) {
    const [widgets, setWidgets] = useState(defaultWidgets);

    // Live Data State
    const [stats, setStats] = useState({
        cpu: 0, memory: 0, memUsedGb: 0, memTotalGb: 0,
        disk: 0, diskUsedGb: 0, diskTotalGb: 0,
        temp: 0, uptime: 0, hostname: '...', os: '...', machine: '...',
        netTx: 0, netRx: 0, netTxSpeed: 0, netRxSpeed: 0,
        // Load averages
        load1m: 0, load5m: 0, load15m: 0,
        // Extended system info
        model: '...', kernel: '...', ip: '...'
    });
    const [history, setHistory] = useState({
        cpu: Array(20).fill(0),
        memory: Array(20).fill(0),
        networkRx: Array(20).fill(0),
        networkTx: Array(20).fill(0),
        // New history arrays for widgets
        temp: Array(20).fill(0),
        disk: Array(20).fill(0)
    });
    const [resources, setResources] = useState([]);
    const [processes, setProcesses] = useState([]);
    const [alerts, setAlerts] = useState([]);

    const lastNetStats = useRef({ tx: 0, rx: 0, time: Date.now() });

    useEffect(() => {
        loadDashboardData();
        const interval = setInterval(loadDashboardData, 2000);
        return () => clearInterval(interval);
    }, []);

    const loadDashboardData = async () => {
        try {
            const [telemetryRes, resourcesRes, alertsRes, systemInfoRes] = await Promise.all([
                api.get('/telemetry/current').catch(() => ({ data: {} })),
                api.get('/resources').catch(() => ({ data: [] })),
                api.get('/alerts').catch(() => ({ data: [] })),
                api.get('/system/info').catch(() => ({ data: {} }))
            ]);

            const metrics = telemetryRes.data?.metrics || {};
            const systemInfo = telemetryRes.data?.system || systemInfoRes.data || {};

            // Network Speed Calculation
            const currentTx = metrics['net.all.bytes_sent'] || (metrics['net.wlan0.tx_bytes'] || 0) + (metrics['net.eth0.tx_bytes'] || 0);
            const currentRx = metrics['net.all.bytes_recv'] || (metrics['net.wlan0.rx_bytes'] || 0) + (metrics['net.eth0.rx_bytes'] || 0);
            const now = Date.now();
            const timeDiff = (now - lastNetStats.current.time) / 1000; // seconds

            let txSpeed = 0;
            let rxSpeed = 0;

            if (timeDiff > 0 && lastNetStats.current.tx > 0) {
                txSpeed = Math.max(0, (currentTx - lastNetStats.current.tx) / timeDiff);
                rxSpeed = Math.max(0, (currentRx - lastNetStats.current.rx) / timeDiff);
            }

            lastNetStats.current = { tx: currentTx, rx: currentRx, time: now };

            // Handle both disk._ and disk._root keys (fallback between them)
            const diskPct = metrics['disk._root.used_pct'] || metrics['disk._.used_pct'] || 0;
            const diskUsedGb = metrics['disk._root.used_gb'] || metrics['disk._.used_gb'] || 0;
            const diskTotalGb = metrics['disk._root.total_gb'] || metrics['disk._.total_gb'] || 0;

            // Update Stats
            const newStats = {
                cpu: Math.round(metrics['host.cpu.pct_total'] || 0),
                memory: Math.round(metrics['host.mem.pct'] || 0),
                memUsedGb: ((metrics['host.mem.used_mb'] || 0) / 1024).toFixed(1),
                memTotalGb: ((metrics['host.mem.total_mb'] || 0) / 1024).toFixed(1),
                disk: Math.round(diskPct),
                diskUsedGb: diskUsedGb.toFixed ? diskUsedGb.toFixed(1) : diskUsedGb,
                diskTotalGb: diskTotalGb.toFixed ? diskTotalGb.toFixed(1) : diskTotalGb,
                temp: Math.round(metrics['host.temp.cpu_c'] || 0),
                uptime: metrics['host.uptime.seconds'] || systemInfo.uptime_seconds || 0,
                hostname: systemInfo.hostname || 'Unknown',
                os: systemInfo.os || systemInfo.os_info || 'Unknown',
                machine: systemInfo.machine || systemInfo.architecture || 'Unknown',
                netTx: currentTx,
                netRx: currentRx,
                netTxSpeed: txSpeed,
                netRxSpeed: rxSpeed,
                // Load averages from telemetry
                load1m: metrics['host.load.1m'] || 0,
                load5m: metrics['host.load.5m'] || 0,
                load15m: metrics['host.load.15m'] || 0,
                // Extended system info (from /system/info)
                model: systemInfo.model || systemInfo.machine || systemInfo.architecture || 'Unknown',
                kernel: systemInfo.kernel || systemInfo.os || 'N/A',
                ip: 'N/A' // Will be fetched from network interfaces
            };

            setStats(newStats);
            setResources(Array.isArray(resourcesRes.data) ? resourcesRes.data : []);
            setAlerts(Array.isArray(alertsRes.data) ? alertsRes.data : []);

            // Limit history to 20 points (including temp and disk)
            setHistory(prev => ({
                cpu: [...prev.cpu.slice(1), newStats.cpu],
                memory: [...prev.memory.slice(1), newStats.memory],
                networkRx: [...prev.networkRx.slice(1), newStats.netRxSpeed],
                networkTx: [...prev.networkTx.slice(1), newStats.netTxSpeed],
                temp: [...prev.temp.slice(1), newStats.temp],
                disk: [...prev.disk.slice(1), newStats.disk]
            }));

            // Fetch Processes separately to avoid blocking main stats if relying on slow method
            api.get('/system/processes')
                .then(res => setProcesses(Array.isArray(res.data) ? res.data : []))
                .catch(err => console.warn('Failed to fetch processes:', err));

        } catch (err) {
            console.error('Failed to load dashboard data:', err);
        }
    };

    const addWidget = (widget) => {
        setWidgets([...widgets, widget]);
    };

    const removeWidget = (id) => {
        setWidgets(widgets.filter(w => w.id !== id));
    };

    const updateWidget = (id, updates) => {
        setWidgets(widgets.map(w => w.id === id ? { ...w, ...updates } : w));
    };

    const moveWidget = (id, position) => {
        setWidgets(widgets.map(w => w.id === id ? { ...w, position } : w));
    };

    const resizeWidget = (id, width, height) => {
        setWidgets(widgets.map(w => w.id === id ? { ...w, width, height } : w));
    };

    const changeWidgetVariant = (id, variant) => {
        setWidgets(widgets.map(w => w.id === id ? { ...w, variant } : w));
    };

    return (
        <DashboardContext.Provider value={{
            widgets,
            stats,
            history,
            resources,
            processes,
            alerts,
            addWidget,
            removeWidget,
            updateWidget,
            moveWidget,
            resizeWidget,
            changeWidgetVariant,
        }}>
            {children}
        </DashboardContext.Provider>
    );
}

export function useDashboard() {
    const context = useContext(DashboardContext);
    if (context === undefined) {
        throw new Error('useDashboard must be used within a DashboardProvider');
    }
    return context;
}
