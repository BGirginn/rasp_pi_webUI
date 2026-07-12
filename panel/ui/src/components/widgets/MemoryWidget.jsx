import { Cpu } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

export function MemoryWidget({ variant, width, height }) {
  const { theme, isDarkMode } = useTheme();
  const { stats, history } = useDashboard();
  const themeColors = getThemeColors(theme);

  const memUsage = stats.memory;
  const memHistory = history.memory;

  // List variant
  if (variant === 'list') {
    return (
      <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-4 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} flex items-center justify-between`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center flex-shrink-0`}>
            <Cpu size={20} className="text-white" />
          </div>
          <div>
            <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Memory</div>
            <div className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{memUsage}%</div>
          </div>
        </div>
        <div className={`h-16 w-24 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'} p-2`}>
          <div className="h-full flex items-end gap-0.5">
            {memHistory.slice(-10).map((val, i) => (
              <div key={i} className={`flex-1 bg-gradient-to-t from-emerald-500 to-green-600 rounded-t`} style={{ height: `${Math.max(5, val)}%` }} />
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
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center`}>
          <Cpu size={24} className="text-white" />
        </div>
        <div className="flex-1">
          <h3 className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Memory</h3>
          <p className={`text-3xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{memUsage}<span className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>%</span></p>
        </div>
      </div>

      <div className={`h-3 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden mb-2`}>
        <div className={`h-full bg-gradient-to-r from-emerald-500 to-green-600 rounded-full transition-all duration-300`} style={{ width: `${memUsage}%` }} />
      </div>

      <div className="flex justify-between text-xs">
        <span className={isDarkMode ? 'text-gray-500' : 'text-gray-600'}>{stats.memUsedGb} GB Used</span>
        <span className={isDarkMode ? 'text-gray-500' : 'text-gray-600'}>{stats.memTotalGb} GB Total</span>
      </div>
    </div>
  );
}
