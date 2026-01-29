import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Store, 
  Search, 
  Download, 
  Trash2, 
  Play, 
  Square, 
  RefreshCw, 
  ExternalLink,
  Cpu,
  HardDrive,
  Activity,
  Shield,
  Home,
  PlayCircle,
  Code,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronRight,
  Terminal,
  Settings,
  X
} from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { api } from '../services/api';

// Category icon mapping
const categoryIcons = {
  'media': PlayCircle,
  'network': Shield,
  'home': Home,
  'storage': HardDrive,
  'monitoring': Activity,
  'development': Code,
};

// Status badge component
function StatusBadge({ status }) {
  const statusConfig = {
    'running': { color: 'bg-green-500', text: 'Running', icon: CheckCircle },
    'stopped': { color: 'bg-gray-500', text: 'Stopped', icon: Square },
    'installing': { color: 'bg-blue-500', text: 'Installing', icon: Loader2, animate: true },
    'error': { color: 'bg-red-500', text: 'Error', icon: XCircle },
    'not_installed': { color: 'bg-gray-400', text: 'Not Installed', icon: null },
  };
  
  const config = statusConfig[status] || statusConfig['not_installed'];
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium text-white ${config.color}`}>
      {Icon && <Icon size={12} className={config.animate ? 'animate-spin' : ''} />}
      {config.text}
    </span>
  );
}

// App Card Component
function AppCard({ app, onInstall, onUninstall, onStart, onStop, onRestart, onViewDetails, isDarkMode, themeColors }) {
  const [isHovered, setIsHovered] = useState(false);
  const CategoryIcon = categoryIcons[app.category] || Store;
  
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      whileHover={{ scale: 1.02 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className={`relative rounded-xl overflow-hidden ${
        isDarkMode ? 'bg-white/5 border-white/10' : 'bg-white border-gray-200'
      } border p-5 cursor-pointer transition-all hover:shadow-lg`}
      onClick={() => onViewDetails(app)}
    >
      {/* App Header */}
      <div className="flex items-start gap-4 mb-4">
        {/* Logo */}
        <div className={`w-16 h-16 rounded-xl flex items-center justify-center overflow-hidden ${
          isDarkMode ? 'bg-white/10' : 'bg-gray-100'
        }`}>
          {app.logo ? (
            <img 
              src={app.logo} 
              alt={app.name} 
              className="w-12 h-12 object-contain"
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.parentElement.innerHTML = `<div class="text-2xl">${app.name.charAt(0)}</div>`;
              }}
            />
          ) : (
            <CategoryIcon size={32} className={isDarkMode ? 'text-gray-400' : 'text-gray-500'} />
          )}
        </div>
        
        {/* App Info */}
        <div className="flex-1 min-w-0">
          <h3 className={`font-semibold text-lg ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            {app.name}
          </h3>
          <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'} line-clamp-2`}>
            {app.description}
          </p>
        </div>
        
        {/* Status */}
        <StatusBadge status={app.status} />
      </div>
      
      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-4">
        {app.tags?.slice(0, 3).map((tag) => (
          <span 
            key={tag}
            className={`px-2 py-1 rounded text-xs ${
              isDarkMode ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {tag}
          </span>
        ))}
      </div>
      
      {/* Actions */}
      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
        {app.installed && app.status === 'running' ? (
          <>
            <button
              onClick={() => onStop(app.id)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
            >
              <Square size={16} />
              Stop
            </button>
            <button
              onClick={() => onRestart(app.id)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors"
            >
              <RefreshCw size={16} />
              Restart
            </button>
            {app.web_url && (
              <a
                href={app.web_url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 rounded-lg bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors"
              >
                <ExternalLink size={16} />
              </a>
            )}
          </>
        ) : app.installed && app.status === 'stopped' ? (
          <>
            <button
              onClick={() => onStart(app.id)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors"
            >
              <Play size={16} />
              Start
            </button>
            <button
              onClick={() => onUninstall(app.id)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
            >
              <Trash2 size={16} />
              Uninstall
            </button>
          </>
        ) : (
          <button
            onClick={() => onInstall(app.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 transition-opacity`}
          >
            <Download size={16} />
            Install
          </button>
        )}
      </div>
    </motion.div>
  );
}

// App Detail Modal
function AppDetailModal({ app, onClose, onInstall, onUninstall, onStart, onStop, onRestart, isDarkMode, themeColors }) {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  
  const fetchLogs = useCallback(async () => {
    if (!app.installed) return;
    try {
      const { data } = await api.get(`/appstore/logs/${app.id}?tail=50`);
      setLogs(data.logs || []);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  }, [app.id, app.installed]);
  
  const fetchStats = useCallback(async () => {
    if (!app.installed || app.status !== 'running') return;
    try {
      const { data } = await api.get(`/appstore/stats/${app.id}`);
      setStats(data.stats);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, [app.id, app.installed, app.status]);
  
  useEffect(() => {
    if (activeTab === 'logs') fetchLogs();
    if (activeTab === 'stats') fetchStats();
  }, [activeTab, fetchLogs, fetchStats]);
  
  // Auto-refresh stats
  useEffect(() => {
    if (activeTab !== 'stats' || !app.installed) return;
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [activeTab, app.installed, fetchStats]);
  
  const CategoryIcon = categoryIcons[app.category] || Store;
  
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className={`w-full max-w-3xl max-h-[90vh] rounded-2xl overflow-hidden ${
          isDarkMode ? 'bg-gray-900 border-white/10' : 'bg-white border-gray-200'
        } border shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`p-6 border-b ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
          <div className="flex items-start gap-4">
            <div className={`w-20 h-20 rounded-xl flex items-center justify-center overflow-hidden ${
              isDarkMode ? 'bg-white/10' : 'bg-gray-100'
            }`}>
              {app.logo ? (
                <img src={app.logo} alt={app.name} className="w-16 h-16 object-contain" />
              ) : (
                <CategoryIcon size={40} className={isDarkMode ? 'text-gray-400' : 'text-gray-500'} />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h2 className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {app.name}
                </h2>
                <StatusBadge status={app.status} />
              </div>
              <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                {app.description}
              </p>
              <div className="flex items-center gap-4 mt-2">
                <a 
                  href={app.website} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className={`text-sm flex items-center gap-1 ${isDarkMode ? 'text-blue-400' : 'text-blue-600'} hover:underline`}
                >
                  Website <ExternalLink size={14} />
                </a>
                <a 
                  href={app.documentation} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className={`text-sm flex items-center gap-1 ${isDarkMode ? 'text-blue-400' : 'text-blue-600'} hover:underline`}
                >
                  Documentation <ExternalLink size={14} />
                </a>
              </div>
            </div>
            <button
              onClick={onClose}
              className={`p-2 rounded-lg ${isDarkMode ? 'hover:bg-white/10' : 'hover:bg-gray-100'} transition-colors`}
            >
              <X size={20} />
            </button>
          </div>
        </div>
        
        {/* Tabs */}
        <div className={`flex border-b ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
          {['overview', 'ports', app.installed && 'logs', app.installed && 'stats'].filter(Boolean).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 text-sm font-medium capitalize transition-colors ${
                activeTab === tab
                  ? isDarkMode 
                    ? 'text-white border-b-2 border-purple-500' 
                    : 'text-purple-600 border-b-2 border-purple-500'
                  : isDarkMode 
                    ? 'text-gray-400 hover:text-white' 
                    : 'text-gray-500 hover:text-gray-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        
        {/* Content */}
        <div className="p-6 max-h-[50vh] overflow-y-auto">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div>
                <h3 className={`font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  About
                </h3>
                <p className={`${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                  {app.long_description || app.description}
                </p>
              </div>
              
              <div>
                <h3 className={`font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  Requirements
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                    <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>Min Memory</div>
                    <div className={`font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {app.min_memory_mb || 128} MB
                    </div>
                  </div>
                  <div className={`p-3 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                    <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>Recommended</div>
                    <div className={`font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {app.recommended_memory_mb || 256} MB
                    </div>
                  </div>
                </div>
              </div>
              
              <div>
                <h3 className={`font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  Docker Image
                </h3>
                <code className={`block p-3 rounded-lg text-sm ${
                  isDarkMode ? 'bg-white/5 text-green-400' : 'bg-gray-100 text-green-600'
                }`}>
                  {app.image}
                </code>
              </div>
              
              <div>
                <h3 className={`font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  Tags
                </h3>
                <div className="flex flex-wrap gap-2">
                  {app.tags?.map((tag) => (
                    <span 
                      key={tag}
                      className={`px-3 py-1 rounded-full text-sm ${
                        isDarkMode ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
          
          {activeTab === 'ports' && (
            <div className="space-y-4">
              <h3 className={`font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Port Mappings
              </h3>
              <div className={`rounded-lg overflow-hidden border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                <table className="w-full">
                  <thead className={isDarkMode ? 'bg-white/5' : 'bg-gray-50'}>
                    <tr>
                      <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Host Port</th>
                      <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Container Port</th>
                      <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Protocol</th>
                      <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {app.ports?.map((port, idx) => (
                      <tr key={idx} className={isDarkMode ? 'border-t border-white/5' : 'border-t border-gray-100'}>
                        <td className={`px-4 py-3 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{port.host}</td>
                        <td className={`px-4 py-3 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{port.container}</td>
                        <td className={`px-4 py-3 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{port.protocol || 'tcp'}</td>
                        <td className={`px-4 py-3 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{port.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {app.volumes?.length > 0 && (
                <>
                  <h3 className={`font-semibold mt-6 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                    Volumes
                  </h3>
                  <div className={`rounded-lg overflow-hidden border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                    <table className="w-full">
                      <thead className={isDarkMode ? 'bg-white/5' : 'bg-gray-50'}>
                        <tr>
                          <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Host Path</th>
                          <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Container Path</th>
                          <th className={`px-4 py-3 text-left text-sm font-medium ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {app.volumes?.map((vol, idx) => (
                          <tr key={idx} className={isDarkMode ? 'border-t border-white/5' : 'border-t border-gray-100'}>
                            <td className={`px-4 py-3 font-mono text-sm ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>{vol.host}</td>
                            <td className={`px-4 py-3 font-mono text-sm ${isDarkMode ? 'text-blue-400' : 'text-blue-600'}`}>{vol.container}</td>
                            <td className={`px-4 py-3 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>{vol.description}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}
          
          {activeTab === 'logs' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className={`font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  Container Logs
                </h3>
                <button
                  onClick={fetchLogs}
                  className={`p-2 rounded-lg ${isDarkMode ? 'hover:bg-white/10' : 'hover:bg-gray-100'} transition-colors`}
                >
                  <RefreshCw size={16} />
                </button>
              </div>
              <div className={`rounded-lg p-4 font-mono text-sm h-80 overflow-y-auto ${
                isDarkMode ? 'bg-black/50 text-green-400' : 'bg-gray-900 text-green-400'
              }`}>
                {logs.length > 0 ? (
                  logs.map((line, idx) => (
                    <div key={idx} className="whitespace-pre-wrap break-all">
                      {line}
                    </div>
                  ))
                ) : (
                  <div className="text-gray-500">No logs available</div>
                )}
              </div>
            </div>
          )}
          
          {activeTab === 'stats' && (
            <div className="space-y-4">
              <h3 className={`font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Resource Usage
              </h3>
              {stats ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <Cpu size={20} className="text-blue-500" />
                      <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>CPU Usage</span>
                    </div>
                    <div className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {stats.cpu_pct}%
                    </div>
                  </div>
                  <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <Activity size={20} className="text-purple-500" />
                      <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>Memory Usage</span>
                    </div>
                    <div className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {stats.memory_pct.toFixed(1)}%
                    </div>
                    <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      {stats.memory_usage_mb.toFixed(0)} MB / {stats.memory_limit_mb.toFixed(0)} MB
                    </div>
                  </div>
                </div>
              ) : (
                <div className={`text-center py-8 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  {app.status === 'running' ? 'Loading stats...' : 'Container not running'}
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Footer Actions */}
        <div className={`p-6 border-t ${isDarkMode ? 'border-white/10' : 'border-gray-200'} flex justify-end gap-3`}>
          {app.installed && app.status === 'running' ? (
            <>
              <button
                onClick={() => onStop(app.id)}
                className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors flex items-center gap-2"
              >
                <Square size={16} />
                Stop
              </button>
              <button
                onClick={() => onRestart(app.id)}
                className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors flex items-center gap-2"
              >
                <RefreshCw size={16} />
                Restart
              </button>
              {app.web_url && (
                <a
                  href={app.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`px-4 py-2 rounded-lg bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 transition-opacity flex items-center gap-2`}
                >
                  <ExternalLink size={16} />
                  Open App
                </a>
              )}
            </>
          ) : app.installed && app.status === 'stopped' ? (
            <>
              <button
                onClick={() => onUninstall(app.id)}
                className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors flex items-center gap-2"
              >
                <Trash2 size={16} />
                Uninstall
              </button>
              <button
                onClick={() => onStart(app.id)}
                className={`px-4 py-2 rounded-lg bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 transition-opacity flex items-center gap-2`}
              >
                <Play size={16} />
                Start
              </button>
            </>
          ) : (
            <button
              onClick={() => onInstall(app.id)}
              className={`px-4 py-2 rounded-lg bg-gradient-to-r ${themeColors.secondary} text-white hover:opacity-90 transition-opacity flex items-center gap-2`}
            >
              <Download size={16} />
              Install App
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// Main App Store Page
export function AppStorePage() {
  const { theme, isDarkMode } = useTheme();
  const themeColors = getThemeColors(theme);
  
  const [apps, setApps] = useState([]);
  const [categories, setCategories] = useState([]);
  const [installedApps, setInstalledApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [viewMode, setViewMode] = useState('all'); // 'all' or 'installed'
  
  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [appsRes, categoriesRes, installedRes] = await Promise.all([
        api.get('/appstore/apps'),
        api.get('/appstore/categories'),
        api.get('/appstore/installed'),
      ]);
      
      setApps(appsRes.data);
      setCategories(categoriesRes.data);
      setInstalledApps(installedRes.data);
    } catch (err) {
      console.error('Failed to fetch app store data:', err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Filter apps
  const filteredApps = apps.filter((app) => {
    if (viewMode === 'installed' && !app.installed) return false;
    if (selectedCategory && app.category !== selectedCategory) return false;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        app.name.toLowerCase().includes(query) ||
        app.description.toLowerCase().includes(query) ||
        app.tags?.some((tag) => tag.toLowerCase().includes(query))
      );
    }
    return true;
  });
  
  // Actions
  const handleInstall = async (appId) => {
    setActionLoading(appId);
    try {
      await api.post('/appstore/install', { app_id: appId });
      await fetchData();
    } catch (err) {
      console.error('Install failed:', err);
      alert(err.response?.data?.detail || 'Installation failed');
    } finally {
      setActionLoading(null);
    }
  };
  
  const handleUninstall = async (appId) => {
    if (!confirm('Are you sure you want to uninstall this app?')) return;
    setActionLoading(appId);
    try {
      await api.post('/appstore/uninstall', { app_id: appId });
      await fetchData();
      setSelectedApp(null);
    } catch (err) {
      console.error('Uninstall failed:', err);
      alert(err.response?.data?.detail || 'Uninstall failed');
    } finally {
      setActionLoading(null);
    }
  };
  
  const handleStart = async (appId) => {
    setActionLoading(appId);
    try {
      await api.post('/appstore/start', { app_id: appId });
      await fetchData();
    } catch (err) {
      console.error('Start failed:', err);
    } finally {
      setActionLoading(null);
    }
  };
  
  const handleStop = async (appId) => {
    setActionLoading(appId);
    try {
      await api.post('/appstore/stop', { app_id: appId });
      await fetchData();
    } catch (err) {
      console.error('Stop failed:', err);
    } finally {
      setActionLoading(null);
    }
  };
  
  const handleRestart = async (appId) => {
    setActionLoading(appId);
    try {
      await api.post('/appstore/restart', { app_id: appId });
      await fetchData();
    } catch (err) {
      console.error('Restart failed:', err);
    } finally {
      setActionLoading(null);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={40} className="animate-spin text-purple-500" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`text-3xl font-bold bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            App Store
          </h1>
          <p className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>
            Install and manage Docker applications
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className={`p-2 rounded-lg ${isDarkMode ? 'bg-white/10 hover:bg-white/20' : 'bg-gray-100 hover:bg-gray-200'} transition-colors`}
          >
            <RefreshCw size={20} />
          </button>
        </div>
      </div>
      
      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Search apps..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`w-full pl-10 pr-4 py-3 rounded-xl border ${
              isDarkMode 
                ? 'bg-white/5 border-white/10 text-white placeholder-gray-500' 
                : 'bg-white border-gray-200 text-gray-900 placeholder-gray-400'
            } focus:outline-none focus:ring-2 focus:ring-purple-500/50`}
          />
        </div>
        
        {/* View Mode Toggle */}
        <div className={`flex rounded-xl overflow-hidden border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
          <button
            onClick={() => setViewMode('all')}
            className={`px-4 py-3 text-sm font-medium transition-colors ${
              viewMode === 'all'
                ? `bg-gradient-to-r ${themeColors.secondary} text-white`
                : isDarkMode ? 'bg-white/5 text-gray-400 hover:text-white' : 'bg-gray-50 text-gray-600 hover:text-gray-900'
            }`}
          >
            All Apps
          </button>
          <button
            onClick={() => setViewMode('installed')}
            className={`px-4 py-3 text-sm font-medium transition-colors ${
              viewMode === 'installed'
                ? `bg-gradient-to-r ${themeColors.secondary} text-white`
                : isDarkMode ? 'bg-white/5 text-gray-400 hover:text-white' : 'bg-gray-50 text-gray-600 hover:text-gray-900'
            }`}
          >
            Installed ({installedApps.length})
          </button>
        </div>
      </div>
      
      {/* Categories */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
            selectedCategory === null
              ? `bg-gradient-to-r ${themeColors.secondary} text-white`
              : isDarkMode 
                ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          All
        </button>
        {categories.map((category) => {
          const Icon = categoryIcons[category.id] || Store;
          return (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex items-center gap-2 ${
                selectedCategory === category.id
                  ? `bg-gradient-to-r ${themeColors.secondary} text-white`
                  : isDarkMode 
                    ? 'bg-white/10 text-gray-300 hover:bg-white/20' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Icon size={16} />
              {category.name}
            </button>
          );
        })}
      </div>
      
      {/* Apps Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <AnimatePresence mode="popLayout">
          {filteredApps.map((app) => (
            <AppCard
              key={app.id}
              app={app}
              onInstall={handleInstall}
              onUninstall={handleUninstall}
              onStart={handleStart}
              onStop={handleStop}
              onRestart={handleRestart}
              onViewDetails={setSelectedApp}
              isDarkMode={isDarkMode}
              themeColors={themeColors}
            />
          ))}
        </AnimatePresence>
      </div>
      
      {/* Empty State */}
      {filteredApps.length === 0 && (
        <div className={`text-center py-12 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          <Store size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No apps found</p>
          <p className="text-sm">Try adjusting your search or filters</p>
        </div>
      )}
      
      {/* App Detail Modal */}
      <AnimatePresence>
        {selectedApp && (
          <AppDetailModal
            app={selectedApp}
            onClose={() => setSelectedApp(null)}
            onInstall={handleInstall}
            onUninstall={handleUninstall}
            onStart={handleStart}
            onStop={handleStop}
            onRestart={handleRestart}
            isDarkMode={isDarkMode}
            themeColors={themeColors}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
