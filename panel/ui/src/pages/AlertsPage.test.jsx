import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertsPage } from './AlertsPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ isAdmin: true, isOperator: true }),
}));

describe('AlertsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((path) => Promise.resolve({
      data: path === '/alerts'
        ? [{ id: 'a1', rule_id: 'r1', rule_name: 'CPU', state: 'firing', severity: 'critical', message: 'Hot', value: 91 }]
        : [{ id: 'r1', name: 'CPU', description: 'CPU load', metric: 'host.cpu.pct_total', condition: 'gt', threshold: 80, severity: 'critical', cooldown_minutes: 15, enabled: true }],
    }));
    api.post.mockResolvedValue({ data: {} });
    api.delete.mockResolvedValue({ data: {} });
  });

  it('loads live alerts and acknowledges an active alert', async () => {
    const user = userEvent.setup();
    render(<AlertsPage />);

    expect(await screen.findByText('Hot')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^✓ acknowledge$/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/alerts/a1/acknowledge'));
  });

  it('creates a rule with form values and refreshes rules', async () => {
    const user = userEvent.setup();
    render(<AlertsPage />);
    await screen.findByText('Hot');

    await user.click(screen.getByRole('button', { name: /create rule/i }));
    await user.type(screen.getByPlaceholderText('High CPU Usage'), 'Disk full');
    await user.click(screen.getByRole('button', { name: /^create rule$/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/alerts/rules',
      expect.objectContaining({ name: 'Disk full' }),
    ));
  });
});
