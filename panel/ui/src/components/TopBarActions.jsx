import { motion } from 'motion/react';
import { Bell, Terminal } from 'lucide-react';
import { useNavigation } from '../contexts/NavigationContext';
import { useEffect, useState } from 'react';
import { api } from '../services/api';

export function TopBarActions() {
  const { setCurrentPage } = useNavigation();
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    async function loadAlerts() {
      try {
        const response = await api.get('/alerts');
        // Count only firing alerts
        const firingCount = response.data.filter(a => a.state === 'firing').length;
        setAlertCount(firingCount);
      } catch (err) {
        // Silently fail
      }
    }
    loadAlerts();
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  return (<div className="topbar-quick-actions">
    <motion.button whileTap={{ scale: 0.96 }} onClick={() => setCurrentPage('alerts')} className="icon-button" title="Alerts">
      <Bell size={18} />
      {alertCount > 0 && (
        <span className="notification-count">
          {alertCount > 99 ? '99+' : alertCount}
        </span>
      )}
    </motion.button>

    <motion.button whileTap={{ scale: 0.96 }} onClick={() => setCurrentPage('terminal')} className="icon-button" title="Terminal">
      <Terminal size={18} />
    </motion.button>
  </div>);
}
