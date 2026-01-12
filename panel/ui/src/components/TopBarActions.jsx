import { motion } from 'motion/react';
import { Bell, Terminal } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { useNavigation } from '../contexts/NavigationContext';
export function TopBarActions() {
    const { isDarkMode } = useTheme();
    const { setCurrentPage } = useNavigation();
    return (<div className="flex items-center gap-3">
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setCurrentPage('alerts')} className={`relative p-3 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-white border-gray-300 hover:border-gray-400'} border transition-all`}>
        <Bell size={20}/>
        <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-xs text-white">
          0
        </span>
      </motion.button>

      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setCurrentPage('terminal')} className={`p-3 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-white border-gray-300 hover:border-gray-400'} border transition-all`}>
        <Terminal size={20}/>
      </motion.button>
    </div>);
}
