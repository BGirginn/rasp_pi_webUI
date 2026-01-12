import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

// Icons
const icons = {
    dashboard: '◆',
    services: '⚙',
    devices: '⬢',
    telemetry: '◈',
    network: '◎',
    terminal: '▣',
    alerts: '◉',
    settings: '⚡',
    logout: '↗',
    user: '●',
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
        <aside className="w-72 h-screen sticky top-0 bg-[#050507] border-r border-white/[0.03] flex flex-col relative">
            {/* Sidebar glow line */}
            <div className="sidebar-glow"></div>

            {/* Logo */}
            <div className="p-6 border-b border-white/[0.03]">
                <div className="flex items-center gap-4">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center shadow-[0_0_30px_rgba(168,85,247,0.4)]">
                        <span className="text-xl text-white">π</span>
                    </div>
                    <div>
                        <h1 className="text-lg font-bold gradient-text">Pi Control</h1>
                        <p className="text-[11px] text-zinc-600 tracking-wide">UNIVERSAL PANEL</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                <p className="px-4 py-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">Main</p>
                {navItems.slice(0, 4).map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        end={item.path === '/'}
                        className={({ isActive }) =>
                            clsx('nav-link', isActive && 'active')
                        }
                    >
                        <span className="text-sm opacity-70">{item.icon}</span>
                        <span>{item.label}</span>
                    </NavLink>
                ))}

                <p className="px-4 py-2 mt-4 text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">System</p>
                {navItems.slice(4).map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            clsx('nav-link', isActive && 'active')
                        }
                    >
                        <span className="text-sm opacity-70">{item.icon}</span>
                        <span>{item.label}</span>
                    </NavLink>
                ))}

                {isAdmin && (
                    <>
                        <p className="px-4 py-2 mt-4 text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">Admin</p>
                        <NavLink
                            to="/settings"
                            className={({ isActive }) =>
                                clsx('nav-link', isActive && 'active')
                            }
                        >
                            <span className="text-sm opacity-70">{icons.settings}</span>
                            <span>Settings</span>
                        </NavLink>
                    </>
                )}
            </nav>

            {/* User section */}
            <div className="p-4 border-t border-white/[0.03]">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02]">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-600/50 to-pink-600/50 flex items-center justify-center">
                        <span className="text-xs text-purple-300">{icons.user}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">{user?.username}</p>
                        <p className="text-[10px] text-purple-400 uppercase tracking-wider">{user?.role}</p>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="p-2 rounded-lg hover:bg-white/[0.05] text-zinc-500 hover:text-red-400 transition-colors"
                        title="Logout"
                    >
                        <span className="text-sm">{icons.logout}</span>
                    </button>
                </div>
            </div>
        </aside>
    )
}

function Header() {
    const navigate = useNavigate()

    return (
        <header className="h-16 bg-[#050507]/80 backdrop-blur-xl border-b border-white/[0.03] flex items-center justify-between px-6">
            <div className="flex items-center gap-4">
                {/* Breadcrumb placeholder */}
            </div>

            <div className="flex items-center gap-2">
                <button
                    onClick={() => navigate('/alerts')}
                    className="relative p-3 rounded-xl bg-white/[0.02] hover:bg-purple-500/10 border border-white/[0.03] hover:border-purple-500/20 transition-all group"
                >
                    <span className="text-zinc-400 group-hover:text-purple-400 transition-colors">{icons.alerts}</span>
                    <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                </button>

                <button
                    onClick={() => navigate('/terminal')}
                    className="p-3 rounded-xl bg-white/[0.02] hover:bg-purple-500/10 border border-white/[0.03] hover:border-purple-500/20 transition-all group"
                >
                    <span className="text-zinc-400 group-hover:text-purple-400 transition-colors">{icons.terminal}</span>
                </button>
            </div>
        </header>
    )
}

export default function Layout() {
    return (
        <div className="min-h-screen flex bg-black aurora-bg">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
                <Header />
                <main className="flex-1 p-8 overflow-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
