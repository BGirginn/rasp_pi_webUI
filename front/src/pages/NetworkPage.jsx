import { motion } from "motion/react";
import { RefreshCw, Wifi, Cable, Network, Download, Upload, } from "lucide-react";
import { useTheme, getThemeColors, } from "../contexts/ThemeContext";
import { useState, useEffect } from "react";
import { api } from "../services/api";

// Helper to format bytes
function formatBytes(bytes, decimals = 2) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

// Get icon based on interface type
function getInterfaceIcon(type) {
  if (type === 'wifi') return Wifi;
  return Cable;
}

export function NetworkPage() {
  const [activeTab, setActiveTab] = useState("interfaces");
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);

  // Real data from API
  const [interfaces, setInterfaces] = useState([]);
  const [connectivity, setConnectivity] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadNetworkData();
    const interval = setInterval(loadNetworkData, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadNetworkData() {
    try {
      const [ifaceRes, connRes] = await Promise.all([
        api.get('/network/interfaces').catch(() => ({ data: [] })),
        api.get('/network/connectivity').catch(() => ({ data: {} }))
      ]);
      setInterfaces(ifaceRes.data || []);
      setConnectivity(connRes.data || {});
    } catch (err) {
      console.error('Failed to load network data:', err);
    } finally {
      setLoading(false);
    }
  }

  // Build connectivity status from API response
  const connectivityStatus = [
    { label: "LAN", status: connectivity.lan !== false },
    { label: "Internet", status: connectivity.internet !== false },
    { label: "DNS", status: connectivity.dns !== false },
    { label: "Tailscale", status: connectivity.tailscale !== false },
  ];
  return (<div>
    <div className="flex items-center justify-between mb-6">
      <h1 className={`text-4xl bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
        Network
      </h1>
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? "bg-white/5 border-white/10 hover:border-white/30" : "bg-white border-gray-300 hover:border-gray-400"} border`}>
        <RefreshCw size={18} />
        <span>Refresh</span>
      </motion.button>
    </div>

    {/* Connectivity Status */}
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? "bg-black/40" : "bg-white"} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? "border-white/10" : "border-gray-300"} mb-8`}>
      <h3 className={`text-lg mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
        Connectivity Status
      </h3>
      <div className="flex gap-4">
        {connectivityStatus.map((item, index) => (<motion.div key={item.label} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: index * 0.1 }} className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${item.status ? "bg-green-500" : "bg-red-500"}`} />
          <span className={`text-sm ${isDarkMode ? "text-gray-300" : "text-gray-700"}`}>
            {item.label}
          </span>
        </motion.div>))}
        <div className={`ml-auto text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
          Latency:{" "}
          <span className={isDarkMode ? "text-white" : "text-gray-900"}>
            15ms
          </span>
        </div>
      </div>
    </motion.div>

    {/* Tabs */}
    <div className="flex gap-3 mb-6">
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveTab("interfaces")} className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm transition-all ${activeTab === "interfaces"
        ? isDarkMode
          ? "bg-gradient-to-r from-purple-600 to-fuchsia-600 text-white shadow-lg shadow-purple-500/30"
          : "bg-gradient-to-r from-purple-500 to-fuchsia-500 text-white shadow-lg shadow-purple-500/30"
        : isDarkMode
          ? "bg-white/5 text-gray-400 hover:bg-white/10"
          : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
        <Network size={18} />
        Interfaces
      </motion.button>
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveTab("wifi")} className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm transition-all ${activeTab === "wifi"
        ? isDarkMode
          ? "bg-gradient-to-r from-purple-600 to-fuchsia-600 text-white shadow-lg shadow-purple-500/30"
          : "bg-gradient-to-r from-purple-500 to-fuchsia-500 text-white shadow-lg shadow-purple-500/30"
        : isDarkMode
          ? "bg-white/5 text-gray-400 hover:bg-white/10"
          : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
        <Wifi size={18} />
        WiFi
      </motion.button>
    </div>

    {/* Interfaces Content */}
    {activeTab === "interfaces" && (<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {interfaces.length === 0 && !loading && (
        <div className={`col-span-2 text-center py-12 ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
          No network interfaces found
        </div>
      )}
      {interfaces.map((iface, index) => {
        const Icon = getInterfaceIcon(iface.type);
        return (<motion.div key={iface.name} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + index * 0.1 }} className={`${isDarkMode ? "bg-black/40" : "bg-white"} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? "border-white/10" : "border-gray-300"}`}>
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${isDarkMode ? themeColors.secondary : themeColors.lightSecondary} flex items-center justify-center`}>
                <Icon size={24} className="text-white" />
              </div>
              <div>
                <h3 className={`text-lg ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  {iface.name}
                </h3>
                <p className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                  {iface.type}
                </p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs ${iface.status === "up"
              ? isDarkMode
                ? "bg-green-500/20 text-green-400 border border-green-500/30"
                : "bg-green-100 text-green-700 border border-green-300"
              : isDarkMode
                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                : "bg-red-100 text-red-700 border border-red-300"}`}>
              {iface.status}
            </span>
          </div>

          <div className="space-y-3 mb-6">
            <div className="flex justify-between">
              <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                IP Address
              </span>
              <span className={`text-sm ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                {iface.ip || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                MAC
              </span>
              <span className={`text-sm ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                {iface.mac || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                Gateway
              </span>
              <span className={`text-sm ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                {iface.gateway || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                Speed
              </span>
              <span className={`text-sm ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                {iface.speed_mbps ? `${iface.speed_mbps} Mbps` : 'N/A'}
              </span>
            </div>
          </div>

          <div className={`grid grid-cols-2 gap-4 pt-4 border-t ${isDarkMode ? "border-white/10" : "border-gray-200"} mb-4`}>
            <div>
              <div className={`text-xs ${isDarkMode ? "text-gray-500" : "text-gray-600"} mb-1 flex items-center gap-1`}>
                <Download size={14} /> RX
              </div>
              <div className={`text-lg ${isDarkMode ? "text-green-400" : "text-green-600"}`}>
                {formatBytes(iface.rx_bytes)}
              </div>
            </div>
            <div>
              <div className={`text-xs ${isDarkMode ? "text-gray-500" : "text-gray-600"} mb-1 flex items-center gap-1`}>
                <Upload size={14} /> TX
              </div>
              <div className={`text-lg ${isDarkMode ? "text-blue-400" : "text-blue-600"}`}>
                {formatBytes(iface.tx_bytes)}
              </div>
            </div>
          </div>

          <button className={`w-full px-4 py-2 rounded-lg ${isDarkMode ? "bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30" : "bg-red-100 border-red-500 text-red-700 hover:bg-red-200"} border transition-all`}>
            Disable
          </button>
        </motion.div>);
      })}
    </div>)}

    {/* WiFi Content */}
    {activeTab === "wifi" && (<motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? "bg-black/40" : "bg-white"} backdrop-blur-xl rounded-2xl p-16 border ${isDarkMode ? "border-white/10" : "border-gray-300"} text-center`}>
      <Wifi size={64} className={`mx-auto mb-4 ${isDarkMode ? "text-gray-600" : "text-gray-400"}`} />
      <h3 className={`text-xl mb-2 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
        WiFi Configuration
      </h3>
      <p className={`${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
        WiFi settings and network scanning coming soon
      </p>
    </motion.div>)}
  </div>);
}
