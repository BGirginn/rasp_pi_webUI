import { describe, it, expect, beforeEach, vi } from 'vitest';

// Simple localStorage mock
const store = {};
const localStorageMock = {
    getItem: (key) => store[key] ?? null,
    setItem: (key, value) => { store[key] = String(value); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { Object.keys(store).forEach(k => delete store[k]); },
};
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true });

// We need to re-import the module fresh for each test
let api;

beforeEach(async () => {
    vi.restoreAllMocks();
    localStorageMock.clear();
    // Reset module cache
    vi.resetModules();
    const mod = await import('./api.js');
    api = mod.api;
});

describe('ApiService', () => {
    it('should add Authorization header when token exists', async () => {
        localStorage.setItem('access_token', 'test-token');

        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({ data: 'test' }),
        });

        await api.get('/test');

        expect(global.fetch).toHaveBeenCalledWith(
            '/api/test',
            expect.objectContaining({
                headers: expect.objectContaining({
                    Authorization: 'Bearer test-token',
                }),
            })
        );
    });

    it('should not add Authorization header when no token', async () => {
        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({}),
        });

        await api.get('/test');

        const callHeaders = global.fetch.mock.calls[0][1].headers;
        expect(callHeaders.Authorization).toBeUndefined();
    });

    it('should retry with refreshed token on 401', async () => {
        localStorage.setItem('access_token', 'old-token');

        global.fetch = vi.fn()
            // First call returns 401
            .mockResolvedValueOnce({
                ok: false,
                status: 401,
                json: async () => ({}),
            })
            // Refresh call succeeds
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: async () => ({ access_token: 'new-token' }),
            })
            // Retry call succeeds
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: async () => ({ data: 'success' }),
            });

        const result = await api.get('/test');

        expect(result.data.data).toBe('success');
        expect(localStorage.getItem('access_token')).toBe('new-token');
    });

    it('should only refresh once for concurrent 401s (singleton pattern)', async () => {
        localStorage.setItem('access_token', 'old-token');

        let refreshCallCount = 0;

        global.fetch = vi.fn().mockImplementation(async (url) => {
            if (url.includes('/auth/refresh')) {
                refreshCallCount++;
                // Simulate some delay
                await new Promise((r) => setTimeout(r, 50));
                return {
                    ok: true,
                    status: 200,
                    json: async () => ({ access_token: 'new-token' }),
                };
            }
            // First calls return 401, retries return 200
            const token = localStorage.getItem('access_token');
            if (token === 'old-token') {
                return { ok: false, status: 401, json: async () => ({}) };
            }
            return { ok: true, status: 200, json: async () => ({ data: 'ok' }) };
        });

        // Make concurrent requests
        await Promise.allSettled([api.get('/test1'), api.get('/test2'), api.get('/test3')]);

        // Should only have called refresh once
        expect(refreshCallCount).toBe(1);
    });

    it('should throw on non-ok response', async () => {
        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            json: async () => ({ detail: 'Something went wrong' }),
        });

        await expect(api.get('/test')).rejects.toThrow('Something went wrong');
    });

    it('should send JSON body on POST', async () => {
        localStorage.setItem('access_token', 'token');

        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({ created: true }),
        });

        await api.post('/items', { name: 'test' });

        const callConfig = global.fetch.mock.calls[0][1];
        expect(callConfig.method).toBe('POST');
        expect(callConfig.body).toBe(JSON.stringify({ name: 'test' }));
    });

    it('should return blob responses for downloads', async () => {
        const blob = new Blob(['archive-data'], { type: 'application/json' });

        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: true,
            status: 200,
            blob: async () => blob,
            clone: () => ({
                json: async () => ({}),
                text: async () => '',
            }),
            headers: new Headers({
                'content-disposition': 'attachment; filename="daily_2026-03-11_telemetry.json"',
            }),
        });

        const result = await api.get('/archive/export/telemetry', { responseType: 'blob' });

        expect(result.data).toBe(blob);
        expect(result.headers.get('content-disposition')).toContain('daily_2026-03-11_telemetry.json');
    });
});
