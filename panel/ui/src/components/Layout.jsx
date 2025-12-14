import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

// Icons (emoji-based for simplicity)
const icons = {
    dashboard: '🏠',
    services: '⚙️',
    devices: '🔌',
    telemetry: '📊',
    jobs: '⏰',
    settings: '🔧',
    logout: '🚪',
    alerts: '🔔',
    user: '👤',
    network: '🌐',
    terminal: '💻',
}

function Sidebar() {
    const { user, logout, isAdmin } = useAuth()
    const navigate = useNavigate()

    const navItems = [
        { path: '/', label: 'Dashboard', icon: icons.dashboard },
        { path: '/services', label: 'Services', icon: icons.services },
        { path: '/devices', label: 'Devices', icon: icons.devices },
        { path: '/telemetry', label: 'Telemetry', icon: icons.telemetry },
        { path: '/network', label: 'Network', icon: icons.network },
        { path: '/terminal', label: 'Terminal', icon: icons.terminal },
        { path: '/alerts', label: 'Alerts', icon: icons.alerts },
    ]

    const handleLogout = async () => {
        await logout()
        navigate('/login')
    }

    return (
        <aside className="w-64 h-screen sticky top-0 bg-dark-200/80 backdrop-blur-xl border-r border-primary-500/10 flex flex-col">
            {/* Logo with glow */}
            <div className="p-6 border-b border-primary-500/10 flex-shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-neon">
                        <span className="text-xl">🥧</span>
                    </div>
                    <div>
                        <h1 className="text-lg font-bold gradient-text">Pi Control</h1>
                        <p className="text-xs text-gray-500">Universal Panel</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        end={item.path === '/'}
                        className={({ isActive }) =>
                            clsx('nav-link', isActive && 'active')
                        }
                    >
                        <span className="text-lg">{item.icon}</span>
                        <span className="font-medium">{item.label}</span>
                    </NavLink>
                ))}

                {isAdmin && (
                    <NavLink
                        to="/settings"
                        className={({ isActive }) =>
                            clsx('nav-link', isActive && 'active')
                        }
                    >
                        <span className="text-lg">{icons.settings}</span>
                        <span className="font-medium">Settings</span>
                    </NavLink>
                )}
            </nav>

            {/* User section */}
            <div className="p-4 border-t border-primary-500/10 flex-shrink-0 bg-dark-200/50">
                <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center">
                        <span className="text-lg">{icons.user}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
                        <p className="text-xs text-primary-400 capitalize">{user?.role}</p>
                    </div>
                </div>
                <button
                    onClick={handleLogout}
                    className="w-full btn btn-ghost text-sm justify-start gap-2 text-gray-400 hover:text-red-400"
                >
                    <span>{icons.logout}</span>
                    <span>Logout</span>
                </button>
            </div>
        </aside>
    )
}

function Header() {
    const navigate = useNavigate()

    return (
        <header className="h-16 bg-dark-200/50 backdrop-blur-xl border-b border-primary-500/10 flex items-center justify-between px-6">
            <div className="flex items-center gap-4">
                {/* Breadcrumb or page title can go here */}
            </div>

            <div className="flex items-center gap-3">
                {/* Quick actions */}
                <button
                    onClick={() => navigate('/alerts')}
                    className="relative p-2.5 rounded-xl bg-dark-100/50 hover:bg-primary-500/10 border border-primary-500/10 transition-all group"
                >
                    <span className="text-lg group-hover:scale-110 transition-transform inline-block">{icons.alerts}</span>
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                </button>

                <button
                    onClick={() => navigate('/terminal')}
                    className="p-2.5 rounded-xl bg-dark-100/50 hover:bg-primary-500/10 border border-primary-500/10 transition-all group"
                >
                    <span className="text-lg group-hover:scale-110 transition-transform inline-block">{icons.terminal}</span>
                </button>
            </div>
        </header>
    )
}

export default function Layout() {
    return (
        <div className="min-h-screen flex bg-dark-300 bg-aurora">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
                <Header />
                <main className="flex-1 p-6 overflow-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
