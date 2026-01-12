import { motion } from 'motion/react';
import { useState } from 'react';
import { RefreshCw, CheckCircle, Plus, Bell, Settings } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const alertStats = [
    { label: 'Total Alerts', value: 0, color: 'purple' },
    { label: 'Firing', value: 0, color: 'red' },
    { label: 'Acknowledged', value: 0, color: 'blue' },
    { label: 'Critical', value: 0, color: 'orange' },
];
const filterTabs = [
    { label: 'All', value: 'all' },
    { label: 'Firing', value: 'firing' },
    { label: 'Acknowledged', value: 'acknowledged' },
    { label: 'Critical', value: 'critical' },
    { label: 'Warning', value: 'warning' },
];
export function AlertsPage() {
    const [activeTab, setActiveTab] = useState('all');
    const [activeFilter, setActiveFilter] = useState('alerts');
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    return (<div>
      <div className="flex items-center justify-between mb-6">
        <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
          Alerts
        </h1>
        <div className="flex items-center gap-3">
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-white border-gray-300 hover:border-gray-400'} border`}>
            <RefreshCw size={18}/>
            <span>Refresh</span>
          </motion.button>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border`}>
            <Plus size={18}/>
            <span>Create Rule</span>
          </motion.button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {alertStats.map((stat, index) => {
            const colorClasses = {
                purple: isDarkMode ? 'from-purple-500 to-fuchsia-500' : 'from-purple-600 to-fuchsia-600',
                red: isDarkMode ? 'from-red-500 to-pink-500' : 'from-red-600 to-pink-600',
                blue: isDarkMode ? 'from-blue-500 to-cyan-500' : 'from-blue-600 to-cyan-600',
                orange: isDarkMode ? 'from-orange-500 to-yellow-500' : 'from-orange-600 to-yellow-600',
            };
            return (<motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} text-center`}>
              <div className={`text-5xl mb-2 bg-gradient-to-r ${colorClasses[stat.color]} bg-clip-text text-transparent`}>
                {stat.value}
              </div>
              <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{stat.label}</div>
            </motion.div>);
        })}
      </div>

      {/* Tabs */}
      <div className="flex gap-3 mb-6">
        <button onClick={() => setActiveFilter('alerts')} className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm border transition-all ${activeFilter === 'alerts'
            ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
            : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
          <Bell size={16}/>
          Alerts (0)
        </button>
        <button onClick={() => setActiveFilter('rules')} className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm border transition-all ${activeFilter === 'rules'
            ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
            : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
          <Settings size={16}/>
          Rules (0)
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-8">
        {filterTabs.map((tab) => (<motion.button key={tab.value} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveTab(tab.value)} className={`px-4 py-2 rounded-lg text-sm border transition-all ${activeTab === tab.value
                ? isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-300' : 'bg-purple-50 border-purple-400 text-purple-700'
                : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10' : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}>
            {tab.label}
          </motion.button>))}
      </div>

      {/* Empty State */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-16 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} text-center`}>
        <CheckCircle size={64} className={`mx-auto mb-4 ${isDarkMode ? 'text-green-500' : 'text-green-600'}`}/>
        <h3 className={`text-xl mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>No alerts</h3>
        <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>All systems operating normally</p>
      </motion.div>
    </div>);
}
