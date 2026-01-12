import { motion, AnimatePresence } from 'motion/react';
import { X, Plus, Cpu, Activity, HardDrive, Thermometer, Wifi, Terminal, Server } from 'lucide-react';
import { useDashboard } from '../contexts/DashboardContext';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const widgetTemplates = [
    { type: 'cpu', name: 'CPU Monitor', icon: Cpu },
    { type: 'memory', name: 'Memory Monitor', icon: Activity },
    { type: 'disk', name: 'Disk Monitor', icon: HardDrive },
    { type: 'temperature', name: 'Temperature', icon: Thermometer },
    { type: 'performance', name: 'Performance Chart', icon: Activity },
    { type: 'network', name: 'Network Activity', icon: Wifi },
    { type: 'processes', name: 'Process List', icon: Terminal },
    { type: 'system-info', name: 'System Info', icon: Server },
];
export function WidgetLibrary({ isOpen, onClose }) {
    const { addWidget, widgets } = useDashboard();
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    const handleAddWidget = (template) => {
        const newWidget = {
            id: `${template.type}-${Date.now()}`,
            type: template.type,
            width: template.type === 'cpu' || template.type === 'memory' || template.type === 'disk' || template.type === 'temperature' ? 1 : 2,
            height: template.type === 'cpu' || template.type === 'memory' || template.type === 'disk' || template.type === 'temperature' ? 1 : 2,
            variant: 'default',
            position: {
                row: Math.floor(widgets.length / 4),
                col: widgets.length % 4
            },
        };
        addWidget(newWidget);
        onClose();
    };
    return (<AnimatePresence>
      {isOpen && (<>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"/>
          <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }} className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl ${isDarkMode ? 'bg-black/90' : 'bg-white'} backdrop-blur-xl rounded-2xl border ${isDarkMode ? 'border-white/20' : 'border-gray-300'} p-6 z-50 shadow-2xl`}>
            <div className="flex items-center justify-between mb-6">
              <h2 className={`text-2xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
                Widget Library
              </h2>
              <button onClick={onClose} className={`p-2 ${isDarkMode ? 'hover:bg-white/10' : 'hover:bg-gray-100'} rounded-lg transition-all`}>
                <X size={24}/>
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {widgetTemplates.map((template, index) => {
                const Icon = template.icon;
                return (<motion.button key={template.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }} onClick={() => handleAddWidget(template)} className={`flex items-center gap-4 p-4 ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'} rounded-xl border ${isDarkMode ? 'border-white/10 hover:border-purple-500/50' : 'border-gray-200 hover:border-purple-500'} transition-all group text-left`}>
                    <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
                      <Icon size={24} className="text-white"/>
                    </div>
                    <div className="flex-1">
                      <div className={`text-sm mb-1 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{template.name}</div>
                      <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Click to add</div>
                    </div>
                    <Plus size={20} className={`${isDarkMode ? 'text-gray-400 group-hover:text-purple-400' : 'text-gray-600 group-hover:text-purple-600'} transition-colors`}/>
                  </motion.button>);
            })}
            </div>
          </motion.div>
        </>)}
    </AnimatePresence>);
}
