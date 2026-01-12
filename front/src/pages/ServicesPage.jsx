import { motion } from 'motion/react';
import { useState } from 'react';
import { RefreshCw, Package } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const filterOptions = [
    { label: 'All', value: 'all', color: 'purple' },
    { label: 'Docker', value: 'docker', color: 'blue' },
    { label: 'Systemd', value: 'systemd', color: 'gray' },
    { label: 'Running', value: 'running', color: 'green' },
    { label: 'Stopped', value: 'stopped', color: 'red' },
];
export function ServicesPage() {
    const [activeFilter, setActiveFilter] = useState('all');
    const [searchTerm, setSearchTerm] = useState('');
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    return (<div>
      <div className="flex items-center justify-between mb-6">
        <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
          Services
        </h1>
        <div className="flex items-center gap-4">
          <input type="text" placeholder="Search services..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className={`px-4 py-2 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 text-white placeholder-gray-500' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400'} border focus:outline-none focus:border-purple-500`}/>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border`}>
            <RefreshCw size={18}/>
            <span>Refresh</span>
          </motion.button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-8">
        {filterOptions.map((option) => (<motion.button key={option.value} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveFilter(option.value)} className={`px-4 py-2 rounded-lg border text-sm transition-all ${activeFilter === option.value
                ? option.color === 'purple'
                    ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
                    : option.color === 'blue'
                        ? isDarkMode ? 'bg-blue-500/30 border-blue-500 text-blue-300' : 'bg-blue-100 border-blue-500 text-blue-700'
                        : option.color === 'green'
                            ? isDarkMode ? 'bg-green-500/30 border-green-500 text-green-300' : 'bg-green-100 border-green-500 text-green-700'
                            : option.color === 'red'
                                ? isDarkMode ? 'bg-red-500/30 border-red-500 text-red-300' : 'bg-red-100 border-red-500 text-red-700'
                                : isDarkMode ? 'bg-gray-500/30 border-gray-500 text-gray-300' : 'bg-gray-100 border-gray-500 text-gray-700'
                : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
            {option.label}
            {activeFilter === option.value && <span className="ml-2">0</span>}
          </motion.button>))}
      </div>

      {/* Empty State */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-16 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} text-center`}>
        <Package size={64} className={`mx-auto mb-4 ${isDarkMode ? 'text-gray-600' : 'text-gray-400'}`}/>
        <h3 className={`text-xl mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>No services found</h3>
        <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>No services discovered yet</p>
      </motion.div>
    </div>);
}
