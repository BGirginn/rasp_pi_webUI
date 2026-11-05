import { motion, AnimatePresence } from "motion/react";
import { RefreshCw, Wifi, Cable, Network, Download, Upload, Activity, Shield, CheckCircle2, XCircle, Globe, Lock, Unlock, SignalHigh, SignalMedium, SignalLow, SignalZero, Power, RotateCcw, Search, Bluetooth } from "lucide-react";
import { useTheme, getThemeColors, } from "../contexts/ThemeContext";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { formatBytes } from "../utils/format";

// Get icon based on interface type
function getInterfaceIcon(type) {
  if (type === 'wifi') return Wifi;
  if (type === 'vpn' || type === 'tailscale') return Shield;
  return Cable;
}

export function NetworkPage({ initialTab = "interfaces" }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const { theme, isDarkMode } = useTheme();
  const { isAdmin } = useAuth();
  const themeColors = getThemeColors(theme);

  const [interfaces, setInterfaces] = useState([]);
  const [connectivity, setConnectivity] = useState({});
  const [wifiNetworks, setWifiNetworks] = useState([]);
  const [wifiStatus, setWifiStatus] = useState(null);
  const [networkCheckpoint, setNetworkCheckpoint] = useState(null);
  const [bluetoothStatus, setBluetoothStatus] = useState(null);
  const [bluetoothDevices, setBluetoothDevices] = useState([]);
  const [bluetoothBusy, setBluetoothBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [connectModal, setConnectModal] = useState(null);
  const [wifiPassword, setWifiPassword] = useState('');
  const hasLoadedNetworkRef = useRef(false);
  const interfacesHashRef = useRef('');
  const connectivityHashRef = useRef('');
  const wifiNetworksHashRef = useRef('');
  const wifiStatusHashRef = useRef('');

  const loadNetworkData = useCallback(async () => {
    if (hasLoadedNetworkRef.current) setRefreshing(true);
    try {
      const [ifaceRes, connRes] = await Promise.all([
        api.get('/network/interfaces'),
        api.get('/network/connectivity')
      ]);
      const nextInterfaces = ifaceRes.data || [];
      const nextConnectivity = connRes.data || {};
      const nextInterfacesHash = JSON.stringify(nextInterfaces);
      const nextConnectivityHash = JSON.stringify(nextConnectivity);

      if (nextInterfacesHash !== interfacesHashRef.current) {
        interfacesHashRef.current = nextInterfacesHash;
        setInterfaces(nextInterfaces);
      }
      if (nextConnectivityHash !== connectivityHashRef.current) {
        connectivityHashRef.current = nextConnectivityHash;
        setConnectivity(nextConnectivity);
      }
    } catch (err) {
      console.error('Failed to load network data:', err);
    } finally {
      setRefreshing(false);
      hasLoadedNetworkRef.current = true;
    }
  }, []);

  const scanWifi = useCallback(async () => {
    setScanning(true);
    try {
      const [networksRes, statusRes] = await Promise.all([
        api.get('/network/wifi/networks'),
        api.get('/network/wifi/status')
      ]);
      const nextNetworks = networksRes.data || [];
      const nextStatus = statusRes.data || null;
      const nextNetworksHash = JSON.stringify(nextNetworks);
      const nextStatusHash = JSON.stringify(nextStatus);

      if (nextNetworksHash !== wifiNetworksHashRef.current) {
        wifiNetworksHashRef.current = nextNetworksHash;
        setWifiNetworks(nextNetworks);
      }
      if (nextStatusHash !== wifiStatusHashRef.current) {
        wifiStatusHashRef.current = nextStatusHash;
        setWifiStatus(nextStatus);
      }
    } catch (err) {
      console.error('WiFi scan failed:', err);
    } finally {
      setScanning(false);
    }
  }, []);

  const loadBluetooth = useCallback(async (scan = false) => {
    setBluetoothBusy(true);
    try {
      const status = await api.get('/network/bluetooth/status', { cache: false });
      setBluetoothStatus(status.data);
      setBluetoothDevices(status.data.paired_devices || []);
      if (scan && status.data.enabled) {
        const discovered = await api.get('/network/bluetooth/scan?seconds=8', { cache: false });
        setBluetoothDevices(discovered.data.devices || []);
      }
    } catch (err) {
      alert(err.response?.data?.detail || err.message);
    } finally { setBluetoothBusy(false); }
  }, []);

  useEffect(() => {
    loadNetworkData();
    if (activeTab === 'wifi') scanWifi();
    if (activeTab === 'bluetooth') loadBluetooth();

    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadNetworkData();
      if (activeTab === 'wifi') scanWifi();
      if (activeTab === 'bluetooth') loadBluetooth();
    }, 10000);
    return () => clearInterval(interval);
  }, [activeTab, loadNetworkData, scanWifi, loadBluetooth]);

  const handleInterfaceAction = async (ifaceName, action) => {
    const rollback = action === 'disable' ? 120 : 0;

    if (action === 'disable' && !confirm(`Disable ${ifaceName}? This will auto-restore after ${rollback}s if you lose connection.`)) {
      return;
    }

    try {
      const response = await api.post(`/network/interfaces/${ifaceName}/action`, {
        action,
        rollback_seconds: rollback
      });
      if (response.data.checkpoint_id) {
        setNetworkCheckpoint({ id: response.data.checkpoint_id, interface: ifaceName, seconds: rollback });
      }
      loadNetworkData();
    } catch (err) {
      alert('Action failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const checkpointAction = async (action) => {
    if (!networkCheckpoint) return;
    try {
      await api.post(`/network/checkpoints/${action}`, { checkpoint_id: networkCheckpoint.id });
      setNetworkCheckpoint(null);
      loadNetworkData();
    } catch (err) { alert(err.response?.data?.detail || err.message); }
  };

  const bluetoothPower = async () => {
    setBluetoothBusy(true);
    try {
      await api.post(`/network/bluetooth/toggle?enable=${!bluetoothStatus?.enabled}`);
      await loadBluetooth();
    } catch (err) { alert(err.response?.data?.detail || err.message); setBluetoothBusy(false); }
  };

  const bluetoothAction = async (action, address) => {
    setBluetoothBusy(true);
    try {
      await api.post(`/network/bluetooth/${action}`, { address });
      await loadBluetooth();
    } catch (err) { alert(err.response?.data?.detail || err.message); setBluetoothBusy(false); }
  };

  const handleWifiConnect = async (e) => {
    e.preventDefault();
    if (!connectModal) return;

    try {
      await api.post('/network/wifi/connect', {
        ssid: connectModal.ssid,
        password: wifiPassword
      });
      setConnectModal(null);
      setWifiPassword('');
      scanWifi();
    } catch (err) {
      alert('Failed to connect: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleWifiDisconnect = async () => {
    if (!confirm(`Disconnect from ${wifiStatus?.ssid || 'the current WiFi network'}?`)) {
      return;
    }
    try {
      await api.post('/network/wifi/disconnect');
      await scanWifi();
    } catch (err) {
      alert('Failed to disconnect: ' + (err.response?.data?.detail || err.message));
    }
  };

  const connectivityStatus = [
    { label: "LAN", status: connectivity.lan, icon: Network },
    { label: "Internet", status: connectivity.internet, icon: Globe },
    { label: "DNS", status: connectivity.dns, icon: Activity },
    { label: "TS", status: connectivity.tailscale, icon: Shield },
  ];

  const getSignalIcon = (quality) => {
    if (quality > 75) return <SignalHigh size={18} />;
    if (quality > 50) return <SignalMedium size={18} />;
    if (quality > 25) return <SignalLow size={18} />;
    return <SignalZero size={18} />;
  };

  return (
    <div className="animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Network
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Manage interfaces, WiFi connections and monitor traffic
          </p>
        </div>
        <div className="flex items-center gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadNetworkData}
            disabled={refreshing}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all ${isDarkMode ? "bg-white/5 border-white/10 hover:border-white/30 text-white" : "bg-white border-gray-200 hover:border-gray-300 text-gray-700"} shadow-sm`}
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Updating...' : 'Refresh'}</span>
          </motion.button>
        </div>
      </div>

      {/* Connectivity Status Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-8">
        {connectivityStatus.map((item, index) => {
          const Icon = item.icon;
          return (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} backdrop-blur-xl rounded-2xl p-4 border flex items-center justify-between group overflow-hidden relative`}
            >
              <div className={`absolute -right-4 -bottom-4 opacity-[0.05] group-hover:scale-110 transition-transform ${item.status ? 'text-green-500' : 'text-red-500'}`}>
                <Icon size={80} />
              </div>
              <div className="flex items-center gap-3 relative z-10">
                <div className={`p-2 rounded-xl ${item.status ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                  <Icon size={20} />
                </div>
                <div>
                  <p className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>{item.label}</p>
                  <p className={`text-sm font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                    {item.status ? 'ONLINE' : 'OFFLINE'}
                  </p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Tabs */}
      <div className="flex gap-3 mb-8">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setActiveTab("interfaces")}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl text-sm font-bold transition-all ${activeTab === "interfaces"
            ? isDarkMode ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30" : "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
            : isDarkMode ? "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10" : "bg-white border-gray-200 text-gray-600 shadow-sm hover:border-gray-300"} border`}
        >
          <Network size={18} />
          INTERFACES
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setActiveTab("wifi")}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl text-sm font-bold transition-all ${activeTab === "wifi"
            ? isDarkMode ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30" : "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
            : isDarkMode ? "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10" : "bg-white border-gray-200 text-gray-600 shadow-sm hover:border-gray-300"} border`}
        >
          <Wifi size={18} />
          WIFI NETWORKS
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setActiveTab("bluetooth")}
          className={`flex items-center gap-2 px-6 py-3 rounded-2xl text-sm font-bold transition-all ${activeTab === "bluetooth"
            ? "bg-blue-600 text-white shadow-lg shadow-blue-500/30"
            : isDarkMode ? "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10" : "bg-white border-gray-200 text-gray-600 shadow-sm hover:border-gray-300"} border`}
        >
          <Bluetooth size={18} />
          BLUETOOTH
        </motion.button>
      </div>

      {networkCheckpoint && <div className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
        <span className="flex-1">{networkCheckpoint.interface} will automatically restore in {networkCheckpoint.seconds}s unless confirmed.</span>
        <button onClick={() => checkpointAction('rollback')} className="rounded-lg border border-amber-500/40 px-3 py-2">Rollback now</button>
        <button onClick={() => checkpointAction('confirm')} className="rounded-lg bg-amber-600 px-3 py-2 text-white">Keep disabled</button>
      </div>}

      {/* Content */}
      <AnimatePresence mode="wait">
        {activeTab === "interfaces" ? (
          <motion.div
            key="interfaces"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {interfaces.map((iface, index) => {
              const Icon = getInterfaceIcon(iface.type);
              return (
                <motion.div
                  key={iface.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} backdrop-blur-xl rounded-[32px] p-6 border group hover:border-purple-500/50 transition-all`}
                >
                  <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center gap-4">
                      <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${isDarkMode ? "from-purple-950 to-purple-900" : "from-purple-500 to-fuchsia-500"} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform`}>
                        <Icon size={28} className="text-white" />
                      </div>
                      <div>
                        <h3 className={`text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{iface.name}</h3>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>{iface.type}</span>
                        </div>
                      </div>
                    </div>
                    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${iface.status === "up" ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"}`}>
                      {iface.status === 'up' ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                      {iface.status}
                    </div>
                  </div>

                  <div className="space-y-4 mb-8">
                    <div className={`p-4 rounded-2xl ${isDarkMode ? "bg-white/5" : "bg-gray-50"} space-y-3`}>
                      <div className="flex justify-between items-center text-xs">
                        <span className={`${isDarkMode ? "text-gray-500" : "text-gray-500"} font-bold uppercase`}>IP</span>
                        <span className={`font-mono font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{iface.ip || '---'}</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className={`${isDarkMode ? "text-gray-500" : "text-gray-500"} font-bold uppercase`}>MAC</span>
                        <span className={`font-mono text-[10px] ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>{iface.mac || '---'}</span>
                      </div>
                      {iface.gateway && (
                        <div className="flex justify-between items-center text-xs">
                          <span className={`${isDarkMode ? "text-gray-500" : "text-gray-500"} font-bold uppercase`}>Gateway</span>
                          <span className={`font-mono ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>{iface.gateway}</span>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className={`p-3 rounded-2xl ${isDarkMode ? "bg-green-500/5 border-green-500/10" : "bg-green-50 border-green-100"} border`}>
                        <div className="flex items-center gap-2 mb-1 text-[10px] font-bold text-green-500 uppercase">
                          <Download size={14} /> DOWNLOAD
                        </div>
                        <div className={`text-sm font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{formatBytes(iface.rx_bytes)}</div>
                      </div>
                      <div className={`p-3 rounded-2xl ${isDarkMode ? "bg-blue-500/5 border-blue-500/10" : "bg-blue-50 border-blue-100"} border`}>
                        <div className="flex items-center gap-2 mb-1 text-[10px] font-bold text-blue-500 uppercase">
                          <Upload size={14} /> UPLOAD
                        </div>
                        <div className={`text-sm font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{formatBytes(iface.tx_bytes)}</div>
                      </div>
                    </div>
                  </div>

                  {isAdmin && iface.type !== 'loopback' && (
                    <div className="flex gap-2">
                      {iface.status === 'up' ? (
                        <button
                          onClick={() => handleInterfaceAction(iface.name, 'disable')}
                          className="flex-1 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-xl text-xs font-bold uppercase tracking-widest border border-red-500/20 transition-all"
                        >
                          Disable
                        </button>
                      ) : (
                        <button
                          onClick={() => handleInterfaceAction(iface.name, 'enable')}
                          className="flex-1 px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-500 rounded-xl text-xs font-bold uppercase tracking-widest border border-green-500/20 transition-all"
                        >
                          Enable
                        </button>
                      )}
                      <button
                        onClick={() => handleInterfaceAction(iface.name, 'restart')}
                        className={`p-2 rounded-xl border transition-all ${isDarkMode ? "bg-white/5 border-white/10 hover:bg-white/10 text-gray-400" : "bg-white border-gray-200 hover:bg-gray-50 text-gray-600"}`}
                      >
                        <RotateCcw size={16} />
                      </button>
                    </div>
                  )}
                </motion.div>
              )
            })}
          </motion.div>
        ) : activeTab === "wifi" ? (
          <motion.div
            key="wifi"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="space-y-8"
          >
            {/* Current Connection */}
            {wifiStatus?.connected && (
              <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className={`${isDarkMode ? "bg-gradient-to-br from-green-900/40 to-black/40 border-green-500/20" : "bg-gradient-to-br from-green-50 to-white border-green-200"} border-2 rounded-[32px] p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-xl relative overflow-hidden`}
              >
                <div className="absolute right-0 top-0 p-4 opacity-5">
                  <Wifi size={200} />
                </div>
                <div className="flex items-center gap-6 relative z-10">
                  <div className="w-16 h-16 bg-green-500 rounded-3xl flex items-center justify-center shadow-lg shadow-green-500/30">
                    <Wifi size={32} className="text-white" />
                  </div>
                  <div>
                    <h3 className={`text-2xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{wifiStatus.ssid}</h3>
                    <div className="flex flex-wrap gap-3 mt-2">
                      <span className="flex items-center gap-1.5 text-xs font-bold text-green-500 uppercase bg-green-500/10 px-3 py-1 rounded-full border border-green-500/20">
                        <CheckCircle2 size={12} /> Connected
                      </span>
                      <span className={`text-xs font-mono font-bold ${isDarkMode ? 'text-gray-500' : 'text-gray-500'}`}>{wifiStatus.ip_address || wifiStatus.ip || 'No IP'}</span>
                      {(wifiStatus.frequency || wifiStatus.signal_quality != null) && (
                        <span className={`text-xs font-bold ${isDarkMode ? 'text-gray-600' : 'text-gray-400'}`}>
                          {wifiStatus.frequency ? `• ${wifiStatus.frequency}` : ''}
                          {wifiStatus.signal_quality != null ? ` • ${wifiStatus.signal_quality}% Quality` : ''}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-3 relative z-10">
                  <button onClick={handleWifiDisconnect} className={`px-6 py-3 rounded-2xl text-sm font-bold uppercase tracking-widest transition-all ${isDarkMode ? "bg-red-500/10 text-red-500 border-red-500/20 hover:bg-red-500/20" : "bg-red-50 text-red-600 border-red-100 hover:bg-red-100"} border`}>
                    DISCONNECT
                  </button>
                </div>
              </motion.div>
            )}

            {/* WiFi Operations */}
            <div className="flex items-center justify-between">
              <h2 className={`text-2xl font-bold ${isDarkMode ? "text-white" : "text-gray-800"}`}>Available Networks</h2>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={scanWifi}
                disabled={scanning}
                className={`flex items-center gap-2 px-6 py-3 rounded-2xl bg-purple-600 text-white font-bold shadow-lg shadow-purple-500/20 disabled:opacity-50 transition-all`}
              >
                <RefreshCw size={20} className={scanning ? 'animate-spin' : ''} />
                {scanning ? 'SCANNING...' : 'SCAN NETWORKS'}
              </motion.button>
            </div>

            {/* Networks List */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {wifiNetworks.map((net, index) => (
                <motion.div
                  key={net.bssid}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} backdrop-blur-xl rounded-[32px] p-6 border group hover:border-purple-500/50 transition-all cursor-pointer relative overflow-hidden`}
                  onClick={() => !net.connected && setConnectModal(net)}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className={`p-3 rounded-xl ${isDarkMode ? 'bg-white/10 text-gray-400' : 'bg-gray-100 text-gray-500'} group-hover:bg-purple-500 group-hover:text-white transition-all`}>
                        {getSignalIcon(net.signal_quality)}
                      </div>
                      <div>
                        <h4 className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'} group-hover:text-purple-600 transition-colors truncate w-32`}>{net.ssid}</h4>
                        <p className={`text-[10px] font-bold uppercase text-gray-500`}>{net.frequency} • {net.security}</p>
                      </div>
                    </div>
                    {net.security !== 'open' ? <Lock size={14} className="text-gray-500" /> : <Unlock size={14} className="text-gray-500" />}
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <span className={`text-[10px] font-bold tracking-widest ${isDarkMode ? 'text-gray-600' : 'text-gray-400'}`}>{net.bssid}</span>
                    {net.connected && <span className="text-[10px] font-bold text-green-500 uppercase bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">CONNECTED</span>}
                  </div>
                </motion.div>
              ))}
              {wifiNetworks.length === 0 && !scanning && (
                <div className="col-span-full py-20 text-center">
                  <Wifi size={48} className="mx-auto mb-4 text-gray-500 opacity-20" />
                  <p className="text-gray-500 font-medium italic">No networks discovered. Click Scan to search.</p>
                </div>
              )}
            </div>
          </motion.div>
        ) : activeTab === "bluetooth" ? (
          <motion.div key="bluetooth" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200"} flex flex-wrap items-center gap-4 rounded-lg border p-5`}>
              <Bluetooth size={26} className={bluetoothStatus?.enabled ? 'text-blue-500' : 'text-gray-500'} />
              <div className="flex-1"><h2 className="font-semibold">Bluetooth adapter</h2><p className="text-sm text-gray-500">{bluetoothStatus?.enabled ? 'Powered on' : 'Powered off'}{bluetoothStatus?.controller ? ` · ${bluetoothStatus.controller}` : ''}</p></div>
              {isAdmin && <button disabled={bluetoothBusy} onClick={bluetoothPower} className={`h-10 rounded-lg px-4 text-white ${bluetoothStatus?.enabled ? 'bg-red-600' : 'bg-blue-600'}`}><Power className="inline mr-2" size={16} />{bluetoothStatus?.enabled ? 'Turn off' : 'Turn on'}</button>}
              {isAdmin && bluetoothStatus?.enabled && <button disabled={bluetoothBusy} onClick={() => loadBluetooth(true)} className="h-10 rounded-lg border px-4"><Search className="inline mr-2" size={16} />Scan</button>}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {bluetoothDevices.map((device) => <div key={device.address} className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200"} rounded-lg border p-4`}>
                <div className="mb-3"><h3 className="font-medium">{device.name}</h3><p className="font-mono text-xs text-gray-500">{device.address}</p></div>
                {isAdmin && <div className="flex flex-wrap gap-2 text-xs">
                  {!device.paired && <button onClick={() => bluetoothAction('pair', device.address)} className="rounded-lg bg-blue-600 px-3 py-2 text-white">Pair</button>}
                  {device.paired && !device.trusted && <button onClick={() => bluetoothAction('trust', device.address)} className="rounded-lg border px-3 py-2">Trust</button>}
                  {device.connected ? <button onClick={() => bluetoothAction('disconnect', device.address)} className="rounded-lg border px-3 py-2">Disconnect</button> : <button onClick={() => bluetoothAction('connect', device.address)} className="rounded-lg border px-3 py-2">Connect</button>}
                  {device.paired && <button onClick={() => bluetoothAction('remove', device.address)} className="rounded-lg border border-red-500/30 px-3 py-2 text-red-400">Remove</button>}
                </div>}
              </div>)}
              {!bluetoothDevices.length && <p className="text-sm text-gray-500">No Bluetooth devices found.</p>}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* WiFi Connect Modal */}
      <AnimatePresence>
        {connectModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setConnectModal(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className={`${isDarkMode ? "bg-black border-white/10" : "bg-white border-gray-200"} relative z-10 w-full max-w-md rounded-[32px] p-8 border shadow-2xl`}
            >
              <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-purple-500/10 text-purple-500 rounded-2xl">
                  <Wifi size={32} />
                </div>
                <div>
                  <h2 className={`text-2xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>Connect to WiFi</h2>
                  <p className="text-sm text-gray-500 font-bold uppercase tracking-widest mt-1">{connectModal.ssid}</p>
                </div>
              </div>

              <form onSubmit={handleWifiConnect} className="space-y-6">
                <div>
                  <label className={`block text-[10px] font-bold uppercase tracking-widest mb-2 ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>PASSWORD</label>
                  <div className="relative">
                    <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      type="password"
                      value={wifiPassword}
                      onChange={(e) => setWifiPassword(e.target.value)}
                      placeholder="••••••••"
                      className={`w-full pl-12 pr-4 py-4 rounded-2xl outline-none transition-all ${isDarkMode ? "bg-white/5 border-white/10 text-white focus:border-purple-500" : "bg-gray-100 border-gray-200 text-gray-900 focus:border-purple-500"} border-2`}
                      autoFocus
                    />
                  </div>
                </div>

                <div className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => setConnectModal(null)}
                    className={`flex-1 py-4 rounded-2xl font-bold uppercase tracking-widest text-xs transition-all ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-gray-400" : "bg-white border-gray-200 text-gray-600 border hover:bg-gray-50"}`}
                  >
                    CANCEL
                  </button>
                  <button
                    type="submit"
                    className="flex-[2] py-4 bg-purple-600 hover:bg-purple-500 text-white rounded-2xl font-bold uppercase tracking-widest text-xs shadow-xl shadow-purple-500/20 transition-all active:scale-95 flex items-center justify-center gap-2"
                  >
                    <Power size={14} /> CONNECT
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>);
}
