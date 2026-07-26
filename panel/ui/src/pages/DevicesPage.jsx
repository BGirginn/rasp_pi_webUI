import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Usb, Cpu, HardDrive, Keyboard, Link, Bluetooth, Wifi, Send, Zap, MousePointer2, AlertCircle, CheckCircle2, Eraser, TestTube2, Unplug, X } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

const formatBytes = (value) => {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return 'Unknown';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index > 2 ? 1 : 0)} ${units[index]}`;
};

export function DevicesPage() {
  const [devices, setDevices] = useState([]);
  const [gpioPins, setGpioPins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [gpioLoading, setGpioLoading] = useState(false);
  const [showGpio, setShowGpio] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [usbBusy, setUsbBusy] = useState('');
  const [usbNotice, setUsbNotice] = useState(null);
  const [formatTarget, setFormatTarget] = useState(null);
  const [formatForm, setFormatForm] = useState({ filesystem: 'exfat', label: 'PI-USB', confirmation: '' });
  const hasLoadedDevicesRef = useRef(false);
  const devicesHashRef = useRef('');
  const gpioHashRef = useRef('');
  const { theme, isDarkMode } = useTheme();
  const { isOperator, isAdmin } = useAuth();
  const themeColors = getThemeColors(theme);

  const getDeviceCategory = (deviceType) => {
    if (['disk', 'storage'].includes(deviceType)) return 'storage';
    if (['usb', 'camera', 'audio'].includes(deviceType)) return 'usb';
    if (['keyboard', 'mouse'].includes(deviceType)) return 'input';
    if (deviceType === 'serial') return 'serial';
    if (deviceType === 'esp') return 'esp';
    return 'default';
  };

  const categoryStyles = {
    usb: {
      icon: isDarkMode ? 'from-sky-500 to-blue-600' : 'from-sky-500 to-blue-500',
      border: isDarkMode ? 'hover:border-sky-500/50' : 'hover:border-sky-400',
      vendor: isDarkMode ? 'bg-sky-500/10 text-sky-300' : 'bg-sky-50 text-sky-700',
    },
    storage: {
      icon: isDarkMode ? 'from-emerald-500 to-green-600' : 'from-emerald-500 to-green-500',
      border: isDarkMode ? 'hover:border-emerald-500/50' : 'hover:border-emerald-400',
      vendor: isDarkMode ? 'bg-emerald-500/10 text-emerald-300' : 'bg-emerald-50 text-emerald-700',
    },
    input: {
      icon: isDarkMode ? 'from-indigo-500 to-violet-600' : 'from-indigo-500 to-violet-500',
      border: isDarkMode ? 'hover:border-indigo-500/50' : 'hover:border-indigo-400',
      vendor: isDarkMode ? 'bg-indigo-500/10 text-indigo-300' : 'bg-indigo-50 text-indigo-700',
    },
    serial: {
      icon: isDarkMode ? 'from-cyan-500 to-teal-600' : 'from-cyan-500 to-teal-500',
      border: isDarkMode ? 'hover:border-cyan-500/50' : 'hover:border-cyan-400',
      vendor: isDarkMode ? 'bg-cyan-500/10 text-cyan-300' : 'bg-cyan-50 text-cyan-700',
    },
    esp: {
      icon: isDarkMode ? 'from-orange-500 to-amber-600' : 'from-orange-500 to-amber-500',
      border: isDarkMode ? 'hover:border-orange-500/50' : 'hover:border-orange-400',
      vendor: isDarkMode ? 'bg-orange-500/10 text-orange-300' : 'bg-orange-50 text-orange-700',
    },
    default: {
      icon: isDarkMode ? themeColors.secondary : themeColors.lightSecondary,
      border: isDarkMode ? 'hover:border-purple-500/50' : 'hover:border-purple-400',
      vendor: isDarkMode ? 'bg-purple-500/10 text-purple-400' : 'bg-purple-50 text-purple-600',
    },
  };

  const dedupeDevices = (rawDevices) => {
    const byId = new Map();
    for (const device of rawDevices) {
      if (!device?.id) continue;
      if (!byId.has(device.id)) byId.set(device.id, device);
    }
    return Array.from(byId.values()).sort((left, right) => left.id.localeCompare(right.id));
  };

  const loadDevices = useCallback(async () => {
    if (hasLoadedDevicesRef.current) setRefreshing(true);
    try {
      const response = await api.get('/devices');
      const nextDevices = dedupeDevices(response.data || []);
      const nextHash = JSON.stringify(nextDevices);
      if (nextHash !== devicesHashRef.current) {
        devicesHashRef.current = nextHash;
        setDevices(nextDevices);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load devices:', err);
      setError('Failed to load devices from backend.');
    } finally {
      setLoading(false);
      setRefreshing(false);
      hasLoadedDevicesRef.current = true;
    }
  }, []);

  const loadGpio = useCallback(async () => {
    setGpioLoading(true);
    try {
      const response = await api.get('/devices/gpio/pins');
      const nextPins = response.data?.pins || [];
      const nextHash = JSON.stringify(nextPins);
      if (nextHash !== gpioHashRef.current) {
        gpioHashRef.current = nextHash;
        setGpioPins(nextPins);
      }
    } catch (err) {
      console.error('Failed to load GPIO:', err);
    } finally {
      setGpioLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDevices();
    if (showGpio) loadGpio();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadDevices();
      if (showGpio) loadGpio();
    }, 5000);
    return () => clearInterval(interval);
  }, [showGpio, loadDevices, loadGpio]);

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

  const runUsbAction = async (device, action, body = {}) => {
    const key = `${device.id}:${action}`;
    setUsbBusy(key);
    setUsbNotice(null);
    try {
      const response = await api.post(`/devices/usb/${device.id}/${action}`, body);
      const job = response.data;
      setUsbNotice({
        type: 'success',
        message: job?.id
          ? `${action === 'write-test' ? 'Write test' : 'Format'} job ${job.id} queued. Track it on Jobs.`
          : response.data?.message || `USB ${action} completed.`,
      });
      setFormatTarget(null);
      setFormatForm({ filesystem: 'exfat', label: 'PI-USB', confirmation: '' });
      await loadDevices();
    } catch (requestError) {
      setUsbNotice({
        type: 'error',
        message: requestError.response?.data?.detail || requestError.message,
      });
    } finally {
      setUsbBusy('');
    }
  };

  const openFormatDialog = (device) => {
    setFormatTarget(device);
    setFormatForm({ filesystem: 'exfat', label: 'PI-USB', confirmation: '' });
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
      {usbNotice && (
        <div className={`mb-8 p-4 rounded-xl border flex items-center gap-3 ${
          usbNotice.type === 'success'
            ? isDarkMode ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-emerald-50 border-emerald-200 text-emerald-700'
            : isDarkMode ? 'bg-red-500/10 border-red-500/20 text-red-300' : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {usbNotice.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
          <span>{usbNotice.message}</span>
          <button type="button" className="ml-auto" onClick={() => setUsbNotice(null)} aria-label="Dismiss">
            <X size={18} />
          </button>
        </div>
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
              const category = getDeviceCategory(device.type);
              const style = categoryStyles[category] || categoryStyles.default;
              const canSendCommand = device.type === 'esp';
              const storage = device.storage;
              const allowed = new Set(device.allowed_actions || []);
              return (
                <motion.div
                  key={device.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.2, delay: index * 0.05 }}
                  className={`${isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200'} backdrop-blur-xl rounded-2xl p-6 border ${style.border} transition-all group`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${style.icon} flex items-center justify-center shadow-lg`}>
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
                      <span className={`px-2 py-1 rounded-md text-[10px] uppercase font-bold ${style.vendor}`}>
                        {device.vendor}
                      </span>
                    )}
                  </div>

                  {storage && (
                    <div className={`p-4 rounded-xl mb-5 border ${isDarkMode ? 'bg-white/[0.04] border-white/10' : 'bg-emerald-50/60 border-emerald-100'}`}>
                      <div className="flex items-center justify-between gap-3 mb-4">
                        <div>
                          <div className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {formatBytes(storage.size_bytes)}
                          </div>
                          <div className="text-[10px] uppercase tracking-widest text-gray-500">
                            {storage.device_path} · {storage.transport || 'unknown transport'}
                          </div>
                        </div>
                        <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${
                          storage.read_only
                            ? 'bg-amber-500/15 text-amber-500'
                            : 'bg-emerald-500/15 text-emerald-500'
                        }`}>
                          {storage.read_only ? 'READ ONLY' : 'READ / WRITE'}
                        </span>
                      </div>

                      <div className="space-y-3">
                        {(storage.partitions || []).length === 0 && (
                          <div className="text-xs text-gray-500">No partition or filesystem detected.</div>
                        )}
                        {(storage.partitions || []).map((volume) => {
                          const used = Number(volume.used_bytes || 0);
                          const size = Number(volume.size_bytes || 0);
                          const percent = size > 0 ? Math.min(100, Math.round((used / size) * 100)) : 0;
                          return (
                            <div key={volume.id} className={`p-3 rounded-lg ${isDarkMode ? 'bg-black/20' : 'bg-white/80'}`}>
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <div className={`text-sm font-semibold ${isDarkMode ? 'text-gray-100' : 'text-gray-800'}`}>
                                    {volume.label || volume.id}
                                  </div>
                                  <div className="text-[10px] text-gray-500">
                                    {(volume.filesystem || 'unformatted').toUpperCase()} · {formatBytes(volume.size_bytes)}
                                  </div>
                                </div>
                                <span className={`text-[10px] font-bold ${volume.mounted ? 'text-emerald-500' : 'text-gray-500'}`}>
                                  {volume.mounted ? 'MOUNTED' : 'UNMOUNTED'}
                                </span>
                              </div>
                              {size > 0 && volume.filesystem && (
                                <div className="mt-2">
                                  <div className={`h-1.5 rounded-full overflow-hidden ${isDarkMode ? 'bg-white/10' : 'bg-gray-200'}`}>
                                    <div className="h-full rounded-full bg-emerald-500" style={{ width: `${percent}%` }} />
                                  </div>
                                  <div className="mt-1 text-[10px] text-gray-500">
                                    {formatBytes(used)} used · {formatBytes(volume.available_bytes)} free
                                  </div>
                                </div>
                              )}
                              {volume.mount_points?.[0] && (
                                <div className="mt-2 text-[10px] font-mono text-gray-500 break-all">{volume.mount_points[0]}</div>
                              )}
                              {isOperator && !volume.mounted && allowed.has('mount') && volume.filesystem && (
                                <button
                                  type="button"
                                  disabled={Boolean(usbBusy)}
                                  onClick={() => runUsbAction(device, 'mount', { volume_id: volume.id, read_only: false })}
                                  className="mt-3 px-3 py-1.5 rounded-lg text-xs border border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10 disabled:opacity-50"
                                >
                                  Mount
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      {isOperator && (
                        <div className="grid grid-cols-2 gap-2 mt-4">
                          {storage.mounted && allowed.has('unmount') && (
                            <button type="button" disabled={Boolean(usbBusy)} onClick={() => runUsbAction(device, 'unmount')} className="px-3 py-2 rounded-lg text-xs border border-amber-500/30 text-amber-500 hover:bg-amber-500/10 disabled:opacity-50">
                              Unmount
                            </button>
                          )}
                          {storage.mounted && !storage.read_only && (
                            <button type="button" disabled={Boolean(usbBusy)} onClick={() => runUsbAction(device, 'write-test', { volume_id: storage.partitions.find((item) => item.mounted)?.id, size_mb: 64 })} className="px-3 py-2 rounded-lg text-xs border border-sky-500/30 text-sky-500 hover:bg-sky-500/10 disabled:opacity-50 flex items-center justify-center gap-1.5">
                              <TestTube2 size={13} /> Write test
                            </button>
                          )}
                          {isAdmin && !storage.read_only && (
                            <button type="button" disabled={Boolean(usbBusy)} onClick={() => openFormatDialog(device)} className="px-3 py-2 rounded-lg text-xs border border-red-500/30 text-red-500 hover:bg-red-500/10 disabled:opacity-50 flex items-center justify-center gap-1.5">
                              <Eraser size={13} /> Format
                            </button>
                          )}
                          {allowed.has('eject') && (
                            <button type="button" disabled={Boolean(usbBusy)} onClick={() => runUsbAction(device, 'eject')} className="px-3 py-2 rounded-lg text-xs border border-gray-500/30 text-gray-500 hover:bg-gray-500/10 disabled:opacity-50 flex items-center justify-center gap-1.5">
                              <Unplug size={13} /> Eject
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

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
                  {isOperator && canSendCommand && (
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
                        title="Ping device"
                        className={`px-3 py-2 rounded-lg border transition-all ${isDarkMode ? 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-400' : 'bg-white border-gray-200 hover:bg-gray-50 text-gray-600'}`}
                      >
                        <Wifi size={16} />
                      </button>
                    </div>
                  )}

                  {isOperator && !canSendCommand && !storage && (
                    <div className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-500'} italic`}>
                      This device type does not support remote command or ping.
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
      {isOperator && (
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
      )}

      <AnimatePresence>
        {formatTarget && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setFormatTarget(null);
            }}
          >
            <motion.form
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              onSubmit={(event) => {
                event.preventDefault();
                runUsbAction(formatTarget, 'format', formatForm);
              }}
              className={`w-full max-w-lg rounded-3xl border p-7 shadow-2xl ${isDarkMode ? 'bg-[#111018] border-white/10' : 'bg-white border-gray-200'}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-bold uppercase tracking-[0.2em] text-red-500">Destructive operation</div>
                  <h2 className={`mt-2 text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>Format USB disk</h2>
                  <p className="mt-2 text-sm text-gray-500">
                    Every partition and file on {formatTarget.name} ({formatBytes(formatTarget.storage?.size_bytes)}) will be erased.
                  </p>
                </div>
                <button type="button" onClick={() => setFormatTarget(null)} className="p-2 rounded-lg text-gray-500 hover:bg-gray-500/10">
                  <X size={19} />
                </button>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-4">
                <label className="text-xs font-semibold text-gray-500">
                  Filesystem
                  <select
                    value={formatForm.filesystem}
                    onChange={(event) => setFormatForm((current) => ({ ...current, filesystem: event.target.value }))}
                    className={`mt-2 w-full rounded-xl border px-3 py-2.5 ${isDarkMode ? 'bg-white/5 border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900'}`}
                  >
                    <option value="exfat">exFAT</option>
                    <option value="fat32">FAT32</option>
                    <option value="ext4">ext4</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-gray-500">
                  Label
                  <input
                    value={formatForm.label}
                    maxLength={16}
                    onChange={(event) => setFormatForm((current) => ({ ...current, label: event.target.value }))}
                    className={`mt-2 w-full rounded-xl border px-3 py-2.5 ${isDarkMode ? 'bg-white/5 border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900'}`}
                  />
                </label>
              </div>

              <label className="mt-5 block text-xs font-semibold text-gray-500">
                Type <strong className={isDarkMode ? 'text-gray-200' : 'text-gray-800'}>ERASE {formatTarget.id}</strong> to continue
                <input
                  value={formatForm.confirmation}
                  autoComplete="off"
                  onChange={(event) => setFormatForm((current) => ({ ...current, confirmation: event.target.value }))}
                  className={`mt-2 w-full rounded-xl border px-3 py-2.5 font-mono ${isDarkMode ? 'bg-white/5 border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900'}`}
                />
              </label>

              <div className="mt-7 flex justify-end gap-3">
                <button type="button" onClick={() => setFormatTarget(null)} className={`px-4 py-2.5 rounded-xl border ${isDarkMode ? 'border-white/10 text-gray-300' : 'border-gray-200 text-gray-700'}`}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={usbBusy || formatForm.confirmation !== `ERASE ${formatTarget.id}`}
                  className="px-4 py-2.5 rounded-xl bg-red-600 text-white font-bold disabled:opacity-40"
                >
                  {usbBusy ? 'Queuing...' : 'Erase and format'}
                </button>
              </div>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
