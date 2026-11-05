import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ServicesPage } from './ServicesPage';
import FilesPage from './FilesPage';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

vi.mock('../services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../hooks/useAuth', () => ({ useAuth: vi.fn() }));
vi.mock('../contexts/ThemeContext', () => ({
    useTheme: () => ({ theme: 'sage', isDarkMode: true }),
    getThemeColors: () => ({}),
}));

const service = {
    id: 'systemd-demo',
    name: 'demo',
    provider: 'systemd',
    resource_class: 'APP',
    state: 'running',
    unit_file_state: 'enabled',
    allowed_actions: ['start', 'stop', 'restart'],
    cpu_usage: 1.2,
    memory_usage: 2.1,
};
const file = {
    name: 'notes.txt',
    path: '/srv/demo/notes.txt',
    type: 'file',
    size: 42,
    modified: '2026-11-05T08:00:00',
    permissions: '600',
    is_hidden: false,
};
beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { role: 'admin' }, isAdmin: true, isOperator: true });
    api.get.mockImplementation(async (path) => {
        if (path.startsWith('/resources')) return { data: [service] };
        if (path.startsWith('/logs/'))
            return { data: { lines: [{ timestamp: '', level: 'info', message: 'Real service started' }] } };
        if (path === '/files/roots') return { data: { roots: ['/srv/demo'] } };
        return { data: [file] };
    });
    api.post.mockResolvedValue({ data: { message: 'Complete' } });
});

describe('daily operations workspace', () => {
    it('opens service details and real logs; surfaces a log refresh failure', async () => {
        render(<ServicesPage />);
        fireEvent.click(await screen.findByRole('button', { name: 'Inspect demo' }));
        expect(await screen.findByText('Real service started')).toBeInTheDocument();
        api.get.mockRejectedValueOnce(new Error('Agent unavailable'));
        fireEvent.click(screen.getByRole('button', { name: 'Refresh logs' }));
        expect(await screen.findByText('Agent unavailable')).toBeInTheDocument();
    });
    it('confirms a stop explicitly and displays the verified resulting state', async () => {
        api.post.mockResolvedValue({ data: { data: { resource: { ...service, state: 'stopped' } } } });
        render(<ServicesPage />);
        fireEvent.click(await screen.findByRole('button', { name: 'Stop demo' }));
        expect(api.post).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'Confirm stop' }));
        await waitFor(() =>
            expect(api.post).toHaveBeenCalledWith('/resources/systemd-demo/action', { action: 'stop' })
        );
        expect(await screen.findByText('demo stopped successfully')).toBeInTheDocument();
    });
    it('starts file browsing inside an allowed root and wires a copy to an explicit target', async () => {
        render(<FilesPage />);
        fireEvent.click(await screen.findByRole('button', { name: 'Inspect notes.txt' }));
        expect(api.get).toHaveBeenCalledWith('/files/list?path=%2Fsrv%2Fdemo', expect.any(Object));
        expect(screen.getByRole('button', { name: 'Parent folder' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
        fireEvent.change(screen.getByLabelText('Destination path'), { target: { value: '/srv/demo/notes-copy.txt' } });
        fireEvent.click(screen.getByRole('button', { name: 'Confirm copy' }));
        await waitFor(() =>
            expect(api.post).toHaveBeenCalledWith('/files/action', {
                action: 'copy',
                path: file.path,
                destination: '/srv/demo/notes-copy.txt',
            })
        );
    });
    it('shows setup when there are no allowed roots and never requests the filesystem root', async () => {
        api.get.mockResolvedValue({ data: { roots: [] } });
        render(<FilesPage />);
        expect(await screen.findByText('No file roots configured')).toBeInTheDocument();
        expect(api.get).toHaveBeenCalledTimes(1);
        expect(screen.queryByPlaceholderText('System Root/Sudo Password')).not.toBeInTheDocument();
    });
    it('keeps conflicts visible in the operation form without claiming success', async () => {
        api.post.mockRejectedValue(new Error('Destination already exists'));
        render(<FilesPage />);
        fireEvent.click(await screen.findByRole('button', { name: 'Inspect notes.txt' }));
        fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
        fireEvent.change(screen.getByLabelText('New name'), { target: { value: 'existing.txt' } });
        fireEvent.click(screen.getByRole('button', { name: 'Confirm rename' }));
        expect(await screen.findByText('Destination already exists')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Confirm rename' })).toBeEnabled();
    });
    it('keeps a failed upload visible and never reports completion', async () => {
        api.post.mockRejectedValue(new Error('No space left on device'));
        render(<FilesPage />);
        await screen.findByRole('button', { name: 'Inspect notes.txt' });
        fireEvent.change(screen.getByLabelText('Upload files'), {
            target: { files: [new File(['data'], 'upload.txt')] },
        });
        expect(await screen.findByRole('alert')).toHaveTextContent('upload.txt: No space left on device');
        expect(screen.queryByText('1 file uploaded.')).not.toBeInTheDocument();
    });
    it('rejects viewer file access and hides service actions', async () => {
        useAuth.mockReturnValue({ user: { role: 'viewer' }, isAdmin: false, isOperator: false });
        const view = render(<FilesPage />);
        expect(screen.getByText('File access requires an operator or administrator')).toBeInTheDocument();
        expect(api.get).not.toHaveBeenCalled();
        view.unmount();
        render(<ServicesPage />);
        await screen.findByRole('button', { name: 'Inspect demo' });
        expect(screen.queryByRole('button', { name: 'Stop demo' })).not.toBeInTheDocument();
    });
    it('ignores late log responses from an earlier service selection', async () => {
        let resolveFirst;
        api.get.mockImplementation(async (path) => {
            if (path === '/resources') return { data: [service, { ...service, id: 'systemd-second', name: 'second' }] };
            if (path.startsWith('/logs/systemd-demo'))
                return new Promise((resolve) => {
                    resolveFirst = resolve;
                });
            return { data: { lines: [{ level: 'info', message: 'Second log' }] } };
        });
        render(<ServicesPage />);
        fireEvent.click(await screen.findByRole('button', { name: 'Inspect demo' }));
        fireEvent.click(screen.getByRole('button', { name: 'Inspect second' }));
        await screen.findByText('Second log');
        resolveFirst({ data: { lines: [{ level: 'info', message: 'Stale log' }] } });
        await waitFor(() => expect(screen.queryByText('Stale log')).not.toBeInTheDocument());
        expect(screen.getByText('Second log')).toBeInTheDocument();
    });
});
