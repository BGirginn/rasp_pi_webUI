import { motion } from 'motion/react';
import { useState, useEffect, useCallback } from 'react';
import {
    ArrowLeft, RefreshCw, Wifi, WifiOff, Activity,
    Thermometer, Droplets, Sun, Zap, Volume2, Fingerprint,
    Clock, TrendingUp, TrendingDown, Minus, Power, Palette
} from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart
} from 'recharts';

export function IoTDeviceDetail({ deviceId, onBack }) {
    const [device, setDevice] = useState(null);
    const [history, setHistory] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [timeRange, setTimeRange] = useState(24); // hours
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [ledColor, setLedColor] = useState('#ff0000');
    const [ledBrightness, setLedBrightness] = useState(255);
    const [ledPowerOn, setLedPowerOn] = useState(true);
    const [ledLoading, setLedLoading] = useState(false);
    const [ledStatus, setLedStatus] = useState(null);
    const { theme, isDarkMode } = useTheme();
    const { isOperator } = useAuth();
    const themeColors = getThemeColors(theme);

    // Load device details
    const loadDevice = useCallback(async () => {
        try {
            const response = await api.get(`/iot/devices/${deviceId}`);
            setDevice(response.data);
            setError(null);
        } catch (err) {
            console.error('Failed to load device:', err);
            setError('Failed to load device details.');
        }
    }, [deviceId]);

    // Load device history
    const loadHistory = useCallback(async () => {
        try {
            const response = await api.get(`/iot/devices/${deviceId}/history?hours=${timeRange}`);
            setHistory(response.data);
        } catch (err) {
            console.error('Failed to load history:', err);
        }
    }, [deviceId, timeRange]);

    // Initial load
    useEffect(() => {
        const loadAll = async () => {
            setLoading(true);
            await loadDevice();
            await loadHistory();
            setLoading(false);
        };
        loadAll();
    }, [loadDevice, loadHistory]);

    // Auto refresh
    useEffect(() => {
        if (!autoRefresh) return;

        const interval = setInterval(() => {
            loadDevice();
            // Only refresh history every 30 seconds to avoid too many DB queries
        }, 2000);

        const historyInterval = setInterval(() => {
            loadHistory();
        }, 30000);

        return () => {
            clearInterval(interval);
            clearInterval(historyInterval);
        };
    }, [autoRefresh, loadDevice, loadHistory]);

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

    // Format timestamp for chart
    const formatTime = (timestamp) => {
        const date = new Date(timestamp * 1000);
        if (timeRange <= 6) {
            return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }
        return date.toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    };

    // Get trend icon
    const getTrendIcon = (readings) => {
        if (!readings || readings.length < 2) return Minus;
        const recent = readings.slice(-5);
        const first = recent[0]?.value || 0;
        const last = recent[recent.length - 1]?.value || 0;
        if (last > first * 1.02) return TrendingUp;
        if (last < first * 0.98) return TrendingDown;
        return Minus;
    };

    // Color for sensor type
    const getSensorColor = (type) => {
        const colors = {
            temperature: '#ef4444',
            humidity: '#3b82f6',
            light: '#eab308',
            voltage: '#22c55e',
            signal_strength: '#8b5cf6',
            noise: '#f97316',
            pressure: '#06b6d4',
            co2: '#84cc16'
        };
        return colors[type?.toLowerCase()] || '#6b7280';
    };

    const hexToRgb = (hex) => {
        const normalized = hex.replace('#', '');
        return {
            red: parseInt(normalized.substring(0, 2), 16),
            green: parseInt(normalized.substring(2, 4), 16),
            blue: parseInt(normalized.substring(4, 6), 16),
        };
    };

    const sendLedColor = async () => {
        if (!isOperator || ledLoading) return;
        setLedLoading(true);
        setLedStatus(null);

        try {
            const rgb = hexToRgb(ledColor);
            const response = await api.post(`/iot/devices/${deviceId}/led/color`, {
                red: rgb.red,
                green: rgb.green,
                blue: rgb.blue,
                brightness: ledBrightness,
                power: ledPowerOn,
                persist: true,
            });
            setLedStatus({
                type: 'success',
                text: `Renk gönderildi (${response.data?.transport || 'unknown'})`
            });
        } catch (err) {
            setLedStatus({
                type: 'error',
                text: err.response?.data?.detail?.message || err.response?.data?.detail || 'LED renk komutu gönderilemedi'
            });
        } finally {
            setLedLoading(false);
        }
    };

    const sendLedPower = async (nextState) => {
        if (!isOperator || ledLoading) return;
        setLedLoading(true);
        setLedStatus(null);

        try {
            const response = await api.post(`/iot/devices/${deviceId}/led/power`, {
                on: nextState,
                persist: true,
            });
            setLedPowerOn(nextState);
            setLedStatus({
                type: 'success',
                text: `LED ${nextState ? 'açıldı' : 'kapatıldı'} (${response.data?.transport || 'unknown'})`
            });
        } catch (err) {
            setLedStatus({
                type: 'error',
                text: err.response?.data?.detail?.message || err.response?.data?.detail || 'LED güç komutu gönderilemedi'
            });
        } finally {
            setLedLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="animate-fade-in p-8">
                <div className="flex items-center gap-4 mb-8">
                    <div className="w-10 h-10 rounded-lg bg-gray-200/10 animate-pulse" />
                    <div className="h-8 w-48 bg-gray-200/10 rounded animate-pulse" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-24 rounded-xl bg-gray-200/10 animate-pulse" />
                    ))}
                </div>
                <div className="h-64 rounded-xl bg-gray-200/10 animate-pulse" />
            </div>
        );
    }

    if (error || !device) {
        return (
            <div className="animate-fade-in p-8">
                <button
                    onClick={onBack}
                    className={`flex items-center gap-2 mb-8 ${isDarkMode ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'} transition-colors`}
                >
                    <ArrowLeft size={20} />
                    <span>Geri</span>
                </button>
                <div className="text-center py-16">
                    <WifiOff size={48} className="mx-auto mb-4 text-red-500" />
                    <h3 className="text-xl font-bold mb-2">Cihaz Bulunamadı</h3>
                    <p className="text-gray-500">{error || 'Cihaz mevcut değil veya çevrimdışı.'}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <button
                        onClick={onBack}
                        className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className={`text-3xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
                                {device.name}
                            </h1>
                            <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${device.status === 'online'
                                ? 'bg-green-500/20 text-green-500'
                                : 'bg-red-500/20 text-red-500'
                                }`}>
                                {device.status === 'online' ? 'Çevrimiçi' : 'Çevrimdışı'}
                            </span>
                        </div>
                        <p className={`mt-1 font-mono text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                            {device.ip}:{device.port}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <label className={`flex items-center gap-2 text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                        <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                            className="rounded"
                        />
                        Otomatik Yenile
                    </label>
                    <button
                        onClick={() => { loadDevice(); loadHistory(); }}
                        className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
                    >
                        <RefreshCw size={20} />
                    </button>
                </div>
            </div>

            {/* Time Range Selector */}
            <div className="flex items-center gap-2 mb-6">
                <Clock size={16} className="text-gray-400" />
                <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Zaman Aralığı:</span>
                {[1, 6, 24, 168].map(hours => (
                    <button
                        key={hours}
                        onClick={() => setTimeRange(hours)}
                        className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${timeRange === hours
                            ? `bg-gradient-to-r ${themeColors.secondary} text-white`
                            : isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                    >
                        {hours === 1 ? '1 Saat' : hours === 6 ? '6 Saat' : hours === 24 ? '24 Saat' : '7 Gün'}
                    </button>
                ))}
            </div>

            {/* LED Controls */}
            <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-xl border rounded-2xl p-6 mb-8`}>
                <div className="flex items-center justify-between gap-4 mb-5">
                    <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
                            <Palette className="text-white" size={18} />
                        </div>
                        <div>
                            <h2 className="font-bold text-lg">LED Kontrol</h2>
                            <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                                Raspberry Pi üzerinden ESP32 LED renk ve güç kontrolü
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => sendLedPower(!ledPowerOn)}
                        disabled={!isOperator || ledLoading || device.status !== 'online'}
                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                            ledPowerOn
                                ? (isDarkMode ? 'bg-green-500/15 text-green-400 hover:bg-green-500/25' : 'bg-green-50 text-green-600 hover:bg-green-100')
                                : (isDarkMode ? 'bg-red-500/15 text-red-400 hover:bg-red-500/25' : 'bg-red-50 text-red-600 hover:bg-red-100')
                        }`}
                    >
                        <Power size={15} />
                        {ledPowerOn ? 'Açık' : 'Kapalı'}
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                        <label className={`block text-xs mb-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Renk</label>
                        <div className="flex items-center gap-3">
                            <input
                                type="color"
                                value={ledColor}
                                onChange={(e) => setLedColor(e.target.value)}
                                disabled={!isOperator || ledLoading || device.status !== 'online'}
                                className="h-10 w-14 rounded cursor-pointer disabled:cursor-not-allowed"
                            />
                            <code className={`text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>{ledColor.toUpperCase()}</code>
                        </div>
                    </div>

                    <div>
                        <label className={`block text-xs mb-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                            Parlaklık: {ledBrightness}
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="255"
                            value={ledBrightness}
                            onChange={(e) => setLedBrightness(Number(e.target.value))}
                            disabled={!isOperator || ledLoading || device.status !== 'online'}
                            className="w-full"
                        />
                    </div>

                    <div className="flex md:justify-end">
                        <button
                            onClick={sendLedColor}
                            disabled={!isOperator || ledLoading || device.status !== 'online'}
                            className={`px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                            {ledLoading ? 'Gönderiliyor...' : 'Rengi Gönder'}
                        </button>
                    </div>
                </div>

                <div className="flex flex-wrap gap-2 mt-4">
                    {['#FF0000', '#00FF00', '#0000FF', '#FFFFFF', '#FFA500', '#8000FF'].map((quickColor) => (
                        <button
                            key={quickColor}
                            onClick={() => setLedColor(quickColor.toLowerCase())}
                            disabled={!isOperator || ledLoading || device.status !== 'online'}
                            className="w-7 h-7 rounded-full border border-white/20 disabled:opacity-40 disabled:cursor-not-allowed"
                            style={{ backgroundColor: quickColor }}
                            title={quickColor}
                        />
                    ))}
                </div>

                {!isOperator && (
                    <p className={`mt-3 text-xs ${isDarkMode ? 'text-yellow-400' : 'text-amber-600'}`}>
                        LED kontrolü için `admin` veya `operator` rolü gerekli.
                    </p>
                )}
                {device.status !== 'online' && (
                    <p className={`mt-3 text-xs ${isDarkMode ? 'text-red-400' : 'text-red-600'}`}>
                        Cihaz çevrimdışı görünüyor. Komut gönderimi devre dışı.
                    </p>
                )}
                {ledStatus && (
                    <p className={`mt-3 text-xs ${ledStatus.type === 'success' ? (isDarkMode ? 'text-green-400' : 'text-green-700') : (isDarkMode ? 'text-red-400' : 'text-red-600')}`}>
                        {ledStatus.text}
                    </p>
                )}
            </div>

            {/* Current Sensor Values */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
                {device.sensors?.map((sensor, idx) => {
                    const Icon = getSensorIcon(sensor.type);
                    const historyData = history?.sensors?.find(s => s.sensor_type === sensor.type);
                    const TrendIcon = getTrendIcon(historyData?.readings);

                    return (
                        <motion.div
                            key={idx}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.05 }}
                            className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-xl border rounded-xl p-4`}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <div
                                        className="w-8 h-8 rounded-lg flex items-center justify-center"
                                        style={{ backgroundColor: `${getSensorColor(sensor.type)}20` }}
                                    >
                                        <Icon size={16} style={{ color: getSensorColor(sensor.type) }} />
                                    </div>
                                    <span className="text-xs font-medium opacity-70 capitalize">{sensor.type}</span>
                                </div>
                                <TrendIcon size={14} className="text-gray-400" />
                            </div>
                            <div className="text-2xl font-bold font-mono">
                                {sensor.value}
                                <span className="text-xs text-gray-500 ml-1">{sensor.unit}</span>
                            </div>
                        </motion.div>
                    );
                })}
            </div>

            {/* Sensor Charts */}
            <div className="space-y-6">
                {history?.sensors?.map((sensorData, idx) => {
                    const chartData = sensorData.readings.map(r => ({
                        time: formatTime(r.timestamp),
                        value: r.value,
                        timestamp: r.timestamp
                    }));

                    // Downsample if too many points
                    const maxPoints = 100;
                    const step = Math.ceil(chartData.length / maxPoints);
                    const displayData = step > 1
                        ? chartData.filter((_, i) => i % step === 0)
                        : chartData;

                    const color = getSensorColor(sensorData.sensor_type);
                    const Icon = getSensorIcon(sensorData.sensor_type);

                    return (
                        <motion.div
                            key={sensorData.sensor_type}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.1 }}
                            className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-xl border rounded-2xl p-6`}
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <div
                                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                                    style={{ backgroundColor: `${color}20` }}
                                >
                                    <Icon size={20} style={{ color }} />
                                </div>
                                <div>
                                    <h3 className="font-bold capitalize">{sensorData.sensor_type}</h3>
                                    <p className="text-xs text-gray-500">
                                        {displayData.length} veri noktası • Son {timeRange} saat
                                    </p>
                                </div>
                            </div>

                            {displayData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={200}>
                                    <AreaChart data={displayData}>
                                        <defs>
                                            <linearGradient id={`gradient-${sensorData.sensor_type}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                                                <stop offset="95%" stopColor={color} stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid
                                            strokeDasharray="3 3"
                                            stroke={isDarkMode ? '#333' : '#eee'}
                                            vertical={false}
                                        />
                                        <XAxis
                                            dataKey="time"
                                            tick={{ fontSize: 10, fill: isDarkMode ? '#888' : '#666' }}
                                            tickLine={false}
                                            axisLine={false}
                                        />
                                        <YAxis
                                            tick={{ fontSize: 10, fill: isDarkMode ? '#888' : '#666' }}
                                            tickLine={false}
                                            axisLine={false}
                                            domain={['auto', 'auto']}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: isDarkMode ? '#1a1a1a' : '#fff',
                                                border: `1px solid ${isDarkMode ? '#333' : '#ddd'}`,
                                                borderRadius: '8px',
                                                fontSize: '12px'
                                            }}
                                            formatter={(value) => [`${value} ${sensorData.unit}`, sensorData.sensor_type]}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="value"
                                            stroke={color}
                                            strokeWidth={2}
                                            fill={`url(#gradient-${sensorData.sensor_type})`}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-48 flex items-center justify-center text-gray-500">
                                    Bu zaman aralığında veri yok
                                </div>
                            )}
                        </motion.div>
                    );
                })}

                {(!history?.sensors || history.sensors.length === 0) && (
                    <div className={`text-center py-16 rounded-2xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'}`}>
                        <Activity size={48} className="mx-auto mb-4 opacity-30" />
                        <h3 className="text-lg font-bold mb-2">Henüz Geçmiş Veri Yok</h3>
                        <p className="text-gray-500 text-sm">
                            Sensör verileri toplanmaya başladığında burada grafikler görünecek.
                        </p>
                    </div>
                )}
            </div>

            {/* Last Seen */}
            <div className={`mt-8 text-center text-sm ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                Son görülme: {new Date(device.last_seen * 1000).toLocaleString('tr-TR')}
            </div>
        </div>
    );
}
