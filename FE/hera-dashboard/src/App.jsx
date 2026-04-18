import React, { useEffect, useState } from 'react';
import Home from './pages/Home';
import Login from './pages/Login';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import Sidebar from './components/layout/Sidebar';
import { getStoredUser, logoutUser } from './services/api';

// Tạo tạm 2 component rỗng cho Devices và Settings để code không bị lỗi
const Devices = () => (
  <div className="p-8 text-2xl font-semibold text-textMain">
    Device Management Coming Soon...
  </div>
);

const DASHBOARD_PAGE_KEY = 'hera_active_page';
const VALID_PAGES = new Set(['home', 'analytics', 'devices', 'settings']);

const App = () => {
  const [user, setUser] = useState(() => getStoredUser());
  const [activePage, setActivePage] = useState(() => {
    const savedPage = localStorage.getItem(DASHBOARD_PAGE_KEY);
    return VALID_PAGES.has(savedPage) ? savedPage : 'home';
  });

  useEffect(() => {
    localStorage.setItem(DASHBOARD_PAGE_KEY, activePage);
  }, [activePage]);

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
    <div className="min-h-screen bg-background">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      <main className="min-h-screen">
        {renderPage()}
      </main>
    </div>
  );
};

export default App;
