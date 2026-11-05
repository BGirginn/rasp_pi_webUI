import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NetworkPage } from './NetworkPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({ api: { get: vi.fn() } }));
vi.mock('../hooks/useAuth', () => ({ useAuth: () => ({ isAdmin: true }) }));
vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'purple', isDarkMode: true }),
  getThemeColors: () => ({}),
}));

describe('network management after DNS filter removal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation(async (path) => ({
      data: path === '/network/interfaces' || path === '/network/wifi/networks'
        ? []
        : { enabled: false, paired_devices: [] },
    }));
  });

  it('keeps interfaces, WiFi and Bluetooth without DNS filter requests', async () => {
    render(<NetworkPage />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/network/interfaces'));
    expect(screen.queryByRole('button', { name: /DNS FILTER/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /WIFI NETWORKS/i }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/network/wifi/status'));

    fireEvent.click(screen.getByRole('button', { name: /BLUETOOTH/i }));
    await waitFor(() => expect(screen.getByText('Bluetooth adapter')).toBeInTheDocument());
    expect(api.get.mock.calls.some(([path]) => path.startsWith('/dns-filter'))).toBe(false);
  });
});
