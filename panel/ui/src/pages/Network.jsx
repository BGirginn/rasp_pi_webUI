import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'

// Interface card component
function InterfaceCard({ iface }) {
    const stateColors = {
        up: 'text-green-400 bg-green-500/20',
        down: 'text-red-400 bg-red-500/20',
        unknown: 'text-gray-400 bg-gray-500/20',
    }

    const typeIcons = {
        ethernet: '🔌',
        wifi: '📶',
        bluetooth: '📱',
        loopback: '🔄',
    }

    return (
        <div className="glass-card rounded-xl p-5 animate-slide-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{typeIcons[iface.type] || '🌐'}</span>
                    <div>
                        <h3 className="font-semibold text-gray-100">{iface.name}</h3>
                        <p className="text-sm text-gray-500">{iface.type}</p>
                    </div>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${stateColors[iface.state]}`}>
                    {iface.state}
                </span>
            </div>

            {/* IP Info */}
            <div className="space-y-2 mb-4">
                {iface.ip_address && (
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">IP Address</span>
                        <span className="text-gray-100 font-mono">{iface.ip_address}</span>
                    </div>
                )}
                {iface.mac_address && (
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">MAC</span>
                        <span className="text-gray-100 font-mono text-xs">{iface.mac_address}</span>
                    </div>
                )}
                {iface.gateway && (
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Gateway</span>
                        <span className="text-gray-100 font-mono">{iface.gateway}</span>
                    </div>
                )}
                {iface.speed_mbps && (
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Speed</span>
                        <span className="text-gray-100">{iface.speed_mbps} Mbps</span>
                    </div>
                )}
            </div>

            {/* Traffic */}
            <div className="grid grid-cols-2 gap-4 p-3 bg-gray-800/50 rounded-lg mb-4">
                <div className="text-center">
                    <p className="text-xs text-gray-500">↓ RX</p>
                    <p className="text-sm font-medium text-green-400">
                        {((iface.rx_bytes || 0) / 1024 / 1024 / 1024).toFixed(2)} GB
                    </p>
                </div>
                <div className="text-center">
                    <p className="text-xs text-gray-500">↑ TX</p>
                    <p className="text-sm font-medium text-blue-400">
                        {((iface.tx_bytes || 0) / 1024 / 1024 / 1024).toFixed(2)} GB
                    </p>
                </div>
            </div>

            {/* Actions removed in Action Registry mode */}
        </div>
    )
}

// WiFi network card
function WiFiNetworkCard({ network }) {
    const signalBars = Math.min(4, Math.max(1, Math.ceil(network.signal_quality / 25)))

    return (
        <div className={`glass-card rounded-xl p-4 animate-slide-in ${network.connected ? 'border-l-4 border-green-500' : ''
            }`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                    <div className="flex items-end gap-0.5 h-4">
                        {[1, 2, 3, 4].map((bar) => (
                            <div
                                key={bar}
                                className={`w-1 rounded-sm ${bar <= signalBars ? 'bg-green-400' : 'bg-gray-600'
                                    }`}
                                style={{ height: `${bar * 4}px` }}
                            />
                        ))}
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-100">{network.ssid}</h4>
                        <p className="text-xs text-gray-500">{network.frequency} • {network.security}</p>
                    </div>
                </div>
                {network.connected ? (
                    <span className="text-xs text-green-400 font-medium">Connected</span>
                ) : (
                    <span className="text-xs text-gray-500">Available</span>
                )}
            </div>
            <div className="text-xs text-gray-500">
                {network.signal_strength} dBm • Channel {network.channel}
            </div>
        </div>
    )
}

export default function Network() {
    const { isAdmin } = useAuth()
    const [interfaces, setInterfaces] = useState([])
    const [wifiNetworks, setWifiNetworks] = useState([])
    const [wifiStatus, setWifiStatus] = useState(null)
    const [connectivity, setConnectivity] = useState(null)
    const [loading, setLoading] = useState(true)
    const [scanning, setScanning] = useState(false)
    const [rollbackInfo, setRollbackInfo] = useState(null)
    const [tab, setTab] = useState('interfaces')

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        try {
            const [ifaceRes, connRes] = await Promise.all([
                api.get('/network/interfaces'),
                api.get('/network/connectivity'),
            ])
            setInterfaces(ifaceRes.data)
            setConnectivity(connRes.data)
        } catch (err) {
            console.error('Failed to load network data:', err)
        } finally {
            setLoading(false)
        }
    }

    async function scanWifi() {
        setScanning(true)
        try {
            const [networks, status] = await Promise.all([
                api.get('/network/wifi/networks'),
                api.get('/network/wifi/status'),
            ])
            setWifiNetworks(networks.data)
            setWifiStatus(status.data)
        } catch (err) {
            console.error('Failed to scan WiFi:', err)
        } finally {
            setScanning(false)
        }
    }

    async function toggleWifi(enabled) {
        if (!confirm('Confirm WiFi toggle? This change will auto-rollback if not confirmed.')) {
            return
        }

        try {
            const response = await api.post('/actions/execute', {
                action_id: 'net.toggle_wifi',
                params: { enabled },
                confirm: true,
            })
            if (response.data.rollback) {
                setRollbackInfo(response.data.rollback)
            }
            await scanWifi()
        } catch (err) {
            console.error('Failed to toggle WiFi:', err)
            alert(`Failed: ${err.message}`)
        }
    }

    async function confirmRollback() {
        if (!rollbackInfo?.job_id) return
        try {
            await api.post('/actions/confirm', { rollback_job_id: rollbackInfo.job_id })
            setRollbackInfo(null)
        } catch (err) {
            alert(err.message)
        }
    }

    const wifiInterface = interfaces.find((iface) => iface.type === 'wifi' || iface.name?.startsWith('wlan'))
    const wifiEnabled = wifiInterface?.state === 'up'

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500" />
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold text-gray-100">Network</h2>
                <button onClick={loadData} className="btn btn-secondary">🔄 Refresh</button>
            </div>

            {rollbackInfo && (
                <div className="glass-card rounded-xl p-4 border border-yellow-500/30 bg-yellow-500/10">
                    <p className="text-sm text-yellow-200">
                        If not confirmed within {rollbackInfo.due_in_seconds}s, this change will rollback.
                    </p>
                    <button onClick={confirmRollback} className="btn btn-secondary mt-3">
                        Confirm Change
                    </button>
                </div>
            )}

            {/* Connectivity Status */}
            {connectivity && (
                <div className="glass-card rounded-xl p-4">
                    <h3 className="text-sm font-medium text-gray-400 mb-3">Connectivity Status</h3>
                    <div className="flex flex-wrap gap-4">
                        <div className="flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${connectivity.lan ? 'bg-green-400' : 'bg-red-400'}`} />
                            <span className="text-sm text-gray-300">LAN</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${connectivity.internet ? 'bg-green-400' : 'bg-red-400'}`} />
                            <span className="text-sm text-gray-300">Internet</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${connectivity.dns ? 'bg-green-400' : 'bg-red-400'}`} />
                            <span className="text-sm text-gray-300">DNS</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${connectivity.tailscale ? 'bg-green-400' : 'bg-yellow-400'}`} />
                            <span className="text-sm text-gray-300">Tailscale</span>
                        </div>
                        {connectivity.latency_ms && (
                            <span className="text-sm text-gray-500">
                                Latency: {connectivity.latency_ms}ms
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2">
                <button
                    onClick={() => setTab('interfaces')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${tab === 'interfaces' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400'
                        }`}
                >
                    🔌 Interfaces
                </button>
                <button
                    onClick={() => { setTab('wifi'); scanWifi() }}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${tab === 'wifi' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400'
                        }`}
                >
                    📶 WiFi
                </button>
            </div>

            {/* Content */}
            {tab === 'interfaces' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {interfaces.map((iface) => (
                        <InterfaceCard
                            key={iface.name}
                            iface={iface}
                        />
                    ))}
                </div>
            ) : (
                <div className="space-y-4">
                    {/* WiFi Status */}
                    {wifiStatus?.connected && (
                        <div className="glass-card rounded-xl p-4 border-l-4 border-green-500">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-500">Currently connected to</p>
                                    <p className="text-lg font-semibold text-gray-100">{wifiStatus.ssid}</p>
                                    <p className="text-xs text-gray-500">
                                        {wifiStatus.ip_address} • {wifiStatus.frequency} • {wifiStatus.signal_quality}%
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {isAdmin && (
                        <div className="glass-card rounded-xl p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-500">WiFi</p>
                                    <p className="text-sm text-gray-300">
                                        {wifiEnabled ? 'Enabled' : 'Disabled'}
                                    </p>
                                </div>
                                <button
                                    onClick={() => toggleWifi(!wifiEnabled)}
                                    className={wifiEnabled ? 'btn btn-danger' : 'btn btn-primary'}
                                >
                                    {wifiEnabled ? 'Disable' : 'Enable'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Scan Button */}
                    <div className="flex gap-3">
                        <button
                            onClick={scanWifi}
                            disabled={scanning}
                            className="btn btn-secondary"
                        >
                            {scanning ? '🔄 Scanning...' : '📡 Scan Networks'}
                        </button>
                    </div>

                    {/* Networks List */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {wifiNetworks.map((network) => (
                            <WiFiNetworkCard
                                key={network.bssid}
                                network={network}
                            />
                        ))}
                    </div>

                    {wifiNetworks.length === 0 && !scanning && (
                        <div className="glass-card rounded-xl p-8 text-center">
                            <span className="text-5xl mb-4 block">📶</span>
                            <h3 className="text-xl font-semibold text-gray-100 mb-2">No networks found</h3>
                            <p className="text-gray-500">Click "Scan Networks" to search for WiFi</p>
                        </div>
                    )}
                </div>
            )}

        </div>
    )
}
