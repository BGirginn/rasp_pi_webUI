import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect, useMemo } from 'react';
import { Cpu, Activity, HardDrive, Thermometer, RefreshCw, AlertCircle, TrendingUp, Clock, History, Download, Upload, Zap } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';

const timeRanges = [
  { label: 'Live', value: 'live', seconds: 300 },
  { label: '1 Hour', value: '1h', seconds: 3600 },
  { label: '6 Hours', value: '6h', seconds: 21600 },
  { label: '1 Day', value: '1d', seconds: 86400 },
  { label: '7 Days', value: '7d', seconds: 604800 },
];

export function TelemetryPage() {
  const [activeRange, setActiveRange] = useState('live');
  const [telemetry, setTelemetry] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

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
    const range = timeRanges.find(r => r.value === activeRange);
    const end = Math.floor(Date.now() / 1000);
    const start = end - range.seconds;

    try {
      const response = await api.get(`/telemetry/metrics?metrics=host.cpu.pct_total,host.mem.pct,host.temp.cpu_c&start=${start}&end=${end}&step=${activeRange === 'live' ? 5 : 60}`);

      // Reformat Recharts-friendly: [{ ts, cpu, mem, temp }, ...]
      const formatted = [];
      const data = response.data; // Array of { metric, points: [{ts, value}] }

      const cpuData = data.find(m => m.metric === 'host.cpu.pct_total')?.points || [];
      const memData = data.find(m => m.metric === 'host.mem.pct')?.points || [];
      const tempData = data.find(m => m.metric === 'host.temp.cpu_c')?.points || [];

      // Use CPU data as time baseline
      cpuData.forEach((point, i) => {
        formatted.push({
          time: new Date(point.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: activeRange === 'live' ? '2-digit' : undefined }),
          cpu: point.value,
          mem: memData[i]?.value || 0,
          temp: tempData[i]?.value || 0,
          ts: point.ts
        });
      });

      setHistory(formatted);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  useEffect(() => {
    loadCurrentTelemetry();
    loadHistory();

    // If live, update frequently
    const interval = setInterval(() => {
      loadCurrentTelemetry();
      if (activeRange === 'live') loadHistory();
    }, activeRange === 'live' ? 5000 : 30000);

    return () => clearInterval(interval);
  }, [activeRange]);

  // Derived stats
  const metrics = useMemo(() => {
    if (!telemetry) return [];
    const m = telemetry.metrics || {};
    return [
      { label: 'CPU Usage', value: m['host.cpu.pct_total'] || 0, unit: '%', icon: Cpu, color: 'blue', key: 'cpu' },
      { label: 'Memory', value: m['host.mem.pct'] || 0, unit: '%', icon: Activity, color: 'green', key: 'mem' },
      { label: 'Disk Usage', value: m['disk._root.pct'] || 0, unit: '%', icon: HardDrive, color: 'orange', key: 'disk' },
      { label: 'Temperature', value: m['host.temp.cpu_c'] || 0, unit: '°C', icon: Thermometer, color: 'red', key: 'temp' },
    ];
  }, [telemetry]);

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const dm = 2;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className={`${isDarkMode ? 'bg-black/80 border-white/10' : 'bg-white/80 border-gray-200'} backdrop-blur-md p-3 border rounded-xl shadow-xl`}>
          <p className="text-xs font-bold text-gray-500 mb-2">{label}</p>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center gap-2 mb-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
              <span className={`text-xs font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{entry.name}: {entry.value.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="animate-fade-in pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Telemetry
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Real-time hardware monitoring and historical performance data
          </p>
        </div>
        <div className="flex bg-white/5 p-1 rounded-2xl border border-white/10 backdrop-blur-md">
          {timeRanges.map((range) => (
            <button
              key={range.value}
              onClick={() => { setActiveRange(range.value); setLoading(true); }}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${activeRange === range.value
                ? 'bg-purple-600 text-white shadow-lg'
                : 'text-gray-500 hover:text-white'}`}
            >
              {range.label === 'Live' && <span className="inline-block w-1.5 h-1.5 bg-green-500 rounded-full mr-1.5 animate-pulse" />}
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Current Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {loading ? (
          [1, 2, 3, 4].map(i => <div key={i} className="h-40 rounded-[32px] animate-pulse bg-white/5" />)
        ) : metrics.map((metric, index) => {
          const colorMap = {
            blue: ['from-blue-600 to-blue-400', 'text-blue-500', 'rgba(59, 130, 246, 0.1)'],
            green: ['from-emerald-600 to-emerald-400', 'text-emerald-500', 'rgba(16, 185, 129, 0.1)'],
            orange: ['from-orange-600 to-orange-400', 'text-orange-500', 'rgba(245, 158, 11, 0.1)'],
            red: ['from-rose-600 to-rose-400', 'text-rose-500', 'rgba(244, 63, 94, 0.1)'],
          };
          const [grad, iconColor, bg] = colorMap[metric.color];
          const Icon = metric.icon;

          return (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border group hover:border-purple-500/30 transition-all overflow-hidden relative`}
            >
              <div className={`absolute -right-4 -bottom-4 opacity-[0.03] group-hover:scale-110 transition-transform ${iconColor}`}>
                <Icon size={120} />
              </div>

              <div className="flex items-center gap-4 mb-4">
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${grad} flex items-center justify-center shadow-lg`}>
                  <Icon size={24} className="text-white" />
                </div>
                <span className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>{metric.label}</span>
              </div>

              <div className="flex items-baseline gap-1">
                <span className={`text-4xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{metric.value.toFixed(1)}</span>
                <span className={`text-sm font-bold ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>{metric.unit}</span>
              </div>

              {/* Simple dynamic bar */}
              <div className="mt-6 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${metric.value}%` }}
                  className={`h-full bg-gradient-to-r ${grad}`}
                />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Main Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[40px] p-8 border mb-8`}
      >
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-600/10 rounded-xl flex items-center justify-center text-purple-500">
              <TrendingUp size={20} />
            </div>
            <h3 className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>System Performance History</h3>
          </div>
        </div>

        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history}>
              <defs>
                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorMem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} />
              <XAxis
                dataKey="time"
                stroke={isDarkMode ? '#555' : '#999'}
                fontSize={10}
                tickLine={false}
                axisLine={false}
                minTickGap={30}
              />
              <YAxis
                stroke={isDarkMode ? '#555' : '#999'}
                fontSize={10}
                tickLine={false}
                axisLine={false}
                domain={[0, 100]}
                unit="%"
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="cpu"
                name="CPU Usage"
                stroke="#3b82f6"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorCpu)"
                animationDuration={1000}
              />
              <Area
                type="monotone"
                dataKey="mem"
                name="Memory Usage"
                stroke="#10b981"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorMem)"
                animationDuration={1000}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Additional Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Load Average */}
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.6 }} className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}>
          <div className="flex items-center gap-3 mb-6">
            <Zap size={18} className="text-yellow-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Load Average</h3>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: '1 min', val: telemetry?.metrics?.['host.load.1m'] },
              { label: '5 min', val: telemetry?.metrics?.['host.load.5m'] },
              { label: '15 min', val: telemetry?.metrics?.['host.load.15m'] }
            ].map(load => (
              <div key={load.label} className="text-center">
                <div className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{load.val?.toFixed(2) || '0.00'}</div>
                <div className="text-[10px] font-bold text-gray-500 uppercase mt-1">{load.label}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Network Stats */}
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.7 }} className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}>
          <div className="flex items-center gap-3 mb-6">
            <Activity size={18} className="text-blue-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Network Activity</h3>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-green-500 uppercase">
                <Download size={14} /> Received
              </div>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatBytes(telemetry?.metrics?.['host.net.rx_bytes'])}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-blue-500 uppercase">
                <Upload size={14} /> Sent
              </div>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatBytes(telemetry?.metrics?.['host.net.tx_bytes'])}</span>
            </div>
          </div>
        </motion.div>

        {/* System Info */}
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.8 }} className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200 shadow-sm'} backdrop-blur-xl rounded-[32px] p-6 border`}>
          <div className="flex items-center gap-3 mb-6">
            <Clock size={18} className="text-purple-500" />
            <h3 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Uptime & Info</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-gray-500 font-bold uppercase">Uptime</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {telemetry?.metrics?.['host.uptime.seconds'] ? Math.floor(telemetry.metrics['host.uptime.seconds'] / 3600) + 'h ' + Math.floor((telemetry.metrics['host.uptime.seconds'] % 3600) / 60) + 'm' : '---'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500 font-bold uppercase">OS</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{telemetry?.system?.os || 'Linux'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500 font-bold uppercase">Model</span>
              <span className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'} truncate w-32 text-right`}>{telemetry?.system?.machine || 'Pi'}</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
