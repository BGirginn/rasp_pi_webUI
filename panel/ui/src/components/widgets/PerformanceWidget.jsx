import { useState, useEffect } from 'react';
import { Activity, Thermometer, HardDrive, Layers, Check } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';
import { api } from '../../services/api';

export function PerformanceWidget({ variant, width, height }) {
  const { stats } = useDashboard();
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  const [metric, setMetric] = useState('all'); // cpu, mem, temp, all
  const [range, setRange] = useState('1h');   // 1m, 1h, 24h, 7d, 15d
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
    const fetchData = async () => {
      setLoading(true);
      try {
        const params = getRangeParams(range);

        if (metric === 'all') {
          // Fetch all 3 metrics
          const keys = {
            cpu: 'host.cpu.pct_total',
            mem: 'host.mem.pct',
            temp: 'host.temp.cpu_c'
          };

          let responses = {};

          if (params.type === 'summary') {
            // Use POST for summary data to avoid antivirus blocks
            const [cpuRes, memRes, tempRes] = await Promise.all([
              api.post(`/telemetry/metrics/series/query`, { metrics: keys.cpu, start: params.start }),
              api.post(`/telemetry/metrics/series/query`, { metrics: keys.mem, start: params.start }),
              api.post(`/telemetry/metrics/series/query`, { metrics: keys.temp, start: params.start })
            ]);
            responses = {
              cpu: cpuRes.data?.[0]?.points || [],
              mem: memRes.data?.[0]?.points || [],
              temp: tempRes.data?.[0]?.points || []
            };
          } else {
            // Use POST for raw data to avoid antivirus blocks
            const [cpuRes, memRes, tempRes] = await Promise.all([
              api.post(`/telemetry/metrics/query`, { metrics: keys.cpu, start: params.start, step: params.step || 60 }),
              api.post(`/telemetry/metrics/query`, { metrics: keys.mem, start: params.start, step: params.step || 60 }),
              api.post(`/telemetry/metrics/query`, { metrics: keys.temp, start: params.start, step: params.step || 60 })
            ]);
            responses = {
              cpu: cpuRes.data?.[0]?.points || [],
              mem: memRes.data?.[0]?.points || [],
              temp: tempRes.data?.[0]?.points || []
            };
          }

          // Merge data
          // Base it on the longest array (usually they should be same length if aligned)
          // Use step as tolerance, defaulting to 2s if step is small or undefined
          const tolerance = (params.step && params.step > 5) ? params.step / 2 : 2;

          const merged = responses.cpu.map(p => {
            const ts = p.ts;
            const memP = responses.mem.find(x => Math.abs(x.ts - ts) <= tolerance);
            const tempP = responses.temp.find(x => Math.abs(x.ts - ts) <= tolerance);
            return {
              time: ts * 1000,
              cpu: Math.round(p.value * 10) / 10,
              mem: memP ? Math.round(memP.value * 10) / 10 : null,
              temp: tempP ? Math.round(tempP.value * 10) / 10 : null
            };
          });
          setData(merged);

        } else {
          // Single metric fetch
          const metricKey = getMetricKey(metric);
          let points = [];

          if (params.type === 'summary') {
            // Use POST for summary data
            const res = await api.post(`/telemetry/metrics/series/query`, { metrics: metricKey, start: params.start });
            if (res.data && res.data[0]) points = res.data[0].points;
          } else {
            // Use POST for raw data
            const res = await api.post(`/telemetry/metrics/query`, { metrics: metricKey, start: params.start, step: params.step || 60 });
            if (res.data && res.data[0]) points = res.data[0].points;
          }

          setData(points.map(p => ({
            time: p.ts * 1000,
            value: Math.round(p.value * 10) / 10
          })));
        }
      } catch (err) {
        console.error("Failed to fetch history:", err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval * 1000);
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
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'cpu' ? `font-bold bg-${themeColors.accent}/10 text-${themeColors.accent}` : 'text-gray-500 hover:text-gray-400'}`}
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
                className={`transition-all duration-200 px-2 py-0.5 rounded ${metric === 'all' ? `font-bold bg-${themeColors.accent}/10 text-${themeColors.accent}` : 'text-gray-500 hover:text-gray-400'}`}
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
                : (isDarkMode ? `hover:bg-${themeColors.accent}/20 text-${themeColors.accent}` : `hover:bg-${themeColors.accent}/10 text-${themeColors.accent}-600`)
                }`}
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
