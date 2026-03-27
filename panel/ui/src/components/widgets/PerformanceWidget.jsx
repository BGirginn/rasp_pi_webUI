import { useState, useEffect, useRef } from 'react';
import { Activity, Thermometer, HardDrive, Layers, Check } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';
import { api } from '../../services/api';

export function PerformanceWidget({ variant }) {
  const { stats } = useDashboard();
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  const [metric, setMetric] = useState('all'); // cpu, mem, temp, all
  const [range, setRange] = useState('1h');   // 1m, 1h, 24h, 7d, 15d
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const requestSeqRef = useRef(0);
  const inFlightRef = useRef(false);

  // Initialize from localStorage or default to 15
  const [refreshInterval, setRefreshInterval] = useState(() => {
    const saved = localStorage.getItem('performance_refresh_interval');
    return saved ? parseInt(saved, 10) : 15;
  });
  const [inputVal, setInputVal] = useState(refreshInterval);
  const [inputUnit, setInputUnit] = useState('s'); // s, m

  // Map ranges to API params
  const getRangeParams = (r) => {
    const now = Math.floor(Date.now() / 1000);
    switch (r) {
      case '1m': return { start: now - 300, step: 1, type: 'raw' }; // Show 5 mins for "1M" (Live)
      case '1h': return { start: now - 3600, step: 60, type: 'raw' };
      case '24h': return { start: now - 86400, step: 300, type: 'raw' };
      case '7d': return { start: now - 604800, step: 3600, type: 'raw' };
      case '15d': return { start: now - 1296000, step: 7200, type: 'raw' };
      default: return { start: now - 3600, type: 'raw' };
    }
  };

  const getMetricKey = (m) => {
    switch (m) {
      case 'cpu': return 'host.cpu.pct_total';
      case 'mem': return 'host.mem.pct';
      case 'temp': return 'host.temp.cpu_c';
      // 'all' case handled separately
      default: return 'host.cpu.pct_total';
    }
  };

  useEffect(() => {
    const fetchData = async (force = false) => {
      if (inFlightRef.current && !force) {
        return;
      }

      const requestToken = ++requestSeqRef.current;
      inFlightRef.current = true;

      try {
        const params = getRangeParams(range);
        const endpoint = params.type === 'summary'
          ? '/telemetry/metrics/series/query'
          : '/telemetry/metrics/query';
        const metricKeys = metric === 'all'
          ? ['host.cpu.pct_total', 'host.mem.pct', 'host.temp.cpu_c']
          : [getMetricKey(metric)];

        const response = await api.post(endpoint, {
          metrics: metricKeys.join(','),
          start: params.start,
          step: params.step || 60,
        });

        if (requestToken !== requestSeqRef.current) {
          return;
        }

        const seriesByMetric = new Map(
          (response.data || []).map((series) => [series.metric, series.points || []])
        );

        if (metric === 'all') {
          const cpuPoints = seriesByMetric.get('host.cpu.pct_total') || [];
          const memPoints = seriesByMetric.get('host.mem.pct') || [];
          const tempPoints = seriesByMetric.get('host.temp.cpu_c') || [];

          const tolerance = (params.step && params.step > 5) ? params.step / 2 : 2;
          const merged = cpuPoints.map((point) => {
            const ts = point.ts;
            const memPoint = memPoints.find((candidate) => Math.abs(candidate.ts - ts) <= tolerance);
            const tempPoint = tempPoints.find((candidate) => Math.abs(candidate.ts - ts) <= tolerance);

            return {
              time: ts * 1000,
              cpu: Math.round(point.value * 10) / 10,
              mem: memPoint ? Math.round(memPoint.value * 10) / 10 : null,
              temp: tempPoint ? Math.round(tempPoint.value * 10) / 10 : null,
            };
          });

          setData(merged);
        } else {
          const metricKey = metricKeys[0];
          const points = seriesByMetric.get(metricKey) || [];
          setData(points.map((point) => ({
            time: point.ts * 1000,
            value: Math.round(point.value * 10) / 10,
          })));
        }
        setError(null);
      } catch (err) {
        console.error("Failed to fetch history:", err);
        setError(err);
      } finally {
        if (requestToken === requestSeqRef.current) {
          inFlightRef.current = false;
        }
      }
    };

    fetchData(true);
    const interval = setInterval(() => fetchData(false), refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [metric, range, refreshInterval]);

  if (variant === 'list') {
    return (
      <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
            <Activity size={20} className="text-white" />
          </div>
          <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>System Status</h3>
        </div>
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>CPU Load</span>
            <span className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{stats?.cpu || 0}%</span>
          </div>
          <div className="flex justify-between items-center">
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Memory</span>
            <span className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{stats?.memory || 0}%</span>
          </div>
          <div className="flex justify-between items-center">
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Temp</span>
            <span className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{stats?.temp || 0}°C</span>
          </div>
        </div>
      </div>
    );
  }

  // Define fixed colors (not theme-dependent)
  const colorCpu = '#8b5cf6'; // purple-500 - fixed color
  const colorMem = '#10b981'; // emerald-500
  const colorTemp = '#f43f5e'; // rose-500

  return (
    <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} flex flex-col`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>

      {/* Header controls */}
      <div className="flex flex-col xl:flex-row items-center justify-between mb-6 gap-4">
        <div className="flex items-center gap-3 w-full xl:w-auto">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
            {metric === 'cpu' && <Activity size={24} className="text-white" />}
            {metric === 'mem' && <HardDrive size={24} className="text-white" />}
            {metric === 'temp' && <Thermometer size={24} className="text-white" />}
            {metric === 'all' && <Layers size={24} className="text-white" />}
          </div>
          <div>
            <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              Performance {error ? `(Error: ${error.message})` : ''}
            </h3>
            <div className="flex gap-1 text-xs items-center">
              <button
                onClick={() => setMetric('cpu')}
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'cpu' ? 'font-bold' : 'text-gray-500 hover:text-gray-400'}`}
                style={metric === 'cpu' ? { backgroundColor: `rgba(${themeColors.accentRgb}, 0.1)`, color: `rgb(${themeColors.accentRgb})` } : undefined}
              >
                CPU
              </button>
              <span className="text-gray-700">|</span>

              <button
                onClick={() => setMetric('mem')}
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'mem' ? 'font-bold bg-emerald-500/10 text-emerald-500' : 'text-gray-500 hover:text-gray-400'}`}
              >
                RAM
              </button>
              <span className="text-gray-700">|</span>

              <button
                onClick={() => setMetric('temp')}
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'temp' ? 'font-bold bg-amber-500/10 text-amber-500' : 'text-gray-500 hover:text-gray-400'}`}
              >
                TEMP
              </button>
              <span className="text-gray-700">|</span>

              <button
                onClick={() => setMetric('all')}
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'all' ? 'font-bold' : 'text-gray-500 hover:text-gray-400'}`}
                style={metric === 'all' ? { backgroundColor: `rgba(${themeColors.accentRgb}, 0.1)`, color: `rgb(${themeColors.accentRgb})` } : undefined}
              >
                ALL
              </button>
            </div>
          </div>
        </div>

        {/* Refresh Rate Control */}
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1 p-1 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
            <div className="flex items-center">
              <input
                type="number"
                min="1"
                max="999"
                value={inputVal}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '') {
                    setInputVal('');
                  } else {
                    setInputVal(parseInt(val));
                  }
                }}
                onBlur={() => {
                  if (inputVal === '' || inputVal < 1) {
                    setInputVal(1);
                  }
                }}
                className={`w-10 px-1 py-0.5 text-xs text-center bg-transparent outline-none appearance-none [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${isDarkMode ? 'text-white' : 'text-gray-900'}`}
              />
              <select
                value={inputUnit}
                onChange={(e) => setInputUnit(e.target.value)}
                className={`text-[10px] mr-1 bg-transparent outline-none border-none cursor-pointer ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}
              >
                <option value="s" className={isDarkMode ? 'bg-gray-800' : 'bg-white'}>s</option>
                <option value="m" className={isDarkMode ? 'bg-gray-800' : 'bg-white'}>m</option>
              </select>
            </div>
            <button
              onClick={() => {
                if (inputVal >= 1) {
                  const multiplier = inputUnit === 'm' ? 60 : 1;
                  const totalSeconds = inputVal * multiplier;
                  setRefreshInterval(totalSeconds);
                  localStorage.setItem('performance_refresh_interval', totalSeconds.toString());
                }
              }}
              className={`p-1 rounded-md transition-colors ${refreshInterval === (inputVal * (inputUnit === 'm' ? 60 : 1))
                ? (isDarkMode ? 'text-gray-600 cursor-default' : 'text-gray-300 cursor-default')
                : ''
                }`}
              style={refreshInterval !== (inputVal * (inputUnit === 'm' ? 60 : 1)) ? { color: `rgb(${themeColors.accentRgb})` } : undefined}
              title="Apply Refresh Rate"
              disabled={refreshInterval === (inputVal * (inputUnit === 'm' ? 60 : 1))}
            >
              <Check size={12} />
            </button>
          </div>

          {/* Time range selector */}
          <div className={`flex items-center p-1 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
            {['1m', '1h', '24h', '7d', '15d'].map(r => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all whitespace-nowrap ${range === r
                  ? `${isDarkMode ? 'bg-white/10 text-white' : 'bg-white text-gray-900 shadow-sm'}`
                  : `${isDarkMode ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-900'}`
                  }`}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Chart */}
      <div className="flex-1 min-h-0 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 5, bottom: 20, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#333' : '#eee'} vertical={false} />
            <XAxis
              dataKey="time"
              type="number"
              domain={['auto', 'auto']}
              tickFormatter={(ts) => {
                const date = new Date(ts);
                if (range === '1m') return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                if (range === '1h' || range === '24h') return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
              }}
              stroke="#666"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
              dy={10}
            />
            {metric === 'all' ? (
              <>
                <YAxis
                  yAxisId="left"
                  stroke="#666"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 100]}
                  unit="%"
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#666"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 85]}
                  tickFormatter={(val) => val}
                  unit="°"
                />
              </>
            ) : (
              <YAxis
                stroke="#666"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                domain={metric === 'temp' ? [0, 85] : [0, 100]}
                tickFormatter={metric === 'temp' ? ((val) => val) : undefined}
                unit={metric === 'temp' ? '°' : '%'}
              />
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: isDarkMode ? '#000' : '#fff',
                border: '1px solid #333',
                borderRadius: '8px'
              }}
              labelFormatter={(ts) => new Date(ts).toLocaleString()}
              formatter={(val, name) => {
                if (metric !== 'all') return [`${val}${metric === 'temp' ? '°C' : '%'}`, metric.toUpperCase()];
                const isTemp = name.toLowerCase() === 'temp';
                const unit = isTemp ? '°C' : '%';
                return [`${val}${unit}`, name];
              }}
            />
            {metric !== 'all' ? (
              <Line
                type="monotone"
                dataKey="value"
                stroke={colorCpu}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
                animationDuration={500}
              />
            ) : (
              <>
                <Line yAxisId="left" type="monotone" dataKey="cpu" stroke={colorCpu} strokeWidth={2} dot={false} name="CPU" />
                <Line yAxisId="left" type="monotone" dataKey="mem" stroke={colorMem} strokeWidth={2} dot={false} name="RAM" />
                <Line yAxisId="right" type="monotone" dataKey="temp" stroke={colorTemp} strokeWidth={2} dot={false} name="Temp" />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
