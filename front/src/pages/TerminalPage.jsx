import { motion } from 'motion/react';
import { useState } from 'react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useDashboard } from '../contexts/DashboardContext';

export function TerminalPage() {
  const [isConnected, setIsConnected] = useState(false);
  const { theme, isDarkMode } = useTheme();
  const { stats } = useDashboard();
  const themeColors = getThemeColors(theme);

  return (<div>
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-4">
        <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
          Terminal
        </h1>
        <span className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs ${isConnected
          ? isDarkMode ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-green-100 text-green-700 border border-green-300'
          : isDarkMode ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-red-100 text-red-700 border border-red-300'}`}>
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setIsConnected(!isConnected)} className={`px-6 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border`}>
        {isConnected ? 'Disconnect' : 'Connect'}
      </motion.button>
    </div>

    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/80' : 'bg-gray-900'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-700'} font-mono text-sm min-h-[600px]`}>
      {/* Terminal Header */}
      <div className={`flex items-center gap-2 pb-4 mb-4 border-b ${isDarkMode ? 'border-white/10' : 'border-gray-700'}`}>
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <div className="w-3 h-3 rounded-full bg-green-500" />
        </div>
        <div className="flex-1 text-center text-green-400 text-xs">
          Pi Control Panel - Web Terminal
        </div>
      </div>

      {/* Terminal Content */}
      {isConnected ? (<div className="space-y-2">
        <div className="text-green-400">
          <span className="text-cyan-400">pi@{stats.hostname || 'raspberrypi'}</span>
          <span className="text-white">:</span>
          <span className="text-blue-400">~</span>
          <span className="text-white">$</span>
          <span className="ml-2 animate-pulse">_</span>
        </div>
      </div>) : (<div className="text-yellow-500">
        Click "Connect" to start a terminal session.
      </div>)}
    </motion.div>

    {/* Footer Help */}
    {isConnected && (<motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mt-4 flex items-center gap-6 text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
      <div className="flex items-center gap-2">
        <kbd className={`px-2 py-1 rounded ${isDarkMode ? 'bg-white/10' : 'bg-gray-200'}`}>Ctrl+C</kbd>
        <span>to interrupt</span>
      </div>
      <div className="flex items-center gap-2">
        <kbd className={`px-2 py-1 rounded ${isDarkMode ? 'bg-white/10' : 'bg-gray-200'}`}>Ctrl+D</kbd>
        <span>to exit shell</span>
      </div>
    </motion.div>)}
  </div>);
}
