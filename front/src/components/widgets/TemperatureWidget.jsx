import { Thermometer } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

export function TemperatureWidget({ variant, width, height }) {
  const { theme, isDarkMode } = useTheme();
  const { stats, history } = useDashboard();
  const themeColors = getThemeColors(theme);

  const temp = stats.temp;
  const tempHistory = history.temp || Array(10).fill(temp || 50);

  // List variant
  if (variant === 'list') {
    return (
      <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-4 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} flex items-center justify-between`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg bg-gradient-to-br from-rose-500 to-pink-600 flex items-center justify-center flex-shrink-0`}>
            <Thermometer size={20} className="text-white" />
          </div>
          <div>
            <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Temp</div>
            <div className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{temp}°C</div>
          </div>
        </div>
        <div className={`h-16 w-24 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'} p-2`}>
          <div className="h-full flex items-end gap-0.5">
            {tempHistory.slice(-10).map((val, i) => (
              <div key={i} className={`flex-1 bg-gradient-to-t from-rose-500 to-pink-600 rounded-t`} style={{ height: `${Math.max(5, Math.min(100, val))}%` }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Graphic variant
  return (
    <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br from-rose-500 to-pink-600 flex items-center justify-center`}>
          <Thermometer size={24} className="text-white" />
        </div>
        <div className="flex-1">
          <h3 className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Temperature</h3>
          <p className={`text-3xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{temp}<span className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>°C</span></p>
        </div>
      </div>

      <div className={`h-3 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden mb-2`}>
        <div className={`h-full bg-gradient-to-r from-rose-500 to-pink-600 rounded-full transition-all duration-300`} style={{ width: `${Math.min(100, (temp / 85) * 100)}%` }} />
      </div>

      <div className="flex justify-between text-xs">
        <span className={isDarkMode ? 'text-gray-500' : 'text-gray-600'}>Optimal</span>
        <span className={isDarkMode ? 'text-gray-500' : 'text-gray-600'}>Max: 85°C</span>
      </div>
    </div>
  );
}
