/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,jsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                // Cyberpunk Purple Palette
                primary: {
                    50: '#faf5ff',
                    100: '#f3e8ff',
                    200: '#e9d5ff',
                    300: '#d8b4fe',
                    400: '#c084fc',
                    500: '#a855f7',
                    600: '#9333ea',
                    700: '#7c3aed',
                    800: '#6b21a8',
                    900: '#581c87',
                    950: '#3b0764',
                },
                // Background colors
                dark: {
                    50: '#1f1f2e',
                    100: '#1a1a24',
                    200: '#13131a',
                    300: '#0a0a0f',
                    400: '#050508',
                },
                // Semantic colors
                success: {
                    400: '#4ade80',
                    500: '#22c55e',
                    600: '#16a34a',
                },
                warning: {
                    400: '#fbbf24',
                    500: '#f59e0b',
                    600: '#d97706',
                },
                danger: {
                    400: '#f87171',
                    500: '#ef4444',
                    600: '#dc2626',
                },
                info: {
                    400: '#60a5fa',
                    500: '#3b82f6',
                    600: '#2563eb',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'spin-slow': 'spin 3s linear infinite',
                'glow': 'glow 3s ease-in-out infinite',
                'float': 'float 3s ease-in-out infinite',
            },
            keyframes: {
                glow: {
                    '0%, 100%': { boxShadow: '0 0 20px rgba(139, 92, 246, 0.3)' },
                    '50%': { boxShadow: '0 0 40px rgba(139, 92, 246, 0.5)' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-5px)' },
                },
            },
            boxShadow: {
                'neon': '0 0 20px rgba(139, 92, 246, 0.4)',
                'neon-lg': '0 0 40px rgba(139, 92, 246, 0.5)',
                'neon-success': '0 0 20px rgba(34, 197, 94, 0.4)',
                'neon-danger': '0 0 20px rgba(239, 68, 68, 0.4)',
            },
            backgroundImage: {
                'aurora': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(139, 92, 246, 0.15) 0%, transparent 50%)',
                'aurora-intense': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(139, 92, 246, 0.25) 0%, transparent 50%)',
                'gradient-purple': 'linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%)',
                'gradient-purple-pink': 'linear-gradient(135deg, #8b5cf6 0%, #c084fc 50%, #a855f7 100%)',
            },
        },
    },
    plugins: [],
}
