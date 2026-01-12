import { motion } from 'motion/react';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { WidgetLibrary } from './WidgetLibrary';
import { useTheme } from '../contexts/ThemeContext';
export function AddWidgetButton() {
    const [showLibrary, setShowLibrary] = useState(false);
    const { isDarkMode } = useTheme();
    return (<>
      <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }} onClick={() => setShowLibrary(true)} className={`w-full p-8 border-2 border-dashed ${isDarkMode ? 'border-white/20 hover:border-purple-500/50 text-gray-400 hover:text-purple-400' : 'border-gray-300 hover:border-purple-500 text-gray-600 hover:text-purple-600'} rounded-xl transition-all flex items-center justify-center gap-3`}>
        <Plus size={24}/>
        <span>Add Widget</span>
      </motion.button>

      <WidgetLibrary isOpen={showLibrary} onClose={() => setShowLibrary(false)}/>
    </>);
}
