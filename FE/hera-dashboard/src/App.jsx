import React, { useEffect, useState } from 'react';
import Home from './pages/Home';
import Login from './pages/Login';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import FloorPlanPage from './pages/FloorPlanPage';
import Sidebar from './components/layout/Sidebar';
import { getStoredUser, logoutUser } from './services/api';

// Tạo tạm 2 component rỗng cho Devices và Settings để code không bị lỗi
const Devices = () => (
  <div className="p-8 text-2xl font-semibold text-textMain">
    Device Management Coming Soon...
  </div>
);

const DASHBOARD_PAGE_KEY = 'hera_active_page';
const VALID_PAGES = new Set(['home', 'analytics', 'floorplan', 'devices', 'settings']);

const isPageReload = () => {
  const navigation = performance.getEntriesByType('navigation')[0];
  return navigation?.type === 'reload';
};

const getSavedDashboardPage = () => {
  const savedPage = localStorage.getItem(DASHBOARD_PAGE_KEY);
  return VALID_PAGES.has(savedPage) ? savedPage : 'home';
};

const App = () => {
  const [shouldResetOnOpen] = useState(() => !isPageReload());
  const [user, setUser] = useState(() => shouldResetOnOpen ? null : getStoredUser());
  const [activePage, setActivePage] = useState(() => shouldResetOnOpen ? 'home' : getSavedDashboardPage());
  const [isSidebarExpanded, setIsSidebarExpanded] = useState(false);

  useEffect(() => {
    if (!shouldResetOnOpen) return;
    logoutUser();
    localStorage.removeItem(DASHBOARD_PAGE_KEY);
  }, [shouldResetOnOpen]);

  useEffect(() => {
    if (!user || !VALID_PAGES.has(activePage)) return;
    localStorage.setItem(DASHBOARD_PAGE_KEY, activePage);
  }, [activePage, user]);

  if (!user) {
    return <Login onLoginSuccess={setUser} />;
  }

  const handleLogout = () => {
    logoutUser();
    localStorage.removeItem(DASHBOARD_PAGE_KEY);
    setUser(null);
    setActivePage('home');
  };

  const renderPage = () => {
    switch (activePage) {
      case 'analytics':
        return <Analytics />;
      case 'floorplan':
        return <FloorPlanPage />;
      case 'devices':
        return <Devices />;
      case 'settings':
        return <Settings />;
      case 'home':
      default:
        return <Home user={user} onLogout={handleLogout} />;
    }
  };

  return (
    <div className={`min-h-screen bg-background transition-all duration-300 ${isSidebarExpanded ? 'pl-64' : 'pl-0'}`}>
      <Sidebar 
        activePage={activePage} 
        setActivePage={setActivePage} 
        isExpanded={isSidebarExpanded}
        setIsExpanded={setIsSidebarExpanded}
      />
      <main className="min-h-screen w-full overflow-hidden">
        {renderPage()}
      </main>
    </div>
  );
};

export default App;
