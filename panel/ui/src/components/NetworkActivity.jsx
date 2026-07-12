import { motion } from 'motion/react';
import { ArrowDown, ArrowUp, Wifi } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
export function NetworkActivity() {
    const { theme } = useTheme();
    const themeColors = getThemeColors(theme);
    return (<motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.3 }} className="bg-black/40 backdrop-blur-xl rounded-2xl p-6 border border-white/10 relative overflow-hidden group hover:border-cyan-500/50 transition-all" style={{
            boxShadow: `inset 0 0 40px -20px ${themeColors.glow}`
        }}>
      {/* Animated background */}
      <motion.div animate={{
            rotate: [0, 360],
            scale: [1, 1.2, 1],
            opacity: [0.05, 0.15, 0.05],
        }} transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
        }} className={`absolute inset-0 bg-gradient-to-br ${themeColors.primary} blur-2xl`}/>

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
              <Wifi size={20}/>
            </div>
            <div>
              <h3 className="text-lg">Network Activity</h3>
              <p className="text-xs text-gray-400">eth0 interface</p>
            </div>
          </div>
          <motion.div animate={{
            scale: [1, 1.2, 1],
        }} transition={{
            duration: 2,
            repeat: Infinity,
        }} className="w-2 h-2 rounded-full bg-green-500"/>
        </div>

        <div className="space-y-6">
          {/* Download */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ArrowDown size={18} className="text-green-400"/>
                <span className="text-sm text-gray-400">Download</span>
              </div>
              <div className="text-right">
                <div className="text-2xl">2.4 <span className="text-sm text-gray-400">MB/s</span></div>
                <div className="text-xs text-gray-500">Peak: 5.2 MB/s</div>
              </div>
            </div>
            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
              <motion.div initial={{ width: 0 }} animate={{ width: '45%' }} transition={{ delay: 0.3, duration: 1 }} className="h-full bg-gradient-to-r from-green-500 to-emerald-500 relative">
                <motion.div animate={{
            x: ['-100%', '200%'],
        }} transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'linear',
        }} className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"/>
              </motion.div>
            </div>
          </div>

          {/* Upload */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ArrowUp size={18} className="text-blue-400"/>
                <span className="text-sm text-gray-400">Upload</span>
              </div>
              <div className="text-right">
                <div className="text-2xl">0.8 <span className="text-sm text-gray-400">MB/s</span></div>
                <div className="text-xs text-gray-500">Peak: 1.9 MB/s</div>
              </div>
            </div>
            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
              <motion.div initial={{ width: 0 }} animate={{ width: '20%' }} transition={{ delay: 0.5, duration: 1 }} className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 relative">
                <motion.div animate={{
            x: ['-100%', '200%'],
        }} transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'linear',
            delay: 0.5,
        }} className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"/>
              </motion.div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-white/10">
            <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.7 }} className="text-center">
              <div className="text-xs text-gray-500 mb-1">Packets</div>
              <div className="text-lg">1.2K</div>
            </motion.div>
            <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.8 }} className="text-center">
              <div className="text-xs text-gray-500 mb-1">Errors</div>
              <div className="text-lg text-green-400">0</div>
            </motion.div>
            <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.9 }} className="text-center">
              <div className="text-xs text-gray-500 mb-1">Dropped</div>
              <div className="text-lg text-yellow-400">3</div>
            </motion.div>
          </div>
        </div>
      </div>
    </motion.div>);
}
