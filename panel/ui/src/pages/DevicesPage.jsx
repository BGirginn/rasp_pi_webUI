import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { RefreshCw, Usb, Cpu, HardDrive, Keyboard, Link, Bluetooth, Wifi, MapPin, Send, Zap, MousePointer2, AlertCircle } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export function DevicesPage() {
  const [devices, setDevices] = useState([]);
  const [gpioPins, setGpioPins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [gpioLoading, setGpioLoading] = useState(false);
  const [showGpio, setShowGpio] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const { theme, isDarkMode } = useTheme();
  const { isOperator } = useAuth();
  const themeColors = getThemeColors(theme);

  const loadDevices = async () => {
    if (!loading) setRefreshing(true);
    try {
      const response = await api.get('/devices');
      setDevices(response.data || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load devices:', err);
      setError('Failed to load devices from backend.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadGpio = async () => {
    setGpioLoading(true);
    try {
      const response = await api.get('/devices/gpio/pins');
      setGpioPins(response.data?.pins || []);
    } catch (err) {
      console.error('Failed to load GPIO:', err);
    } finally {
      setGpioLoading(false);
    }
  };

  useEffect(() => {
    loadDevices();
    if (showGpio) loadGpio();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      loadDevices();
      if (showGpio) loadGpio();
    }, 30000);
    return () => clearInterval(interval);
  }, [showGpio]);

  const toggleGpio = async (pin, currentVal) => {
    try {
      const newVal = currentVal === 1 ? 0 : 1;
      await api.post(`/devices/gpio/${pin}/write?value=${newVal}`);
      loadGpio(); // Refresh GPIO states
    } catch (err) {
      alert('Failed to toggle GPIO: ' + err.message);
    }
  };

  const handleCommand = async (deviceId, command, payload = null) => {
    try {
      await api.post(`/devices/${deviceId}/command`, { command, payload });
      loadDevices(); // Refresh after command
    } catch (err) {
      console.error('Command failed:', err);
      alert(`Command failed: ${err.message || 'Unknown error'}`);
    }
  };

  const typeIcons = {
    usb: Usb,
    disk: HardDrive,
    storage: HardDrive,
    keyboard: Keyboard,
    mouse: MousePointer2,
    serial: Link,
    gpio: Zap,
    esp: Cpu,
    bluetooth: Bluetooth,
  };

  const getStateStyles = (state) => {
    switch (state) {
      case 'online':
      case 'connected':
        return isDarkMode ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-green-100 text-green-700 border border-green-300';
      case 'offline':
      case 'disconnected':
        return isDarkMode ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-red-100 text-red-700 border border-red-300';
      default:
        return isDarkMode ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-blue-100 text-blue-700 border border-blue-300';
    }
  };

  const counts = {
    all: devices.length,
    esp: devices.filter(d => d.type === 'esp').length,
    usb: devices.filter(d => ['usb', 'keyboard', 'mouse', 'camera', 'audio'].includes(d.type)).length,
    storage: devices.filter(d => ['disk', 'storage'].includes(d.type)).length,
    serial: devices.filter(d => d.type === 'serial').length,
  };

  const filterOptions = [
    { label: 'All', value: 'all', count: counts.all },
    { label: 'ESP/MQTT', value: 'esp', count: counts.esp },
    { label: 'USB', value: 'usb', count: counts.usb },
    { label: 'Storage', value: 'storage', count: counts.storage },
    { label: 'Serial', value: 'serial', count: counts.serial },
  ].filter(opt => opt.value === 'all' || opt.count > 0);

  const filteredDevices = activeFilter === 'all'
    ? devices
    : devices.filter(d => {
      if (activeFilter === 'usb') return ['usb', 'keyboard', 'mouse', 'camera', 'audio'].includes(d.type);
      if (activeFilter === 'storage') return ['disk', 'storage'].includes(d.type);
      return d.type === activeFilter;
    });

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Devices
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Manage and monitor connected hardware and IoT devices
          </p>
        </div>
        <div className="flex items-center gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadDevices}
            disabled={refreshing}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-white/5 border-white/10 hover:border-white/30' : 'bg-white border-gray-300 hover:border-gray-400'} border transition-all disabled:opacity-50`}
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadDevices}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-100 border-purple-500 text-purple-700'} border transition-all`}
          >
            <Usb size={18} />
            <span>Scan USB</span>
          </motion.button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mb-8 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 flex items-center gap-3"
        >
          <AlertCircle size={20} />
          <span>{error}</span>
        </motion.div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-8">
        {filterOptions.map((option) => (
          <motion.button
            key={option.value}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setActiveFilter(option.value)}
            className={`px-4 py-2 rounded-lg border text-sm transition-all flex items-center gap-2 ${activeFilter === option.value
              ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
              : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}
          >
            {option.label}
            <span className={`px-2 py-0.5 rounded-full text-[10px] ${activeFilter === option.value
              ? isDarkMode ? 'bg-purple-500/30' : 'bg-purple-200'
              : isDarkMode ? 'bg-white/10' : 'bg-gray-100'}`}>
              {option.count}
            </span>
          </motion.button>
        ))}
      </div>

      {/* Devices Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className={`h-48 rounded-2xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} animate-pulse`} />
          ))}
        </div>
      ) : filteredDevices.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AnimatePresence mode="popLayout">
            {filteredDevices.map((device, index) => {
              const Icon = typeIcons[device.type] || Cpu;
              return (
                <motion.div
                  key={device.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.2, delay: index * 0.05 }}
                  className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10 hover:border-purple-500/50' : 'border-gray-200 hover:border-purple-400'} transition-all group`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center shadow-lg`}>
                        <Icon size={24} className="text-white" />
                      </div>
                      <div>
                        <h3 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900 group-hover:text-purple-600 transition-colors'}`}>
                          {device.name}
                        </h3>
                        <p className={`text-xs font-mono ${isDarkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                          {device.type.toUpperCase()} • {device.id}
                        </p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${getStateStyles(device.state)}`}>
                      {device.state}
                    </span>
                  </div>

                  {/* Metadata / Caps */}
                  <div className="flex flex-wrap gap-2 mb-6">
                    {device.capabilities?.map((cap) => (
                      <span key={cap} className={`px-2 py-1 rounded-md text-[10px] uppercase font-bold ${isDarkMode ? 'bg-white/5 text-gray-400' : 'bg-gray-100 text-gray-600'}`}>
                        {cap}
                      </span>
                    ))}
                    {device.vendor && (
                      <span className={`px-2 py-1 rounded-md text-[10px] uppercase font-bold ${isDarkMode ? 'bg-purple-500/10 text-purple-400' : 'bg-purple-50 text-purple-600'}`}>
                        {device.vendor}
                      </span>
                    )}
                  </div>

                  {/* Telemetry if exists */}
                  {device.telemetry && Object.keys(device.telemetry).length > 0 && (
                    <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'} mb-6 border ${isDarkMode ? 'border-white/5' : 'border-gray-100'}`}>
                      <div className="grid grid-cols-2 gap-4">
                        {Object.entries(device.telemetry).map(([key, value]) => (
                          <div key={key}>
                            <div className={`text-[10px] uppercase font-bold ${isDarkMode ? 'text-gray-500' : 'text-gray-500'} mb-1`}>{key}:</div>
                            <div className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{typeof value === 'boolean' ? (value ? 'YES' : 'NO') : value}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {isOperator && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const cmd = prompt('Enter command for ' + device.name);
                          if (cmd) handleCommand(device.id, cmd);
                        }}
                        className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400 hover:bg-purple-500/30' : 'bg-purple-50 border-purple-200 text-purple-600 hover:bg-purple-100'} border`}
                      >
                        <Send size={14} />
                        Command
                      </button>
                      <button
                        onClick={() => handleCommand(device.id, 'ping')}
                        className={`px-3 py-2 rounded-lg border transition-all ${isDarkMode ? 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-400' : 'bg-white border-gray-200 hover:bg-gray-50 text-gray-600'}`}
                      >
                        <MapPin size={16} />
                      </button>
                    </div>
                  )}

                  {device.last_seen && (
                    <div className={`text-[10px] ${isDarkMode ? 'text-gray-600' : 'text-gray-500'} mt-4 italic font-medium`}>
                      Last seen: {new Date(device.last_seen).toLocaleString()}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className={`${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} border rounded-3xl p-16 text-center`}
        >
          <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-3xl mx-auto flex items-center justify-center mb-6 shadow-2xl">
            <Usb size={40} className="text-white" />
          </div>
          <h3 className={`text-2xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>No devices detected</h3>
          <p className={`max-w-md mx-auto ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            {activeFilter === 'all'
              ? "Connect a USB device to your Raspberry Pi or configure an ESP/MQTT device to see it here."
              : `No devices found matching the "${activeFilter}" filter.`}
          </p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadDevices}
            className="mt-8 px-8 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-bold shadow-lg shadow-purple-500/20 transition-all"
          >
            Try Again
          </motion.button>
        </motion.div>
      )}

      {/* GPIO Pins Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className={`mt-12 group overflow-hidden relative ${isDarkMode ? 'bg-gradient-to-br from-purple-900/40 to-black/40' : 'bg-gradient-to-br from-purple-50 to-white'} backdrop-blur-xl rounded-3xl p-8 border ${isDarkMode ? 'border-white/10' : 'border-purple-100 shadow-xl'}`}
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/10 blur-[100px] rounded-full -mr-32 -mt-32 " />
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4 text-purple-500">
              <div className="p-3 bg-purple-500/10 rounded-2xl">
                <Zap size={32} />
              </div>
              <h3 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                GPIO Pin Management
              </h3>
            </div>
            {showGpio && (
              <button onClick={loadGpio} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                <RefreshCw size={20} className={gpioLoading ? 'animate-spin' : ''} />
              </button>
            )}
          </div>

          {!showGpio ? (
            <>
              <p className={`max-w-2xl mb-8 text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Directly control and monitor the physical General Purpose Input/Output pins on your Raspberry Pi.
                Configure modes, read states, and toggle outputs in real-time.
              </p>
              <div className="flex flex-wrap gap-4">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setShowGpio(true)}
                  className="px-8 py-3 bg-purple-600 text-white rounded-xl font-bold shadow-lg shadow-purple-500/20 transition-all"
                >
                  Open GPIO Manager
                </motion.button>
              </div>
            </>
          ) : (
            <div className="animate-fade-in">
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
                {gpioPins.length > 0 ? (
                  gpioPins.map((pin) => (
                    <motion.div
                      key={pin.pin}
                      whileHover={{ scale: 1.02 }}
                      className={`p-3 rounded-xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-white border-gray-200'} flex flex-col items-center gap-2`}
                    >
                      <span className="text-[10px] font-bold text-gray-500 uppercase">GPIO {pin.pin}</span>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${pin.value === 1 ? 'bg-green-500 text-black' : 'bg-gray-700 text-white'}`}>
                        {pin.value}
                      </div>
                      <div className="text-[10px] text-gray-400 capitalize">{pin.mode}</div>
                      {pin.mode === 'output' && (
                        <button
                          onClick={() => toggleGpio(pin.pin, pin.value)}
                          className={`mt-1 p-1 px-3 rounded-md text-[10px] font-bold uppercase transition-all ${pin.value === 1 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}
                        >
                          {pin.value === 1 ? 'OFF' : 'ON'}
                        </button>
                      )}
                    </motion.div>
                  ))
                ) : (
                  <div className="col-span-full py-8 text-center text-gray-500 italic">
                    No GPIO pins available or tool missing on host.
                  </div>
                )}
              </div>
              <button
                onClick={() => setShowGpio(false)}
                className="mt-8 text-sm text-purple-400 hover:underline flex items-center gap-1"
              >
                ← Close Manager
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
