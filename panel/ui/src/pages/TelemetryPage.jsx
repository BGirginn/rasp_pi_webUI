import { motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import {
  Cpu,
  Activity,
  HardDrive,
  Thermometer,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  Clock,
  Download,
  Upload,
  Zap,
  Gauge,
  Network,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { formatBytes, formatSpeed, formatUptime } from '../utils/format';

const timeRanges = [
  { label: 'Live', value: 'live', seconds: 300, source: 'raw', step: 5, refreshMs: 5000 },
  { label: '1 Hour', value: '1h', seconds: 3600, source: 'raw', step: 30, refreshMs: 30000 },
  { label: '6 Hours', value: '6h', seconds: 21600, source: 'raw', step: 120, refreshMs: 30000 },
  { label: '1 Day', value: '1d', seconds: 86400, source: 'raw', step: 300, refreshMs: 60000 },
  { label: '7 Days', value: '7d', seconds: 604800, source: 'summary', step: 1800, refreshMs: 300000 },
  { label: '30 Days', value: '30d', seconds: 2592000, source: 'summary', step: 7200, refreshMs: 300000 },
  { label: '90 Days', value: '90d', seconds: 7776000, source: 'summary', step: 21600, refreshMs: 300000 },
];

const historyMetricConfigs = [
  { key: 'cpu', label: 'CPU', apiMetric: 'host.cpu.pct_total', color: '#2563eb', unit: '%', axis: 'percent', decimals: 1 },
  { key: 'memory', label: 'Memory', apiMetric: 'host.mem.pct', color: '#16a34a', unit: '%', axis: 'percent', decimals: 1 },
  { key: 'disk', label: 'Disk', apiMetric: 'disk._root.used_pct', color: '#f59e0b', unit: '%', axis: 'percent', decimals: 1 },
  { key: 'temperature', label: 'Temperature', apiMetric: 'host.temp.cpu_c', color: '#ef4444', unit: '°C', axis: 'temperature', decimals: 1 },
  { key: 'load1', label: 'Load 1m', apiMetric: 'host.load.1m', color: '#7c3aed', axis: 'load', decimals: 2 },
  { key: 'load5', label: 'Load 5m', apiMetric: 'host.load.5m', color: '#a855f7', axis: 'load', decimals: 2, dash: '6 4' },
  { key: 'load15', label: 'Load 15m', apiMetric: 'host.load.15m', color: '#c084fc', axis: 'load', decimals: 2, dash: '2 4' },
  { key: 'rxRate', label: 'RX / s', apiMetric: 'host.net.rx_bytes', color: '#0891b2', axis: 'network', format: 'speed', transform: 'rate' },
  { key: 'txRate', label: 'TX / s', apiMetric: 'host.net.tx_bytes', color: '#db2777', axis: 'network', format: 'speed', transform: 'rate' },
];

const metricConfigByApiMetric = Object.fromEntries(
  historyMetricConfigs.map((metric) => [metric.apiMetric, metric])
);

const metricConfigByKey = Object.fromEntries(
  historyMetricConfigs.map((metric) => [metric.key, metric])
);

function formatHistoryTime(ts, rangeValue) {
  const date = new Date(ts * 1000);

  if (rangeValue === '90d' || rangeValue === '30d') {
    return date.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });
  }

  if (rangeValue === '7d') {
    return date.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });
  }

  if (rangeValue === '1d') {
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  }

  return date.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    second: rangeValue === 'live' ? '2-digit' : undefined,
  });
}

function formatTooltipTime(ts) {
  return new Date(ts * 1000).toLocaleString('tr-TR');
}

function toRatePoints(points) {
  if (!points?.length) {
    return [];
  }

  return points.map((point, index) => {
    if (index === 0) {
      return { ts: point.ts, value: 0 };
    }

    const previous = points[index - 1];
    const deltaTs = point.ts - previous.ts;
    if (deltaTs <= 0) {
      return { ts: point.ts, value: 0 };
    }

    return {
      ts: point.ts,
      value: Math.max((point.value - previous.value) / deltaTs, 0),
    };
  });
}

function formatHistoryValue(metric, value) {
  if (value == null || !Number.isFinite(value)) {
    return '-';
  }

  if (metric.format === 'speed') {
    return formatSpeed(value, value >= 1024 ? 1 : 0);
  }

  if (metric.unit === '%') {
    return `${value.toFixed(metric.decimals ?? 1)}%`;
  }

  if (metric.unit) {
    return `${value.toFixed(metric.decimals ?? 1)} ${metric.unit}`;
  }

  return value.toFixed(metric.decimals ?? 2);
}

export function TelemetryPage() {
  const [activeRange, setActiveRange] = useState('live');
  const [telemetry, setTelemetry] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  const activeRangeConfig = useMemo(
    () => timeRanges.find((range) => range.value === activeRange) || timeRanges[0],
    [activeRange]
  );

  const loadCurrentTelemetry = async () => {
    try {
      const response = await api.get('/telemetry/current');
      setTelemetry(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to load telemetry:', err);
      setError('System metrics unavailable');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadHistory = async () => {
    const end = Math.floor(Date.now() / 1000);
    const start = end - activeRangeConfig.seconds;
    const endpoint = activeRangeConfig.source === 'summary'
      ? '/telemetry/metrics/series/query'
      : '/telemetry/metrics/query';

    setHistoryLoading(true);

    try {
      const response = await api.post(endpoint, {
        metrics: historyMetricConfigs.map((metric) => metric.apiMetric).join(','),
        start,
        end,
        step: activeRangeConfig.step,
      });

      const dataMap = new Map();

      response.data.forEach((series) => {
        const metric = metricConfigByApiMetric[series.metric];
        if (!metric) {
          return;
        }

        const sourcePoints = metric.transform === 'rate'
          ? toRatePoints(series.points || [])
          : (series.points || []);

        sourcePoints.forEach((point) => {
          if (!dataMap.has(point.ts)) {
            dataMap.set(point.ts, {
              ts: point.ts,
              time: formatHistoryTime(point.ts, activeRange),
            });
          }

          dataMap.get(point.ts)[metric.key] = Number(point.value);
        });
      });

      const mergedRows = Array.from(dataMap.values()).sort((left, right) => left.ts - right.ts);
      setHistory(mergedRows);
    } catch (err) {
      console.error('Failed to load history:', err);
      setError('History data unavailable');
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleManualRefresh = async () => {
    setRefreshing(true);
    await Promise.all([loadCurrentTelemetry(), loadHistory()]);
  };

  useEffect(() => {
    loadCurrentTelemetry();
    loadHistory();

    const interval = setInterval(() => {
      loadCurrentTelemetry();
      loadHistory();
    }, activeRangeConfig.refreshMs);

    return () => clearInterval(interval);
  }, [activeRange, activeRangeConfig.refreshMs]);

  const metrics = useMemo(() => {
    if (!telemetry) return [];
    const currentMetrics = telemetry.metrics || {};

    return [
      { label: 'CPU Usage', value: currentMetrics['host.cpu.pct_total'] || 0, unit: '%', icon: Cpu, color: 'blue', barValue: currentMetrics['host.cpu.pct_total'] || 0 },
      { label: 'Memory', value: currentMetrics['host.mem.pct'] || 0, unit: '%', icon: Activity, color: 'green', barValue: currentMetrics['host.mem.pct'] || 0 },
      { label: 'Disk Usage', value: currentMetrics['disk._root.used_pct'] || currentMetrics['disk._root.pct'] || 0, unit: '%', icon: HardDrive, color: 'orange', barValue: currentMetrics['disk._root.used_pct'] || currentMetrics['disk._root.pct'] || 0 },
      { label: 'Temperature', value: currentMetrics['host.temp.cpu_c'] || 0, unit: '°C', icon: Thermometer, color: 'red', barValue: Math.min((currentMetrics['host.temp.cpu_c'] || 0) * 1.2, 100) },
    ];
  }, [telemetry]);

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) {
      return null;
    }

    const tooltipTs = payload?.[0]?.payload?.ts;

    return (
      <div className={`${isDarkMode ? 'bg-black/85 border-white/10' : 'bg-white/90 border-gray-200'} backdrop-blur-md p-3 border rounded-xl shadow-xl min-w-52`}>
        <p className="text-xs font-bold text-gray-500 mb-2">{formatTooltipTime(tooltipTs)}</p>
        {payload
          .filter((entry) => entry.value != null)
          .map((entry) => {
            const metric = metricConfigByKey[entry.dataKey];
            if (!metric) {
              return null;
            }

            return (
              <div key={entry.dataKey} className="flex items-center justify-between gap-3 mb-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: metric.color }} />
                  <span className={`text-xs font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                    {metric.label}
                  </span>
                </div>
                <span className="text-xs font-bold text-gray-500">
                  {formatHistoryValue(metric, entry.value)}
                </span>
              </div>
            );
          })}
      </div>
    );
  };

  const legendItems = historyMetricConfigs.map((metric) => (
    <div
      key={metric.key}
      className={`flex items-center gap-2 px-3 py-2 rounded-xl ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border`}
    >
      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: metric.color }} />
      <span className={`text-xs font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
        {metric.label}
      </span>
    </div>
  ));

  return (
    <div className="animate-fade-in pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Telemetry
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Real-time hardware monitoring with long-range system history
          </p>
        </div>

        <div className="flex flex-col gap-3 md:items-end">
          <div className={`flex flex-wrap gap-2 ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-white border-gray-200'} p-1.5 rounded-2xl border backdrop-blur-md`}>
            {timeRanges.map((range) => (
              <button
                key={range.value}
                onClick={() => setActiveRange(range.value)}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${activeRange === range.value
                  ? 'bg-purple-600 text-white shadow-lg'
                  : isDarkMode ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'}`}
              >
                {range.label === 'Live' && <span className="inline-block w-1.5 h-1.5 bg-green-500 rounded-full mr-1.5 animate-pulse" />}
                {range.label}
              </button>
            ))}
          </div>

          <button
            onClick={handleManualRefresh}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium ${isDarkMode ? 'bg-white/5 border-white/10 hover:bg-white/10' : 'bg-white border-gray-200 hover:bg-gray-50'} border transition-colors`}
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className={`mb-6 flex items-center gap-3 px-4 py-3 rounded-2xl border ${isDarkMode ? 'bg-red-500/10 border-red-500/20 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
          <AlertCircle size={18} />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {loading ? (
          [1, 2, 3, 4].map((index) => (
            <div key={index} className="h-40 rounded-[32px] animate-pulse bg-white/5" />
          ))
        ) : metrics.map((metric, index) => {
          const colorMap = {
            blue: ['from-blue-600 to-blue-400', 'text-blue-500'],
            green: ['from-emerald-600 to-emerald-400', 'text-emerald-500'],
            orange: ['from-orange-600 to-orange-400', 'text-orange-500'],
            red: ['from-rose-600 to-rose-400', 'text-rose-500'],
          };

          const [gradient, iconColor] = colorMap[metric.color];
          const Icon = metric.icon;

          return (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08 }}
              className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border group hover:border-purple-500/30 transition-all overflow-hidden relative`}
            >
              <div className={`absolute -right-4 -bottom-4 opacity-[0.03] group-hover:scale-110 transition-transform ${iconColor}`}>
                <Icon size={120} />
              </div>

              <div className="flex items-center gap-4 mb-4">
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg`}>
                  <Icon size={24} className="text-white" />
                </div>
                <span className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                  {metric.label}
                </span>
              </div>

              <div className="flex items-baseline gap-1">
                <span className={`text-4xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {metric.value.toFixed(1)}
                </span>
                <span className={`text-sm font-bold ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                  {metric.unit}
                </span>
              </div>

              <div className="mt-6 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${metric.barValue}%` }}
                  className={`h-full bg-gradient-to-r ${gradient}`}
                />
              </div>
            </motion.div>
          );
        })}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[40px] p-8 border mb-8`}
      >
        <div className="flex flex-col gap-4 mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-600/10 rounded-xl flex items-center justify-center text-purple-500">
              <TrendingUp size={20} />
            </div>
            <div>
              <h3 className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                System Performance History
              </h3>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                CPU, memory, disk, temperature, load, and network traffic up to 90 days
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
            {legendItems}
          </div>
        </div>

        <div className="h-[460px] w-full">
          {historyLoading ? (
            <div className={`h-full w-full rounded-3xl animate-pulse ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'}`} />
          ) : history.length === 0 ? (
            <div className={`h-full flex items-center justify-center rounded-3xl border ${isDarkMode ? 'border-white/10 text-gray-400' : 'border-gray-200 text-gray-500'}`}>
              No historical telemetry available for this range
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke={isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}
                />
                <XAxis
                  dataKey="time"
                  stroke={isDarkMode ? '#6b7280' : '#9ca3af'}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={24}
                />
                <YAxis
                  yAxisId="percent"
                  stroke={isDarkMode ? '#6b7280' : '#9ca3af'}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  width={46}
                />
                <YAxis yAxisId="temperature" hide domain={['auto', 'auto']} />
                <YAxis yAxisId="load" hide domain={['auto', 'auto']} />
                <YAxis yAxisId="network" hide domain={[0, 'auto']} />
                <Tooltip content={<CustomTooltip />} />

                {historyMetricConfigs.map((metric) => (
                  <Line
                    key={metric.key}
                    type="monotone"
                    dataKey={metric.key}
                    yAxisId={metric.axis}
                    stroke={metric.color}
                    strokeWidth={metric.axis === 'percent' || metric.key === 'temperature' ? 2.5 : 1.8}
                    strokeDasharray={metric.dash}
                    dot={false}
                    connectNulls
                    isAnimationActive={activeRange === 'live'}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.55 }}
          className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}
        >
          <div className="flex items-center gap-3 mb-6">
            <Zap size={18} className="text-yellow-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Load Average</h3>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: '1 min', val: telemetry?.metrics?.['host.load.1m'] },
              { label: '5 min', val: telemetry?.metrics?.['host.load.5m'] },
              { label: '15 min', val: telemetry?.metrics?.['host.load.15m'] },
            ].map((load) => (
              <div key={load.label} className="text-center">
                <div className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {load.val?.toFixed(2) || '0.00'}
                </div>
                <div className="text-[10px] font-bold text-gray-500 uppercase mt-1">
                  {load.label}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.62 }}
          className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}
        >
          <div className="flex items-center gap-3 mb-6">
            <Network size={18} className="text-cyan-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Network Activity</h3>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-cyan-500 uppercase">
                <Download size={14} /> Received
              </div>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {formatBytes(telemetry?.metrics?.['host.net.rx_bytes'])}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-pink-500 uppercase">
                <Upload size={14} /> Sent
              </div>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {formatBytes(telemetry?.metrics?.['host.net.tx_bytes'])}
              </span>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.69 }}
          className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}
        >
          <div className="flex items-center gap-3 mb-6">
            <Clock size={18} className="text-purple-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Uptime & Info</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-xs gap-3">
              <span className="text-gray-500 font-bold uppercase">Uptime</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'} text-right`}>
                {telemetry?.metrics?.['host.uptime.seconds']
                  ? formatUptime(telemetry.metrics['host.uptime.seconds'])
                  : '---'}
              </span>
            </div>
            <div className="flex justify-between text-xs gap-3">
              <span className="text-gray-500 font-bold uppercase">OS</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'} text-right`}>
                {telemetry?.system?.os || 'Linux'}
              </span>
            </div>
            <div className="flex justify-between text-xs gap-3">
              <span className="text-gray-500 font-bold uppercase">Model</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'} truncate text-right`}>
                {telemetry?.system?.machine || 'Pi'}
              </span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
