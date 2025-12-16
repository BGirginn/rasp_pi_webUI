import { Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Services from './pages/Services'
import Devices from './pages/Devices'
import Telemetry from './pages/Telemetry'
import Jobs from './pages/Jobs'
import Settings from './pages/Settings'
import Alerts from './pages/Alerts'
import Network from './pages/Network'
import Terminal from './pages/Terminal'

// Auth context
import { AuthProvider, useAuth } from './hooks/useAuth'

// Protected route wrapper
function ProtectedRoute({ children }) {
    const { user, loading } = useAuth()

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-900">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    if (!user) {
        return <Navigate to="/login" replace />
    }

    return children
}

function App() {
    return (
        <AuthProvider>
            <Routes>
                <Route path="/login" element={<Login />} />

                <Route
                    path="/"
                    element={
                        <ProtectedRoute>
                            <Layout />
                        </ProtectedRoute>
                    }
                >
                    <Route index element={<Dashboard />} />
                    <Route path="services" element={<Services />} />
                    <Route path="devices" element={<Devices />} />
                    <Route path="telemetry" element={<Telemetry />} />
                    <Route path="jobs" element={<Jobs />} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="network" element={<Network />} />
                    <Route path="terminal" element={<Terminal />} />
                    <Route path="settings" element={<Settings />} />
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </AuthProvider>
    )
}

export default App

