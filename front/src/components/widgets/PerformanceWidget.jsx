import { Activity } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

export function PerformanceWidget({ variant, width, height }) {
  const { history, stats } = useDashboard();
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  const dataPoints = history.cpu;
  const maxHeight = 100; // CPU is always 0-100
  const currentValue = stats.cpu;

  // Calculate stats ensuring safe numbers and avoid NaN
  const validPoints = dataPoints.filter(p => typeof p === 'number' && !isNaN(p));
  const avgValue = validPoints.length > 0
    ? Math.round(validPoints.reduce((a, b) => a + b, 0) / validPoints.length)
    : 0;
  const peakValue = validPoints.length > 0 ? Math.round(Math.max(...validPoints)) : 0;
  if (variant === 'list') {
    return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
          <Activity size={20} className="text-white" />
        </div>
        <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>CPU Performance</h3>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Current</span>
          <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{currentValue}%</span>
        </div>
        <div className="flex justify-between items-center">
          <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Average</span>
          <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{avgValue}%</span>
        </div>
        <div className="flex justify-between items-center">
          <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Peak</span>
          <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{peakValue}%</span>
        </div>
      </div>
    </div>);
  }
  // Graphic variant - full chart
  return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
          <Activity size={24} className="text-white" />
        </div>
        <div>
          <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Performance</h3>
          <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Real-time CPU usage</p>
        </div>
      </div>
      <div className="text-right">
        <p className={`text-3xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{currentValue}<span className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>%</span></p>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'}`}>Current</p>
      </div>
    </div>

    <div className="relative h-32 mb-4">
      <div className="absolute inset-0 flex items-end gap-0.5">
        {dataPoints.map((point, index) => (<div key={index} className={`flex-1 bg-gradient-to-t ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} rounded-t transition-all duration-300`} style={{ height: `${(point / maxHeight) * 100}%` }} />))}
      </div>
    </div>

    <div className="grid grid-cols-3 gap-4 text-center">
      <div>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Average</p>
        <p className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{avgValue}%</p>
      </div>
      <div>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Peak</p>
        <p className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{peakValue}%</p>
      </div>
      <div>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Load</p>
        <p className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{(stats.load1m || 0).toFixed(2)}</p>
      </div>
    </div>
  </div>);
}
