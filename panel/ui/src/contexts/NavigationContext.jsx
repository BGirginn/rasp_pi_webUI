import { createContext, useCallback, useContext, useEffect, useState } from 'react';

const NavigationContext = createContext(undefined);
const pages = new Set([
  'dashboard', 'telemetry', 'alerts', 'services', 'devices', 'iot', 'network',
  'projects', 'jobs', 'archive', 'terminal', 'files', 'settings',
]);

function readPage() {
  const page = window.location.hash.replace(/^#\/?/, '');
  return pages.has(page) ? page : 'dashboard';
}

export function NavigationProvider({ children }) {
  const [currentPage, updatePage] = useState(readPage);
  const setCurrentPage = useCallback((page) => {
    if (!pages.has(page)) return;
    if (window.location.hash !== `#/${page}`) {
      window.history.pushState(null, '', `#/${page}`);
    }
    updatePage(page);
  }, []);

  useEffect(() => {
    const syncPage = () => {
      const page = readPage();
      if (window.location.hash !== `#/${page}`) {
        window.history.replaceState(null, '', `#/${page}`);
      }
      updatePage(page);
    };
    syncPage();
    window.addEventListener('hashchange', syncPage);
    window.addEventListener('popstate', syncPage);
    return () => {
      window.removeEventListener('hashchange', syncPage);
      window.removeEventListener('popstate', syncPage);
    };
  }, []);

  return <NavigationContext.Provider value={{ currentPage, setCurrentPage }}>{children}</NavigationContext.Provider>;
}

export function useNavigation() {
  const context = useContext(NavigationContext);
  if (context === undefined) throw new Error('useNavigation must be used within a NavigationProvider');
  return context;
}
