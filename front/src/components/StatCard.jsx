import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
const colorConfig = {
    cyan: {
        from: 'from-cyan-500',
        to: 'to-blue-500',
        bg: 'bg-cyan-500',
        text: 'text-cyan-400',
        border: 'border-cyan-500/50',
        shadow: 'shadow-cyan-500/50',
    },
    pink: {
        from: 'from-pink-500',
        to: 'to-purple-500',
        bg: 'bg-pink-500',
        text: 'text-pink-400',
        border: 'border-pink-500/50',
        shadow: 'shadow-pink-500/50',
    },
    green: {
        from: 'from-green-500',
        to: 'to-emerald-500',
        bg: 'bg-green-500',
        text: 'text-green-400',
        border: 'border-green-500/50',
        shadow: 'shadow-green-500/50',
    },
    orange: {
        from: 'from-orange-500',
        to: 'to-red-500',
        bg: 'bg-orange-500',
        text: 'text-orange-400',
        border: 'border-orange-500/50',
        shadow: 'shadow-orange-500/50',
    },
};
export function StatCard({ icon: Icon, title, value, unit, max, color, status }) {
    const [isHovered, setIsHovered] = useState(false);
    const [animatedValue, setAnimatedValue] = useState(0);
    const colors = colorConfig[color];
    const percentage = (parseFloat(value) / parseFloat(max)) * 100;
    useEffect(() => {
        const target = parseFloat(value);
        const duration = 2000;
        const steps = 60;
        const increment = target / steps;
        let current = 0;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                setAnimatedValue(target);
                clearInterval(timer);
            }
            else {
                setAnimatedValue(current);
            }
        }, duration / steps);
        return () => clearInterval(timer);
    }, [value]);
    return (<motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} whileHover={{ y: -4, scale: 1.01 }} transition={{ duration: 0.2, ease: 'easeOut' }} onHoverStart={() => setIsHovered(true)} onHoverEnd={() => setIsHovered(false)} className={`relative bg-black/60 backdrop-blur-xl rounded-2xl p-6 border ${colors.border} overflow-hidden group cursor-pointer transition-all`} style={{
            boxShadow: isHovered
                ? `0 0 30px -5px ${color === 'cyan' ? 'rgba(6, 182, 212, 0.5)' : color === 'pink' ? 'rgba(236, 72, 153, 0.5)' : color === 'green' ? 'rgba(34, 197, 94, 0.5)' : 'rgba(249, 115, 22, 0.5)'}, inset 0 0 60px -20px ${color === 'cyan' ? 'rgba(6, 182, 212, 0.3)' : color === 'pink' ? 'rgba(236, 72, 153, 0.3)' : color === 'green' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(249, 115, 22, 0.3)'}`
                : `inset 0 0 40px -20px ${color === 'cyan' ? 'rgba(6, 182, 212, 0.15)' : color === 'pink' ? 'rgba(236, 72, 153, 0.15)' : color === 'green' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(249, 115, 22, 0.15)'}`
        }}>
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colors.from} ${colors.to} flex items-center justify-center relative overflow-hidden`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${colors.from} ${colors.to} animate-pulse`}/>
            <Icon size={24} className="relative z-10"/>
          </div>
          <div className="text-xs text-gray-400">{status}</div>
        </div>

        <div className="text-xs text-gray-500 mb-2">{title}</div>
        
        <div className="flex items-baseline gap-1 mb-4">
          <motion.span className="text-4xl" key={animatedValue}>
            {animatedValue.toFixed(1)}
          </motion.span>
          <span className="text-gray-400">{unit}</span>
          <span className="text-gray-600 ml-2">/ {max} {unit}</span>
        </div>

        {/* Progress bar */}
        <div className="relative h-2 bg-white/5 rounded-full overflow-hidden">
          <motion.div initial={{ width: 0 }} animate={{ width: `${percentage}%` }} transition={{ duration: 2, ease: 'easeOut' }} className={`h-full bg-gradient-to-r ${colors.from} ${colors.to} rounded-full relative`}>
            <motion.div animate={{
            x: ['-100%', '100%'],
        }} transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'linear',
        }} className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"/>
          </motion.div>
        </div>
      </div>
    </motion.div>);
}
