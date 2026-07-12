import { Server } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

// Format uptime to human readable
function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return 'N/A';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days > 0) parts.push(`${days} days`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0 && days === 0) parts.push(`${minutes}m`);
  return parts.join(', ') || '< 1m';
}

export function SystemInfoWidget({ variant, width, height }) {
  const { theme, isDarkMode } = useTheme();
  const { stats } = useDashboard();
  const themeColors = getThemeColors(theme);

  // Build system info from live data
  const systemInfo = [
    { label: 'Hostname', value: stats.hostname || 'Unknown' },
    { label: 'Model', value: stats.model || stats.machine || 'Unknown' },
    { label: 'OS', value: stats.os || 'Unknown' },
    { label: 'Kernel', value: stats.kernel || 'N/A' },
    { label: 'Uptime', value: formatUptime(stats.uptime) },
    { label: 'IP Address', value: stats.ip || 'N/A' },
  ];

  return (
    <div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} overflow-hidden`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
      <div className="flex items-center gap-3 mb-6">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
          <Server size={24} className="text-white" />
        </div>
        <div>
          <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>System Info</h3>
          <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Device details</p>
        </div>
      </div>

      <div className="space-y-3">
        {systemInfo.map((item) => (
          <div key={item.label} className="flex justify-between items-start">
            <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{item.label}</span>
            <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-gray-900'} text-right max-w-[60%] truncate`}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
