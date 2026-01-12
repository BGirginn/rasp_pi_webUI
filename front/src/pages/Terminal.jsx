import { useState, useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'

export default function Terminal() {
    const terminalRef = useRef(null)
    const xtermRef = useRef(null)
    const wsRef = useRef(null)
    const fitAddonRef = useRef(null)

    const [connected, setConnected] = useState(false)
    const [error, setError] = useState(null)
    const [connecting, setConnecting] = useState(false)

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
            // Send auth token and terminal size
            ws.send(JSON.stringify({
                token: token,
                user: 'admin',
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
                        term.writeln('\x1b[32mConnected! You now have shell access.\x1b[0m')
                        term.writeln('')

                        // Focus terminal
                        term.focus()
                    } else if (data.error) {
                        setError(data.error)
                        setConnecting(false)
                        term.writeln(`\x1b[31mError: ${data.error}\x1b[0m`)
                    }
                } catch {
                    // Regular text output
                    term.write(event.data)
                }
            } else if (event.data instanceof Blob) {
                // Binary data
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
            term.writeln('\x1b[31mConnection error occurred.\x1b[0m')
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

    return (
        <div className="h-full flex flex-col animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold text-gray-100">Terminal</h2>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${connected
                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                        }`}>
                        {connected ? '● Connected' : '○ Disconnected'}
                    </span>
                </div>

                <div className="flex gap-3">
                    {!connected ? (
                        <button
                            onClick={connect}
                            disabled={connecting}
                            className="btn btn-primary"
                        >
                            {connecting ? '⏳ Connecting...' : '🔌 Connect'}
                        </button>
                    ) : (
                        <button
                            onClick={disconnect}
                            className="btn btn-danger"
                        >
                            ✕ Disconnect
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
            <div className="flex-1 glass-card rounded-xl overflow-hidden">
                <div
                    ref={terminalRef}
                    className="h-full p-2"
                    style={{ minHeight: '400px' }}
                />
            </div>

            {/* Help text */}
            <div className="mt-4 text-sm text-gray-500">
                <p>💡 Tip: Use <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+C</kbd> to interrupt, <kbd className="px-2 py-1 bg-gray-800 rounded text-gray-400">Ctrl+D</kbd> to exit shell.</p>
            </div>
        </div>
    )
}
