import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../services/api';
import { ServicesPage } from './ServicesPage';
import { DevicesPage } from './DevicesPage';
import { TelemetryPage } from './TelemetryPage';
import { NetworkPage, AdGuardPage } from './NetworkPage';
import { IoTPage } from './IoTPage';
import { IoTDeviceDetail } from './IoTDeviceDetail';
import { ArchivePage } from './ArchivePage';
import { ProjectsPage } from './ProjectsPage';
import FilesPage from './FilesPage';
import JobsPage from './Jobs';
import { AlertsPage } from './AlertsPage';
import { SettingsPage } from './SettingsPage';
import Login from './Login';
import { TerminalPage } from './TerminalPage';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    createSSE: vi.fn(() => ({ close: vi.fn() })),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', role: 'admin', has_totp: false },
    isAdmin: true,
    isOperator: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'purple',
    isDarkMode: true,
    isEditMode: false,
    setTheme: vi.fn(),
    setIsDarkMode: vi.fn(),
    setIsEditMode: vi.fn(),
  }),
  getThemeColors: () => ({
    primary: 'from-purple-600 to-fuchsia-600',
    secondary: 'from-purple-500 to-fuchsia-500',
    lightPrimary: 'from-purple-700 to-fuchsia-700',
    lightSecondary: 'from-purple-600 to-fuchsia-600',
  }),
}));

vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 80;
    rows = 24;
    loadAddon() {}
    open() {}
    writeln() {}
    write() {}
    clear() {}
    dispose() {}
    onData() { return { dispose() {} }; }
  },
}));
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() {} } }));
vi.mock('@xterm/addon-web-links', () => ({ WebLinksAddon: class {} }));

function responseFor(path) {
  if (path === '/resources' || path.startsWith('/resources?')) return [];
  if (path === '/devices') return [];
  if (path === '/devices/gpio/pins') return { pins: [] };
  if (path === '/telemetry/current') return {};
  if (path === '/network/interfaces') return [];
  if (path === '/network/connectivity') return {};
  if (path === '/network/wifi/networks') return [];
  if (path === '/network/wifi/status') return {};
  if (path === '/network/bluetooth/status') return { enabled: false, paired_devices: [] };
  if (path.startsWith('/network/bluetooth/scan')) return { devices: [] };
  if (path === '/dns-filter/status') return { installed: false, managed: false };
  if (path === '/dns-filter/rules') return { blocked_domains: [], allowed_domains: [] };
  if (path.startsWith('/dns-filter/querylog')) return { items: [] };
  if (path.startsWith('/dns-filter/coverage')) return { clients: [], client_count: 0, sample_size: 0 };
  if (path === '/iot/devices') return [];
  if (/^\/iot\/devices\/[^/]+\/history/.test(path)) return { sensors: [] };
  if (/^\/iot\/devices\/[^/]+$/.test(path)) {
    return { id: 'device-1', name: 'Test device', status: 'offline', ip: '', port: 0, sensors: [], last_seen: 0 };
  }
  if (path === '/archive/stats') return {};
  if (path.startsWith('/archive/')) return { data: [], total: 0 };
  if (path === '/backup/status') return {};
  if (path === '/backup/files') return { files: [] };
  if (path === '/projects') return [];
  if (path.startsWith('/files/list')) return [];
  if (path.startsWith('/jobs?')) return [];
  if (path === '/jobs/types') return {};
  if (path === '/alerts') return [];
  if (path === '/alerts/rules') return [];
  if (path === '/auth/sessions') return [];
  if (path === '/auth/users') return [];
  if (path === '/notifications/settings/telegram') return { configured: false };
  return {};
}

describe('active screen smoke matrix', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('alert', vi.fn());
    vi.stubGlobal('confirm', vi.fn(() => false));
    api.get.mockImplementation((path) => Promise.resolve({ data: responseFor(path) }));
    api.post.mockImplementation((path) => Promise.resolve({
      data: path.startsWith('/telemetry/') ? [] : {},
    }));
    api.put.mockResolvedValue({ data: {} });
    api.delete.mockResolvedValue({ data: {} });
  });

  it.each([
    ['Services', <ServicesPage />, /services/i],
    ['Devices', <DevicesPage />, /devices/i],
    ['Telemetry', <TelemetryPage />, /telemetry/i],
    ['Network', <NetworkPage />, /network/i],
    ['AdGuard', <AdGuardPage />, /adguard/i],
    ['IoT', <IoTPage onDeviceClick={vi.fn()} />, /iot/i],
    ['IoT detail', <IoTDeviceDetail deviceId="device-1" onBack={vi.fn()} />, /test device/i],
    ['Archive', <ArchivePage />, /veri arşivi/i],
    ['Projects', <ProjectsPage />, /projects/i],
    ['Files', <FilesPage />, /empty directory/i],
    ['Jobs', <JobsPage />, /jobs/i],
    ['Alerts', <AlertsPage />, /alerts/i],
    ['Settings', <SettingsPage />, /settings/i],
    ['Login', <Login />, /sign in to pi control/i],
    ['Terminal', <TerminalPage />, /connect/i],
  ])('renders the %s screen without a runtime failure', async (_name, component, expected) => {
    render(component);
    await waitFor(() => expect(screen.getAllByText(expected).length).toBeGreaterThan(0));
  });

  it('disconnects the active WiFi connection and refreshes status', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    api.get.mockImplementation((path) => Promise.resolve({
      data: path === '/network/wifi/status'
        ? {
            connected: true,
            ssid: 'Lab WiFi',
            ip: '192.168.1.5',
            signal_quality: 78,
            frequency: '5180 MHz',
          }
        : responseFor(path),
    }));

    render(<NetworkPage initialTab="wifi" />);
    fireEvent.click(await screen.findByRole('button', { name: 'DISCONNECT' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/network/wifi/disconnect');
    });
  });
});
