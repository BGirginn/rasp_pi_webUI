import { ThemeProvider } from './contexts/ThemeContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { NavigationProvider } from './contexts/NavigationContext';
import { Dashboard } from './components/Dashboard';

export default function App() {
    return (
        <ThemeProvider>
            <NavigationProvider>
                <DashboardProvider>
                    <Dashboard />
                </DashboardProvider>
            </NavigationProvider>
        </ThemeProvider>
    );
}
