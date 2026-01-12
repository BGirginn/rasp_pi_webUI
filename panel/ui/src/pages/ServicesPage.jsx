import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { RefreshCw, Package, Play, Square, RotateCcw, Search, Activity, Cpu, HardDrive, Shield, Terminal, AlertCircle, CheckCircle2, XCircle, Info } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export function ServicesPage() {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const { theme, isDarkMode } = useTheme();
  const { isOperator } = useAuth();
  const themeColors = getThemeColors(theme);

  const loadServices = async () => {
    if (!loading) setRefreshing(true);
    try {
      const response = await api.get('/resources');
      setServices(response.data || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load services:', err);
      setError('Failed to fetch services from backend.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadServices();
    const interval = setInterval(loadServices, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (serviceId, action) => {
    try {
      await api.post(`/resources/${serviceId}/action`, { action });
      loadServices(); // Refresh after action
    } catch (err) {
      console.error('Service action failed:', err);
      alert(`Action failed: ${err.response?.data?.detail || err.message}`);
    }
  };

  const counts = {
    all: services.length,
    docker: services.filter(s => s.provider === 'docker').length,
    systemd: services.filter(s => s.provider === 'systemd').length,
    running: services.filter(s => s.state === 'running').length,
    stopped: services.filter(s => s.state === 'stopped').length,
  };

  const filterOptions = [
    { label: 'All', value: 'all', count: counts.all, color: 'purple' },
    { label: 'Docker', value: 'docker', count: counts.docker, color: 'blue', hidden: counts.docker === 0 },
    { label: 'Systemd', value: 'systemd', count: counts.systemd, color: 'gray' },
    { label: 'Running', value: 'running', count: counts.running, color: 'green' },
    { label: 'Stopped', value: 'stopped', count: counts.stopped, color: 'red' },
  ].filter(opt => !opt.hidden);

  const filteredServices = services.filter(s => {
    const matchesSearch = s.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = activeFilter === 'all' ||
      (activeFilter === 'running' && s.state === 'running') ||
      (activeFilter === 'stopped' && s.state === 'stopped') ||
      (activeFilter === 'docker' && s.provider === 'docker') ||
      (activeFilter === 'systemd' && s.provider === 'systemd');
    return matchesSearch && matchesFilter;
  });

  const getStatusIcon = (state) => {
    switch (state) {
      case 'running': return <CheckCircle2 size={16} className="text-green-500" />;
      case 'failed': return <XCircle size={16} className="text-red-500" />;
      case 'stopped': return <Info size={16} className="text-gray-500" />;
      default: return <Activity size={16} className="text-blue-500" />;
    }
  };

  const getStateStyles = (state) => {
    switch (state) {
      case 'running':
        return isDarkMode ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-green-100 text-green-700 border-green-200';
      case 'failed':
        return isDarkMode ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-red-100 text-red-700 border-red-200';
      default:
        return isDarkMode ? 'bg-gray-500/20 text-gray-400 border-gray-500/30' : 'bg-gray-100 text-gray-600 border-gray-200';
    }
  };

  return (
    <div className="animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className={`text-4xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Services
          </h1>
          <p className={`mt-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            Monitor and control system daemons and docker containers
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className={`absolute left-3 top-1/2 -translate-y-1/2 ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`} size={18} />
            <input
              type="text"
              placeholder="Find service..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`pl-10 pr-4 py-2 rounded-xl text-sm ${isDarkMode ? 'bg-white/5 border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900'} border focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all w-full md:w-64`}
            />
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadServices}
            disabled={refreshing}
            className={`p-2 rounded-xl ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-white border-gray-200 shadow-sm'} border transition-all disabled:opacity-50`}
          >
            <RefreshCw size={20} className={refreshing ? 'animate-spin' : ''} />
          </motion.button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-8 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-500 flex items-center gap-3">
          <AlertCircle size={20} />
          <span>{error}</span>
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

      {/* Services Grid / List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className={`h-40 rounded-3xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} animate-pulse`} />
          ))}
        </div>
      ) : filteredServices.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AnimatePresence mode="popLayout">
            {filteredServices.map((service, index) => (
              <motion.div
                key={service.id}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2, delay: index * 0.05 }}
                className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-3xl p-6 border ${isDarkMode ? 'border-white/10 hover:border-purple-500/50' : 'border-gray-200 hover:border-purple-400 shadow-sm'} transition-all group relative overflow-hidden`}
              >
                {/* Provider Badge Background Decoration */}
                <div className={`absolute -right-4 -top-4 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity ${service.provider === 'docker' ? 'text-blue-500' : 'text-gray-500'}`}>
                  {service.provider === 'docker' ? <Package size={120} /> : <Terminal size={120} />}
                </div>

                <div className="relative z-10">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-lg ${service.resource_class === 'CORE' ? 'bg-red-500/10 text-red-500' : service.resource_class === 'SYSTEM' ? 'bg-blue-500/10 text-blue-500' : 'bg-purple-500/10 text-purple-500'}`}>
                        {service.provider === 'docker' ? <Package size={24} /> : <Terminal size={24} />}
                      </div>
                      <div>
                        <h3 className={`font-bold text-lg truncate w-40 ${isDarkMode ? 'text-white' : 'text-gray-900 group-hover:text-purple-600 transition-colors'}`}>
                          {service.name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-[10px] font-bold uppercase tracking-widest ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                            {service.resource_class}
                          </span>
                          <span className={`w-1 h-1 rounded-full ${isDarkMode ? 'bg-gray-700' : 'bg-gray-300'}`} />
                          <span className={`text-[10px] font-bold uppercase tracking-widest ${service.provider === 'docker' ? 'text-blue-500' : 'text-purple-500'}`}>
                            {service.provider}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${getStateStyles(service.state)}`}>
                      {getStatusIcon(service.state)}
                      {service.state}
                    </div>
                  </div>

                  {/* Stats (CPU/MEM) */}
                  {(service.cpu_usage > 0 || service.memory_usage > 0) && (
                    <div className="grid grid-cols-2 gap-4 mb-6">
                      <div className={`p-2 rounded-xl ${isDarkMode ? 'bg-white/5 border-white/5' : 'bg-gray-50 border-gray-100'} border`}>
                        <div className="flex items-center gap-2 mb-1">
                          <Cpu size={12} className="text-purple-500" />
                          <span className="text-[10px] font-bold text-gray-500 uppercase">CPU</span>
                        </div>
                        <div className={`text-sm font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{service.cpu_usage.toFixed(1)}%</div>
                      </div>
                      <div className={`p-2 rounded-xl ${isDarkMode ? 'bg-white/5 border-white/5' : 'bg-gray-50 border-gray-100'} border`}>
                        <div className="flex items-center gap-2 mb-1">
                          <HardDrive size={12} className="text-blue-500" />
                          <span className="text-[10px] font-bold text-gray-500 uppercase">RAM</span>
                        </div>
                        <div className={`text-sm font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{service.memory_usage.toFixed(1)}%</div>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {isOperator && service.resource_class !== 'CORE' && (
                    <div className="flex gap-2">
                      {service.state === 'running' ? (
                        <>
                          <button
                            onClick={() => handleAction(service.id, 'restart')}
                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400 hover:bg-purple-500/30' : 'bg-purple-50 border-purple-200 text-purple-600 hover:bg-purple-100'} border`}
                          >
                            <RotateCcw size={14} /> RESTART
                          </button>
                          {service.resource_class === 'APP' && (
                            <button
                              onClick={() => handleAction(service.id, 'stop')}
                              className={`px-3 py-2 rounded-xl border transition-all ${isDarkMode ? 'bg-red-500/10 border-red-500/30 text-red-500 hover:bg-red-500/20' : 'bg-red-50 border-red-200 text-red-600 hover:bg-red-100'}`}
                            >
                              <Square size={14} fill="currentColor" />
                            </button>
                          )}
                        </>
                      ) : (
                        <button
                          onClick={() => handleAction(service.id, 'start')}
                          className={`hover:scale-[1.02] active:scale-95 flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${isDarkMode ? 'bg-green-500/20 border-green-500/50 text-green-400 hover:bg-green-500/30' : 'bg-green-100 border-green-200 text-green-700 hover:bg-green-200'} border shadow-lg shadow-green-500/10`}
                        >
                          <Play size={14} fill="currentColor" /> START
                        </button>
                      )}
                    </div>
                  )}

                  {/* Core Protection Label */}
                  {service.resource_class === 'CORE' && (
                    <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase mt-4">
                      <Shield size={12} className="text-red-500" />
                      System Protected Resource
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className={`${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200 shadow-inner'} border rounded-[32px] p-20 text-center`}
        >
          <Package size={80} className={`mx-auto mb-6 ${isDarkMode ? 'text-gray-700' : 'text-gray-300'}`} />
          <h3 className={`text-2xl font-bold mb-3 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            {searchTerm ? `No matches for "${searchTerm}"` : 'No services found'}
          </h3>
          <p className={`max-w-md mx-auto ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            {searchTerm
              ? "Try searching for a different service name or clear the current search."
              : "Systemd or Docker services haven't been discovered yet. Try refreshing the page."}
          </p>
          <button
            onClick={() => { setSearchTerm(''); loadServices(); }}
            className="mt-8 px-10 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-2xl font-bold shadow-xl shadow-purple-500/20 transition-all active:scale-95"
          >
            Reset & Refresh
          </button>
        </motion.div>
      )}
    </div>
  );
}
