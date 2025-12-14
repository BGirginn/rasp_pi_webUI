import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'http://100.80.90.68:8080/api';

interface ApiResponse<T> {
    data: T;
    status: number;
}

class ApiClient {
    private baseUrl: string;
    private token: string | null = null;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    async setToken(token: string | null) {
        this.token = token;
        if (token) {
            await AsyncStorage.setItem('authToken', token);
        } else {
            await AsyncStorage.removeItem('authToken');
        }
    }

    async loadToken() {
        this.token = await AsyncStorage.getItem('authToken');
        return this.token;
    }

    private async request<T>(
        method: string,
        endpoint: string,
        data?: any
    ): Promise<ApiResponse<T>> {
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const config: RequestInit = {
            method,
            headers,
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, config);

        if (response.status === 401) {
            // Token expired
            await this.setToken(null);
            throw new Error('Session expired');
        }

        const responseData = response.status !== 204 ? await response.json() : {};

        if (!response.ok) {
            throw new Error(responseData.detail || 'Request failed');
        }

        return {
            data: responseData,
            status: response.status,
        };
    }

    get<T>(endpoint: string) {
        return this.request<T>('GET', endpoint);
    }

    post<T>(endpoint: string, data?: any) {
        return this.request<T>('POST', endpoint, data);
    }

    put<T>(endpoint: string, data?: any) {
        return this.request<T>('PUT', endpoint, data);
    }

    delete<T>(endpoint: string) {
        return this.request<T>('DELETE', endpoint);
    }
}

export const api = new ApiClient(API_BASE_URL);
export default api;
