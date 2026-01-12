import { motion } from 'motion/react';
import { useState } from 'react';
import { Trash2, Settings } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { useDashboard } from '../contexts/DashboardContext';
export function WidgetWrapper({ widget, children }) {
    const { isEditMode, isDarkMode } = useTheme();
    const { removeWidget, resizeWidget, changeWidgetVariant } = useDashboard();
    const [showMenu, setShowMenu] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const handleDragStart = (e) => {
        if (!isEditMode)
            return;
        setIsDragging(true);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('widgetId', widget.id);
    };
    const handleDragEnd = () => {
        setIsDragging(false);
    };
    const sizes = [
        { width: 1, height: 1, label: '1×1' },
        { width: 2, height: 1, label: '2×1' },
        { width: 1, height: 2, label: '1×2' },
        { width: 2, height: 2, label: '2×2' },
        { width: 3, height: 2, label: '3×2' },
        { width: 2, height: 3, label: '2×3' },
        { width: 4, height: 2, label: '4×2' },
        { width: 4, height: 4, label: '4×4' },
    ];
    const variants = ['list', 'graphic'];
    return (<div className={`relative group/widget h-full ${showMenu ? 'z-[9999]' : ''}`} draggable={isEditMode} onDragStart={handleDragStart} onDragEnd={handleDragEnd} style={{ gridColumn: `span ${widget.width}`, gridRow: `span ${widget.height}` }}>
      <motion.div className={`h-full relative ${isDragging ? 'opacity-50' : ''} ${isEditMode ? 'cursor-move' : ''}`} whileHover={isEditMode ? { scale: 1.01 } : {}} transition={{ duration: 0.2 }}>
        {isEditMode && (<div className="absolute top-2 right-2 z-50 flex gap-2">
            <button onClick={() => setShowMenu(!showMenu)} className={`p-2 ${isDarkMode ? 'bg-black/80' : 'bg-white'} backdrop-blur-sm rounded-lg border ${isDarkMode ? 'border-white/20 hover:border-purple-500/50' : 'border-gray-300 hover:border-purple-500'} transition-all shadow-lg`}>
              <Settings size={16}/>
            </button>
            <button onClick={() => removeWidget(widget.id)} className={`p-2 ${isDarkMode ? 'bg-black/80' : 'bg-white'} backdrop-blur-sm rounded-lg border ${isDarkMode ? 'border-white/20 hover:border-red-500/50' : 'border-gray-300 hover:border-red-500'} transition-all text-red-400 shadow-lg`}>
              <Trash2 size={16}/>
            </button>
          </div>)}

        {isEditMode && showMenu && (<motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className={`absolute top-14 right-2 z-[9999] ${isDarkMode ? 'bg-black/90' : 'bg-white'} backdrop-blur-xl rounded-xl border ${isDarkMode ? 'border-white/20' : 'border-gray-300'} p-4 w-64 shadow-2xl max-h-[80vh] overflow-y-auto`}>
            <div className="mb-4">
              <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-2`}>SIZE</div>
              <div className="grid grid-cols-3 gap-2">
                {sizes.map(size => (<button key={size.label} onClick={() => resizeWidget(widget.id, size.width, size.height)} className={`px-3 py-2 rounded-lg text-sm transition-all ${widget.width === size.width && widget.height === size.height
                    ? isDarkMode
                        ? 'bg-purple-500/30 border border-purple-500/50 text-purple-300'
                        : 'bg-purple-100 border border-purple-500 text-purple-700'
                    : isDarkMode
                        ? 'bg-white/5 border border-white/10 hover:bg-white/10'
                        : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'}`}>
                    {size.label}
                  </button>))}
              </div>
            </div>

            <div>
              <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-2`}>VARIANT</div>
              <div className="grid grid-cols-2 gap-2">
                {variants.map(variant => (<button key={variant} onClick={() => changeWidgetVariant(widget.id, variant)} className={`px-3 py-2 rounded-lg text-sm transition-all ${widget.variant === variant
                    ? isDarkMode
                        ? 'bg-purple-500/30 border border-purple-500/50 text-purple-300'
                        : 'bg-purple-100 border border-purple-500 text-purple-700'
                    : isDarkMode
                        ? 'bg-white/5 border border-white/10 hover:bg-white/10'
                        : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'}`}>
                    {variant}
                  </button>))}
              </div>
            </div>
          </motion.div>)}

        {children}
      </motion.div>
    </div>);
}
