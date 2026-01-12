import { Wifi, ArrowDown, ArrowUp } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

function formatBytes(bytes, decimals = 1) {
  if (!+bytes) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function formatSpeed(bytesPerSec) {
  if (!+bytesPerSec) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytesPerSec) / Math.log(k));
  return `${parseFloat((bytesPerSec / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function NetworkWidget({ variant, width, height }) {
  const { theme, isDarkMode } = useTheme();
  const { stats } = useDashboard();
  const themeColors = getThemeColors(theme);

  // List variant - compact horizontal layout
  if (variant === 'list') {
    return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} flex items-center justify-between`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
          <Wifi size={20} className="text-white" />
        </div>
        <div>
          <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Network</h3>
          <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>eth0</p>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowDown size={16} className={isDarkMode ? 'text-green-400' : 'text-green-600'} />
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Download</span>
          </div>
          <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatSpeed(stats.netRxSpeed)}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowUp size={16} className={isDarkMode ? 'text-blue-400' : 'text-blue-600'} />
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Upload</span>
          </div>
          <span className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatSpeed(stats.netTxSpeed)}</span>
        </div>
      </div>
    </div>);
  }
  // Graphic variant - full network card
  return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
    <div className="flex items-center gap-3 mb-6">
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
        <Wifi size={24} className="text-white" />
      </div>
      <div>
        <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Network Activity</h3>
        <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>eth0 - Connected</p>
      </div>
    </div>

    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <ArrowDown size={20} className={isDarkMode ? 'text-green-400' : 'text-green-600'} />
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Download</span>
          </div>
          <span className={`text-2xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatSpeed(stats.netRxSpeed)}</span>
        </div>
        <div className={`h-2 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden`}>
          {/* Logic for bar width - normalizing to 10MB/s for visualization */}
          <div className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full" style={{ width: `${Math.min(100, (stats.netRxSpeed / 10485760) * 100)}%` }} />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <ArrowUp size={20} className={isDarkMode ? 'text-blue-400' : 'text-blue-600'} />
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Upload</span>
          </div>
          <span className={`text-2xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatSpeed(stats.netTxSpeed)}</span>
        </div>
        <div className={`h-2 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden`}>
          {/* Logic for bar width - normalizing to 5MB/s for visualization */}
          <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full" style={{ width: `${Math.min(100, (stats.netTxSpeed / 5242880) * 100)}%` }} />
        </div>
      </div>
    </div>

    <div className={`mt-6 pt-4 border-t ${isDarkMode ? 'border-white/10' : 'border-gray-200'} grid grid-cols-2 gap-4 text-center`}>
      <div>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Total RX</p>
        <p className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatBytes(stats.netRx)}</p>
      </div>
      <div>
        <p className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Total TX</p>
        <p className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{formatBytes(stats.netTx)}</p>
      </div>
    </div>
  </div>);
}
