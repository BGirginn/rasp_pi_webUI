import { motion } from 'motion/react';
import { useState } from 'react';
import { RefreshCw, Usb, Cpu, HardDrive } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
const filterOptions = [
    { label: 'All', value: 'all', count: 2 },
    { label: 'ESP/MQTT', value: 'esp', count: 0 },
    { label: 'USB', value: 'usb', count: 1 },
    { label: 'GPIO', value: 'gpio', count: 0 },
    { label: 'Serial', value: 'serial', count: 0 },
];
const devices = [
    {
        id: 1,
        name: 'USB Mass Storage',
        type: 'USB • usb-0001',
        status: 'connected',
        tags: ['storage', 'mass', 'write'],
        icon: HardDrive,
    },
    {
        id: 2,
        name: 'Kitchen Sensor',
        type: 'ESP • esp-kitchen',
        status: 'online',
        tags: ['temperature', 'humidity'],
        icon: Cpu,
        telemetry: {
            temperature: 22.5,
            humidity: 45,
        },
        liveData: true,
        lastSeen: '10/15/2025, 7:23:48 AM',
    },
];
export function DevicesPage() {
    const [activeFilter, setActiveFilter] = useState('all');
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    return (<div>
      <div className="flex items-center justify-between mb-6">
        <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
          Devices
        </h1>
        <div className="flex items-center gap-3">
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-white border-gray-300 hover:border-gray-400'} border`}>
            <RefreshCw size={18}/>
            <span>Refresh</span>
          </motion.button>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border`}>
            <Usb size={18}/>
            <span>Scan USB</span>
          </motion.button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-8">
        {filterOptions.map((option) => (<motion.button key={option.value} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveFilter(option.value)} className={`px-4 py-2 rounded-lg border text-sm transition-all ${activeFilter === option.value
                ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
                : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
            {option.label}
            <span className="ml-2">{option.count}</span>
          </motion.button>))}
      </div>

      {/* Devices Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {devices.map((device, index) => {
            const Icon = device.icon;
            return (<motion.div key={device.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10 hover:border-purple-500/50' : 'border-gray-300 hover:border-purple-400'} transition-all`}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
                    <Icon size={24} className="text-white"/>
                  </div>
                  <div>
                    <h3 className={`text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{device.name}</h3>
                    <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{device.type}</p>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs ${device.status === 'online'
                    ? isDarkMode ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-green-100 text-green-700 border border-green-300'
                    : isDarkMode ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-blue-100 text-blue-700 border border-blue-300'}`}>
                  {device.status}
                </span>
              </div>

              <div className="flex gap-2 mb-4">
                {device.tags.map((tag) => (<span key={tag} className={`px-2 py-1 rounded text-xs ${isDarkMode ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
                    {tag}
                  </span>))}
              </div>

              {device.telemetry && (<div className={`p-4 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'} mb-4`}>
                  {device.liveData && (<div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-2`}>Live Telemetry</div>)}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Temperature:</div>
                      <div className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{device.telemetry.temperature}°C</div>
                    </div>
                    <div>
                      <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mb-1`}>Humidity:</div>
                      <div className={`text-xl ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{device.telemetry.humidity}%</div>
                    </div>
                  </div>
                </div>)}

              <div className="flex gap-2">
                {device.telemetry && (<>
                    <button className={`flex-1 px-3 py-2 rounded-lg text-sm ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400 hover:bg-purple-500/30' : 'bg-purple-100 border-purple-500 text-purple-700 hover:bg-purple-200'} border`}>
                      📤 Send Command
                    </button>
                    <button className={`flex-1 px-3 py-2 rounded-lg text-sm ${isDarkMode ? 'bg-white/5 border-white/10 hover:bg-white/10' : 'bg-white border-gray-300 hover:bg-gray-50'} border`}>
                      📍 Ping
                    </button>
                  </>)}
              </div>

              {device.lastSeen && (<div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-600'} mt-3`}>
                  Last seen: {device.lastSeen}
                </div>)}
            </motion.div>);
        })}
      </div>

      {/* GPIO Pins Section */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
        <h3 className={`text-lg mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>GPIO Pins</h3>
        <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>Configure and monitor GPIO pins on your Raspberry Pi</p>
        <button className={`px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border`}>
          + Open GPIO Manager
        </button>
      </motion.div>
    </div>);
}
