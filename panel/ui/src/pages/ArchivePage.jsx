import { useState, useEffect, useMemo } from 'react';
import { motion } from 'motion/react';
import {
    Database, Download, Calendar, Filter, RefreshCw,
    HardDrive, Cloud, CloudOff, Clock, FileJson, FileSpreadsheet,
    ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Search, Trash2, Play,
    Thermometer, Droplets, Sun, Gauge, Flame, Wind, Volume2, Zap, Activity
} from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { formatBytes, formatUptime } from '../utils/format';

const TELEMETRY_METRIC_DETAILS = {
    'host.cpu.pct_total': { label: 'Toplam CPU kullanimi', unit: '%', decimals: 1 },
    'host.mem.pct': { label: 'Bellek kullanimi', unit: '%', decimals: 1 },
    'host.mem.available_mb': { label: 'Kullanilabilir bellek', unit: 'GB', decimals: 1, transform: (value) => value / 1024 },
    'host.mem.used_mb': { label: 'Kullanilan bellek', unit: 'GB', decimals: 1, transform: (value) => value / 1024 },
    'host.mem.total_mb': { label: 'Toplam bellek', unit: 'GB', decimals: 1, transform: (value) => value / 1024 },
    'host.temp.cpu_c': { label: 'CPU sicakligi', unit: '°C', decimals: 1 },
    'disk._root.pct': { label: 'Disk kullanimi', unit: '%', decimals: 1 },
    'disk._root.used_pct': { label: 'Disk kullanimi', unit: '%', decimals: 1 },
    'disk._root.used_gb': { label: 'Kullanilan disk alani', unit: 'GB', decimals: 1 },
    'disk._root.total_gb': { label: 'Toplam disk alani', unit: 'GB', decimals: 1 },
    'host.net.rx_bytes': { label: 'Alinan veri', format: 'bytes' },
    'host.net.tx_bytes': { label: 'Gonderilen veri', format: 'bytes' },
    'host.load.1m': { label: '1 dakikalik yuk ortalamasi', decimals: 2 },
    'host.load.5m': { label: '5 dakikalik yuk ortalamasi', decimals: 2 },
    'host.load.15m': { label: '15 dakikalik yuk ortalamasi', decimals: 2 },
    'host.uptime.seconds': { label: 'Calisma suresi', format: 'uptime' },
};

const telemetryCategoryDefinitions = {
    'CPU': { prefixes: ['host.cpu'], icon: Activity, color: 'from-purple-500 to-violet-500' },
    'Bellek': { prefixes: ['host.mem'], icon: HardDrive, color: 'from-green-500 to-emerald-500' },
    'Sicaklik': { prefixes: ['host.temp'], icon: Thermometer, color: 'from-red-500 to-orange-500' },
    'Disk': { prefixes: ['disk.'], icon: Database, color: 'from-blue-500 to-cyan-500' },
    'Ag': { prefixes: ['host.net'], icon: Activity, color: 'from-yellow-500 to-amber-500' },
    'Sistem': { prefixes: ['host.load', 'host.uptime'], icon: Gauge, color: 'from-slate-500 to-gray-600' },
    'Diger': { prefixes: [], icon: Filter, color: 'from-gray-500 to-gray-600' },
};

export function ArchivePage() {
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);

    // State
    const [activeTab, setActiveTab] = useState('telemetry'); // stats, telemetry, iot, backups
    const [stats, setStats] = useState(null);
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Filters
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [deviceFilter, setDeviceFilter] = useState('');
    const [metricFilter, setMetricFilter] = useState('');

    // View mode
    const [viewMode, setViewMode] = useState('grouped'); // 'grouped' or 'table'
    const [expandedGroups, setExpandedGroups] = useState({});

    // Pagination
    const [page, setPage] = useState(0);
    const [limit] = useState(200);
    const [total, setTotal] = useState(0);

    // Backup state
    const [backupStatus, setBackupStatus] = useState(null);
    const [backupFiles, setBackupFiles] = useState([]);
    const [backupRunning, setBackupRunning] = useState(false);
    const [folderIdInput, setFolderIdInput] = useState('');
    const [savingFolder, setSavingFolder] = useState(false);

    // Sensor icon helper
    const getSensorIcon = (type) => {
        const icons = {
            temperature: Thermometer,
            humidity: Droplets,
            light: Sun,
            pressure: Gauge,
            gas: Flame,
            smoke: Flame,
            air_quality: Wind,
            noise: Volume2,
            voltage: Zap,
            motion: Activity,
            co2: Wind,
        };
        return icons[type?.toLowerCase()] || Activity;
    };

    // Sensor color helper
    const getSensorColor = (type) => {
        const colors = {
            temperature: 'from-red-500 to-orange-500',
            humidity: 'from-blue-500 to-cyan-500',
            light: 'from-yellow-500 to-amber-500',
            pressure: 'from-purple-500 to-violet-500',
            gas: 'from-orange-500 to-red-500',
            smoke: 'from-gray-500 to-gray-600',
            air_quality: 'from-green-500 to-emerald-500',
            noise: 'from-pink-500 to-rose-500',
            voltage: 'from-yellow-500 to-lime-500',
            motion: 'from-indigo-500 to-blue-500',
            co2: 'from-teal-500 to-cyan-500',
        };
        return colors[type?.toLowerCase()] || 'from-gray-500 to-gray-600';
    };

    const getTelemetryMetricDetail = (metric) => {
        const exactMatch = TELEMETRY_METRIC_DETAILS[metric];
        if (exactMatch) {
            return exactMatch;
        }

        const fallbackLabel = metric
            ?.split('.')
            .filter(Boolean)
            .slice(-2)
            .join(' ')
            .replace(/_/g, ' ');

        return {
            label: fallbackLabel || metric || 'Bilinmeyen metrik',
            decimals: 2,
        };
    };

    const formatNumberValue = (value, decimals = 1) => {
        return new Intl.NumberFormat('tr-TR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value);
    };

    const formatCompactPercent = (value, decimals = 0) => {
        return `%${formatNumberValue(value, decimals)}`;
    };

    const formatTelemetryValue = (metric, rawValue) => {
        const numericValue = Number(rawValue);
        if (!Number.isFinite(numericValue)) {
            return '-';
        }

        const detail = getTelemetryMetricDetail(metric);

        if (detail.format === 'bytes') {
            return formatBytes(numericValue, numericValue >= 1024 ? 1 : 0);
        }

        if (detail.format === 'uptime') {
            return formatUptime(numericValue);
        }

        const transformedValue = detail.transform ? detail.transform(numericValue) : numericValue;
        const formattedValue = formatNumberValue(transformedValue, detail.decimals ?? 1);

        if (!detail.unit) {
            return formattedValue;
        }

        return detail.unit === '%'
            ? `${formattedValue}%`
            : `${formattedValue} ${detail.unit}`;
    };

    const buildGenericTelemetryRows = (rows) => {
        return rows.map((row) => {
            const metricDetail = getTelemetryMetricDetail(row.metric);

            return {
                timestamp: row.timestamp,
                datetime: row.datetime,
                primaryLabel: metricDetail.label,
                secondaryLabel: row.metric,
                valueText: formatTelemetryValue(row.metric, row.value),
            };
        });
    };

    const groupTelemetryRowsByTimestamp = (rows) => {
        const groupedRows = new Map();

        rows.forEach((row) => {
            const key = row.timestamp ?? row.datetime;
            if (!groupedRows.has(key)) {
                groupedRows.set(key, []);
            }
            groupedRows.get(key).push(row);
        });

        return Array.from(groupedRows.values()).sort(
            (left, right) => (right[0]?.timestamp ?? 0) - (left[0]?.timestamp ?? 0)
        );
    };

    const buildMemorySummaryRows = (rows) => {
        const displayRows = [];

        groupTelemetryRowsByTimestamp(rows).forEach((snapshotRows) => {
            const values = Object.fromEntries(
                snapshotRows.map((row) => [row.metric, Number(row.value)])
            );

            const usedGb = Number.isFinite(values['host.mem.used_mb']) ? values['host.mem.used_mb'] / 1024 : null;
            const totalGb = Number.isFinite(values['host.mem.total_mb']) ? values['host.mem.total_mb'] / 1024 : null;
            const availableGb = Number.isFinite(values['host.mem.available_mb']) ? values['host.mem.available_mb'] / 1024 : null;
            const pct = Number.isFinite(values['host.mem.pct']) ? values['host.mem.pct'] : null;

            if (usedGb == null && totalGb == null && pct == null) {
                displayRows.push(...buildGenericTelemetryRows(snapshotRows));
                return;
            }

            const summaryParts = [];

            if (usedGb != null && totalGb != null) {
                summaryParts.push(`${formatNumberValue(usedGb, 1)} / ${formatNumberValue(totalGb, 1)} GB`);
            } else if (usedGb != null) {
                summaryParts.push(`${formatNumberValue(usedGb, 1)} GB`);
            } else if (totalGb != null) {
                summaryParts.push(`${formatNumberValue(totalGb, 1)} GB toplam`);
            }

            if (pct != null) {
                summaryParts.push(`(${formatCompactPercent(pct, 0)})`);
            }

            displayRows.push({
                timestamp: snapshotRows[0]?.timestamp,
                datetime: snapshotRows[0]?.datetime,
                primaryLabel: 'Bellek ozeti',
                secondaryLabel: availableGb != null ? `Bos: ${formatNumberValue(availableGb, 1)} GB` : 'host.mem.*',
                valueText: summaryParts.join(' '),
            });
        });

        return displayRows;
    };

    const buildDiskSummaryRows = (rows) => {
        const displayRows = [];

        groupTelemetryRowsByTimestamp(rows).forEach((snapshotRows) => {
            const values = Object.fromEntries(
                snapshotRows.map((row) => [row.metric, Number(row.value)])
            );

            const usedGb = Number.isFinite(values['disk._root.used_gb']) ? values['disk._root.used_gb'] : null;
            const totalGb = Number.isFinite(values['disk._root.total_gb']) ? values['disk._root.total_gb'] : null;
            const pct = Number.isFinite(values['disk._root.used_pct'])
                ? values['disk._root.used_pct']
                : (Number.isFinite(values['disk._root.pct']) ? values['disk._root.pct'] : null);
            const freeGb = usedGb != null && totalGb != null ? Math.max(totalGb - usedGb, 0) : null;

            if (usedGb == null && totalGb == null && pct == null) {
                displayRows.push(...buildGenericTelemetryRows(snapshotRows));
                return;
            }

            const summaryParts = [];

            if (usedGb != null && totalGb != null) {
                summaryParts.push(`${formatNumberValue(usedGb, 1)} / ${formatNumberValue(totalGb, 1)} GB`);
            } else if (usedGb != null) {
                summaryParts.push(`${formatNumberValue(usedGb, 1)} GB`);
            } else if (totalGb != null) {
                summaryParts.push(`${formatNumberValue(totalGb, 1)} GB toplam`);
            }

            if (pct != null) {
                summaryParts.push(`(${formatCompactPercent(pct, 0)})`);
            }

            displayRows.push({
                timestamp: snapshotRows[0]?.timestamp,
                datetime: snapshotRows[0]?.datetime,
                primaryLabel: 'Disk ozeti',
                secondaryLabel: freeGb != null ? `Bos: ${formatNumberValue(freeGb, 1)} GB` : 'Kok dizin',
                valueText: summaryParts.join(' '),
            });
        });

        return displayRows;
    };

    const buildTelemetryDisplayRows = (categoryName, rows) => {
        if (categoryName === 'Bellek') {
            return buildMemorySummaryRows(rows);
        }

        if (categoryName === 'Disk') {
            return buildDiskSummaryRows(rows);
        }

        return buildGenericTelemetryRows(rows);
    };

    // Group data by device and sensor type
    const groupedData = useMemo(() => {
        if (activeTab !== 'iot' || !data.length) return {};

        const groups = {};
        data.forEach(row => {
            const deviceKey = row.device_id || 'unknown';
            if (!groups[deviceKey]) {
                groups[deviceKey] = {
                    device_id: deviceKey,
                    sensors: {},
                    totalReadings: 0
                };
            }

            const sensorKey = row.sensor_type || 'unknown';
            if (!groups[deviceKey].sensors[sensorKey]) {
                groups[deviceKey].sensors[sensorKey] = {
                    type: sensorKey,
                    readings: [],
                    min: Infinity,
                    max: -Infinity,
                    avg: 0,
                    unit: row.unit || ''
                };
            }

            const sensor = groups[deviceKey].sensors[sensorKey];
            sensor.readings.push({
                value: row.value,
                timestamp: row.timestamp,
                datetime: row.datetime
            });
            sensor.min = Math.min(sensor.min, row.value);
            sensor.max = Math.max(sensor.max, row.value);
            groups[deviceKey].totalReadings++;
        });

        // Calculate averages
        Object.values(groups).forEach(device => {
            Object.values(device.sensors).forEach(sensor => {
                const sum = sensor.readings.reduce((a, b) => a + b.value, 0);
                sensor.avg = sum / sensor.readings.length;
            });
        });

        return groups;
    }, [data, activeTab]);

    // Group telemetry by metric category
    const groupedTelemetry = useMemo(() => {
        if (activeTab !== 'telemetry' || !data.length) return {};

        const categories = Object.fromEntries(
            Object.entries(telemetryCategoryDefinitions).map(([name, config]) => [
                name,
                { ...config, metrics: [] }
            ])
        );

        data.forEach(row => {
            let assigned = false;
            for (const [catName, cat] of Object.entries(categories)) {
                if (catName !== 'Diger' && cat.prefixes.some((prefix) => row.metric?.startsWith(prefix))) {
                    cat.metrics.push(row);
                    assigned = true;
                    break;
                }
            }
            if (!assigned) {
                categories['Diger'].metrics.push(row);
            }
        });

        // Remove empty categories
        Object.keys(categories).forEach(key => {
            if (categories[key].metrics.length === 0) {
                delete categories[key];
            } else {
                categories[key].displayRows = buildTelemetryDisplayRows(key, categories[key].metrics);
            }
        });

        return categories;
    }, [data, activeTab]);

    // Toggle group expansion
    const toggleGroup = (groupKey) => {
        setExpandedGroups(prev => ({
            ...prev,
            [groupKey]: !prev[groupKey]
        }));
    };

    // Load stats
    const loadStats = async () => {
        try {
            const response = await api.get('/archive/stats');
            setStats(response.data);
        } catch (err) {
            console.error('Failed to load stats:', err);
        }
    };

    // Load data based on active tab
    const loadData = async () => {
        setLoading(true);
        setError(null);

        try {
            let endpoint = '';
            const params = new URLSearchParams();

            params.append('limit', limit.toString());
            params.append('offset', (page * limit).toString());

            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

            if (activeTab === 'telemetry') {
                endpoint = '/archive/telemetry';
                if (metricFilter) params.append('metric', metricFilter);
            } else if (activeTab === 'iot') {
                endpoint = '/archive/iot';
                if (deviceFilter) params.append('device_id', deviceFilter);
            }

            if (endpoint) {
                const response = await api.get(`${endpoint}?${params.toString()}`);
                setData(response.data.data || []);
                setTotal(response.data.total || 0);
            }
        } catch (err) {
            console.error('Failed to load data:', err);
            setError('Veri yüklenemedi');
        } finally {
            setLoading(false);
        }
    };

    // Load backup status
    const loadBackupStatus = async () => {
        try {
            const [statusRes, filesRes] = await Promise.all([
                api.get('/backup/status'),
                api.get('/backup/files')
            ]);
            setBackupStatus(statusRes.data);
            setBackupFiles(filesRes.data.files || []);
            setFolderIdInput(statusRes.data.folder_id || '');
        } catch (err) {
            console.error('Failed to load backup status:', err);
        }
    };

    // Trigger backup
    const triggerBackup = async (format = 'json') => {
        setBackupRunning(true);
        try {
            await api.post(`/backup/trigger?format=${format}`);
            setTimeout(() => {
                loadBackupStatus();
                setBackupRunning(false);
            }, 5000);
        } catch (err) {
            console.error('Backup failed:', err);
            setBackupRunning(false);
        }
    };

    // Download backup
    const downloadBackup = async (filename) => {
        try {
            const response = await api.get(`/backup/download/${filename}`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(response.data);
            const link = document.createElement('a');
            link.href = url;
            const headerName = response.headers?.get('content-disposition')?.match(/filename="?([^"]+)"?/)?.[1];
            link.setAttribute('download', headerName || filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Download failed:', err);
        }
    };

    // Export data
    const exportData = async (dataType, format) => {
        try {
            const params = new URLSearchParams();
            params.append('format', format);
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

            const response = await api.get(`/archive/export/${dataType}?${params.toString()}`, {
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(response.data);
            const link = document.createElement('a');
            link.href = url;
            const headerName = response.headers?.get('content-disposition')?.match(/filename="?([^"]+)"?/)?.[1];
            link.setAttribute('download', headerName || `export_${dataType}_${new Date().toISOString().split('T')[0]}.${format}`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Export failed:', err);
        }
    };

    const saveFolderId = async () => {
        if (!folderIdInput.trim()) return;
        setSavingFolder(true);
        try {
            await api.post(`/backup/gdrive/set-folder?folder_id=${encodeURIComponent(folderIdInput.trim())}`);
            await loadBackupStatus();
        } catch (err) {
            console.error('Failed to save Google Drive folder:', err);
        } finally {
            setSavingFolder(false);
        }
    };

    // Effects
    useEffect(() => {
        loadStats();
        loadBackupStatus();
    }, []);

    useEffect(() => {
        if (activeTab === 'telemetry' || activeTab === 'iot') {
            loadData();
        }
    }, [activeTab, page, startDate, endDate, deviceFilter, metricFilter]);

    useEffect(() => {
        if (activeTab === 'telemetry' && Object.keys(groupedTelemetry).length > 0) {
            setExpandedGroups(prev => (
                Object.keys(prev).length > 0
                    ? prev
                    : Object.keys(groupedTelemetry).reduce((acc, key, index) => {
                        acc[key] = index === 0;
                        return acc;
                    }, {})
            ));
        }
    }, [activeTab, groupedTelemetry]);

    useEffect(() => {
        if (activeTab === 'iot' && Object.keys(groupedData).length > 0) {
            setExpandedGroups(prev => (
                Object.keys(prev).length > 0
                    ? prev
                    : Object.keys(groupedData).reduce((acc, key, index) => {
                        acc[key] = index === 0;
                        return acc;
                    }, {})
            ));
        }
    }, [activeTab, groupedData]);

    const formatNumber = (num) => {
        return new Intl.NumberFormat('tr-TR').format(num);
    };

    const formatValue = (value, decimals = 1) => {
        if (typeof value !== 'number') return value;
        return formatNumberValue(value, decimals);
    };

    return (
        <div className="animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
                        Veri Arşivi
                    </h1>
                    <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                        Geçmiş veriler, export ve yedekleme yönetimi
                    </p>
                </div>
                <button
                    onClick={() => { loadStats(); loadBackupStatus(); if (activeTab !== 'stats' && activeTab !== 'backups') loadData(); }}
                    className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
                >
                    <RefreshCw size={20} />
                </button>
            </div>

            {/* Tabs */}
            <div className={`flex gap-2 mb-6 p-1 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'}`}>
                {[
                    { id: 'stats', label: 'İstatistikler', icon: Database },
                    { id: 'telemetry', label: 'Sistem', icon: Activity },
                    { id: 'iot', label: 'IoT Cihazlar', icon: Thermometer },
                    { id: 'backups', label: 'Yedekler', icon: Cloud },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => { setActiveTab(tab.id); setPage(0); setExpandedGroups({}); }}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                            ? `bg-gradient-to-r ${themeColors.secondary} text-white`
                            : isDarkMode ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
                            }`}
                    >
                        <tab.icon size={16} />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Stats Tab */}
            {activeTab === 'stats' && stats && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-6`}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
                                <Activity size={20} className="text-white" />
                            </div>
                            <span className="text-sm opacity-70">Sistem Kayıtları</span>
                        </div>
                        <div className="text-3xl font-bold">{formatNumber(stats.telemetry?.total_records || 0)}</div>
                        <div className="text-xs text-gray-500 mt-2">
                            {stats.unique_metrics || 0} benzersiz metrik
                        </div>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-6`}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                                <Thermometer size={20} className="text-white" />
                            </div>
                            <span className="text-sm opacity-70">IoT Sensör Kayıtları</span>
                        </div>
                        <div className="text-3xl font-bold">{formatNumber(stats.iot_sensors?.total_records || 0)}</div>
                        <div className="text-xs text-gray-500 mt-2">
                            {stats.iot_devices?.total || 0} cihaz • {stats.unique_sensor_types || 0} sensör tipi
                        </div>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-6`}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center">
                                <Calendar size={20} className="text-white" />
                            </div>
                            <span className="text-sm opacity-70">Veri Aralığı</span>
                        </div>
                        <div className="text-lg font-bold">
                            {stats.telemetry?.oldest?.split('T')[0] || '-'}
                        </div>
                        <div className="text-xs text-gray-500 mt-2">
                            → {stats.telemetry?.newest?.split('T')[0] || '-'}
                        </div>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-6`}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
                                <HardDrive size={20} className="text-white" />
                            </div>
                            <span className="text-sm opacity-70">Veritabanı Boyutu</span>
                        </div>
                        <div className="text-3xl font-bold">{stats.database_size_mb || 0} MB</div>
                    </motion.div>
                </div>
            )}

            {/* IoT Grouped View */}
            {activeTab === 'iot' && (
                <div className="space-y-4">
                    {/* Filters */}
                    <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-4 flex flex-wrap gap-4`}>
                        <div className="flex items-center gap-2">
                            <Calendar size={16} className="text-gray-500" />
                            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                            <span className="text-gray-500">-</span>
                            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                                className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                        </div>
                        <input type="text" value={deviceFilter} onChange={(e) => setDeviceFilter(e.target.value)}
                            placeholder="Cihaz filtrele..."
                            className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                        <div className="flex-1" />
                        <div className="flex gap-2">
                            <button onClick={() => exportData('iot', 'json')}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'}`}>
                                <FileJson size={16} /> JSON
                            </button>
                            <button onClick={() => exportData('iot', 'csv')}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'}`}>
                                <FileSpreadsheet size={16} /> CSV
                            </button>
                        </div>
                    </div>

                    {loading ? (
                        <div className="text-center py-8 text-gray-500">Yükleniyor...</div>
                    ) : error ? (
                        <div className="text-center py-8 text-red-500">{error}</div>
                    ) : Object.keys(groupedData).length === 0 ? (
                        <div className="text-center py-8 text-gray-500">Veri bulunamadı</div>
                    ) : (
                        Object.entries(groupedData).map(([deviceId, device]) => (
                            <motion.div key={deviceId} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl overflow-hidden`}>
                                {/* Device Header */}
                                <div onClick={() => toggleGroup(deviceId)}
                                    className={`p-4 flex items-center justify-between cursor-pointer ${isDarkMode ? 'hover:bg-white/5' : 'hover:bg-gray-50'}`}>
                                    <div className="flex items-center gap-3">
                                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
                                            <Activity size={20} className="text-white" />
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-lg">{deviceId.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</h3>
                                            <p className="text-xs text-gray-500">
                                                {Object.keys(device.sensors).length} sensör • {device.totalReadings} okuma
                                            </p>
                                        </div>
                                    </div>
                                    {expandedGroups[deviceId] ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                                </div>

                                {/* Sensors Grid */}
                                {expandedGroups[deviceId] && (
                                    <div className={`p-4 pt-0 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3`}>
                                        {Object.entries(device.sensors).map(([sensorType, sensor]) => {
                                            const Icon = getSensorIcon(sensorType);
                                            const colorClass = getSensorColor(sensorType);
                                            return (
                                                <div key={sensorType}
                                                    className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                                    <div className="flex items-center gap-2 mb-3">
                                                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${colorClass} flex items-center justify-center`}>
                                                            <Icon size={16} className="text-white" />
                                                        </div>
                                                        <span className="font-medium capitalize">{sensorType.replace(/_/g, ' ')}</span>
                                                    </div>
                                                    <div className="grid grid-cols-3 gap-2 text-center">
                                                        <div>
                                                            <div className="text-xs text-gray-500">Min</div>
                                                            <div className="font-mono font-bold">{formatValue(sensor.min)} {sensor.unit}</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-xs text-gray-500">Ort</div>
                                                            <div className="font-mono font-bold">{formatValue(sensor.avg)} {sensor.unit}</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-xs text-gray-500">Max</div>
                                                            <div className="font-mono font-bold">{formatValue(sensor.max)} {sensor.unit}</div>
                                                        </div>
                                                    </div>
                                                    <div className="text-xs text-gray-500 mt-2 text-center">
                                                        {sensor.readings.length} okuma
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </motion.div>
                        ))
                    )}

                    {/* Pagination */}
                    {total > limit && (
                        <div className="flex items-center justify-center gap-4">
                            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                                className={`p-2 rounded-lg ${page === 0 ? 'opacity-50' : 'hover:bg-white/10'}`}>
                                <ChevronLeft size={16} />
                            </button>
                            <span className="text-sm">Sayfa {page + 1} / {Math.ceil(total / limit)}</span>
                            <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * limit >= total}
                                className={`p-2 rounded-lg ${(page + 1) * limit >= total ? 'opacity-50' : 'hover:bg-white/10'}`}>
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Telemetry Grouped View */}
            {activeTab === 'telemetry' && (
                <div className="space-y-4">
                    {/* Filters */}
                    <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl p-4 flex flex-wrap gap-4`}>
                        <div className="flex items-center gap-2">
                            <Calendar size={16} className="text-gray-500" />
                            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                            <span className="text-gray-500">-</span>
                            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                                className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                        </div>
                        <input type="text" value={metricFilter} onChange={(e) => setMetricFilter(e.target.value)}
                            placeholder="Metrik filtrele..."
                            className={`px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`} />
                        <div className="flex-1" />
                        <div className="flex gap-2">
                            <button onClick={() => exportData('telemetry', 'json')}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'}`}>
                                <FileJson size={16} /> JSON
                            </button>
                            <button onClick={() => exportData('telemetry', 'csv')}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'}`}>
                                <FileSpreadsheet size={16} /> CSV
                            </button>
                        </div>
                    </div>

                    {loading ? (
                        <div className="text-center py-8 text-gray-500">Yükleniyor...</div>
                    ) : error ? (
                        <div className="text-center py-8 text-red-500">{error}</div>
                    ) : Object.keys(groupedTelemetry).length === 0 ? (
                        <div className="text-center py-8 text-gray-500">Veri bulunamadı</div>
                    ) : (
                        Object.entries(groupedTelemetry).map(([category, catData]) => (
                            <motion.div key={category} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                                className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-xl overflow-hidden`}>
                                {/* Category Header */}
                                <div onClick={() => toggleGroup(category)}
                                    className={`p-4 flex items-center justify-between cursor-pointer ${isDarkMode ? 'hover:bg-white/5' : 'hover:bg-gray-50'}`}>
                                    <div className="flex items-center gap-3">
                                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${catData.color} flex items-center justify-center`}>
                                            <catData.icon size={20} className="text-white" />
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-lg">{category}</h3>
                                            <p className="text-xs text-gray-500">
                                                {catData.displayRows?.length === catData.metrics.length
                                                    ? `${catData.metrics.length} kayıt`
                                                    : `${catData.displayRows?.length || 0} özet • ${catData.metrics.length} kayıt`}
                                            </p>
                                        </div>
                                    </div>
                                    {expandedGroups[category] ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                                </div>

                                {/* Metrics Table */}
                                {expandedGroups[category] && (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead className={isDarkMode ? 'bg-white/5' : 'bg-gray-50'}>
                                                <tr>
                                                    <th className="px-4 py-2 text-left font-medium">Tarih</th>
                                                    <th className="px-4 py-2 text-left font-medium">Metrik</th>
                                                    <th className="px-4 py-2 text-right font-medium">Değer</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(catData.displayRows || []).slice(0, 20).map((row, idx) => {
                                                    return (
                                                        <tr key={idx} className={`border-t ${isDarkMode ? 'border-white/5' : 'border-gray-100'}`}>
                                                            <td className="px-4 py-2 font-mono text-xs">{row.datetime?.split('T').join(' ').substring(0, 19)}</td>
                                                            <td className="px-4 py-2">
                                                                <div className="text-sm font-medium">
                                                                    {row.primaryLabel}
                                                                </div>
                                                                <div className="text-[11px] text-gray-500">
                                                                    {row.secondaryLabel}
                                                                </div>
                                                            </td>
                                                            <td className="px-4 py-2 text-right font-mono">
                                                                {row.valueText}
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                        {(catData.displayRows?.length || 0) > 20 && (
                                            <div className="px-4 py-2 text-center text-xs text-gray-500">
                                                +{(catData.displayRows?.length || 0) - 20} daha fazla kayıt
                                            </div>
                                        )}
                                    </div>
                                )}
                            </motion.div>
                        ))
                    )}
                </div>
            )}

            {/* Backups Tab */}
            {activeTab === 'backups' && (
                <div className="space-y-6">
                    <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-2xl p-6`}>
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold">Yedekleme Durumu</h3>
                            <div className="flex items-center gap-2">
                                {backupStatus?.authenticated ? (
                                    <span className="flex items-center gap-2 text-green-500 text-sm"><Cloud size={16} />Google Drive Bağlı</span>
                                ) : (
                                    <span className="flex items-center gap-2 text-gray-500 text-sm"><CloudOff size={16} />Sadece Lokal</span>
                                )}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                <div className="text-sm text-gray-500 mb-1">Son Yedekleme</div>
                                <div className="font-medium">
                                    {backupStatus?.last_backup?.completed_at
                                        ? new Date(backupStatus.last_backup.completed_at).toLocaleString('tr-TR')
                                        : 'Henüz yapılmadı'}
                                </div>
                            </div>
                            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                <div className="text-sm text-gray-500 mb-1">Durum</div>
                                <div className={`font-medium ${backupStatus?.last_backup?.status === 'completed' ? 'text-green-500' : backupStatus?.last_backup?.status === 'failed' ? 'text-red-500' : ''}`}>
                                    {backupStatus?.last_backup?.status || 'Bekleniyor'}
                                </div>
                            </div>
                            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                <div className="text-sm text-gray-500 mb-1">Lokal Yedekler</div>
                                <div className="font-medium">{backupFiles.length} dosya</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                <div className="text-sm text-gray-500 mb-1">Zamanlama</div>
                                <div className="font-medium">
                                    Her gun {String(backupStatus?.daily_export?.hour ?? 0).padStart(2, '0')}:
                                    {String(backupStatus?.daily_export?.minute ?? 0).padStart(2, '0')}
                                </div>
                                <div className="text-xs text-gray-500 mt-2">
                                    Son gunluk export: {backupStatus?.last_daily_export_date || 'Henuz yok'}
                                </div>
                            </div>
                            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                                <div className="text-sm text-gray-500 mb-1">Local Saklama</div>
                                <div className="font-medium">
                                    Sistem: {backupStatus?.retention_days?.telemetry ?? 90} gun
                                </div>
                                <div className="text-xs text-gray-500 mt-2">
                                    IoT: {backupStatus?.retention_days?.iot ?? 90} gun
                                </div>
                            </div>
                        </div>

                        <div className={`p-4 rounded-xl mb-6 ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                            <div className="text-sm text-gray-500 mb-3">Google Drive Klasoru</div>
                            <div className="flex flex-col md:flex-row gap-3">
                                <input
                                    type="text"
                                    value={folderIdInput}
                                    onChange={(e) => setFolderIdInput(e.target.value)}
                                    placeholder="Folder ID veya Google Drive klasor URL"
                                    className={`flex-1 px-3 py-2 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-white border-gray-200'} border`}
                                />
                                <button
                                    onClick={saveFolderId}
                                    disabled={savingFolder || !folderIdInput.trim()}
                                    className={`px-4 py-2 rounded-lg text-sm font-medium ${isDarkMode ? 'bg-white/10 hover:bg-white/20' : 'bg-gray-200 hover:bg-gray-300'} ${savingFolder || !folderIdInput.trim() ? 'opacity-50' : ''}`}
                                >
                                    {savingFolder ? 'Kaydediliyor...' : 'Klasoru Kaydet'}
                                </button>
                            </div>
                            <div className="text-xs text-gray-500 mt-2">
                                Sonraki planli calisma: {backupStatus?.next_run_at ? new Date(backupStatus.next_run_at).toLocaleString('tr-TR') : 'Bekleniyor'}
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button onClick={() => triggerBackup('json')} disabled={backupRunning}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r ${themeColors.secondary} text-white font-medium ${backupRunning ? 'opacity-50' : 'hover:opacity-90'}`}>
                                {backupRunning ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
                                {backupRunning ? 'Yedekleniyor...' : 'Şimdi Yedekle (JSON)'}
                            </button>
                            <button onClick={() => triggerBackup('csv')} disabled={backupRunning}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-white/10 hover:bg-white/20' : 'bg-gray-100 hover:bg-gray-200'} ${backupRunning ? 'opacity-50' : ''}`}>
                                <FileSpreadsheet size={16} /> CSV Olarak
                            </button>
                        </div>
                    </div>

                    <div className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} border rounded-2xl overflow-hidden`}>
                        <div className={`px-6 py-4 border-b ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                            <h3 className="font-bold">Lokal Yedek Dosyaları</h3>
                        </div>
                        {backupFiles.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">Henüz yedek dosyası yok</div>
                        ) : (
                            <div className={`divide-y ${isDarkMode ? 'divide-white/5' : 'divide-gray-100'}`}>
                                {backupFiles.map((file, idx) => (
                                    <div key={idx} className={`px-6 py-3 flex items-center justify-between ${isDarkMode ? 'hover:bg-white/5' : 'hover:bg-gray-50'}`}>
                                        <div className="flex items-center gap-3">
                                            {file.filename.endsWith('.json') ? (
                                                <FileJson size={20} className="text-yellow-500" />
                                            ) : (
                                                <FileSpreadsheet size={20} className="text-green-500" />
                                            )}
                                            <div>
                                                <div className="font-medium">{file.filename}</div>
                                                <div className="text-xs text-gray-500">
                                                    {formatBytes(file.size_bytes)} • {new Date(file.modified).toLocaleString('tr-TR')}
                                                </div>
                                            </div>
                                        </div>
                                        <button onClick={() => downloadBackup(file.filename)}
                                            className={`p-2 rounded-lg ${isDarkMode ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}>
                                            <Download size={18} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
