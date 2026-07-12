import { motion } from 'motion/react';
import { Activity, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
export function PerformanceChart() {
    const [dataPoints, setDataPoints] = useState([]);
    const { theme } = useTheme();
    const themeColors = getThemeColors(theme);
    useEffect(() => {
        // Generate random data points for the chart
        const points = Array.from({ length: 30 }, () => Math.random() * 100);
        setDataPoints(points);
    }, []);
    return (<motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.2 }} className="bg-black/40 backdrop-blur-xl rounded-2xl p-6 border border-white/10 relative overflow-hidden group hover:border-purple-500/50 transition-all" style={{
            boxShadow: `inset 0 0 40px -20px ${themeColors.glow}`
        }}>
      {/* Animated background */}
      <motion.div animate={{
            x: [-100, 100, -100],
            opacity: [0.05, 0.15, 0.05],
        }} transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
        }} className={`absolute inset-0 bg-gradient-to-r ${themeColors.primary} blur-2xl`}/>

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${themeColors.secondary} flex items-center justify-center`}>
              <Activity size={20}/>
            </div>
            <div>
              <h3 className="text-lg">CPU Performance</h3>
              <p className="text-xs text-gray-400">Real-time monitoring</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-green-400">
            <TrendingUp size={16}/>
            <span className="text-sm">+12%</span>
          </div>
        </div>

        {/* Chart */}
        <div className="h-40 flex items-end gap-1">
          {dataPoints.map((value, index) => (<motion.div key={index} initial={{ height: 0, opacity: 0 }} animate={{ height: `${value}%`, opacity: 1 }} transition={{ delay: index * 0.02, duration: 0.5 }} className={`flex-1 bg-gradient-to-t ${themeColors.primary} rounded-t relative group/bar`}>
              <motion.div animate={{
                opacity: [0.3, 0.8, 0.3],
            }} transition={{
                duration: 2,
                repeat: Infinity,
                delay: index * 0.1,
            }} className="absolute inset-0 bg-white/20 rounded-t"/>
            </motion.div>))}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between mt-4 text-xs text-gray-500">
          <span>0s</span>
          <span>15s</span>
          <span>30s</span>
        </div>
      </div>
    </motion.div>);
}
