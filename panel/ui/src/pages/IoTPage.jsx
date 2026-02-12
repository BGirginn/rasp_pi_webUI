import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { RefreshCw, Wifi, Activity, AlertCircle, Thermometer, Droplets, Sun, Zap, Volume2, Fingerprint, ChevronRight } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';

export function IoTPage({ onDeviceClick }) {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [manualIp, setManualIp] = useState('');
    const [manualPort, setManualPort] = useState(80);
    const [manualName, setManualName] = useState('');
    const [manualLoading, setManualLoading] = useState(false);
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);

    // Load initial devices
    const loadDevices = async () => {
        try {
            const response = await api.get('/iot/devices');
            setDevices(response.data || []);
            setError(null);
        } catch (err) {
            console.error('Failed to load IoT devices:', err);
            setError('Failed to load devices.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDevices();

        // Polling for real-time updates (every 2 seconds)
        const pollInterval = setInterval(() => {
            loadDevices();
        }, 2000);

        // Also connect to SSE for real-time updates (backup)
        // Correct SSE endpoint is `/api/sse/telemetry` (token is passed as query param).
        const eventSource = api.createSSE('/sse/telemetry', (data, type) => {
            if (type === 'iot_update') {
                setDevices(data);
            }
        });

        return () => {
            clearInterval(pollInterval);
            if (eventSource) eventSource.close();
        };
    }, []);

    // Sensor Icon Helper
    const getSensorIcon = (type) => {
        switch (type?.toLowerCase()) {
            case 'temperature': return Thermometer;
            case 'humidity': return Droplets;
            case 'light': return Sun;
            case 'sound': case 'noise': return Volume2;
            case 'touch': return Fingerprint;
            case 'voltage': return Zap;
            default: return Activity;
        }
    };

    // Add simulated devices for testing
    const simulateDevices = async () => {
        try {
            const response = await api.post('/iot/devices/simulate');
            if (response.data) {
                loadDevices();
            }
        } catch (err) {
            console.error('Failed to add simulated devices:', err);
            setError('Failed to add simulated devices.');
        }
    };

    // Clear all devices
    const clearDevices = async () => {
        try {
            await api.post('/iot/devices/clear');
            setDevices([]);
        } catch (err) {
            console.error('Failed to clear devices:', err);
        }
    };

    // Handle device card click
    const handleDeviceClick = (deviceId) => {
        if (onDeviceClick) {
            onDeviceClick(deviceId);
        }
    };

    const addManualDevice = async () => {
        if (manualLoading) return;
        const ip = manualIp.trim();
        if (!ip) return;

        setManualLoading(true);
        setError(null);
        try {
            const response = await api.post('/iot/devices/manual', {
                ip,
                port: Number(manualPort) || 80,
                name: manualName.trim() || null,
                probe: true,
            });
            const createdId = response?.data?.device_id;
            await loadDevices();
            setManualIp('');
            setManualName('');
            if (createdId) handleDeviceClick(createdId);
        } catch (err) {
            console.error('Failed to add device manually:', err);
            setError(err.response?.data?.detail?.message || err.response?.data?.detail || 'Cihaz eklenemedi.');
        } finally {
            setManualLoading(false);
        }
    };

    return (
        <div className="animate-fade-in">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
                        IoT Dashboard
                    </h1>
                    <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                        Auto-discovered IoT sensors and real-time data
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {devices.length === 0 && (
                        <button
                            onClick={simulateDevices}
                            className={`px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 transition-opacity`}
                        >
                            + Simulate Devices
                        </button>
                    )}
                    {devices.length > 0 && (
                        <button
                            onClick={clearDevices}
                            className={`px-3 py-2 rounded-lg text-sm ${isDarkMode ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'bg-red-50 text-red-500 hover:bg-red-100'} transition-colors`}
                        >
                            Clear All
                        </button>
                    )}
                    <button
                        onClick={loadDevices}
                        className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
                    >
                        <RefreshCw size={20} />
                    </button>
                </div>
            </div>

            {/* Manual device add (useful when mDNS isn't available) */}
            <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-xl border rounded-2xl p-5 mb-8`}>
                <div className="flex items-center justify-between gap-4 mb-3">
                    <div>
                        <h2 className="font-bold">IP ile Cihaz Ekle</h2>
                        <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                            mDNS çalışmıyorsa ESP’nin IP adresini girerek ekleyebilirsin (örn: 192.168.0.104)
                        </p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                        value={manualIp}
                        onChange={(e) => setManualIp(e.target.value)}
                        placeholder="IP (örn: 192.168.0.104)"
                        className={`px-3 py-2 rounded-lg text-sm outline-none border ${isDarkMode ? 'bg-black/30 border-white/10 text-white placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400'}`}
                        disabled={manualLoading}
                    />
                    <input
                        value={manualPort}
                        onChange={(e) => setManualPort(e.target.value)}
                        placeholder="Port"
                        className={`px-3 py-2 rounded-lg text-sm outline-none border ${isDarkMode ? 'bg-black/30 border-white/10 text-white placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400'}`}
                        disabled={manualLoading}
                        inputMode="numeric"
                    />
                    <input
                        value={manualName}
                        onChange={(e) => setManualName(e.target.value)}
                        placeholder="İsim (opsiyonel)"
                        className={`px-3 py-2 rounded-lg text-sm outline-none border ${isDarkMode ? 'bg-black/30 border-white/10 text-white placeholder:text-gray-500' : 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400'}`}
                        disabled={manualLoading}
                    />
                    <button
                        onClick={addManualDevice}
                        disabled={manualLoading || !manualIp.trim()}
                        className={`px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        {manualLoading ? 'Ekleniyor...' : 'Cihazı Ekle'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl flex items-center gap-3">
                    <AlertCircle /> {error}
                </div>
            )}

            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-64 rounded-2xl bg-gray-100/5 animate-pulse" />
                    ))}
                </div>
            ) : devices.length === 0 ? (
                <div className={`p-16 text-center rounded-3xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'}`}>
                    <Wifi size={48} className="mx-auto mb-4 opacity-50" />
                    <h3 className="text-xl font-bold mb-2">No Devices Found</h3>
                    <p className="text-gray-500">
                        Make sure your IoT devices are powered on and connected to the same network.
                        <br />They should be broadcasting mDNS service <code>_iot-device._tcp</code>.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <AnimatePresence>
                        {devices.map(device => (
                            <motion.div
                                key={device.id}
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                onClick={() => handleDeviceClick(device.id)}
                                className={`${isDarkMode ? 'bg-black/40 border-white/10 hover:border-white/20' : 'bg-white/80 border-gray-200 hover:border-gray-300'} backdrop-blur-xl border rounded-2xl p-6 shadow-lg cursor-pointer transition-all hover:scale-[1.02] group`}
                            >
                                <div className="flex justify-between items-start mb-6">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center bg-gradient-to-br ${themeColors.secondary}`}>
                                            <Wifi className="text-white" size={20} />
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-lg">{device.name}</h3>
                                            <div className="text-xs font-mono text-gray-500">{device.ip}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${device.status === 'online' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                                            {device.status}
                                        </span>
                                        <ChevronRight size={16} className="text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    {device.sensors && device.sensors.length > 0 ? (
                                        device.sensors.slice(0, 3).map((sensor, idx) => {
                                            const Icon = getSensorIcon(sensor.type);
                                            return (
                                                <div key={idx} className={`flex items-center justify-between p-3 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                                    <div className="flex items-center gap-3">
                                                        <Icon size={16} className="text-gray-400" />
                                                        <span className="text-sm font-medium opacity-80 capitalize">{sensor.type}</span>
                                                    </div>
                                                    <div className="font-bold font-mono text-lg">
                                                        {sensor.value} <span className="text-xs text-gray-500">{sensor.unit}</span>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="text-center py-4 text-gray-500 text-sm italic">
                                            No sensors data available
                                        </div>
                                    )}
                                    {device.sensors && device.sensors.length > 3 && (
                                        <div className="text-center text-xs text-gray-500">
                                            +{device.sensors.length - 3} more sensors
                                        </div>
                                    )}
                                </div>

                                <div className="mt-4 pt-4 border-t border-gray-500/10 text-[10px] text-gray-500 flex justify-between items-center">
                                    <span>ID: {device.id}</span>
                                    <span className="flex items-center gap-1">
                                        Last seen: {new Date(device.last_seen * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                        <ChevronRight size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </span>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            )}
        </div>
    );
}
