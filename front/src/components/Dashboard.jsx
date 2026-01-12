import { Sidebar } from './Sidebar';
import { ThemeSelector } from './ThemeSelector';
import { EditModeToggle } from './EditModeToggle';
import { DashboardGrid } from './DashboardGrid';
import { ServicesPage } from '../pages/ServicesPage';
import { DevicesPage } from '../pages/DevicesPage';
import { TelemetryPage } from '../pages/TelemetryPage';
import { NetworkPage } from '../pages/NetworkPage';
import { TerminalPage } from '../pages/TerminalPage';
import { AlertsPage } from '../pages/AlertsPage';
import { SettingsPage } from '../pages/SettingsPage';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useNavigation } from '../contexts/NavigationContext';
import { TopBarActions } from './TopBarActions';
export function Dashboard() {
    const { theme, isEditMode, isDarkMode } = useTheme();
    const { currentPage } = useNavigation();
    const themeColors = getThemeColors(theme);
    const renderPage = () => {
        switch (currentPage) {
            case 'dashboard':
                return (<>
            {isEditMode && (<div className={`mb-6 p-4 ${isDarkMode ? 'bg-purple-500/10 border-purple-500/30' : 'bg-purple-50 border-purple-300'} border rounded-xl`}>
                <p className={`text-sm ${isDarkMode ? 'text-purple-300' : 'text-purple-700'}`}>
                  🎨 Edit mode enabled - Drag widgets to reposition, click settings to resize/change variants, or add new widgets
                </p>
              </div>)}
            <DashboardGrid />
          </>);
            case 'services':
                return <ServicesPage />;
            case 'devices':
                return <DevicesPage />;
            case 'telemetry':
                return <TelemetryPage />;
            case 'network':
                return <NetworkPage />;
            case 'terminal':
                return <TerminalPage />;
            case 'alerts':
                return <AlertsPage />;
            case 'settings':
                return <SettingsPage />;
            default:
                return <DashboardGrid />;
        }
    };
    return (<div className={`min-h-screen ${isDarkMode ? 'bg-[#0a0a0f] text-white' : 'bg-gray-50 text-gray-900'} flex overflow-hidden relative`}>
      <Sidebar />
      
      <main className="flex-1 p-8 ml-64 relative z-10">
        {currentPage === 'dashboard' && (<div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className={`text-4xl mb-2 bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
                Dashboard
              </h1>
              <p className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>Welcome to Raspberry Pi Control</p>
            </div>
            <div className="flex items-center gap-4">
              <TopBarActions />
              <ThemeSelector />
              <EditModeToggle />
            </div>
          </div>)}

        {currentPage !== 'dashboard' && (<div className="mb-8 flex items-center justify-end">
            <div className="flex items-center gap-4">
              <TopBarActions />
              <ThemeSelector />
            </div>
          </div>)}

        {renderPage()}
      </main>
    </div>);
}
