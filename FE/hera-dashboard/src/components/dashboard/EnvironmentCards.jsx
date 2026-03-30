import React, { useState, useEffect } from 'react';

const EnvironmentCards = () => {
  // 1. Khai báo state để lưu dữ liệu từ API
  const [currentEnv, setCurrentEnv] = useState({
    temperature: 0,
    humidity: 0,
    light: 0,
    airQuality: 'Loading...',
    gasStatus: 'Loading...'
  });

  // 2. Dùng useEffect để gọi API ngay khi component render
  useEffect(() => {
    const fetchLatestData = async () => {
      try {
        // Thay URL này bằng endpoint backend Python của em (vd: http://localhost:5000/api/sensors/latest)
        const response = await fetch('YOUR_PYTHON_BACKEND_URL/api/sensors/latest');
        
        if (response.ok) {
          const data = await response.json();
          // Cập nhật state với dữ liệu từ MongoDB/Backend
          setCurrentEnv({
            temperature: data.temperature,
            humidity: data.humidity,
            light: data.light,
            airQuality: data.temperature > 30 ? 'Warning' : 'Good', // Logic ví dụ
            gasStatus: data.gas_detected ? 'Danger' : 'Safe'
          });
        }
      } catch (error) {
        console.error("Lỗi khi gọi API:", error);
      }
    };

    // Gọi lần đầu
    fetchLatestData();

    // Tùy chọn: Set interval để tự động cập nhật mỗi 5 giây
    const intervalId = setInterval(fetchLatestData, 5000);
    
    // Cleanup function để dọn dẹp bộ nhớ khi chuyển trang
    return () => clearInterval(intervalId);
  }, []); // Mảng rỗng [] giúp effect chỉ chạy 1 lần lúc mount

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
      {/* Hiển thị data thật ra UI */}
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Temperature</p>
        <p className="text-2xl font-medium">{currentEnv.temperature}°C</p>
      </div>
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Humidity</p>
        <p className="text-2xl font-medium">{currentEnv.humidity}%</p>
      </div>
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Light</p>
        <p className="text-2xl font-medium">{currentEnv.light} lux</p>
      </div>
    </div>
  );
};

export default EnvironmentCards;