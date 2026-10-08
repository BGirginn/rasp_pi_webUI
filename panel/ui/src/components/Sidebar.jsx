import { motion } from 'motion/react';
import {
  Activity,
  Archive,
  Ban,
  Bell,
  Cpu,
  Database,
  Files,
  FolderKanban,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Monitor,
  Server,
  Settings,
  Terminal,
  Wifi,
} from 'lucide-react';
import { useNavigation } from '../contexts/NavigationContext';
import { useAuth } from '../hooks/useAuth';

const navigationGroups = [
  {
    label: 'Overview',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard', page: 'dashboard' },
      { icon: Activity, label: 'Telemetry', page: 'telemetry' },
      { icon: Bell, label: 'Alerts', page: 'alerts' },
    ],
  },
  {
    label: 'Infrastructure',
    items: [
      { icon: Server, label: 'Services', page: 'services' },
      { icon: Monitor, label: 'Devices', page: 'devices' },
      { icon: Cpu, label: 'IoT', page: 'iot' },
      { icon: Wifi, label: 'Network', page: 'network' },
      { icon: Ban, label: 'AdGuard', page: 'adguard' },
    ],
  },
  {
    label: 'Operations',
    items: [
      { icon: FolderKanban, label: 'Projects', page: 'projects' },
      { icon: ListTodo, label: 'Jobs', page: 'jobs' },
      { icon: Archive, label: 'Archive', page: 'archive' },
      { icon: Terminal, label: 'Terminal', page: 'terminal', restricted: true },
      { icon: Files, label: 'Files', page: 'files', restricted: true },
    ],
  },
];

export function Sidebar() {
  const { currentPage, setCurrentPage } = useNavigation();
  const { user, isAdmin, logout } = useAuth();

  return (
    <motion.aside
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="app-sidebar"
    >
      <div className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true">
          <span>π</span>
          <i />
        </div>
        <div className="min-w-0">
          <div className="brand-name">Pi Control</div>
          <div className="brand-caption">Raspberry operations</div>
        </div>
        <button className="sidebar-mobile-logout" onClick={logout} title="Log out">
          <LogOut size={18} />
        </button>
      </div>

      <nav className="sidebar-navigation" aria-label="Primary navigation">
        {navigationGroups.map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-group-label">{group.label}</div>
            <div className="nav-group-items">
              {group.items
                .filter((item) => !item.restricted || isAdmin)
                .map((item) => {
                  const active = currentPage === item.page;
                  return (
                    <button
                      key={item.page}
                      type="button"
                      className={`nav-item ${active ? 'is-active' : ''}`}
                      onClick={() => setCurrentPage(item.page)}
                      aria-current={active ? 'page' : undefined}
                    >
                      <item.icon size={18} strokeWidth={1.8} />
                      <span>{item.label}</span>
                      {active && <motion.i layoutId="nav-active-dot" />}
                    </button>
                  );
                })}
            </div>
          </div>
        ))}

        <div className="nav-group">
          <div className="nav-group-label">System</div>
          <div className="nav-group-items">
            <button
              type="button"
              className={`nav-item ${currentPage === 'settings' ? 'is-active' : ''}`}
              onClick={() => setCurrentPage('settings')}
            >
              <Settings size={18} strokeWidth={1.8} />
              <span>Settings</span>
              {currentPage === 'settings' && <motion.i layoutId="nav-active-dot" />}
            </button>
          </div>
        </div>
      </nav>

      <div className="sidebar-profile">
        <div className="profile-avatar">{(user?.username || 'A').slice(0, 1).toUpperCase()}</div>
        <div className="profile-copy">
          <strong>{user?.username || 'admin'}</strong>
          <span><i /> Connected</span>
        </div>
        <button type="button" onClick={logout} title="Log out">
          <LogOut size={17} />
        </button>
      </div>
    </motion.aside>
  );
}
