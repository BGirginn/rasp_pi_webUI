import { createContext, useContext, useEffect, useState } from 'react';
const ThemeContext = createContext(undefined);
const themes = {
    purple: {
        primary: 'from-purple-600 via-violet-600 to-fuchsia-600',
        secondary: 'from-purple-500 to-fuchsia-500',
        accent: 'purple-500',
        accentRgb: '168, 85, 247',
        glow: 'rgba(168, 85, 247, 0.4)',
        lightPrimary: 'from-purple-700 via-violet-700 to-fuchsia-700',
        lightSecondary: 'from-purple-600 to-fuchsia-600',
        lightAccent: 'purple-600',
        lightGlow: 'rgba(168, 85, 247, 0.2)',
    },
    cyan: {
        primary: 'from-cyan-600 via-blue-600 to-teal-600',
        secondary: 'from-cyan-500 to-blue-500',
        accent: 'cyan-500',
        accentRgb: '6, 182, 212',
        glow: 'rgba(6, 182, 212, 0.4)',
        lightPrimary: 'from-cyan-700 via-blue-700 to-teal-700',
        lightSecondary: 'from-cyan-600 to-blue-600',
        lightAccent: 'cyan-600',
        lightGlow: 'rgba(6, 182, 212, 0.2)',
    },
    green: {
        primary: 'from-green-600 via-emerald-600 to-teal-600',
        secondary: 'from-green-500 to-emerald-500',
        accent: 'green-500',
        accentRgb: '34, 197, 94',
        glow: 'rgba(34, 197, 94, 0.4)',
        lightPrimary: 'from-green-700 via-emerald-700 to-teal-700',
        lightSecondary: 'from-green-600 to-emerald-600',
        lightAccent: 'green-600',
        lightGlow: 'rgba(34, 197, 94, 0.2)',
    },
    rainbow: {
        primary: 'from-cyan-500 via-purple-500 to-pink-500',
        secondary: 'from-pink-500 to-purple-500',
        accent: 'purple-500',
        accentRgb: '168, 85, 247',
        glow: 'rgba(168, 85, 247, 0.4)',
        lightPrimary: 'from-cyan-600 via-purple-600 to-pink-600',
        lightSecondary: 'from-pink-600 to-purple-600',
        lightAccent: 'purple-600',
        lightGlow: 'rgba(168, 85, 247, 0.2)',
    },
    sage: {
        primary: 'from-emerald-700 via-green-700 to-teal-700',
        secondary: 'from-emerald-600 to-teal-600',
        accent: 'emerald-600',
        accentRgb: '127, 169, 143',
        glow: 'rgba(127, 169, 143, 0.28)',
        lightPrimary: 'from-emerald-800 via-green-800 to-teal-800',
        lightSecondary: 'from-emerald-700 to-teal-700',
        lightAccent: 'emerald-700',
        lightGlow: 'rgba(127, 169, 143, 0.16)',
    },
};
export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
        const savedTheme = localStorage.getItem('pi-control-theme');
        return themes[savedTheme] ? savedTheme : 'purple';
    });
    const [isEditMode, setIsEditMode] = useState(false);
    const [isDarkMode, setIsDarkMode] = useState(() => {
        const savedMode = localStorage.getItem('pi-control-dark-mode');
        return savedMode === null ? true : savedMode === 'true';
    });

    useEffect(() => {
        localStorage.setItem('pi-control-theme', theme);
    }, [theme]);

    useEffect(() => {
        localStorage.setItem('pi-control-dark-mode', String(isDarkMode));
    }, [isDarkMode]);

    return (<ThemeContext.Provider value={{ theme, setTheme, isEditMode, setIsEditMode, isDarkMode, setIsDarkMode }}>
      {children}
    </ThemeContext.Provider>);
}
export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
}
export function getThemeColors(theme) {
    return themes[theme];
}
