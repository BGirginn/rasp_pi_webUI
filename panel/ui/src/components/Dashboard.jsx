import { Suspense, lazy, useState } from 'react';
import { Sidebar } from './Sidebar';
import { ThemeSelector } from './ThemeSelector';
import { EditModeToggle } from './EditModeToggle';
import { DashboardGrid } from './DashboardGrid';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useNavigation } from '../contexts/NavigationContext';
import { useAuth } from '../hooks/useAuth';
import { TopBarActions } from './TopBarActions';
import Loader from './common/Loader';

const ServicesPage = lazy(() => import('../pages/ServicesPage').then(mod => ({ default: mod.ServicesPage })));
const DevicesPage = lazy(() => import('../pages/DevicesPage').then(mod => ({ default: mod.DevicesPage })));
const TelemetryPage = lazy(() => import('../pages/TelemetryPage').then(mod => ({ default: mod.TelemetryPage })));
const NetworkPage = lazy(() => import('../pages/NetworkPage').then(mod => ({ default: mod.NetworkPage })));
const AdGuardPage = lazy(() => import('../pages/NetworkPage').then(mod => ({ default: mod.AdGuardPage })));
const TerminalPage = lazy(() => import('../pages/TerminalPage').then(mod => ({ default: mod.TerminalPage })));
const AlertsPage = lazy(() => import('../pages/AlertsPage').then(mod => ({ default: mod.AlertsPage })));
const SettingsPage = lazy(() => import('../pages/SettingsPage').then(mod => ({ default: mod.SettingsPage })));
const IoTPage = lazy(() => import('../pages/IoTPage').then(mod => ({ default: mod.IoTPage })));
const IoTDeviceDetail = lazy(() => import('../pages/IoTDeviceDetail').then(mod => ({ default: mod.IoTDeviceDetail })));
const ArchivePage = lazy(() => import('../pages/ArchivePage').then(mod => ({ default: mod.ArchivePage })));
const ProjectsPage = lazy(() => import('../pages/ProjectsPage').then(mod => ({ default: mod.ProjectsPage })));
const FilesPage = lazy(() => import('../pages/FilesPage'));
const JobsPage = lazy(() => import('../pages/Jobs'));
const AppStorePage = lazy(() => import('../pages/AppStorePage').then(mod => ({ default: mod.AppStorePage })));

export function Dashboard() {
  const { theme, isEditMode, isDarkMode } = useTheme();
  const { currentPage } = useNavigation();
  const { isAdmin } = useAuth();
  const themeColors = getThemeColors(theme);

  // State for IoT device detail view
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);

  // Handle device click from IoT page
  const handleDeviceClick = (deviceId) => {
    setSelectedDeviceId(deviceId);
  };

  // Handle back from device detail
  const handleBackFromDevice = () => {
    setSelectedDeviceId(null);
  };

  const renderPage = () => {
    // If we're on IoT page and a device is selected, show detail
    if (currentPage === 'iot' && selectedDeviceId) {
      return <IoTDeviceDetail deviceId={selectedDeviceId} onBack={handleBackFromDevice} />;
    }

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
      case 'adguard':
        return <AdGuardPage />;
      case 'iot':
        return <IoTPage onDeviceClick={handleDeviceClick} />;
      case 'terminal':
        return isAdmin ? <TerminalPage /> : (
          <div className={`p-8 rounded-2xl border ${isDarkMode ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-red-50 border-red-200 text-red-600'}`}>
            <h2 className="text-2xl font-bold mb-2">Access Denied</h2>
            <p>You do not have permission to access the terminal.</p>
          </div>
        );
      case 'alerts':
        return <AlertsPage />;
      case 'files':
        return isAdmin ? <FilesPage /> : (
          <div className={`p-8 rounded-2xl border ${isDarkMode ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-red-50 border-red-200 text-red-600'}`}>
            <h2 className="text-2xl font-bold mb-2">Access Denied</h2>
            <p>You do not have permission to access the file manager.</p>
          </div>
        );
      case 'projects':
        return <ProjectsPage />;
      case 'jobs':
        return <JobsPage />;
      case 'appstore':
        return <AppStorePage />;
      case 'settings':
        return <SettingsPage />;
      case 'archive':
        return <ArchivePage />;
      default:
        return <DashboardGrid />;
    }
  };

  return (<div className={`min-h-screen ${isDarkMode ? 'bg-[#0a0a0f] text-white' : 'bg-gray-50 text-gray-900'} flex flex-col md:flex-row overflow-x-hidden relative`}>
    <Sidebar />

    <main className="flex-1 p-4 md:p-8 md:ml-0 relative z-10 min-w-0">
      {currentPage === 'dashboard' && (<div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className={`text-4xl mb-2 bg-gradient-to-r ${isDarkMode ? themeColors.primary : themeColors.lightPrimary} bg-clip-text text-transparent`}>
            Dashboard
          </h1>
          <p className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>Welcome to Raspberry Pi Control</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <TopBarActions />
          <ThemeSelector />
          <EditModeToggle />
        </div>
      </div>)}

      {currentPage !== 'dashboard' && (<div className="mb-8 flex items-center justify-start lg:justify-end">
        <div className="flex flex-wrap items-center gap-3">
          <TopBarActions />
          <ThemeSelector />
        </div>
      </div>)}

      <Suspense fallback={<Loader fullScreen={false} />}>
        {renderPage()}
      </Suspense>
    </main>
  </div>);
}
