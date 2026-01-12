import { motion } from 'motion/react';
import { useState } from 'react';
import { User, Shield, Users, Plus, Edit } from 'lucide-react';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
export function SettingsPage() {
    const [activeTab, setActiveTab] = useState('profile');
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    const tabs = [
        { id: 'profile', label: 'Profile', icon: User },
        { id: 'security', label: 'Security', icon: Shield },
        { id: 'users', label: 'Users', icon: Users },
    ];
    return (<div>
      <h1 className={`text-4xl mb-8 bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
        Settings
      </h1>

      {/* Tabs */}
      <div className="flex gap-3 mb-8">
        {tabs.map((tab) => {
            const Icon = tab.icon;
            return (<motion.button key={tab.id} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={() => setActiveTab(tab.id)} className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm border transition-all ${activeTab === tab.id
                    ? isDarkMode ? 'bg-purple-500/30 border-purple-500 text-purple-300' : 'bg-purple-100 border-purple-500 text-purple-700'
                    : isDarkMode ? 'bg-white/5 border-white/10 text-gray-400 hover:border-white/30' : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'}`}>
              <Icon size={16}/>
              {tab.label}
            </motion.button>);
        })}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  admin
                </div>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Role
                </label>
                <div className={`px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5' : 'bg-gray-50'} border ${isDarkMode ? 'border-white/10' : 'border-gray-200'}`}>
                  <span className={`px-2 py-1 rounded ${isDarkMode ? 'bg-purple-500/20 text-purple-300' : 'bg-purple-100 text-purple-700'}`}>
                    admin
                  </span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    Email
                  </label>
                  <button className={`text-xs flex items-center gap-1 ${isDarkMode ? 'text-purple-400 hover:text-purple-300' : 'text-purple-600 hover:text-purple-700'}`}>
                    <Edit size={12}/>
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
                <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`} placeholder="Enter current password"/>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  New Password
                </label>
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`} placeholder="Enter new password"/>
              </div>

              <div>
                <label className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} block mb-2`}>
                  Confirm New Password
                </label>
                <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className={`w-full px-4 py-3 rounded-lg ${isDarkMode ? 'bg-white/5 text-white border-white/10' : 'bg-white text-gray-900 border-gray-300'} border focus:outline-none focus:border-purple-500`} placeholder="Confirm new password"/>
              </div>

              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className={`w-full px-6 py-3 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-500 border-purple-600 text-white'} border mt-4`}>
                Change Password
              </motion.button>
            </div>
          </motion.div>
        </div>)}

      {/* Security Tab */}
      {activeTab === 'security' && (<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
            <h3 className={`text-lg mb-4 flex items-center gap-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              <Shield size={20}/>
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
        </div>)}

      {/* Users Tab */}
      {activeTab === 'users' && (<motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className={`${isDarkMode ? 'bg-black/40' : 'bg-white'} backdrop-blur-xl rounded-2xl p-6 border ${isDarkMode ? 'border-white/10' : 'border-gray-300'}`}>
          <div className="flex items-center justify-between mb-6">
            <h3 className={`text-lg flex items-center gap-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              <Users size={20}/>
              User Management
            </h3>
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className={`flex items-center gap-2 px-4 py-2 rounded-lg ${isDarkMode ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-purple-500 border-purple-600 text-white'} border`}>
              <Plus size={18}/>
              Add User
            </motion.button>
          </div>

          <div className={`text-center py-16 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            <Users size={48} className="mx-auto mb-4 opacity-50"/>
            <p>No users to display</p>
          </div>
        </motion.div>)}
    </div>);
}
