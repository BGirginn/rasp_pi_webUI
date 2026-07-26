import { motion } from 'motion/react';
import { Check, Moon, Palette, Sun } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { useState } from 'react';
const themes = [
    { name: 'purple', label: 'Purple Neon', color: '#a855f7' },
    { name: 'cyan', label: 'Cyan Wave', color: '#06b6d4' },
    { name: 'green', label: 'Matrix Green', color: '#22c55e' },
    { name: 'rainbow', label: 'RGB Spectrum', color: '#ec4899' },
    { name: 'sage', label: 'Sage', color: '#7fa98f' },
];
export function ThemeSelector() {
    const { theme, setTheme, isDarkMode, setIsDarkMode } = useTheme();
    const [isOpen, setIsOpen] = useState(false);
    return (<div className="relative">
      <motion.button whileTap={{ scale: 0.96 }} onClick={() => setIsOpen(!isOpen)} className="icon-button" title="Appearance">
        <Palette size={18}/>
      </motion.button>

      {isOpen && (<motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="appearance-popover">
          <div className="popover-label">Appearance</div>
          <div className="appearance-mode">
              <button onClick={() => setIsDarkMode(true)} className={isDarkMode ? 'is-selected' : ''}>
                <Moon size={16} /> Dark
              </button>
              <button onClick={() => setIsDarkMode(false)} className={!isDarkMode ? 'is-selected' : ''}>
                <Sun size={16} /> Light
              </button>
          </div>

          <div className="popover-label">Accent</div>
          <div className="accent-options">
            {themes.map((item) => (
              <button key={item.name} onClick={() => {
                setTheme(item.name);
                setIsOpen(false);
              }} className={theme === item.name ? 'is-selected' : ''}>
                <span style={{ backgroundColor: item.color }} />
                <span>{item.label}</span>
                {theme === item.name && <Check size={15} />}
              </button>
            ))}
          </div>
        </motion.div>)}
    </div>);
}
