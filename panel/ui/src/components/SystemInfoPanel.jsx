import { motion } from 'motion/react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useDashboard } from '../contexts/DashboardContext';
import { Server, Cpu, HardDrive, Cloud } from 'lucide-react';

export function SystemInfoPanel() {
  const { theme } = useTheme();
  const { stats } = useDashboard();
  const themeColors = getThemeColors(theme);

  // Build system info from live data
  const systemInfo = [
    { label: 'HOSTNAME', value: stats.hostname || 'Unknown', icon: Server },
    { label: 'MODEL', value: stats.model || stats.machine || 'Unknown', icon: Cpu },
    { label: 'KERNEL', value: stats.kernel || 'N/A', icon: HardDrive },
    { label: 'ARCHITECTURE', value: stats.machine || 'Unknown', icon: Cloud },
  ];

  return (<motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.4 }} className="bg-black/40 backdrop-blur-xl rounded-2xl p-6 border border-white/10 relative overflow-hidden group hover:border-cyan-500/50 transition-all" style={{
    boxShadow: `inset 0 0 40px -20px ${themeColors.glow}`
  }}>
    <div className="relative z-10">
      <div className="flex items-center justify-between mb-6">
        <h3 className={`text-lg bg-gradient-to-r ${themeColors.primary} bg-clip-text text-transparent`}>
          System Info
        </h3>
        <motion.div animate={{
          rotate: 360,
        }} transition={{
          duration: 4,
          repeat: Infinity,
          ease: 'linear',
        }} className={`w-2 h-2 rounded-full bg-gradient-to-r ${themeColors.secondary}`} />
      </div>

      <div className="space-y-3">
        {systemInfo.map((item, index) => {
          const Icon = item.icon;
          return (<motion.div key={item.label} initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.5 + index * 0.1, duration: 0.3 }} whileHover={{ x: 4 }} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg border border-white/10 hover:border-purple-500/50 transition-all cursor-pointer group/item">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center flex-shrink-0`}>
              <Icon size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-500 mb-0.5">{item.label}</div>
              <div className="text-sm text-gray-300 truncate">{item.value}</div>
            </div>
            <div className={`w-1 h-8 bg-gradient-to-b ${themeColors.secondary} rounded-full opacity-0 group-hover/item:opacity-100 transition-opacity`} />
          </motion.div>);
        })}
      </div>
    </div>
  </motion.div>);
}
