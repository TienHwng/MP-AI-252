import React from 'react';
import { Home, BarChart3, House, Lightbulb, Settings } from 'lucide-react';

const Sidebar = ({ activePage, setActivePage, isExpanded, setIsExpanded }) => {
  const menuItems = [
    { id: 'home', Icon: Home, label: 'Home' },
    { id: 'analytics', Icon: BarChart3, label: 'Analytics' },
    { id: 'floorplan', Icon: House, label: 'House' },
    { id: 'devices', Icon: Lightbulb, label: 'Devices' },
    { id: 'settings', Icon: Settings, label: 'Settings' },
  ];

  return (
    <>
      <div
        className="fixed left-0 top-0 z-30 hidden h-screen w-4 md:block"
        onMouseEnter={() => setIsExpanded(true)}
      />

      {isExpanded && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setIsExpanded(false)}
          className="fixed inset-0 z-40 hidden bg-black/20 backdrop-blur-[1px] md:block"
        />
      )}

      <aside
        onMouseEnter={() => setIsExpanded(true)}
        onMouseLeave={() => setIsExpanded(false)}
        className={`fixed left-0 top-0 z-50 hidden h-screen w-64 transform flex-col bg-white pt-8 shadow-md transition-transform duration-300 md:flex ${
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
          {menuItems.map((item) => {
            const Icon = item.Icon;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActivePage(item.id)}
                className={`w-[90%] mx-auto flex items-center px-4 py-3 mb-2 rounded-r-full transition-colors ${
                  activePage === item.id
                    ? 'bg-primary text-white font-medium'
                    : 'text-textMain hover:bg-gray-100'
                }`}
              >
                <Icon size={20} strokeWidth={1.9} className="mr-3 shrink-0" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-gray-200 bg-white/95 px-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] pt-2 shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:hidden">
        <div className="mx-auto grid max-w-lg grid-cols-5 gap-1">
          {menuItems.map((item) => {
            const Icon = item.Icon;
            const active = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActivePage(item.id)}
                className={`flex min-h-[54px] flex-col items-center justify-center rounded-xl px-1 text-[11px] font-medium transition-colors ${
                  active
                    ? 'bg-[#E8F5E9] text-primary'
                    : 'text-textMuted hover:bg-gray-50 hover:text-textMain'
                }`}
              >
                <Icon size={20} strokeWidth={2} className="mb-1 shrink-0" />
                <span className="max-w-full truncate">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
};

export default Sidebar;
