import React, { useState } from 'react';
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

const App = () => {
  const [user, setUser] = useState(() => (import.meta.env.DEV ? null : getStoredUser()));
  const [activePage, setActivePage] = useState('home');

  if (!user) {
    return <Login onLoginSuccess={setUser} />;
  }

  const handleLogout = () => {
    logoutUser();
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
