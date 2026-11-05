import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Terminal from './Terminal';

const terminals = vi.hoisted(() => []);
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 80;
    rows = 24;
    listeners = new Set();
    constructor() { terminals.push(this); }
    loadAddon() {}
    open() {}
    focus() {}
    writeln(text) { if (typeof text !== 'string') throw new TypeError('Terminal output must be text'); }
    write() {}
    dispose() { this.listeners.clear(); }
    onData(listener) {
      this.listeners.add(listener);
      return { dispose: () => this.listeners.delete(listener) };
    }
    type(text) { this.listeners.forEach((listener) => listener(text)); }
  },
}));
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() {} } }));
vi.mock('@xterm/addon-web-links', () => ({ WebLinksAddon: class {} }));
vi.mock('../components/BreakGlassModal', () => ({
  default: ({ isOpen, onSuccess }) => isOpen
    ? <button onClick={() => onSuccess('test-elevation')}>Authorize shell</button>
    : null,
}));

class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances = [];
  readyState = 0;
  sent = [];
  constructor(url) { this.url = url; FakeWebSocket.instances.push(this); }
  send(data) { this.sent.push(data); }
  open() { this.readyState = FakeWebSocket.OPEN; this.onopen?.(); }
  message(data) { this.onmessage?.({ data: JSON.stringify(data) }); }
  close() {
    this.readyState = FakeWebSocket.CLOSED;
    setTimeout(() => this.onclose?.({ code: 1000 }), 0);
  }
  fail() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code: 1006 });
  }
}

function connectRestricted() {
  fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
  let socket = FakeWebSocket.instances.at(-1);
  act(() => {
    socket.open();
    if (JSON.parse(socket.sent[0]).mode === 'full') {
      socket.message({ code: 'BREAKGLASS_REQUIRED', error: 'Break-glass token required' });
      socket = FakeWebSocket.instances.at(-1);
      socket.open();
    }
    socket.message({ status: 'connected', mode: 'restricted' });
  });
  return socket;
}

beforeEach(() => {
  vi.useFakeTimers();
  terminals.length = 0;
  FakeWebSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeWebSocket);
  vi.stubGlobal('localStorage', { getItem: () => 'test-access-token' });
});
afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('terminal connection lifecycle', () => {
  it('keeps the default connection stable without a reconnect loop', () => {
    render(<Terminal />);
    const socket = connectRestricted();
    const count = FakeWebSocket.instances.length;
    act(() => vi.advanceTimersByTime(5000));
    expect(FakeWebSocket.instances).toHaveLength(count);
    expect(socket.readyState).toBe(FakeWebSocket.OPEN);
    expect(screen.getByText('● Connected (restricted)')).toBeInTheDocument();
  });
  it('accepts empty command output and sends each restricted command once', () => {
    render(<Terminal />);
    const socket = connectRestricted();
    act(() => {
      terminals[0].type('whoami');
      terminals[0].type('\r');
      socket.message({ type: 'output', output: '', exit_code: 0 });
    });
    expect(socket.sent.filter((text) => JSON.parse(text).type === 'command')).toEqual([
      JSON.stringify({ type: 'command', command: 'whoami' }),
    ]);
  });
  it('stops reconnecting when authentication is rejected', () => {
    render(<Terminal />);
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.open();
      socket.message({ error: 'Invalid token' });
      socket.close();
      vi.advanceTimersByTime(60000);
    });
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(screen.getByText('Invalid token')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled();
  });
  it('bounds automatic retries instead of resetting the backoff on every connection', () => {
    render(<Terminal />);
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
    for (const delay of [1000, 2000, 4000]) {
      act(() => {
        FakeWebSocket.instances.at(-1).fail();
        vi.advanceTimersByTime(delay);
      });
    }
    act(() => {
      FakeWebSocket.instances.at(-1).fail();
      vi.advanceTimersByTime(60000);
    });
    expect(FakeWebSocket.instances).toHaveLength(4);
    expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled();
  });
  it('releases old input handlers when switching to a full shell and sends no JSON heartbeat to the PTY', () => {
    render(<Terminal />);
    const restricted = connectRestricted();
    fireEvent.click(screen.getByRole('button', { name: 'Full Shell' }));
    fireEvent.click(screen.getByRole('button', { name: 'Authorize shell' }));
    const full = FakeWebSocket.instances.at(-1);
    act(() => {
      full.open();
      full.message({ status: 'connected', mode: 'full' });
      vi.advanceTimersByTime(30000);
      terminals[0].type('pwd\r');
    });
    expect(terminals[0].listeners.size).toBe(1);
    expect(restricted.readyState).toBe(FakeWebSocket.CLOSED);
    expect(full.sent).toEqual([
      expect.stringContaining('"breakglass_token":"test-elevation"'),
      'pwd\r',
    ]);
    expect(screen.getByText('● Connected (full)')).toBeInTheDocument();
  });
  it('cancels retries when the user disconnects or leaves the page', () => {
    const { unmount } = render(<Terminal />);
    connectRestricted();
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
    act(() => vi.advanceTimersByTime(60000));
    expect(screen.getByText('○ Disconnected')).toBeInTheDocument();
    const count = FakeWebSocket.instances.length;
    unmount();
    act(() => vi.advanceTimersByTime(60000));
    expect(FakeWebSocket.instances).toHaveLength(count);
  });
});
