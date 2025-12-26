import { useState, useEffect } from 'react'
import { api } from '../services/api'

// Device card component
function DeviceCard({ device }) {

    const stateColors = {
        online: 'text-green-400 bg-green-500/20',
        offline: 'text-gray-400 bg-gray-500/20',
        connected: 'text-blue-400 bg-blue-500/20',
        disconnected: 'text-red-400 bg-red-500/20',
    }

    const typeIcons = {
        esp: '📡',
        usb: '🔌',
        gpio: '⚡',
        serial: '🔗',
        bluetooth: '📶',
    }

    return (
        <div className="glass-card rounded-xl p-5 animate-slide-in">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{typeIcons[device.type] || '🔧'}</span>
                    <div>
                        <h3 className="font-semibold text-gray-100">{device.name}</h3>
                        <p className="text-sm text-gray-500">{device.type} • {device.id}</p>
                    </div>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${stateColors[device.state]}`}>
                    {device.state}
                </span>
            </div>

            {/* Telemetry data */}
            {device.telemetry && Object.keys(device.telemetry).length > 0 && (
                <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
                    <p className="text-xs text-gray-500 mb-2">Live Telemetry</p>
                    <div className="grid grid-cols-2 gap-2">
                        {Object.entries(device.telemetry).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                                <span className="text-sm text-gray-400">{key}:</span>
                                <span className="text-sm text-gray-100 font-mono">
                                    {typeof value === 'boolean' ? (value ? '✅' : '❌') : value}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Capabilities */}
            {device.capabilities && device.capabilities.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-4">
                    {device.capabilities.map((cap) => (
                        <span
                            key={cap}
                            className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300"
                        >
                            {cap}
                        </span>
                    ))}
                </div>
            )}

            {/* Last seen */}
            {device.last_seen && (
                <p className="text-xs text-gray-500 mt-3">
                    Last seen: {new Date(device.last_seen).toLocaleString()}
                </p>
            )}
        </div>
    )
}

// Filter tabs
function FilterTabs({ filters, active, onChange }) {
    return (
        <div className="flex gap-2 flex-wrap">
            {filters.map((f) => (
                <button
                    key={f.value}
                    onClick={() => onChange(f.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${active === f.value
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                >
                    {f.icon} {f.label}
                    {f.count !== undefined && (
                        <span className="ml-2 px-2 py-0.5 rounded-full bg-gray-700 text-xs">
                            {f.count}
                        </span>
                    )}
                </button>
            ))}
        </div>
    )
}

export default function Devices() {
    const [devices, setDevices] = useState([])
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState(null)
    const [filter, setFilter] = useState('all')
    const [lastUpdate, setLastUpdate] = useState(null)

    useEffect(() => {
        loadDevices()

        // Auto-refresh every 30 seconds
        const interval = setInterval(loadDevices, 30000)
        return () => clearInterval(interval)
    }, [])

    async function loadDevices() {
        if (!loading) setRefreshing(true)
        try {
            const response = await api.get('/devices')
            setDevices(response.data)
            setLastUpdate(new Date())
            setError(null)
        } catch (err) {
            setError('Failed to load devices')
            console.error(err)
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }

    // Filter devices
    const filteredDevices = filter === 'all'
        ? devices
        : devices.filter((d) => d.type === filter)

    // Calculate counts for all device types
    const counts = {
        all: devices.length,
        keyboard: devices.filter((d) => d.type === 'keyboard').length,
        storage: devices.filter((d) => d.type === 'storage').length,
        disk: devices.filter((d) => d.type === 'disk').length,
        usb: devices.filter((d) => d.type === 'usb').length,
        serial: devices.filter((d) => d.type === 'serial').length,
        esp: devices.filter((d) => d.type === 'esp').length,
    }

    const filters = [
        { value: 'all', label: 'All', icon: '📱', count: counts.all },
        { value: 'keyboard', label: 'Keyboard', icon: '⌨️', count: counts.keyboard },
        { value: 'storage', label: 'Storage', icon: '💾', count: counts.storage },
        { value: 'disk', label: 'Disk', icon: '💿', count: counts.disk },
        { value: 'usb', label: 'USB', icon: '🔌', count: counts.usb },
        { value: 'serial', label: 'Serial', icon: '🔗', count: counts.serial },
        { value: 'esp', label: 'ESP/MQTT', icon: '📡', count: counts.esp },
    ].filter(f => f.value === 'all' || f.count > 0)  // Only show tabs with devices

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-gray-100">Devices</h2>
                    {lastUpdate && (
                        <p className="text-xs text-gray-500 mt-1">
                            Last updated: {lastUpdate.toLocaleTimeString()}
                            {refreshing && <span className="ml-2 text-purple-400">• Refreshing...</span>}
                        </p>
                    )}
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={loadDevices}
                        disabled={refreshing}
                        className={`btn btn-secondary ${refreshing ? 'opacity-50' : ''}`}
                    >
                        {refreshing ? (
                            <span className="flex items-center gap-2">
                                <span className="w-4 h-4 border-2 border-gray-400 border-t-white rounded-full animate-spin"></span>
                                Refreshing...
                            </span>
                        ) : '🔄 Refresh'}
                    </button>
                    <button className="btn btn-ghost">
                        📡 Scan USB
                    </button>
                </div>
            </div>

            {/* Filters */}
            <FilterTabs filters={filters} active={filter} onChange={setFilter} />

            {/* Error */}
            {error && (
                <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400">
                    {error}
                </div>
            )}

            {/* Grid */}
            {filteredDevices.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredDevices.map((device) => (
                        <DeviceCard
                            key={device.id}
                            device={device}
                        />
                    ))}
                </div>
            ) : (
                <div className="glass-card rounded-xl p-8 text-center">
                    <span className="text-5xl mb-4 block">🔌</span>
                    <h3 className="text-xl font-semibold text-gray-100 mb-2">
                        No devices found
                    </h3>
                    <p className="text-gray-500">
                        {filter === 'all'
                            ? 'Connect USB or configure ESP devices to get started'
                            : `No ${filter.toUpperCase()} devices detected`}
                    </p>
                </div>
            )}

            {/* GPIO Pins Section */}
            <div className="glass-card rounded-xl p-5">
                <h3 className="text-lg font-semibold text-gray-100 mb-4">GPIO Pins</h3>
                <p className="text-gray-500 text-sm mb-4">
                    Configure and monitor GPIO pins on your Raspberry Pi
                </p>
                <button className="btn btn-secondary">
                    ⚡ Open GPIO Manager
                </button>
            </div>
        </div>
    )
}
