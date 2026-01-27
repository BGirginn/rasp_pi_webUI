import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import BreakGlassModal from '../components/BreakGlassModal'

export default function Terminal() {
    const terminalRef = useRef(null)
    const xtermRef = useRef(null)
    const wsRef = useRef(null)
    const fitAddonRef = useRef(null)

    const [connected, setConnected] = useState(false)
    const [error, setError] = useState(null)
    const [connecting, setConnecting] = useState(false)
    const [mode, setMode] = useState('restricted') // 'restricted' or 'full'

    // Break-glass state (stored in memory only, never localStorage)
    const [showBreakGlass, setShowBreakGlass] = useState(false)
    const [breakglassToken, setBreakglassToken] = useState(null)
    const [breakglassExpiry, setBreakglassExpiry] = useState(null)
    const [remainingTime, setRemainingTime] = useState(null)
    const [hasTotp, setHasTotp] = useState(false)

    // Restricted mode command state
    const [commandInput, setCommandInput] = useState('')
    const [commandHistory, setCommandHistory] = useState([])
    const [allowedCommands, setAllowedCommands] = useState([])

    // Check user's TOTP status on mount
    useEffect(() => {
        checkUserStatus()
    }, [])

    const checkUserStatus = async () => {
        try {
            const token = localStorage.getItem('access_token')
            const response = await fetch('/api/auth/me', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (response.ok) {
                const data = await response.json()
                setHasTotp(data.has_totp)
            }
        } catch (e) {
            console.error('Failed to check user status:', e)
        }
    }

    // Countdown timer for break-glass session
    useEffect(() => {
        if (!breakglassExpiry) return

        const interval = setInterval(() => {
            const now = new Date()
            const expiry = new Date(breakglassExpiry + 'Z')
            const remaining = Math.max(0, Math.floor((expiry - now) / 1000))

            setRemainingTime(remaining)

            if (remaining <= 0) {
                // Session expired
                handleBreakglassExpiry()
                clearInterval(interval)
            }
        }, 1000)

        return () => clearInterval(interval)
    }, [breakglassExpiry])

    const handleBreakglassExpiry = useCallback(() => {
        setBreakglassToken(null)
        setBreakglassExpiry(null)
        setRemainingTime(null)

        if (mode === 'full' && connected) {
            disconnect()
            const term = xtermRef.current
            if (term) {
                term.writeln('')
                term.writeln('\x1b[31m[Break-glass session expired]\x1b[0m')
            }
        }
    }, [mode, connected])

    useEffect(() => {
        // Initialize xterm.js
        const term = new XTerm({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#0d1117',
                foreground: '#c9d1d9',
                cursor: '#58a6ff',
                cursorAccent: '#0d1117',
                selection: 'rgba(88, 166, 255, 0.3)',
                black: '#484f58',
                red: '#ff7b72',
                green: '#3fb950',
                yellow: '#d29922',
                blue: '#58a6ff',
                magenta: '#bc8cff',
                cyan: '#39c5cf',
                white: '#b1bac4',
                brightBlack: '#6e7681',
                brightRed: '#ffa198',
                brightGreen: '#56d364',
                brightYellow: '#e3b341',
                brightBlue: '#79c0ff',
                brightMagenta: '#d2a8ff',
                brightCyan: '#56d4dd',
                brightWhite: '#f0f6fc',
            },
            allowProposedApi: true,
        })

        const fitAddon = new FitAddon()
        const webLinksAddon = new WebLinksAddon()

        term.loadAddon(fitAddon)
        term.loadAddon(webLinksAddon)

        if (terminalRef.current) {
            term.open(terminalRef.current)
            fitAddon.fit()
        }

        xtermRef.current = term
        fitAddonRef.current = fitAddon

        // Handle window resize
        const handleResize = () => {
            if (fitAddonRef.current) {
                fitAddonRef.current.fit()

                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({
                        resize: {
                            cols: term.cols,
                            rows: term.rows
                        }
                    }))
                }
            }
        }

        window.addEventListener('resize', handleResize)

        // Welcome message
        term.writeln('\x1b[1;36m╔════════════════════════════════════════╗\x1b[0m')
        term.writeln('\x1b[1;36m║\x1b[0m   \x1b[1;32mPi Control Panel - Web Terminal\x1b[0m    \x1b[1;36m║\x1b[0m')
        term.writeln('\x1b[1;36m╚════════════════════════════════════════╝\x1b[0m')
        term.writeln('')
        term.writeln('\x1b[33mRestricted Mode:\x1b[0m Use command input below')
        term.writeln('\x1b[33mFull Shell:\x1b[0m Requires break-glass authentication')
        term.writeln('')

        return () => {
            window.removeEventListener('resize', handleResize)
            term.dispose()
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [])

    const connectRestricted = () => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        setConnecting(true)
        setError(null)
        setMode('restricted')

        const term = xtermRef.current
        const token = localStorage.getItem('access_token')

        if (!token) {
            setError('Not authenticated. Please log in first.')
            setConnecting(false)
            return
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/api/terminal/ws`

        term.writeln('\x1b[33mConnecting (restricted mode)...\x1b[0m')

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({
                token: token,
                mode: 'restricted',
                cols: term.cols,
                rows: term.rows
            }))
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)

                if (data.status === 'connected') {
                    setConnected(true)
                    setConnecting(false)
                    setAllowedCommands(data.allowed_commands || [])
                    term.writeln('\x1b[32mConnected in restricted mode.\x1b[0m')
                    term.writeln('\x1b[90mUse the command input below to run allowed commands.\x1b[0m')
                    term.writeln('')
                } else if (data.type === 'output') {
                    term.writeln(`\x1b[36m$ ${data.command}\x1b[0m`)
                    term.writeln(data.output)
                    if (data.exit_code !== 0) {
                        term.writeln(`\x1b[31m[Exit code: ${data.exit_code}]\x1b[0m`)
                    }
                    term.writeln('')
                } else if (data.type === 'error' || data.error) {
                    setError(data.error || data.type)
                    term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)
                }
            } catch {
                // Regular text output
                term.write(event.data)
            }
        }

        ws.onerror = () => {
            setError('Connection error')
            setConnecting(false)
            setConnected(false)
        }

        ws.onclose = () => {
            setConnected(false)
            setConnecting(false)
            term.writeln('\x1b[33mDisconnected.\x1b[0m')
        }
    }

    const connectFull = async (bgToken) => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        const tokenToUse = bgToken || breakglassToken
        if (!tokenToUse) {
            setShowBreakGlass(true)
            return
        }

        setConnecting(true)
        setError(null)
        setMode('full')

        const term = xtermRef.current
        const token = localStorage.getItem('access_token')

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/api/terminal/ws`

        term.writeln('\x1b[33mConnecting (full PTY mode)...\x1b[0m')

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({
                token: token,
                mode: 'full',
                breakglass_token: tokenToUse,
                cols: term.cols,
                rows: term.rows
            }))
        }

        ws.onmessage = (event) => {
            if (typeof event.data === 'string') {
                try {
                    const data = JSON.parse(event.data)

                    if (data.status === 'connected') {
                        setConnected(true)
                        setConnecting(false)
                        term.writeln('\x1b[32mFull shell access granted.\x1b[0m')
                        term.writeln('\x1b[31m⚠️  This session is logged and time-limited.\x1b[0m')
                        term.writeln('')
                        term.focus()
                    } else if (data.error) {
                        setError(data.error)
                        setConnecting(false)
                        term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)

                        if (data.code === 'BREAKGLASS_REQUIRED' || data.code === 'BREAKGLASS_INVALID') {
                            setBreakglassToken(null)
                            setBreakglassExpiry(null)
                            setShowBreakGlass(true)
                        }
                    }
                } catch {
                    term.write(event.data)
                }
            } else if (event.data instanceof Blob) {
                event.data.arrayBuffer().then(buffer => {
                    const text = new TextDecoder().decode(buffer)
                    term.write(text)
                })
            }
        }

        ws.onerror = () => {
            setError('Connection error')
            setConnecting(false)
            setConnected(false)
        }

        ws.onclose = () => {
            setConnected(false)
            setConnecting(false)
            term.writeln('')
            term.writeln('\x1b[33mConnection closed.\x1b[0m')
        }

        // Send terminal input to server
        term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(data)
            }
        })
    }

    const disconnect = () => {
        if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
        }
        setConnected(false)
    }

    const endBreakglassSession = async () => {
        try {
            const token = localStorage.getItem('access_token')
            await fetch('/api/terminal/breakglass/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ reason: 'user_ended' })
            })
        } catch (e) {
            console.error('Failed to end break-glass session:', e)
        }

        setBreakglassToken(null)
        setBreakglassExpiry(null)
        setRemainingTime(null)

        if (connected) {
            disconnect()
        }

        const term = xtermRef.current
        if (term) {
            term.writeln('')
            term.writeln('\x1b[33m[Break-glass session ended]\x1b[0m')
        }
    }

    const handleBreakglassSuccess = (token, expiresAt, ttlSeconds) => {
        setShowBreakGlass(false)
        setBreakglassToken(token)
        setBreakglassExpiry(expiresAt)
        setRemainingTime(ttlSeconds)

        // If we got a token (not continuing existing session), connect
        if (token) {
            connectFull(token)
        } else {
            // Continuing existing session - just connect with existing state
            connectFull()
        }
    }

    const executeRestrictedCommand = () => {
        if (!commandInput.trim() || !wsRef.current) return

        wsRef.current.send(JSON.stringify({
            type: 'command',
            command: commandInput.trim()
        }))

        setCommandHistory(prev => [...prev, commandInput])
        setCommandInput('')
    }

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins}:${String(secs).padStart(2, '0')}`
    }

    return (
        <div className="h-full flex flex-col animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold text-gray-100">Terminal</h2>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${connected
                            ? mode === 'full'
                                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                : 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                        }`}>
                        {connected
                            ? mode === 'full' ? '🔓 Full Shell' : '🔒 Restricted'
                            : '○ Disconnected'}
                    </span>

                    {/* Break-glass timer */}
                    {remainingTime !== null && remainingTime > 0 && (
                        <span className={`px-2 py-1 rounded-full text-xs font-mono font-medium ${remainingTime < 120
                                ? 'bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse'
                                : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                            }`}>
                            ⏱ {formatTime(remainingTime)}
                        </span>
                    )}
                </div>

                <div className="flex gap-3">
                    {!connected ? (
                        <>
                            <button
                                onClick={connectRestricted}
                                disabled={connecting}
                                className="btn btn-primary"
                            >
                                {connecting ? '⏳ Connecting...' : '🔒 Restricted Mode'}
                            </button>
                            <button
                                onClick={() => breakglassToken ? connectFull() : setShowBreakGlass(true)}
                                disabled={connecting}
                                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                            >
                                🔓 Full Shell
                            </button>
                        </>
                    ) : (
                        <>
                            {mode === 'full' && (
                                <button
                                    onClick={endBreakglassSession}
                                    className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg transition-colors"
                                >
                                    🛑 End Emergency Access
                                </button>
                            )}
                            <button
                                onClick={disconnect}
                                className="btn btn-danger"
                            >
                                ✕ Disconnect
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Error message */}
            {error && (
                <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                    {error}
                </div>
            )}

            {/* Full shell warning */}
            {connected && mode === 'full' && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-300 text-sm flex items-center gap-2">
                    <span>⚠️</span>
                    <span>Full shell access is active. All commands are logged.</span>
                </div>
            )}

            {/* Terminal container */}
            <div className={`flex-1 glass-card rounded-xl overflow-hidden ${connected && mode === 'full' ? 'ring-2 ring-red-500/50' : ''
                }`}>
                <div
                    ref={terminalRef}
                    className="h-full p-2"
                    style={{ minHeight: '400px' }}
                />
            </div>

            {/* Restricted mode command input */}
            {connected && mode === 'restricted' && (
                <div className="mt-4 flex gap-3">
                    <input
                        type="text"
                        value={commandInput}
                        onChange={(e) => setCommandInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && executeRestrictedCommand()}
                        placeholder="Enter command (e.g., uptime, df -h, docker ps)..."
                        className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                    <button
                        onClick={executeRestrictedCommand}
                        disabled={!commandInput.trim()}
                        className="btn btn-primary"
                    >
                        Run
                    </button>
                </div>
            )}

            {/* Help text */}
            <div className="mt-4 text-sm text-gray-500">
                {mode === 'restricted' ? (
                    <p>💡 Restricted mode allows only approved commands. For full access, use "Full Shell" with break-glass authentication.</p>
                ) : (
                    <p>💡 Use <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+C</kbd> to interrupt, <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+D</kbd> to exit shell.</p>
                )}
            </div>

            {/* Break-Glass Modal */}
            <BreakGlassModal
                isOpen={showBreakGlass}
                onClose={() => setShowBreakGlass(false)}
                onSuccess={handleBreakglassSuccess}
                hasTotp={hasTotp}
            />
        </div>
    )
}
