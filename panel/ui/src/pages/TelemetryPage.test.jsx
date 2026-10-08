import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TelemetryPage } from './TelemetryPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'purple', isDarkMode: true }),
  getThemeColors: () => ({}),
}));
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  LineChart: ({ data, children }) => <div data-testid="history-chart" data-rows={JSON.stringify(data)}>{children}</div>,
  Line: ({ dataKey, dot }) => <span data-testid={`line-${dataKey}`} data-dot={JSON.stringify(dot)} />,
  XAxis: () => null, YAxis: () => null, CartesianGrid: () => null, Tooltip: () => null,
}));

function historyResponse(body) {
  const ts = Math.floor(Date.now() / 1000) - 90;
  const values = {
    'host.cpu.pct_total': [0, 10, 20],
    'disk.root.used_pct': [70, 71, 72],
    'host.power.input_voltage_v': [4.9, 5, 4.95],
    'host.power.pmic.vdd_core.current_a': [0.5, 0.6, 0.4],
  };
  return { data: body.metrics.split(',').map((metric) => ({ metric, points: (values[metric] || []).map((value, index) => ({ ts: ts + index * 30, value })) })) };
}

describe('recorded power and performance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: { metrics: {
      'host.power.input_voltage_v': 5,
      'host.power.pmic.vdd_core.voltage_v': 0.75,
      'host.power.pmic.vdd_core.current_a': 0.5,
      'host.power.pmic.ext5v.voltage_v': 5,
    } } });
    api.post.mockImplementation((path, body) => Promise.resolve(historyResponse(body)));
  });

  it('connects recorded 30-second live samples and queries the canonical disk metric', async () => {
    render(<TelemetryPage />);
    const table = await screen.findByRole('table', { name: 'System performance statistics' });
    expect(api.post.mock.calls[0][1].step).toBe(30);
    expect(api.post.mock.calls[0][1].metrics).toContain('disk.root.used_pct');
    const rows = JSON.parse(screen.getAllByTestId('history-chart')[1].dataset.rows);
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.cpu)).toEqual([0, 10, 20]);
    expect(within(table).getByRole('row', { name: /CPU 20.0% 10.0% 0.0% 20.0% 3/ })).toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /Disk 72.0%/ })).toBeInTheDocument();
    const rails = screen.getByRole('table', { name: 'Power rail measurements' });
    expect(within(rails).getByRole('row', { name: /VDD CORE 0.750 500.0 375.0/ })).toBeInTheDocument();
    expect(within(rails).getByRole('row', { name: /EXT5V 5.000 — —/ })).toBeInTheDocument();
  });

  it('keeps single samples visible and preserves an actual recording outage', async () => {
    api.post.mockImplementation((path, body) => {
      const response = historyResponse(body);
      response.data[0].points = [{ ts: 100, value: 1 }];
      const cpu = response.data.find((series) => series.metric === 'host.cpu.pct_total');
      cpu.points = [{ ts: 100, value: 0 }, { ts: 130, value: 10 }, { ts: 400, value: 20 }];
      return Promise.resolve(response);
    });
    render(<TelemetryPage />);
    await screen.findByRole('table', { name: 'System performance statistics' });
    fireEvent.click(screen.getByRole('button', { name: 'Internet Reachability' }));
    expect(screen.getByTestId('line-internet').dataset.dot).toBe('{"r":4}');
    const rows = JSON.parse(screen.getAllByTestId('history-chart')[1].dataset.rows);
    expect(rows.some((row) => row.ts === 160 && row.cpu === undefined)).toBe(true);
  });

  it('reports a failed history request even when the current request succeeds', async () => {
    api.post.mockRejectedValue(new Error('offline'));
    render(<TelemetryPage />);
    await waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2));
    expect(screen.queryByText('No historical telemetry available for this range')).not.toBeInTheDocument();
  });
  it('ignores an older request after switching the time range', async () => {
    const requests = [];
    api.post.mockImplementation((path, body) => new Promise((resolve) => requests.push({ body, resolve })));
    render(<TelemetryPage />);
    fireEvent.click(screen.getByRole('button', { name: '1 Hour' }));
    expect(requests).toHaveLength(2);
    const reply = (request, value) => {
      const result = historyResponse(request.body);
      result.data.find((series) => series.metric === 'host.cpu.pct_total').points = [{ ts: 100, value }];
      request.resolve(result);
    };
    await act(async () => reply(requests[1], 42));
    const table = screen.getByRole('table', { name: 'System performance statistics' });
    expect(within(table).getByRole('row', { name: /CPU 42.0%/ })).toBeInTheDocument();
    await act(async () => reply(requests[0], 99));
    expect(within(table).getByRole('row', { name: /CPU 42.0%/ })).toBeInTheDocument();
  });

});
