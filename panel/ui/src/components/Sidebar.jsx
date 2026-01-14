import { motion } from 'motion/react';
import { LayoutDashboard, Settings, Server, Wifi, Terminal, Bell, Activity, Monitor, LogOut } from 'lucide-react';
import { useState } from 'react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useNavigation } from '../contexts/NavigationContext';
import { api } from '../services/api';

export function Sidebar() {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const { theme, isDarkMode } = useTheme();
  const { currentPage, setCurrentPage } = useNavigation();
  const themeColors = getThemeColors(theme);

  const menuItems = [
    { icon: LayoutDashboard, label: 'Dashboard', active: currentPage === 'dashboard', page: 'dashboard' },
    { icon: Server, label: 'Services', active: currentPage === 'services', page: 'services' },
    { icon: Monitor, label: 'Devices', active: currentPage === 'devices', page: 'devices' },
    { icon: Activity, label: 'Telemetry', active: currentPage === 'telemetry', page: 'telemetry' },
    { icon: Wifi, label: 'Network', active: currentPage === 'network', page: 'network' },
    { icon: Terminal, label: 'Terminal', active: currentPage === 'terminal', page: 'terminal' },
    { icon: Bell, label: 'Alerts', active: currentPage === 'alerts', page: 'alerts' },
  ];
  const adminItems = [
    { icon: Settings, label: 'Settings', active: currentPage === 'settings', page: 'settings' },
  ];
  return (<motion.aside initial={{ x: -100, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className={`fixed left-0 top-0 h-full w-64 ${isDarkMode ? 'bg-black/40' : 'bg-white/80'} backdrop-blur-xl border-r ${isDarkMode ? 'border-white/10' : 'border-gray-200'} p-6 z-20 flex flex-col`}>

    {/* Scrollable Content Area */}
    <div className="flex-1 overflow-y-auto overflow-x-hidden -mx-4 px-4 scrollbar-none">
      {/* Logo */}
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.2, type: 'spring' }} className="flex items-center gap-3 mb-10 mt-2">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${themeColors.primary} flex items-center justify-center relative overflow-hidden`}>
          <motion.div animate={{
            rotate: 360,
          }} transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'linear',
          }} className={`absolute inset-0 bg-gradient-to-br ${themeColors.primary} opacity-50`} />
          <span className="text-2xl relative z-10">π</span>
        </div>
        <div>
          <div className="font-bold">Pi Control</div>
          <div className="text-xs text-gray-400">WIRELESS PANEL</div>
        </div>
      </motion.div>

      {/* Navigation */}
      <nav className="space-y-2 mb-8">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-4`}>
          MAIN
        </motion.div>
        {menuItems.map((item, index) => (<motion.button key={item.label} initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.4 + index * 0.05 }} onClick={() => setCurrentPage(item.page)} onMouseEnter={() => setHoveredIndex(index)} onMouseLeave={() => setHoveredIndex(null)} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all relative group ${item.active
          ? isDarkMode ? 'bg-white/10' : 'bg-purple-50'
          : isDarkMode ? 'hover:bg-white/5' : 'hover:bg-gray-100'}`}>
          {item.active && (<motion.div layoutId="activeTab" className={`absolute inset-0 bg-gradient-to-r ${themeColors.secondary} opacity-20 rounded-lg border border-${themeColors.accent}/50`} transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }} />)}

          <motion.div whileHover={{ scale: 1.1 }} transition={{ duration: 0.2 }} className={`relative z-10 ${item.active
            ? 'text-white'
            : isDarkMode ? 'text-gray-400 group-hover:text-white' : 'text-gray-600 group-hover:text-gray-900'}`}>
            <item.icon size={20} />
          </motion.div>

          <span className={`relative z-10 ${item.active ? 'text-white' : isDarkMode ? 'text-gray-400 group-hover:text-white' : 'text-gray-600 group-hover:text-gray-900'}`}>
            {item.label}
          </span>

          {hoveredIndex === index && (<motion.div initial={{ width: 0 }} animate={{ width: 4 }} className={`absolute right-0 top-1/2 -translate-y-1/2 h-8 bg-gradient-to-b ${themeColors.secondary} rounded-l`} />)}
        </motion.button>))}
      </nav>

      {/* Admin Section */}
      <div className="mt-8 mb-6">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-4`}>
          ADMIN
        </motion.div>
        {adminItems.map((item, index) => (<motion.button key={item.label} initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.7 + index * 0.05 }} onClick={() => setCurrentPage(item.page)} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all relative group ${item.active
          ? isDarkMode ? 'bg-white/10' : 'bg-purple-50'
          : isDarkMode ? 'hover:bg-white/5' : 'hover:bg-gray-100'}`}>
          {item.active && (<motion.div layoutId="activeTab" className={`absolute inset-0 bg-gradient-to-r ${themeColors.secondary} opacity-20 rounded-lg border border-${themeColors.accent}/50`} transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }} />)}

          <motion.div whileHover={{ scale: 1.1 }} transition={{ duration: 0.2 }} className={`relative z-10 ${item.active
            ? 'text-white'
            : isDarkMode ? 'text-gray-400 group-hover:text-white' : 'text-gray-600 group-hover:text-gray-900'}`}>
            <item.icon size={20} />
          </motion.div>

          <span className={`relative z-10 ${item.active ? 'text-white' : isDarkMode ? 'text-gray-400 group-hover:text-white' : 'text-gray-600 group-hover:text-gray-900'}`}>
            {item.label}
          </span>

          {hoveredIndex === index && (<motion.div initial={{ width: 0 }} animate={{ width: 4 }} className={`absolute right-0 top-1/2 -translate-y-1/2 h-8 bg-gradient-to-b ${themeColors.secondary} rounded-l`} />)}
        </motion.button>))}

        {/* Logout Button */}
        <motion.button initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.7 + adminItems.length * 0.05 }} onClick={() => {
          fetch('/api/auth/logout', { method: 'POST' }).finally(() => {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
          });
        }} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all relative group ${isDarkMode ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}>
          <motion.div whileHover={{ scale: 1.1 }} transition={{ duration: 0.2 }} className={`relative z-10 ${isDarkMode ? 'text-gray-400 group-hover:text-red-400' : 'text-gray-600 group-hover:text-red-600'}`}>
            <LogOut size={20} />
          </motion.div>
          <span className={`relative z-10 ${isDarkMode ? 'text-gray-400 group-hover:text-red-400' : 'text-gray-600 group-hover:text-red-600'}`}>
            Log Out
          </span>
        </motion.button>
      </div>
    </div>

    {/* Admin Profile (Static relative positioning) */}
    <motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.8 }} className="mt-auto pt-4 border-t border-gray-200/10">
      <div onClick={() => {
        fetch('/api/auth/logout', { method: 'POST' }).finally(() => {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        });
      }} className={`flex items-center gap-3 p-3 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-100 border-gray-300'} border hover:border-red-500/50 transition-all cursor-pointer group`}>
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center relative overflow-hidden`}>
          <div className={`absolute inset-0 bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} animate-pulse`} />
          <span className="relative z-10 text-white">A</span>
        </div>
        <div className="flex-1">
          <div className={`text-sm ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>admin</div>
          <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'group-hover:text-red-500 text-gray-600 transition-colors'}`}>
            <span className="group-hover:hidden">online</span>
            <span className="hidden group-hover:inline">Log Out</span>
          </div>
        </div>
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse group-hover:bg-red-500 transition-colors" />
      </div>
    </motion.div>
  </motion.aside>);
}
