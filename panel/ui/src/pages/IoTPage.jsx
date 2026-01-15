import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { RefreshCw, Wifi, Activity, AlertCircle, Thermometer, Droplets, Sun, Zap, Volume2, Fingerprint } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';

export function IoTPage() {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
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

        // Connect to SSE for real-time updates
        const eventSource = api.createSSE('/telemetry/stream', (data, type) => {
            if (type === 'iot_update') {
                // data is list of devices
                setDevices(data);
            }
        });

        return () => {
            if (eventSource) eventSource.close();
        };
    }, []);

    // Sensor Icon Helper
    const getSensorIcon = (type) => {
        switch (type.toLowerCase()) {
            case 'temperature': return Thermometer;
            case 'humidity': return Droplets;
            case 'light': return Sun;
            case 'sound': return Volume2;
            case 'touch': return Fingerprint;
            case 'voltage': return Zap;
            default: return Activity;
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
                        Auto-discovered ESP32 sensors and real-time data
                    </p>
                </div>
                <button
                    onClick={loadDevices}
                    className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
                >
                    <RefreshCw size={20} />
                </button>
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
                        Make sure your ESP32 devices are powered on and connected to the same network.
                        <br />They should be broadcasting mDNS service <code>_esp-sensor._tcp</code>.
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
                                className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-xl border rounded-2xl p-6 shadow-lg`}
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
                                    <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${device.status === 'online' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                                        {device.status}
                                    </span>
                                </div>

                                <div className="space-y-3">
                                    {device.sensors && device.sensors.length > 0 ? (
                                        device.sensors.map((sensor, idx) => {
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
                                </div>

                                <div className="mt-4 pt-4 border-t border-gray-500/10 text-[10px] text-gray-500 flex justify-between">
                                    <span>ID: {device.id}</span>
                                    <span>Last seen: {new Date(device.last_seen * 1000).toLocaleTimeString()}</span>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            )}
        </div>
    );
}
