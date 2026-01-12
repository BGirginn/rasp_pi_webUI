import { motion } from 'motion/react';
import { Terminal, Zap } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const processes = [
    { name: 'systemd', cpu: '0.1%', mem: '1.2%', color: 'from-cyan-500 to-blue-500' },
    { name: 'nginx', cpu: '2.3%', mem: '3.1%', color: 'from-green-500 to-emerald-500' },
    { name: 'python3', cpu: '5.7%', mem: '8.4%', color: 'from-purple-500 to-pink-500' },
    { name: 'docker', cpu: '1.2%', mem: '12.3%', color: 'from-orange-500 to-red-500' },
    { name: 'node', cpu: '3.4%', mem: '6.7%', color: 'from-pink-500 to-purple-500' },
];
export function ProcessList() {
    const { theme } = useTheme();
    const themeColors = getThemeColors(theme);
    return (<motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.4 }} className="bg-black/40 backdrop-blur-xl rounded-2xl p-6 border border-white/10 relative overflow-hidden group hover:border-pink-500/50 transition-all" style={{
            boxShadow: `inset 0 0 40px -20px ${themeColors.glow}`
        }}>
      {/* Animated background */}
      <motion.div animate={{
            y: [0, -50, 0],
            opacity: [0.05, 0.1, 0.05],
        }} transition={{
            duration: 6,
            repeat: Infinity,
            ease: 'easeInOut',
        }} className="absolute inset-0 bg-gradient-to-b from-pink-500 via-purple-500 to-cyan-500 blur-2xl"/>

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
              <Terminal size={20}/>
            </div>
            <div>
              <h3 className="text-lg">Top Processes</h3>
              <p className="text-xs text-gray-400">Active tasks</p>
            </div>
          </div>
          <motion.div animate={{
            opacity: [0.5, 1, 0.5],
        }} transition={{
            duration: 2,
            repeat: Infinity,
        }} className="flex items-center gap-2 text-yellow-400">
            <Zap size={16}/>
            <span className="text-sm">5 running</span>
          </motion.div>
        </div>

        <div className="space-y-3">
          {processes.map((process, index) => (<motion.div key={process.name} initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.5 + index * 0.1 }} whileHover={{ x: 5, scale: 1.02 }} className="p-3 bg-white/5 rounded-lg border border-white/10 hover:border-pink-500/50 transition-all cursor-pointer group/process">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <motion.div animate={{
                rotate: [0, 360],
            }} transition={{
                duration: 3,
                repeat: Infinity,
                ease: 'linear',
            }} className={`w-2 h-2 rounded-full bg-gradient-to-r ${process.color}`}/>
                  <span className="text-sm">{process.name}</span>
                </div>
                <div className="flex gap-4 text-xs text-gray-400">
                  <span>CPU: <span className="text-white">{process.cpu}</span></span>
                  <span>MEM: <span className="text-white">{process.mem}</span></span>
                </div>
              </div>
              <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                <motion.div initial={{ width: 0 }} animate={{ width: process.cpu }} transition={{ delay: 0.5 + index * 0.1, duration: 1 }} className={`h-full bg-gradient-to-r ${process.color} relative`}>
                  <motion.div animate={{
                x: ['-100%', '200%'],
            }} transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'linear',
                delay: index * 0.2,
            }} className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"/>
                </motion.div>
              </div>
            </motion.div>))}
        </div>
      </div>
    </motion.div>);
}
