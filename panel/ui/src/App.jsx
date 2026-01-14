import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { NavigationProvider } from './contexts/NavigationContext';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { Dashboard } from './components/Dashboard';
import Login from './pages/Login';

import Loader from './components/common/Loader';

// Protected Route wrapper
function ProtectedRoute({ children }) {
    const { user, loading } = useAuth();

    if (loading) {
        return <Loader />;
    }

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    return children;
}

// Public Route - redirect to dashboard if already logged in
function PublicRoute({ children }) {
    const { user, loading } = useAuth();

    if (loading) {
        return <Loader />;
    }

    if (user) {
        return <Navigate to="/" replace />;
    }

    return children;
}

function AppRoutes() {
    return (
        <Routes>
            <Route
                path="/login"
                element={
                    <PublicRoute>
                        <Login />
                    </PublicRoute>
                }
            />
            <Route
                path="/*"
                element={
                    <ProtectedRoute>
                        <NavigationProvider>
                            <DashboardProvider>
                                <Dashboard />
                            </DashboardProvider>
                        </NavigationProvider>
                    </ProtectedRoute>
                }
            />
        </Routes>
    );
}

export default function App() {
    return (
        <ThemeProvider>
            <AuthProvider>
                <AppRoutes />
            </AuthProvider>
        </ThemeProvider>
    );
}
