import { motion, AnimatePresence } from "motion/react";
import { RefreshCw, Wifi, Cable, Network, Download, Upload, Activity, Shield, CheckCircle2, XCircle, Globe, Lock, Unlock, SignalHigh, SignalMedium, SignalLow, SignalZero, Settings2, Power, RotateCcw, Ban, Search, Trash2, MonitorSmartphone, ChevronDown } from "lucide-react";
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

export function isValidDomain(domain) {
  const normalized = domain.trim().toLowerCase().replace(/\.$/, '');
  return /^(?=.{1,253}$)(?!-)(?:[a-z0-9-]{1,63}\.)+[a-z]{2,63}$/.test(normalized);
}

export function parseDomainList(value) {
  return [...new Set(
    value
      .split(/[\n,]+/)
      .map(item => item.trim().toLowerCase().replace(/\.$/, ''))
      .filter(Boolean)
  )];
}

export function getQueryLogStatus(item) {
  const blocked = Boolean(item.reason?.startsWith?.('Filtered') || item.rule || item.filterId);
  return {
    blocked,
    label: blocked ? 'Blocked' : 'Allowed',
    reason: item.reason || (blocked ? 'Filtered' : 'NotFiltered'),
  };
}

export function formatQueryLogTime(value) {
  if (!value) return '---';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function getQueryLogDetailRows(item) {
  const question = item.question || {};
  const status = getQueryLogStatus(item);
  const answerCount = Array.isArray(item.answer) ? item.answer.length : undefined;
  const rule = item.rule || item.rules?.[0]?.text;
  const filterId = item.filterId || item.filter_id || item.filter_list_id;
  const elapsed = item.elapsedMs ?? item.elapsed_ms;
  const rows = [
    ['Time', item.time || item.timestamp || item.date],
    ['Client', item.client || item.client_id],
    ['Client protocol', item.client_proto],
    ['Domain', question.name || item.domain],
    ['Query type', question.type || item.type],
    ['Query class', question.class],
    ['Decision', status.label],
    ['Reason', status.reason],
    ['Rule', rule],
    ['Filter ID', filterId],
    ['Upstream', item.upstream],
    ['Elapsed', elapsed !== undefined ? `${elapsed} ms` : undefined],
    ['Response status', item.status || item.response_status],
    ['Answers', answerCount !== undefined ? `${answerCount}` : undefined],
  ];

  return rows.filter(([, value]) => value !== undefined && value !== null && value !== '');
}

export function NetworkPage({ initialTab = "interfaces", dnsOnly = false }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const { theme, isDarkMode } = useTheme();
  const { isAdmin } = useAuth();
  const themeColors = getThemeColors(theme);

  const [interfaces, setInterfaces] = useState([]);
  const [connectivity, setConnectivity] = useState({});
  const [wifiNetworks, setWifiNetworks] = useState([]);
  const [wifiStatus, setWifiStatus] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [connectModal, setConnectModal] = useState(null);
  const [wifiPassword, setWifiPassword] = useState('');
  const [dnsStatus, setDnsStatus] = useState(null);
  const [blockedText, setBlockedText] = useState('');
  const [allowedText, setAllowedText] = useState('');
  const [queryLog, setQueryLog] = useState([]);
  const [queryLogLimit, setQueryLogLimit] = useState(50);
  const [queryLogBlockedOnly, setQueryLogBlockedOnly] = useState(false);
  const [expandedQueryKey, setExpandedQueryKey] = useState('');
  const [coverage, setCoverage] = useState({ clients: [], client_count: 0, sample_size: 0 });
  const [dnsBusy, setDnsBusy] = useState(false);
  const [dnsMessage, setDnsMessage] = useState('');
  const [checkDomain, setCheckDomain] = useState('doubleclick.net');
  const [checkResult, setCheckResult] = useState(null);
  const hasLoadedNetworkRef = useRef(false);
  const interfacesHashRef = useRef('');
  const connectivityHashRef = useRef('');
  const wifiNetworksHashRef = useRef('');
  const wifiStatusHashRef = useRef('');
  const dnsStatusHashRef = useRef('');
  const dnsRulesHashRef = useRef('');
  const queryLogHashRef = useRef('');
  const coverageHashRef = useRef('');

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

  const loadDnsFilterData = useCallback(async () => {
    setDnsBusy(true);
    setDnsMessage('');
    try {
      const statusRes = await api.get('/dns-filter/status', { cache: false });
      const nextStatus = statusRes.data || {};
      const nextStatusHash = JSON.stringify(nextStatus);
      if (nextStatusHash !== dnsStatusHashRef.current) {
        dnsStatusHashRef.current = nextStatusHash;
        setDnsStatus(nextStatus);
      }

      if (nextStatus.installed && nextStatus.managed) {
        const [rulesRes, logRes, coverageRes] = await Promise.all([
          api.get('/dns-filter/rules', { cache: false }),
          isAdmin ? api.get(`/dns-filter/querylog?limit=${queryLogLimit}&blocked_only=${queryLogBlockedOnly}`, { cache: false }) : Promise.resolve({ data: { items: [] } }),
          isAdmin ? api.get('/dns-filter/coverage?limit=200', { cache: false }) : Promise.resolve({ data: { clients: [], client_count: 0, sample_size: 0 } }),
        ]);
        const nextRules = rulesRes.data || { blocked_domains: [], allowed_domains: [] };
        const nextLog = logRes.data?.items || [];
        const nextCoverage = coverageRes.data || { clients: [], client_count: 0, sample_size: 0 };
        const nextRulesHash = JSON.stringify(nextRules);
        const nextLogHash = JSON.stringify(nextLog);
        const nextCoverageHash = JSON.stringify(nextCoverage);
        if (nextRulesHash !== dnsRulesHashRef.current) {
          dnsRulesHashRef.current = nextRulesHash;
          setBlockedText((nextRules.blocked_domains || []).join('\n'));
          setAllowedText((nextRules.allowed_domains || []).join('\n'));
        }
        if (nextLogHash !== queryLogHashRef.current) {
          queryLogHashRef.current = nextLogHash;
          setQueryLog(nextLog);
        }
        if (nextCoverageHash !== coverageHashRef.current) {
          coverageHashRef.current = nextCoverageHash;
          setCoverage(nextCoverage);
        }
      } else {
        setQueryLog([]);
        setCoverage({ clients: [], client_count: 0, sample_size: 0 });
      }
    } catch (err) {
      setDnsMessage(err.response?.data?.detail || err.message);
    } finally {
      setDnsBusy(false);
    }
  }, [isAdmin, queryLogBlockedOnly, queryLogLimit]);

  useEffect(() => {
    loadNetworkData();
    if (activeTab === 'wifi') scanWifi();
    if (activeTab === 'dns') loadDnsFilterData();

    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadNetworkData();
      if (activeTab === 'wifi') scanWifi();
      if (activeTab === 'dns') loadDnsFilterData();
    }, 10000);
    return () => clearInterval(interval);
  }, [activeTab, loadNetworkData, scanWifi, loadDnsFilterData]);

  const handleInterfaceAction = async (ifaceName, action) => {
    const rollback = action === 'disable' ? 120 : 0;

    if (action === 'disable' && !confirm(`Disable ${ifaceName}? This will auto-restore after ${rollback}s if you lose connection.`)) {
      return;
    }

    try {
      await api.post(`/network/interfaces/${ifaceName}/action`, {
        action,
        rollback_seconds: rollback
      });
      loadNetworkData();
    } catch (err) {
      alert('Action failed: ' + (err.response?.data?.detail || err.message));
    }
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

  const handleDnsToggle = async (path, enabled) => {
    setDnsBusy(true);
    setDnsMessage('');
    try {
      await api.post(`/dns-filter/${path}`, { enabled });
      await loadDnsFilterData();
    } catch (err) {
      setDnsMessage(err.response?.data?.detail || err.message);
    } finally {
      setDnsBusy(false);
    }
  };

  const handleSaveDnsRules = async () => {
    const blocked = parseDomainList(blockedText);
    const allowed = parseDomainList(allowedText);
    const invalid = [...blocked, ...allowed].find(domain => !isValidDomain(domain));
    if (invalid) {
      setDnsMessage(`Invalid domain: ${invalid}`);
      return;
    }
    setDnsBusy(true);
    setDnsMessage('');
    try {
      await api.put('/dns-filter/rules', {
        blocked_domains: blocked,
        allowed_domains: allowed,
      });
      await loadDnsFilterData();
      setDnsMessage('Rules saved.');
    } catch (err) {
      setDnsMessage(err.response?.data?.detail || err.message);
    } finally {
      setDnsBusy(false);
    }
  };

  const handleCheckDomain = async (e) => {
    e.preventDefault();
    const domain = checkDomain.trim();
    if (!isValidDomain(domain)) {
      setDnsMessage(`Invalid domain: ${domain}`);
      return;
    }
    setDnsBusy(true);
    setDnsMessage('');
    try {
      const res = await api.post('/dns-filter/check', { domain });
      setCheckResult(res.data);
    } catch (err) {
      setDnsMessage(err.response?.data?.detail || err.message);
    } finally {
      setDnsBusy(false);
    }
  };

  const handleClearDnsCache = async () => {
    setDnsBusy(true);
    setDnsMessage('');
    try {
      await api.post('/dns-filter/cache/clear');
      setDnsMessage('DNS cache cleared.');
    } catch (err) {
      setDnsMessage(err.response?.data?.detail || err.message);
    } finally {
      setDnsBusy(false);
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
            {dnsOnly ? 'AdGuard DNS Filter' : 'Network'}
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            {dnsOnly ? 'Monitor DNS filtering, client coverage, rules and AdGuard query logs' : 'Manage interfaces, WiFi connections and monitor traffic'}
          </p>
        </div>
        {!dnsOnly && <div className="flex items-center gap-3">
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
        </div>}
      </div>

      {/* Connectivity Status Bar */}
      {!dnsOnly && <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-8">
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
      </div>}

      {/* Tabs */}
      {!dnsOnly && <div className="flex gap-3 mb-8">
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
          onClick={() => setActiveTab("dns")}
          className={`flex items-center gap-2 px-8 py-3 rounded-2xl text-sm font-bold transition-all ${activeTab === "dns"
            ? isDarkMode ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30" : "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
            : isDarkMode ? "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10" : "bg-white border-gray-200 text-gray-600 shadow-sm hover:border-gray-300"} border`}
        >
          <Ban size={18} />
          DNS FILTER
        </motion.button>
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
                      <span className={`text-xs font-mono font-bold ${isDarkMode ? 'text-gray-500' : 'text-gray-500'}`}>{wifiStatus.ip_address}</span>
                      <span className={`text-xs font-bold ${isDarkMode ? 'text-gray-600' : 'text-gray-400'}`}>• {wifiStatus.frequency} • {wifiStatus.signal_quality}% Quality</span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-3 relative z-10">
                  <button className={`px-6 py-3 rounded-2xl text-sm font-bold uppercase tracking-widest transition-all ${isDarkMode ? "bg-red-500/10 text-red-500 border-red-500/20 hover:bg-red-500/20" : "bg-red-50 text-red-600 border-red-100 hover:bg-red-100"} border`}>
                    DISCONNECT
                  </button>
                  <button className={`p-3 rounded-2xl border transition-all ${isDarkMode ? "bg-white/5 border-white/10 hover:bg-white/10 text-gray-400" : "bg-white border-gray-200 hover:bg-gray-50 text-gray-600"}`}>
                    <Settings2 size={24} />
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
        ) : (
          <motion.div
            key="dns"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="space-y-6"
          >
            <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[24px] p-6`}>
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-2xl ${dnsStatus?.installed && dnsStatus?.managed ? 'bg-green-500/10 text-green-500' : 'bg-yellow-500/10 text-yellow-500'}`}>
                    <Ban size={28} />
                  </div>
                  <div>
                    <h2 className={`text-2xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>DNS Filter</h2>
                    <p className={`mt-1 max-w-3xl text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                      AdGuard Home filters DNS requests for devices that use this Raspberry Pi as their DNS server.
                    </p>
                    <div className="flex flex-wrap gap-2 mt-4">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase border ${dnsStatus?.installed ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'}`}>
                        {dnsStatus?.installed ? 'Installed' : 'Not Installed'}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase border ${dnsStatus?.managed ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>
                        {dnsStatus?.managed ? 'Managed' : 'Unmanaged'}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase border ${dnsStatus?.protection_enabled ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-gray-500/10 text-gray-500 border-gray-500/20'}`}>
                        {dnsStatus?.protection_enabled ? 'Protection On' : 'Protection Off'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={loadDnsFilterData}
                    disabled={dnsBusy}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-bold transition-all ${isDarkMode ? "bg-white/5 border-white/10 text-white hover:bg-white/10" : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"}`}
                  >
                    <RefreshCw size={16} className={dnsBusy ? 'animate-spin' : ''} />
                    Refresh
                  </button>
                  {isAdmin && dnsStatus?.installed && dnsStatus?.managed && (
                    <button
                      onClick={handleClearDnsCache}
                      disabled={dnsBusy}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl border border-blue-500/20 bg-blue-500/10 text-blue-500 text-sm font-bold hover:bg-blue-500/20 transition-all"
                    >
                      <Trash2 size={16} />
                      Clear Cache
                    </button>
                  )}
                </div>
              </div>

              {dnsMessage && (
                <div className={`mt-4 p-3 rounded-xl text-sm ${dnsMessage.includes('Invalid') || dnsMessage.includes('failed') || dnsMessage.includes('rejected') ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-blue-500/10 text-blue-500 border-blue-500/20'} border`}>
                  {dnsMessage}
                </div>
              )}
            </div>

            {(!dnsStatus?.installed || !dnsStatus?.managed) ? (
              <div className={`${isDarkMode ? "bg-black/40 border-yellow-500/20" : "bg-yellow-50 border-yellow-200"} border rounded-[24px] p-6`}>
                <h3 className={`text-lg font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>Install Required</h3>
                <p className={`mt-2 text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                  Install with AdGuard enabled, then set your router DHCP DNS server to this Pi IP for LAN-wide filtering.
                </p>
                <pre className={`mt-4 overflow-x-auto rounded-xl p-4 text-xs ${isDarkMode ? "bg-white/5 text-gray-200" : "bg-white text-gray-800 border border-gray-200"}`}>sudo ./install.sh --profile local --with-adguard</pre>
                {dnsStatus?.error && <p className="mt-3 text-sm text-yellow-600">{dnsStatus.error}</p>}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {[
                    { label: 'Protection', key: 'protection_enabled', path: 'protection' },
                    { label: 'Malware/Phishing', key: 'safebrowsing_enabled', path: 'safebrowsing' },
                    { label: 'Adult Content', key: 'parental_enabled', path: 'parental' },
                  ].map(item => (
                    <div key={item.key} className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[20px] p-5 flex items-center justify-between`}>
                      <div>
                        <p className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>{item.label}</p>
                        <p className={`mt-1 text-sm font-bold ${dnsStatus?.[item.key] ? 'text-green-500' : 'text-gray-500'}`}>{dnsStatus?.[item.key] ? 'Enabled' : 'Disabled'}</p>
                      </div>
                      <button
                        disabled={!isAdmin || dnsBusy}
                        onClick={() => handleDnsToggle(item.path, !dnsStatus?.[item.key])}
                        className={`w-12 h-7 rounded-full transition-all p-1 ${dnsStatus?.[item.key] ? 'bg-green-500' : isDarkMode ? 'bg-white/10' : 'bg-gray-300'} disabled:opacity-50`}
                      >
                        <span className={`block w-5 h-5 rounded-full bg-white transition-transform ${dnsStatus?.[item.key] ? 'translate-x-5' : 'translate-x-0'}`} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[24px] p-6`}>
                  <div className="flex items-center justify-between gap-4 mb-4">
                    <div>
                      <h3 className={`text-lg font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>Device Coverage</h3>
                      <p className={`text-sm mt-1 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                        Devices appear here after they send DNS queries to this Pi.
                      </p>
                    </div>
                    <div className="flex items-center gap-2 text-green-500">
                      <MonitorSmartphone size={20} />
                      <span className="text-sm font-bold">{coverage.client_count || 0} clients</span>
                    </div>
                  </div>
                  {!isAdmin ? (
                    <p className="text-sm text-gray-500">Device coverage is admin-only because it is derived from DNS metadata.</p>
                  ) : coverage.clients?.length ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      {coverage.clients.map(client => (
                        <div key={client.client} className={`p-4 rounded-2xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-gray-50 border-gray-200"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <span className={`font-mono text-sm font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>{client.client}</span>
                            <span className="text-[10px] font-bold uppercase text-green-500">{client.queries} queries</span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="text-[10px] font-bold uppercase bg-red-500/10 text-red-500 border border-red-500/20 px-2 py-1 rounded-full">{client.blocked} blocked</span>
                            {(client.sample_domains || []).slice(0, 3).map(domain => (
                              <span key={domain} className={`text-[10px] font-mono px-2 py-1 rounded-full ${isDarkMode ? "bg-black/30 text-gray-400" : "bg-white text-gray-600 border border-gray-200"}`}>{domain}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">No client DNS traffic has been seen yet. Set router DHCP DNS to 192.168.0.102, then reconnect a device or renew DHCP.</p>
                  )}
                </div>

                <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[24px] p-6`}>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <label className={`block text-[10px] font-bold uppercase tracking-widest mb-2 ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>Blocked Domains</label>
                      <textarea
                        value={blockedText}
                        onChange={(e) => setBlockedText(e.target.value)}
                        disabled={!isAdmin}
                        rows={8}
                        className={`w-full rounded-2xl p-4 font-mono text-sm outline-none border ${isDarkMode ? "bg-white/5 border-white/10 text-white focus:border-purple-500" : "bg-gray-50 border-gray-200 text-gray-900 focus:border-purple-500"}`}
                        placeholder="ads.example.com"
                      />
                    </div>
                    <div>
                      <label className={`block text-[10px] font-bold uppercase tracking-widest mb-2 ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>Allowed Domains</label>
                      <textarea
                        value={allowedText}
                        onChange={(e) => setAllowedText(e.target.value)}
                        disabled={!isAdmin}
                        rows={8}
                        className={`w-full rounded-2xl p-4 font-mono text-sm outline-none border ${isDarkMode ? "bg-white/5 border-white/10 text-white focus:border-purple-500" : "bg-gray-50 border-gray-200 text-gray-900 focus:border-purple-500"}`}
                        placeholder="safe.example.com"
                      />
                    </div>
                  </div>
                  <div className="mt-4 flex justify-end">
                    <button
                      onClick={handleSaveDnsRules}
                      disabled={!isAdmin || dnsBusy}
                      className="px-5 py-3 rounded-2xl bg-purple-600 text-white text-sm font-bold disabled:opacity-50 hover:bg-purple-500 transition-all"
                    >
                      Save Rules
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[24px] p-6`}>
                    <h3 className={`text-lg font-bold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>Domain Check</h3>
                    <form onSubmit={handleCheckDomain} className="flex gap-3">
                      <input
                        value={checkDomain}
                        onChange={(e) => setCheckDomain(e.target.value)}
                        className={`flex-1 rounded-2xl px-4 py-3 outline-none border ${isDarkMode ? "bg-white/5 border-white/10 text-white focus:border-purple-500" : "bg-gray-50 border-gray-200 text-gray-900 focus:border-purple-500"}`}
                        placeholder="doubleclick.net"
                      />
                      <button type="submit" disabled={dnsBusy} className="px-4 py-3 rounded-2xl bg-purple-600 text-white font-bold disabled:opacity-50">
                        <Search size={18} />
                      </button>
                    </form>
                    {checkResult && (
                      <div className={`mt-4 p-4 rounded-2xl border ${checkResult.blocked ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-green-500/10 text-green-500 border-green-500/20'}`}>
                        <p className="text-sm font-bold">{checkResult.domain}: {checkResult.blocked ? 'Blocked' : 'Allowed'}</p>
                        <p className="text-xs mt-1 opacity-80">{checkResult.reason || 'No matching rule'}</p>
                      </div>
                    )}
                  </div>

                  <div className={`${isDarkMode ? "bg-black/40 border-white/10" : "bg-white border-gray-200 shadow-sm"} border rounded-[24px] p-6`}>
                    <div className="flex flex-col gap-4 mb-4 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h3 className={`text-lg font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>AdGuard Query Logs</h3>
                        <p className={`mt-1 text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                          Recent DNS requests, client addresses and filter decisions.
                        </p>
                      </div>
                      {isAdmin && (
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            value={queryLogLimit}
                            onChange={(e) => setQueryLogLimit(Number(e.target.value))}
                            className={`h-10 rounded-xl px-3 text-xs font-bold outline-none border ${isDarkMode ? "bg-white/5 border-white/10 text-white" : "bg-gray-50 border-gray-200 text-gray-700"}`}
                            aria-label="Query log limit"
                          >
                            {[25, 50, 100, 200].map(limit => (
                              <option key={limit} value={limit}>{limit}</option>
                            ))}
                          </select>
                          <button
                            type="button"
                            onClick={() => setQueryLogBlockedOnly(value => !value)}
                            className={`h-10 px-3 rounded-xl border text-[10px] font-bold uppercase tracking-widest transition-all ${queryLogBlockedOnly ? 'bg-red-500/10 text-red-500 border-red-500/20' : isDarkMode ? 'bg-white/5 border-white/10 text-gray-300' : 'bg-gray-50 border-gray-200 text-gray-600'}`}
                          >
                            Blocked Only
                          </button>
                          <button
                            type="button"
                            onClick={loadDnsFilterData}
                            disabled={dnsBusy}
                            className={`h-10 px-3 rounded-xl border transition-all ${isDarkMode ? "bg-white/5 border-white/10 text-gray-300 hover:bg-white/10" : "bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100"}`}
                            aria-label="Refresh query logs"
                          >
                            <RefreshCw size={16} className={dnsBusy ? 'animate-spin' : ''} />
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
                      {!isAdmin && <p className="text-sm text-gray-500">DNS query logs are admin-only because they contain browsing metadata.</p>}
                      {isAdmin && queryLog.map((item, index) => {
                        const host = item.question?.name || item.domain || 'unknown';
                        const type = item.question?.type || item.type || 'A';
                        const client = item.client || item.client_id || 'unknown';
                        const status = getQueryLogStatus(item);
                        const time = formatQueryLogTime(item.time || item.timestamp || item.date);
                        const upstream = item.upstream || 'local/filter';
                        const queryKey = `${host}-${client}-${item.time || item.timestamp || index}`;
                        const expanded = expandedQueryKey === queryKey;
                        const detailRows = getQueryLogDetailRows(item);
                        return (
                          <div key={queryKey} className={`p-3 rounded-2xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-gray-50 border-gray-200"}`}>
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className={`font-mono text-xs font-bold truncate max-w-full ${isDarkMode ? "text-gray-100" : "text-gray-900"}`}>{host}</span>
                                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${status.blocked ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-green-500/10 text-green-500 border-green-500/20'}`}>
                                    {status.label}
                                  </span>
                                </div>
                                <div className={`mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>
                                  <span>{time}</span>
                                  <span className="font-mono">{client}</span>
                                  <span>{type}</span>
                                  <span className="truncate max-w-[12rem]">{upstream}</span>
                                </div>
                              </div>
                              <span className={`shrink-0 max-w-[9rem] truncate text-[10px] font-bold uppercase ${status.blocked ? 'text-red-500' : isDarkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                                {status.reason}
                              </span>
                            </div>
                            <div className="mt-3 flex justify-end">
                              <button
                                type="button"
                                onClick={() => setExpandedQueryKey(expanded ? '' : queryKey)}
                                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-all ${isDarkMode ? "border-white/10 bg-black/20 text-gray-300 hover:bg-white/10" : "border-gray-200 bg-white text-gray-600 hover:bg-gray-100"}`}
                              >
                                Details
                                <ChevronDown size={14} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
                              </button>
                            </div>
                            {expanded && (
                              <div className={`mt-3 rounded-2xl border p-4 ${isDarkMode ? "bg-black/30 border-white/10" : "bg-white border-gray-200"}`}>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                  {detailRows.map(([label, value]) => (
                                    <div key={label} className="min-w-0">
                                      <div className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>{label}</div>
                                      <div className={`mt-1 break-words font-mono text-xs ${isDarkMode ? "text-gray-200" : "text-gray-800"}`}>{String(value)}</div>
                                    </div>
                                  ))}
                                </div>
                                {Array.isArray(item.answer) && item.answer.length > 0 && (
                                  <div className="mt-4">
                                    <div className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? "text-gray-500" : "text-gray-500"}`}>Answer Records</div>
                                    <div className="mt-2 space-y-2">
                                      {item.answer.slice(0, 5).map((answer, answerIndex) => (
                                        <div key={`${queryKey}-answer-${answerIndex}`} className={`rounded-xl px-3 py-2 font-mono text-xs ${isDarkMode ? "bg-white/5 text-gray-300" : "bg-gray-50 text-gray-700"}`}>
                                          {answer.type || 'record'} {answer.value || answer.data || answer.name || JSON.stringify(answer)}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                <details className="mt-4">
                                  <summary className={`cursor-pointer text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>Raw AdGuard Entry</summary>
                                  <pre className={`mt-2 max-h-56 overflow-auto rounded-xl p-3 text-[11px] ${isDarkMode ? "bg-black/40 text-gray-300" : "bg-gray-50 text-gray-700"}`}>{JSON.stringify(item, null, 2)}</pre>
                                </details>
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {isAdmin && queryLog.length === 0 && <p className="text-sm text-gray-500">No DNS queries yet.</p>}
                    </div>
                  </div>
                </div>
              </>
            )}
          </motion.div>
        )}
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

export function AdGuardPage() {
  return <NetworkPage initialTab="dns" dnsOnly />;
}
