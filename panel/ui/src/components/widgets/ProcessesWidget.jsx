import { Terminal, Cpu, HardDrive } from 'lucide-react';
import { useTheme, getThemeColors } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';

export function ProcessesWidget({ variant, width, height }) {
  const { theme, isDarkMode } = useTheme();
  const { processes } = useDashboard();
  const themeColors = getThemeColors(theme);

  // Graphic variant - show visual representation with bars
  if (variant === 'graphic') {
    const maxCpu = Math.max(...processes.map(p => p.cpu));
    const maxMemory = Math.max(...processes.map(p => p.memory));
    return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} overflow-hidden`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
            <Terminal size={24} className="text-white" />
          </div>
          <div>
            <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Top Processes</h3>
            <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{processes.length} running</p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {processes.map((process) => (<div key={process.pid}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-100'} flex items-center justify-center`}>
                <Terminal size={14} className={isDarkMode ? 'text-gray-400' : 'text-gray-600'} />
              </div>
              <div>
                <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{process.name}</span>
                <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} ml-2`}>PID: {process.pid}</span>
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1">
                <Cpu size={12} className={isDarkMode ? 'text-cyan-400' : 'text-cyan-600'} />
                <span className={isDarkMode ? 'text-cyan-400' : 'text-cyan-600'}>{process.cpu}%</span>
              </div>
              <div className="flex items-center gap-1">
                <HardDrive size={12} className={isDarkMode ? 'text-purple-400' : 'text-purple-600'} />
                <span className={isDarkMode ? 'text-purple-400' : 'text-purple-600'}>{process.memory}MB</span>
              </div>
            </div>
          </div>

          {/* CPU Usage Bar */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} w-12`}>CPU</span>
            <div className={`flex-1 h-2 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden`}>
              <div className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-300" style={{ width: `${(process.cpu / maxCpu) * 100}%` }} />
            </div>
          </div>

          {/* Memory Usage Bar */}
          <div className="flex items-center gap-2">
            <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} w-12`}>MEM</span>
            <div className={`flex-1 h-2 ${isDarkMode ? 'bg-white/5' : 'bg-gray-200'} rounded-full overflow-hidden`}>
              <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-300" style={{ width: `${(process.memory / maxMemory) * 100}%` }} />
            </div>
          </div>
        </div>))}
      </div>
    </div>);
  }
  // List variant - compact list view
  return (<div className={`h-full ${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} overflow-hidden`} style={{ boxShadow: isDarkMode ? `inset 0 0 40px -20px ${themeColors.glow}` : `0 4px 20px -5px ${themeColors.lightGlow}` }}>
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
          <Terminal size={24} className="text-white" />
        </div>
        <div>
          <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Top Processes</h3>
          <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{processes.length} running</p>
        </div>
      </div>
    </div>

    <div className="space-y-2">
      {processes.map((process) => (<div key={process.pid} className={`p-3 rounded-lg ${isDarkMode ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-50 hover:bg-gray-100'} transition-colors`}>
        <div className="flex items-center justify-between mb-1">
          <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{process.name}</span>
          <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'}`}>PID: {process.pid}</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>CPU: <span className={isDarkMode ? 'text-cyan-400' : 'text-cyan-600'}>{process.cpu}%</span></span>
          <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>MEM: <span className={isDarkMode ? 'text-purple-400' : 'text-purple-600'}>{process.memory}MB</span></span>
        </div>
      </div>))}
    </div>
  </div>);
}
