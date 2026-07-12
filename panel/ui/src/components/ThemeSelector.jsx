import { motion } from 'motion/react';
import { Palette } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { useState } from 'react';
const themes = [
    { name: 'purple', label: 'Purple Neon', gradient: 'from-purple-600 to-fuchsia-600' },
    { name: 'cyan', label: 'Cyan Wave', gradient: 'from-cyan-600 to-blue-600' },
    { name: 'green', label: 'Matrix Green', gradient: 'from-green-600 to-emerald-600' },
    { name: 'rainbow', label: 'RGB Spectrum', gradient: 'from-cyan-500 via-purple-500 to-pink-500' },
];
export function ThemeSelector() {
    const { theme, setTheme, isDarkMode, setIsDarkMode } = useTheme();
    const [isOpen, setIsOpen] = useState(false);
    return (<div className="relative">
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setIsOpen(!isOpen)} className={`p-3 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-purple-500/50' : 'bg-white border-gray-300 hover:border-purple-500'} border transition-all`}>
        <Palette size={20}/>
      </motion.button>

      {isOpen && (<motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`absolute top-14 right-0 w-56 ${isDarkMode ? 'bg-black/90' : 'bg-white'} backdrop-blur-xl rounded-xl border ${isDarkMode ? 'border-white/10' : 'border-gray-300'} p-3 z-50 shadow-2xl`}>
          {/* Dark/Light Mode Toggle */}
          <div className={`mb-4 pb-3 border-b ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
            <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-2`}>APPEARANCE</div>
            <div className="flex gap-2">
              <button onClick={() => setIsDarkMode(true)} className={`flex-1 px-3 py-2 rounded-lg text-sm transition-all ${isDarkMode
                ? 'bg-white/10 border border-purple-500/50'
                : 'bg-gray-50 border border-transparent hover:bg-gray-100'}`}>
                Dark
              </button>
              <button onClick={() => setIsDarkMode(false)} className={`flex-1 px-3 py-2 rounded-lg text-sm transition-all ${!isDarkMode
                ? 'bg-purple-100 border border-purple-500 text-purple-700'
                : 'bg-white/5 border border-transparent hover:bg-white/10'}`}>
                Light
              </button>
            </div>
          </div>

          <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-3`}>COLOR THEME</div>
          <div className="space-y-2">
            {themes.map((t) => (<button key={t.name} onClick={() => {
                    setTheme(t.name);
                    setIsOpen(false);
                }} className={`w-full flex items-center gap-3 p-2 rounded-lg transition-all ${theme === t.name
                    ? isDarkMode
                        ? 'bg-white/10 border border-purple-500/50'
                        : 'bg-purple-50 border border-purple-500'
                    : isDarkMode
                        ? 'hover:bg-white/5 border border-transparent'
                        : 'hover:bg-gray-50 border border-transparent'}`}>
                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${t.gradient}`}/>
                <span className="text-sm">{t.label}</span>
              </button>))}
          </div>
        </motion.div>)}
    </div>);
}
