import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { Cpu, Activity, HardDrive, Thermometer } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const timeRanges = [
    { label: 'Live', value: 'live' },
    { label: '1 Hour', value: '1h' },
    { label: '6 Hours', value: '6h' },
    { label: '24 Hours', value: '24h' },
    { label: '7 Days', value: '7d' },
];
const metrics = [
    { label: 'CPU Usage', value: 0.0, unit: '%', icon: Cpu, color: 'blue' },
    { label: 'Memory', value: 0.0, unit: '%', icon: Activity, color: 'green' },
    { label: 'Disk Usage', value: 0.0, unit: '%', icon: HardDrive, color: 'orange' },
    { label: 'Temperature', value: 0, unit: '°C', icon: Thermometer, color: 'red' },
];
export function TelemetryPage() {
    const [activeRange, setActiveRange] = useState('live');
    const [dataPoints, setDataPoints] = useState([]);
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    useEffect(() => {
        const points = Array.from({ length: 50 }, () => Math.random() * 100);
        setDataPoints(points);
    }, []);
    const maxHeight = Math.max(...dataPoints, 1);
    return (<div>
      <div className="flex items-center justify-between mb-6">
        <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
          Telemetry
        </h1>
        <div className="flex gap-2">
          {timeRanges.map((range) => (<motion.button key={range.value} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveRange(range.value)} className={`px-4 py-2 rounded-lg text-sm border transition-all ${activeRange === range.value
                ? range.value === 'live'
                    ? isDarkMode ? 'bg-green-500/30 border-green-500 text-green-300' : 'bg-green-100 border-green-500 text-green-700'
                    : isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
                : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
              {activeRange === range.value && range.value === 'live' && (<span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"/>)}
              {range.label}
            </motion.button>))}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {metrics.map((metric, index) => {
            const Icon = metric.icon;
            const colorClasses = {
                blue: isDarkMode ? 'from-blue-500 to-cyan-500' : 'from-blue-600 to-cyan-600',
                green: isDarkMode ? 'from-green-500 to-emerald-500' : 'from-green-600 to-emerald-600',
                orange: isDarkMode ? 'from-orange-500 to-yellow-500' : 'from-orange-600 to-yellow-600',
                red: isDarkMode ? 'from-red-500 to-pink-500' : 'from-red-600 to-pink-600',
            };
            return (<motion.div key={metric.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${colorClasses[metric.color]} flex items-center justify-center`}>
                  <Icon size={24} className="text-white"/>
                </div>
              </div>
              <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-2`}>{metric.label}</div>
              <div className={`text-3xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {metric.value.toFixed(metric.unit === '°C' ? 0 : 1)}
                <span className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} ml-1`}>{metric.unit}</span>
              </div>

              {/* Mini chart */}
              <div className="flex items-end gap-0.5 h-12 mt-4">
                {Array.from({ length: 20 }).map((_, i) => {
                    const height = Math.random() * 100;
                    return (<div key={i} className={`flex-1 bg-gradient-to-t ${colorClasses[metric.color]} rounded-t opacity-50`} style={{ height: `${height}%` }}/>);
                })}
              </div>
            </motion.div>);
        })}
      </div>

      {/* System Metrics Chart */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} mb-8`}>
        <h3 className={`text-lg mb-6 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>System Metrics</h3>
        
        <div className="flex items-end justify-between gap-1 h-64 mb-4">
          {dataPoints.map((point, index) => (<motion.div key={index} initial={{ height: 0 }} animate={{ height: `${(point / maxHeight) * 100}%` }} transition={{ delay: index * 0.01, duration: 0.3 }} className={`flex-1 bg-gradient-to-t ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} rounded-t`}/>))}
        </div>

        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full bg-gradient-to-r ${isDarkMode ? 'from-cyan-500 to-blue-500' : 'from-cyan-600 to-blue-600'}`}/>
            <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>pct_total</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full bg-gradient-to-r ${isDarkMode ? 'from-green-500 to-emerald-500' : 'from-green-600 to-emerald-600'}`}/>
            <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>pct</span>
          </div>
        </div>
      </motion.div>

      {/* Bottom Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
          <h3 className={`text-lg mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Load Average</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className={`text-2xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>0.00</div>
              <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'}`}>1 min</div>
            </div>
            <div>
              <div className={`text-2xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>0.00</div>
              <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'}`}>5 min</div>
            </div>
            <div>
              <div className={`text-2xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>0.00</div>
              <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'}`}>15 min</div>
            </div>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
          <h3 className={`text-lg mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Network I/O</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>⬇️ Received</span>
              <span className={`text-xl ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>0.00 GB</span>
            </div>
            <div className="flex items-center justify-between">
              <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>⬆️ Transmitted</span>
              <span className={`text-xl ${isDarkMode ? 'text-blue-400' : 'text-blue-600'}`}>0.00 GB</span>
            </div>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
          <h3 className={`text-lg mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Memory</h3>
          <div className="flex items-center justify-between">
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Used</span>
            <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>0.0 GB / 0.0 GB</span>
          </div>
        </motion.div>
      </div>
    </div>);
}
