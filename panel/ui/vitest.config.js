import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
    plugins: [react()],
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: './src/test/setup.js',
        css: true,
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json-summary'],
            exclude: [
                'node_modules/',
                'src/test/',
                '**/*.test.{js,jsx}',
                'src/components/ui/**',
            ],
        },
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
});
