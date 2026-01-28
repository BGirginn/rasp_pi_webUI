import { useState, useEffect, useRef } from 'react'
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
    const [mode, setMode] = useState(null) // 'restricted' or 'full'
    const [error, setError] = useState(null)
    const [connecting, setConnecting] = useState(false) // Restore
    const [showBreakGlass, setShowBreakGlass] = useState(false) // Restore
    const [expiryTime, setExpiryTime] = useState(null)
    const [timeLeft, setTimeLeft] = useState(null)

    useEffect(() => {
        if (!expiryTime) {
            setTimeLeft(null)
            return
        }

        const interval = setInterval(() => {
            const remaining = Math.max(0, Math.ceil((expiryTime - Date.now()) / 1000))
            setTimeLeft(remaining)

            if (remaining <= 0) {
                setExpiryTime(null)
                // Optionally disconnect or show expired state here
            }
        }, 1000)

        // Initial set
        setTimeLeft(Math.max(0, Math.ceil((expiryTime - Date.now()) / 1000)))

        return () => clearInterval(interval)
    }, [expiryTime])

    const formatTime = (seconds) => {
        if (seconds === null) return ''
        const m = Math.floor(seconds / 60)
        const s = seconds % 60
        return `${m}:${s.toString().padStart(2, '0')}`
    }

    // ... (rest of imports/setup)

    const handleFullConnectSuccess = () => {
        // Set expiry to 10 minutes from now (matching backend default)
        // Ideally backend should send expires_at in handshake
        setExpiryTime(Date.now() + 10 * 60 * 1000)
    }

    // In connectFullWithToken's onmessage:
    // ...
    // if (data.status === 'connected') {
    //    ...
    //    handleFullConnectSuccess()
    // }

    // In disconnect:
    // setExpiryTime(null)


    useEffect(() => {
        // Initialize xterm.js
        const term = new XTerm({
            cursorBlink: true,
            cursorStyle: 'bar',
            fontSize: 14,
            fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Monaco, "Courier New", monospace',
            scrollback: 1000,
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

                // Send resize to server
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
        term.writeln('\x1b[33mClick "Connect" to start a terminal session.\x1b[0m')
        term.writeln('')

        return () => {
            window.removeEventListener('resize', handleResize)
            term.dispose()
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [])

    const connect = () => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        setConnecting(true)
        setError(null)
        setMode(null)

        const term = xtermRef.current
        const token = localStorage.getItem('access_token')

        if (!token) {
            setError('Not authenticated. Please log in first.')
            setConnecting(false)
            return
        }

        // Determine WebSocket URL based on current location
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/api/terminal/ws`

        term.writeln('\x1b[33mConnecting to terminal...\x1b[0m')

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            // Send auth token and terminal size - request full mode
            // Try full mode first, if no breakglass token, backend will return error
            // and we fall back to restricted mode
            ws.send(JSON.stringify({
                token: token,
                mode: 'full',  // Request full PTY mode
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
                        setMode(data.mode)
                        term.writeln('\x1b[32mConnected! You now have shell access.\x1b[0m')
                        term.writeln('')

                        // Focus terminal
                        term.focus()
                    } else if (data.code === 'BREAKGLASS_REQUIRED') {
                        // Switch to restricted mode - break-glass not available
                        term.writeln('\x1b[33mFull shell requires break-glass elevation.\x1b[0m')
                        term.writeln('\x1b[33mConnecting in restricted mode...\x1b[0m')

                        // Reconnect in restricted mode
                        ws.close()
                        connectRestricted()
                    } else if (data.error) {
                        setError(data.error)
                        setConnecting(false)
                        term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)
                    }
                } catch {
                    // Regular text output from full PTY mode
                    term.write(event.data)
                }
            } else if (event.data instanceof Blob) {
                // Binary data from full PTY mode
                event.data.arrayBuffer().then(buffer => {
                    const text = new TextDecoder().decode(buffer)
                    term.write(text)
                })
            }
        }

        ws.onerror = (err) => {
            setError('Connection error')
            setConnecting(false)
            setConnected(false)
            setMode(null)
            term.writeln('\x1b[31mConnection error occurred.\x1b[0m')
        }

        ws.onclose = () => {
            setConnected(false)
            setConnecting(false)
            setMode(null)
            term.writeln('')
            term.writeln('\x1b[33mConnection closed.\x1b[0m')
        }

        // Send terminal input to server (for full PTY mode)
        term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(data)
            }
        })
    }

    const connectFullWithToken = (breakglassToken) => {
        if (wsRef.current) {
            wsRef.current.close()
        }

        setConnecting(true)
        setError(null)
        setMode(null)

        const term = xtermRef.current
        const token = localStorage.getItem('access_token')

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/api/terminal/ws`

        term.writeln('\x1b[33mConnecting to Full Shell (Elevated)...\x1b[0m')

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({
                token: token,
                mode: 'full',
                breakglass_token: breakglassToken,
                cols: term.cols,
                rows: term.rows
            }))
        }

        // Re-use standard handler logic (simplified for brevity as they are similar)
        ws.onmessage = (event) => {
            if (typeof event.data === 'string') {
                try {
                    const data = JSON.parse(event.data)
                    if (data.status === 'connected') {
                        setConnected(true)
                        setConnecting(false)
                        setMode('full')
                        setExpiryTime(Date.now() + 10 * 60 * 1000) // Start timer (10m)
                        term.writeln('\x1b[32mConnected to Full Shell! Access granted.\x1b[0m')
                        term.writeln('')
                        term.focus()
                    } else if (data.error) {
                        setError(data.error)
                        setConnecting(false)
                        term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)
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
            term.writeln('\x1b[31mConnection error.\x1b[0m')
        }

        ws.onclose = () => {
            setConnected(false)
            setConnecting(false)
            setMode(null)
            setExpiryTime(null)
            term.writeln('\x1b[33mConnection closed.\x1b[0m')
        }

        term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) ws.send(data)
        })
    }

    const connectRestricted = () => {
        const term = xtermRef.current
        const token = localStorage.getItem('access_token')

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/api/terminal/ws`

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
                    setMode('restricted')
                    term.writeln('\x1b[32mConnected in restricted mode.\x1b[0m')
                    term.writeln('\x1b[33mType commands and press Enter. Only allowlisted commands work.\x1b[0m')
                    term.writeln('')
                    term.write('$ ')
                } else if (data.type === 'output') {
                    term.writeln(data.output)
                    term.write('$ ')
                } else if (data.type === 'error') {
                    term.writeln(`\x1b[31m${data.error}\x1b[0m`)
                    term.write('$ ')
                } else if (data.error) {
                    term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)
                }
            } catch {
                term.write(event.data)
            }
        }

        ws.onerror = () => {
            setError('Connection error')
            setConnecting(false)
            setConnected(false)
            setMode(null)
        }

        ws.onclose = () => {
            setConnected(false)
            setMode(null)
            term.writeln('\x1b[33mConnection closed.\x1b[0m')
        }

        // For restricted mode, buffer input and send as command on Enter
        let inputBuffer = ''
        term.onData((data) => {
            if (ws.readyState !== WebSocket.OPEN) return

            if (data === '\r') {
                // Enter pressed - send command
                term.writeln('')
                if (inputBuffer.trim()) {
                    ws.send(JSON.stringify({
                        type: 'command',
                        command: inputBuffer.trim()
                    }))
                } else {
                    term.write('$ ')
                }
                inputBuffer = ''
            } else if (data === '\x7f') {
                // Backspace
                if (inputBuffer.length > 0) {
                    inputBuffer = inputBuffer.slice(0, -1)
                    term.write('\b \b')
                }
            } else if (data >= ' ' || data === '\t') {
                // Printable character
                inputBuffer += data
                term.write(data)
            }
        })
    }

    const disconnect = () => {
        if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
        }
        setConnected(false)
        setMode(null)
        setExpiryTime(null)
    }

    return (
        <div className="h-[calc(100vh-10rem)] flex flex-col animate-fade-in relative">
            <BreakGlassModal
                isOpen={showBreakGlass}
                onClose={() => setShowBreakGlass(false)}
                onSuccess={connectFullWithToken}
            />

            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold text-gray-100">Terminal</h2>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${connected
                        ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                        : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                        }`}>
                        {connected ? `● Connected (${mode})` : '○ Disconnected'}
                    </span>

                    {/* Timer */}
                    {mode === 'full' && timeLeft !== null && (
                        <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 animate-pulse">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            {formatTime(timeLeft)}
                        </span>
                    )}
                </div>

                <div className="flex gap-3">
                    {!connected && (
                        <button
                            onClick={connect}
                            disabled={connecting}
                            className="px-4 py-2 rounded-lg bg-green-500/20 border border-green-500/50 text-green-400 hover:bg-green-500/30 transition-all flex items-center gap-2 disabled:opacity-50"
                        >
                            {connecting ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-green-400/30 border-t-green-400 rounded-full animate-spin"></span>
                                    Connecting...
                                </>
                            ) : (
                                <>
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Connect
                                </>
                            )}
                        </button>
                    )}

                    {(!connected || mode === 'restricted') && (
                        <button
                            onClick={() => setShowBreakGlass(true)}
                            disabled={connecting}
                            className="px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30 transition-all flex items-center gap-2 disabled:opacity-50"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                            Full Shell
                        </button>
                    )}

                    {connected && (
                        <button
                            onClick={disconnect}
                            className="px-4 py-2 rounded-lg bg-gray-500/20 border border-gray-500/50 text-gray-400 hover:bg-gray-500/30 transition-all flex items-center gap-2"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Disconnect
                        </button>
                    )}
                </div>
            </div>

            {/* Error message */}
            {error && (
                <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                    {error}
                </div>
            )}

            {/* Terminal container */}
            <div className="flex-1 rounded-xl overflow-hidden bg-[#0d1117] border border-white/10" style={{ minHeight: '400px' }}>
                <div
                    ref={terminalRef}
                    className="w-full h-full"
                    style={{ padding: '8px' }}
                />
            </div>

            {/* Help text */}
            <div className="mt-4 text-sm text-gray-500">
                <p>💡 Tip: Use <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+C</kbd> to interrupt, <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+D</kbd> to exit shell.</p>
            </div>
        </div>
    )
}
