import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

// Icons (using emoji for now, replace with proper icons)
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
}

function Sidebar() {
    const { user, logout, isAdmin } = useAuth()
    const navigate = useNavigate()

    const navItems = [
        { path: '/', label: 'Dashboard', icon: icons.dashboard },
        { path: '/services', label: 'Services', icon: icons.services },
        { path: '/devices', label: 'Devices', icon: icons.devices },
        { path: '/telemetry', label: 'Telemetry', icon: icons.telemetry },
        { path: '/network', label: 'Network', icon: '🌐' },
        { path: '/terminal', label: 'Terminal', icon: '💻' },
    ]

    const handleLogout = async () => {
        await logout()
        navigate('/login')
    }

    return (
        <aside className="w-64 h-screen sticky top-0 bg-gray-800/50 border-r border-gray-700/50 flex flex-col">
            {/* Logo */}
            <div className="p-4 border-b border-gray-700/50 flex-shrink-0">
                <h1 className="text-xl font-bold gradient-text">Pi Control</h1>
                <p className="text-xs text-gray-500 mt-1">Universal Control Panel</p>
            </div>

            {/* Navigation - scrollable */}
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
                        <span>{item.label}</span>
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
                        <span>Settings</span>
                    </NavLink>
                )}
            </nav>

            {/* User section - always visible */}
            <div className="p-4 border-t border-gray-700/50 flex-shrink-0">
                <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-full bg-primary-600 flex items-center justify-center">
                        <span className="text-lg">{icons.user}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{user?.username}</p>
                        <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
                    </div>
                </div>
                <button
                    onClick={handleLogout}
                    className="w-full btn btn-ghost text-sm justify-start gap-2"
                >
                    <span>{icons.logout}</span>
                    <span>Logout</span>
                </button>
            </div>
        </aside>
    )
}

function Header() {
    return (
        <header className="h-16 bg-gray-800/30 border-b border-gray-700/50 flex items-center justify-between px-6">
            <div className="flex items-center gap-4">
                <h2 className="text-lg font-semibold text-gray-100">Dashboard</h2>
            </div>

            <div className="flex items-center gap-4">
                {/* Alerts indicator */}
                <button className="relative p-2 rounded-lg hover:bg-gray-700/50 transition-colors">
                    <span className="text-xl">{icons.alerts}</span>
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>
            </div>
        </header>
    )
}

export default function Layout() {
    return (
        <div className="min-h-screen flex bg-gray-900">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 overflow-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
