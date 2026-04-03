import React, { useState } from 'react';

// Import các component và trang đã tạo
import Sidebar from './components/layout/Sidebar';
import Home from './pages/Home';
import Analytics from './pages/Analytics';
// import Setting from './pages/Setting';
// import Device from './pages/Device'

// Tạo tạm 2 component rỗng cho Devices và Settings để code không bị lỗi
const Devices = () => <div className="p-8 text-2xl font-semibold text-textMain">Device Management Coming Soon...</div>;
const Settings = () => <div className="p-8 text-2xl font-semibold text-textMain">Settings Panel Coming Soon...</div>;

function App() {
  // State lưu trữ trang đang được chọn, mặc định là 'home'
  const [activePage, setActivePage] = useState('home');

  // Hàm này sẽ render ra component tương ứng dựa vào activePage
  const renderContent = () => {
    switch (activePage) {
      case 'home':
        return <Home />;
      case 'analytics':
        return <Analytics />;
      case 'devices':
        return <Devices />;
      case 'settings':
        return <Settings />;
      default:
        return <Home />;
    }
  };

  return (
    // Bộ khung chính: Chiếm toàn bộ màn hình, nền màu background (đã config trong Tailwind)
    <div className="flex h-screen w-full bg-background overflow-hidden font-sans">
      
      {/* Menu bên trái - Truyền state và hàm set state xuống Sidebar */}
      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      {/* Vùng nội dung chính bên phải */}
      <main className="flex-1 h-full overflow-y-auto">
        {renderContent()}
      </main>

    </div>
  );
}

export default App;