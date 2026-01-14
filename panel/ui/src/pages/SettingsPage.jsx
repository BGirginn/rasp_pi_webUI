import { motion } from 'motion/react';
import { useState } from 'react';
import { User, Shield, Users, Plus, Edit, Trash2, Eye, EyeOff } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'viewer' });
  const [showAddUser, setShowAddUser] = useState(false);
  const [showAddUserPassword, setShowAddUserPassword] = useState(false);

  const { theme, isDarkMode } = useTheme();
  const { user, isAdmin } = useAuth();
  const themeColors = getThemeColors(theme);

  // Fetch users when tab changes to 'users'
  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const response = await api.get('/auth/users');
      setUsers(response.data);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const handleAddUser = async () => {
    try {
      await api.post('/auth/users', newUser);
      setNewUser({ username: '', password: '', role: 'viewer' });
      setShowAddUser(false);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!confirm('Are you sure you want to delete this user?')) return;
    try {
      await api.delete(`/auth/users/${userId}`);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    ...(isAdmin ? [
      { id: 'security', label: 'Security', icon: Shield },
      { id: 'users', label: 'Users', icon: Users },
    ] : []),
  ];

  return (
    <div>
      <h1 className={`text-4xl mb-8 bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
        Settings
      </h1>

      {/* Tabs */}
      <div className="flex gap-3 mb-8">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <motion.button
              key={tab.id}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => { setActiveTab(tab.id); if (tab.id === 'users') loadUsers(); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm border transition-all ${activeTab === tab.id
                ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
                : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                }`}
            >
              <Icon size={16} />
              {tab.label}
            </motion.button>
          );
        })}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
            <h3 className={`text-lg mb-6 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              Profile
            </h3>

            <div className="space-y-6">
              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Username
                </label>
                <div className={`px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white' : 'bg-gray-50 text-gray-900'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                  {user?.username}
                </div>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Role
                </label>
                <div className={`px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                  <span className={`px-2 py-1 rounded ${isDarkMode ? 'bg-purple-500/20 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                    {user?.role}
                  </span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Email
                  </label>
                  <button className={`text-xs flex items-center gap-1 ${isDarkMode ? 'text-purple-400 hover:text-purple-300' : 'text-purple-600 hover:text-purple-700'}`}>
                    <Edit size={12} />
                    Edit
                  </button>
                </div>
                <div className={`px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-gray-400' : 'bg-gray-50 text-gray-500'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                  Not set
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
            <h3 className={`text-lg mb-6 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              🔑 Change Password
            </h3>

            <div className="space-y-4">
              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Current Password
                </label>
                <div className="relative">
                  <input
                    type={showCurrentPassword ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`}
                    placeholder="Enter current password"
                    style={{ paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-purple-500 transition-colors focus:outline-none"
                  >
                    {showCurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`}
                    placeholder="Enter new password"
                    style={{ paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-purple-500 transition-colors focus:outline-none"
                  >
                    {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Confirm New Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`}
                    placeholder="Confirm new password"
                    style={{ paddingRight: '40px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-purple-500 transition-colors focus:outline-none"
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className={`w-full px-6 py-3 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-500 border-purple-600 text-white'} border mt-4`}>
                Change Password
              </motion.button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
            <h3 className={`text-lg mb-4 flex items-center gap-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              <Shield size={20} />
              Two-Factor Authentication
            </h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-6`}>
              Add an extra layer of security to your account by enabling two-factor authentication.
            </p>
            <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className={`px-6 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-500 border-purple-600 text-white'} border`}>
              Enable 2FA
            </motion.button>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
            <h3 className={`text-lg mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              Active Sessions
            </h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              No active sessions
            </p>
          </motion.div>
        </div>
      )}

      {/* Users Tab */}
      {activeTab === 'users' && isAdmin && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
          <div className="flex items-center justify-between mb-6">
            <h3 className={`text-lg flex items-center gap-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              <Users size={20} />
              User Management
            </h3>
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setShowAddUser(!showAddUser)} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-500 border-purple-600 text-white'} border`}>
              <Plus size={18} />
              {showAddUser ? 'Cancel' : 'Add User'}
            </motion.button>
          </div>

          {/* Add User Form */}
          {showAddUser && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} className="mb-6 overflow-hidden">
              <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'} space-y-4`}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <input
                    type="text"
                    placeholder="Username"
                    value={newUser.username}
                    onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                    className={`px-4 py-2 rounded-lg border ${isDarkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-gray-300'} focus:outline-none focus:border-purple-500`}
                  />
                  <div className="relative">
                    <input
                      type={showAddUserPassword ? "text" : "password"}
                      placeholder="Password"
                      value={newUser.password}
                      onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                      className={`w-full px-4 py-2 rounded-lg border ${isDarkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-gray-300'} focus:outline-none focus:border-purple-500`}
                      style={{ paddingRight: '35px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowAddUserPassword(!showAddUserPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-purple-500 transition-colors focus:outline-none"
                    >
                      {showAddUserPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <select
                    value={newUser.role}
                    onChange={e => setNewUser({ ...newUser, role: e.target.value })}
                    className={`px-4 py-2 rounded-lg border ${isDarkMode ? 'bg-black/20 border-white/10 text-white' : 'bg-white border-gray-300'} focus:outline-none focus:border-purple-500`}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="operator">Operator</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <button
                  onClick={handleAddUser}
                  disabled={!newUser.username || !newUser.password}
                  className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create User
                </button>
              </div>
            </motion.div>
          )}

          <div className="space-y-3">
            {users.map(u => (
              <div key={u.id} className={`flex items-center justify-between p-4 rounded-xl border ${isDarkMode ? 'bg-white/5 border-white/10' : 'bg-gray-50 border-gray-200'}`}>
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isDarkMode ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                    <User size={20} />
                  </div>
                  <div>
                    <div className={`font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{u.username}</div>
                    <div className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'} uppercase tracking-wider`}>{u.role}</div>
                  </div>
                </div>
                {u.username !== 'admin' && u.id !== user.id && (
                  <button
                    onClick={() => handleDeleteUser(u.id)}
                    className="p-2 text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                    title="Delete User"
                  >
                    <Trash2 size={18} />
                  </button>
                )}
              </div>
            ))}
            {users.length === 0 && !loadingUsers && (
              <div className={`text-center py-16 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                <Users size={48} className="mx-auto mb-4 opacity-50" />
                <p>No users found</p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
