import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';
import { api } from '../services/api';

const refreshUser = vi.fn();

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', role: 'admin', has_totp: false },
    isAdmin: true,
    refreshUser,
  }),
}));

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'purple', isDarkMode: true }),
  getThemeColors: () => ({ primary: 'from-purple-600 to-fuchsia-600', lightPrimary: 'from-purple-700 to-fuchsia-700' }),
}));

describe('SettingsPage actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('alert', vi.fn());
    vi.stubGlobal('confirm', vi.fn(() => true));
    api.get.mockImplementation((path) => Promise.resolve({
      data: path === '/auth/sessions' ? [] : { configured: false },
    }));
    api.post.mockResolvedValue({ data: {} });
    api.put.mockResolvedValue({ data: {} });
    api.delete.mockResolvedValue({ data: {} });
  });

  it('submits a validated password change', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.type(screen.getByPlaceholderText('Enter current password'), 'current-pass');
    await user.type(screen.getByPlaceholderText('Enter new password'), 'new-pass-123');
    await user.type(screen.getByPlaceholderText('Confirm new password'), 'new-pass-123');
    await user.click(screen.getByRole('button', { name: 'Change Password' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/auth/password/change', {
      current_password: 'current-pass',
      new_password: 'new-pass-123',
    }));
  });

  it('starts and verifies TOTP setup', async () => {
    const user = userEvent.setup();
    api.post.mockImplementation((path) => Promise.resolve({
      data: path === '/auth/totp/setup'
        ? { secret: 'SECRET123', provisioning_uri: 'otpauth://totp/PiControl:admin' }
        : {},
    }));
    render(<SettingsPage />);

    await user.click(screen.getByRole('button', { name: 'Security' }));
    await user.click(screen.getByRole('button', { name: 'Enable 2FA' }));
    expect(await screen.findByText('SECRET123')).toBeInTheDocument();

    await user.type(screen.getByLabelText('TOTP verification code'), '123456');
    await user.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/auth/totp/verify', { code: '123456' }));
    expect(refreshUser).toHaveBeenCalled();
  });
});
