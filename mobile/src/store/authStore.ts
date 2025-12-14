import { create } from 'zustand';
import { api } from '../services/api';

interface User {
    id: number;
    username: string;
    role: string;
}

interface AuthState {
    user: User | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    login: (username: string, password: string) => Promise<boolean>;
    logout: () => Promise<void>;
    checkAuth: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isLoading: true,
    isAuthenticated: false,

    login: async (username: string, password: string) => {
        try {
            const { data } = await api.post<{ access_token: string; user: User }>(
                '/auth/login',
                { username, password }
            );
            await api.setToken(data.access_token);
            set({ user: data.user, isAuthenticated: true, isLoading: false });
            return true;
        } catch (error) {
            set({ user: null, isAuthenticated: false, isLoading: false });
            return false;
        }
    },

    logout: async () => {
        try {
            await api.post('/auth/logout');
        } catch (error) {
            // Ignore logout errors
        }
        await api.setToken(null);
        set({ user: null, isAuthenticated: false });
    },

    checkAuth: async () => {
        set({ isLoading: true });
        const token = await api.loadToken();
        if (!token) {
            set({ user: null, isAuthenticated: false, isLoading: false });
            return false;
        }

        try {
            const { data } = await api.get<User>('/auth/me');
            set({ user: data, isAuthenticated: true, isLoading: false });
            return true;
        } catch (error) {
            await api.setToken(null);
            set({ user: null, isAuthenticated: false, isLoading: false });
            return false;
        }
    },
}));
