import React, { useState } from 'react';

const Sidebar = ({ activePage, setActivePage }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const menuItems = [
    { id: 'home', icon: '🏠', label: 'Home' },
    { id: 'analytics', icon: '📊', label: 'Analytics' },
    { id: 'devices', icon: '💡', label: 'Devices' },
    { id: 'settings', icon: '⚙️', label: 'Settings' },
  ];

  return (
    <>
      <div
        className="fixed left-0 top-0 h-screen w-4 z-30"
        onMouseEnter={() => setIsExpanded(true)}
      />

      {isExpanded && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setIsExpanded(false)}
          className="fixed inset-0 bg-black/20 backdrop-blur-[1px] z-40"
        />
      )}

      <aside
        onMouseEnter={() => setIsExpanded(true)}
        onMouseLeave={() => setIsExpanded(false)}
        className={`fixed left-0 top-0 h-screen w-64 bg-white flex flex-col pt-8 shadow-md z-50 transform transition-transform duration-300 ${
          isExpanded ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="px-6 mb-10">
          <h1 className="text-2xl font-bold text-primary mb-1">H.E.R.A.</h1>
          <p className="text-xs text-textMuted">
            Home Environmental Resource
            <br />
            Assistant
          </p>
        </div>

        <nav className="flex-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className={`w-[90%] mx-auto flex items-center px-4 py-3 mb-2 rounded-r-full transition-colors ${
                activePage === item.id
                  ? 'bg-primary text-white font-medium'
                  : 'text-textMain hover:bg-gray-100'
              }`}
            >
              <span className="mr-3">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;