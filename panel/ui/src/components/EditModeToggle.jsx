import { motion } from 'motion/react';
import { Edit3, Eye } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
export function EditModeToggle() {
    const { isEditMode, setIsEditMode, isDarkMode } = useTheme();
    return (<motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setIsEditMode(!isEditMode)} className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${isEditMode
            ? isDarkMode
                ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
                : 'bg-purple-100 border-purple-500 text-purple-700'
            : isDarkMode
                ? 'bg-white/5 border-white/10 hover:border-purple-500/50'
                : 'bg-white border-gray-300 hover:border-purple-500'}`}>
      {isEditMode ? <Eye size={18}/> : <Edit3 size={18}/>}
      <span className="text-sm">{isEditMode ? 'View Mode' : 'Edit Mode'}</span>
    </motion.button>);
}
