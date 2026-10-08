import { lazy, Suspense } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { NavigationProvider } from './contexts/NavigationContext';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Loader from './components/common/Loader';

const Dashboard = lazy(() => import('./components/Dashboard').then(m => ({ default: m.Dashboard })));
const Login = lazy(() => import('./pages/Login'));

function AuthenticatedApp() {
    const { user, loading } = useAuth();

    if (loading) {
        return <Loader />;
    }

    if (!user) {
        if (window.location.pathname !== '/login') {
            window.history.replaceState(null, '', '/login');
        }
        return <Login />;
    }

    if (window.location.pathname !== '/') {
        window.history.replaceState(null, '', '/');
    }

    return (
        <NavigationProvider>
            <DashboardProvider>
                <Dashboard />
            </DashboardProvider>
        </NavigationProvider>
    );
}

export default function App() {
    return (
        <ThemeProvider>
            <AuthProvider>
                <Suspense fallback={<Loader />}>
                    <AuthenticatedApp />
                </Suspense>
            </AuthProvider>
        </ThemeProvider>
    );
}
