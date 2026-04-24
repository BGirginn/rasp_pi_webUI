import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Package, Play, Square, RotateCcw, Search, Activity, Cpu, HardDrive, Shield, Terminal, AlertCircle, CheckCircle2, XCircle, Info, Lock, Unlock } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export function ServicesPage() {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionProgress, setActionProgress] = useState({});
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const servicesHashRef = useRef('');
  const hasLoadedServicesRef = useRef(false);
  const { theme, isDarkMode } = useTheme();
  const { isOperator } = useAuth();
  const themeColors = getThemeColors(theme);

  const loadServices = useCallback(async ({ silent = false } = {}) => {
    if (!silent && hasLoadedServicesRef.current) setRefreshing(true);
    try {
      const response = await api.get('/resources');
      const nextServices = response.data || [];
      const nextHash = JSON.stringify(nextServices);
      if (nextHash !== servicesHashRef.current) {
        servicesHashRef.current = nextHash;
        setServices(nextServices);
      }
      setError(null);
      return nextServices;
    } catch (err) {
      console.error('Failed to load services:', err);
      setError('Failed to fetch services from backend.');
      return [];
    } finally {
      setLoading(false);
      if (!silent) setRefreshing(false);
      hasLoadedServicesRef.current = true;
    }
  }, []);

  useEffect(() => {
    loadServices();
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadServices({ silent: true });
    }, 30000);
    return () => clearInterval(interval);
  }, [loadServices]);

  const monitorServiceTransition = useCallback(async (serviceId, targetState) => {
    const timeoutMs = 90000;
    const pollMs = 1200;
    const startedAt = Date.now();

    while (Date.now() - startedAt < timeoutMs) {
      const nextServices = await loadServices({ silent: true });
      const updatedService = nextServices.find((s) => s.id === serviceId);

      if (updatedService) {
        setActionProgress((prev) => {
          const progress = prev[serviceId];
          if (!progress) return prev;

          const currentState = updatedService.state;
          const nextSteps = progress.steps.includes(currentState)
            ? progress.steps
            : [...progress.steps, currentState];

          return {
            ...prev,
            [serviceId]: {
              ...progress,
              currentState,
              steps: nextSteps,
            },
          };
        });

        if (updatedService.state === targetState) {
          return { success: true };
        }
        if (updatedService.state === 'failed') {
          return { success: false, error: 'Service failed while applying action.' };
        }
      }

      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }

    return { success: false, error: `Timed out waiting for service state: ${targetState}` };
  }, [loadServices]);

  const getTransitionState = (action) => {
    if (action === 'start') return 'starting';
    if (action === 'stop') return 'stopping';
    return 'restarting';
  };

  const getTargetState = (action) => {
    if (action === 'stop') return 'stopped';
    return 'running';
  };

  const handleAction = async (service, action) => {
    const serviceId = service.id;
    const transitionState = getTransitionState(action);
    const targetState = getTargetState(action);

    if (actionProgress[serviceId]) return;

    setActionProgress((prev) => ({
      ...prev,
      [serviceId]: {
        action,
        targetState,
        currentState: transitionState,
        steps: [service.state, transitionState],
      },
    }));

    try {
      await api.post(`/resources/${serviceId}/action`, { action });
      const result = await monitorServiceTransition(serviceId, targetState);

      if (!result.success) {
        throw new Error(result.error || 'Transition failed');
      }

      setActionProgress((prev) => {
        const progress = prev[serviceId];
        if (!progress) return prev;

        const nextSteps = progress.steps.includes(targetState)
          ? progress.steps
          : [...progress.steps, targetState];

        return {
          ...prev,
          [serviceId]: {
            ...progress,
            currentState: targetState,
            steps: nextSteps,
          },
        };
      });

      setTimeout(() => {
        setActionProgress((prev) => {
          if (!prev[serviceId]) return prev;
          const next = { ...prev };
          delete next[serviceId];
          return next;
        });
      }, 1200);
    } catch (err) {
      console.error('Service action failed:', err);
      setActionProgress((prev) => {
        const progress = prev[serviceId];
        if (!progress) return prev;
        const nextSteps = progress.steps.includes('failed')
          ? progress.steps
          : [...progress.steps, 'failed'];
        return {
          ...prev,
          [serviceId]: {
            ...progress,
            currentState: 'failed',
            steps: nextSteps,
          },
        };
      });
      setTimeout(() => {
        setActionProgress((prev) => {
          if (!prev[serviceId]) return prev;
          const next = { ...prev };
          delete next[serviceId];
          return next;
        });
      }, 4000);
      loadServices({ silent: true });
      alert(`Action failed: ${err.response?.data?.detail || err.message}`);
    }
  };

  const counts = {
    all: services.length,
    systemd: services.filter(s => s.provider === 'systemd').length,
    running: services.filter(s => s.state === 'running').length,
    stopped: services.filter(s => s.state === 'stopped').length,
  };

  const filterOptions = [
    { label: 'All', value: 'all', count: counts.all, color: 'purple' },
    { label: 'Systemd', value: 'systemd', count: counts.systemd, color: 'gray' },
    { label: 'Running', value: 'running', count: counts.running, color: 'green' },
    { label: 'Stopped', value: 'stopped', count: counts.stopped, color: 'red' },
  ].filter(opt => !opt.hidden);

  const filteredServices = services.filter(s => {
    const matchesSearch = s.name.toLowerCase().includes(searchTerm.toLowerCase());
    if (!matchesSearch) return false;

    if (actionProgress[s.id]) {
      return true;
    }

    const matchesFilter = activeFilter === 'all' ||
      (activeFilter === 'running' && s.state === 'running') ||
      (activeFilter === 'stopped' && s.state === 'stopped') ||
      (activeFilter === 'systemd' && s.provider === 'systemd');
    return matchesFilter;
  });

  const getStatusIcon = (state) => {
    switch (state) {
      case 'running': return <CheckCircle2 size={16} className="text-green-500" />;
      case 'failed': return <XCircle size={16} className="text-red-500" />;
      case 'starting': return <RefreshCw size={16} className="text-blue-500 animate-spin" />;
      case 'stopping': return <RefreshCw size={16} className="text-amber-500 animate-spin" />;
      case 'restarting': return <RefreshCw size={16} className="text-purple-500 animate-spin" />;
      case 'stopped': return <Info size={16} className="text-gray-500" />;
      default: return <Activity size={16} className="text-blue-500" />;
    }
  };

  const getStateStyles = (state) => {
    switch (state) {
      case 'running':
        return isDarkMode ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-green-100 text-green-700 border-green-200';
      case 'starting':
        return isDarkMode ? 'bg-blue-500/20 text-blue-300 border-blue-500/30' : 'bg-blue-100 text-blue-700 border-blue-200';
      case 'stopping':
        return isDarkMode ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'bg-amber-100 text-amber-700 border-amber-200';
      case 'restarting':
        return isDarkMode ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'bg-purple-100 text-purple-700 border-purple-200';
      case 'failed':
        return isDarkMode ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-red-100 text-red-700 border-red-200';
      default:
        return isDarkMode ? 'bg-gray-500/20 text-gray-400 border-gray-500/30' : 'bg-gray-100 text-gray-600 border-gray-200';
    }
  };

  const getActionPermissions = (service, serviceState = service.state) => {
    const canManage = isOperator;
    const isCore = service.resource_class === 'CORE';
    const isSystem = service.resource_class === 'SYSTEM';
    const isApp = service.resource_class === 'APP';

    const canRestart = canManage && !isCore;
    const canStartStop = canManage && isApp && !isSystem;

    return {
      canRestart,
      canStartStop,
      canStart: canStartStop && !['running', 'starting', 'restarting', 'stopping'].includes(serviceState),
      canStop: canStartStop && serviceState === 'running',
    };
  };

  const formatStateLabel = (state) => {
    switch (state) {
      case 'running': return 'WORKING';
      case 'stopped': return 'STOPPED';
      case 'starting': return 'STARTING';
      case 'stopping': return 'STOPPING';
      case 'restarting': return 'RESTARTING';
      case 'failed': return 'FAILED';
      default: return (state || 'unknown').toUpperCase();
    }
  };

  const getTransitionProgressValue = (progress) => {
    if (!progress) return 0;

    if (progress.currentState === 'failed') return 100;
    if (progress.currentState === progress.targetState) return 100;

    if (progress.currentState === 'starting') return 60;
    if (progress.currentState === 'stopping') return 60;
    if (progress.currentState === 'restarting') return 60;

    return 20;
  };

  const getTransitionProgressStyles = (progress) => {
    if (!progress) {
      return {
        track: isDarkMode ? 'bg-white/10' : 'bg-gray-200',
        fill: isDarkMode ? 'bg-blue-400' : 'bg-blue-500',
      };
    }

    if (progress.currentState === 'failed') {
      return {
        track: isDarkMode ? 'bg-red-500/20' : 'bg-red-100',
        fill: isDarkMode ? 'bg-red-400' : 'bg-red-500',
      };
    }

    if (progress.currentState === progress.targetState) {
      return {
        track: isDarkMode ? 'bg-green-500/20' : 'bg-green-100',
        fill: isDarkMode ? 'bg-green-400' : 'bg-green-500',
      };
    }

    if (progress.currentState === 'stopping') {
      return {
        track: isDarkMode ? 'bg-amber-500/20' : 'bg-amber-100',
        fill: isDarkMode ? 'bg-amber-400' : 'bg-amber-500',
      };
    }

    if (progress.currentState === 'restarting') {
      return {
        track: isDarkMode ? 'bg-purple-500/20' : 'bg-purple-100',
        fill: isDarkMode ? 'bg-purple-400' : 'bg-purple-500',
      };
    }

    return {
      track: isDarkMode ? 'bg-blue-500/20' : 'bg-blue-100',
      fill: isDarkMode ? 'bg-blue-400' : 'bg-blue-500',
    };
  };

  const getCapabilityBadgeStyles = (isUnlocked) => {
    if (isUnlocked) {
      return isDarkMode
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
        : 'bg-emerald-50 border-emerald-200 text-emerald-700';
    }
    return isDarkMode
      ? 'bg-zinc-500/10 border-zinc-500/30 text-zinc-400'
      : 'bg-zinc-100 border-zinc-200 text-zinc-600';
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
            Monitor and control system daemons
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
            {filteredServices.map((service, index) => {
              const progress = actionProgress[service.id];
              const displayState = progress?.currentState || service.state;
              const isTransitioning = Boolean(progress);
              const permissions = getActionPermissions(service, displayState);
              const transitionProgressValue = getTransitionProgressValue(progress);
              const transitionProgressStyles = getTransitionProgressStyles(progress);
              return (
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
                  <div className={`absolute -right-4 -top-4 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity ${service.provider === 'systemd' ? 'text-blue-500' : 'text-gray-500'}`}>
                    {service.provider === 'systemd' ? <Package size={120} /> : <Terminal size={120} />}
                  </div>

                  <div className="relative z-10">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-lg ${service.resource_class === 'CORE' ? 'bg-red-500/10 text-red-500' : service.resource_class === 'SYSTEM' ? 'bg-blue-500/10 text-blue-500' : 'bg-purple-500/10 text-purple-500'}`}>
                          {service.provider === 'systemd' ? <Package size={24} /> : <Terminal size={24} />}
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
                            <span className={`text-[10px] font-bold uppercase tracking-widest ${service.provider === 'systemd' ? 'text-blue-500' : 'text-purple-500'}`}>
                              {service.provider}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[10px] font-semibold uppercase tracking-wide ${getCapabilityBadgeStyles(permissions.canStartStop)}`}>
                              {permissions.canStartStop ? <Unlock size={10} /> : <Lock size={10} />}
                              Start/Stop
                            </span>
                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[10px] font-semibold uppercase tracking-wide ${getCapabilityBadgeStyles(permissions.canRestart)}`}>
                              {permissions.canRestart ? <Unlock size={10} /> : <Lock size={10} />}
                              Restart
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${getStateStyles(displayState)}`}>
                        {getStatusIcon(displayState)}
                        {formatStateLabel(displayState)}
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

                    {progress && (
                      <div className={`mb-4 p-3 rounded-xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'}`}>
                        <div className={`text-[10px] font-bold uppercase tracking-wider ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                          Live Transition
                        </div>
                        <div className={`mt-1 text-[11px] font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {progress.steps.map(formatStateLabel).join(' -> ')}
                        </div>
                        <div className={`mt-2 h-1.5 w-full rounded-full overflow-hidden ${transitionProgressStyles.track}`}>
                          <motion.div
                            className={`h-full rounded-full ${transitionProgressStyles.fill} ${isTransitioning ? 'animate-pulse' : ''}`}
                            initial={false}
                            animate={{ width: `${transitionProgressValue}%` }}
                            transition={{ duration: 0.35, ease: 'easeOut' }}
                          />
                        </div>
                        <div className={`mt-1 flex items-center justify-between text-[9px] font-semibold ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                          <span>{progress.action.toUpperCase()}</span>
                          <span>{transitionProgressValue}%</span>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    {isOperator && (permissions.canRestart || permissions.canStartStop) && (
                      <div className="flex gap-2">
                        {isTransitioning ? (
                          <button
                            disabled
                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold border cursor-not-allowed ${isDarkMode ? 'bg-white/5 border-white/10 text-gray-300' : 'bg-gray-100 border-gray-200 text-gray-600'}`}
                          >
                            <RefreshCw size={14} className="animate-spin" />
                            {formatStateLabel(displayState)}
                          </button>
                        ) : (
                          <>
                            {permissions.canRestart && displayState === 'running' && (
                              <button
                                onClick={() => handleAction(service, 'restart')}
                                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400 hover:bg-purple-500/30' : 'bg-purple-50 border-purple-200 text-purple-600 hover:bg-purple-100'} border`}
                              >
                                <RotateCcw size={14} /> RESTART
                              </button>
                            )}
                            {permissions.canStop && (
                              <button
                                onClick={() => handleAction(service, 'stop')}
                                className={`px-3 py-2 rounded-xl border transition-all ${isDarkMode ? 'bg-red-500/10 border-red-500/30 text-red-500 hover:bg-red-500/20' : 'bg-red-50 border-red-200 text-red-600 hover:bg-red-100'}`}
                              >
                                <Square size={14} fill="currentColor" />
                              </button>
                            )}
                            {permissions.canStart && (
                              <button
                                onClick={() => handleAction(service, 'start')}
                                className={`hover:scale-[1.02] active:scale-95 flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${isDarkMode ? 'bg-green-500/20 border-green-500/50 text-green-400 hover:bg-green-500/30' : 'bg-green-100 border-green-200 text-green-700 hover:bg-green-200'} border shadow-lg shadow-green-500/10`}
                              >
                                <Play size={14} fill="currentColor" /> START
                              </button>
                            )}
                          </>
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
              );
            })}
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
              : "No services have been discovered yet. Try refreshing the page."}
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
