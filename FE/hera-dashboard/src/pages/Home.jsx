import React, { useEffect, useState } from 'react';
import AiAssistant from '../components/chat/AI';
import ControlCard from '../components/dashboard/ControlCard';
import EnvironmentCards from '../components/dashboard/EnvironmentCards';

const Home = () => {
  const [currentTime, setCurrentTime] = useState(() => new Date());

  useEffect(() => {
    const timerId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  return (
    <div className="p-6 lg:p-8 w-full h-full min-h-full grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-6 lg:gap-8">
      {/* Cột trái: Bảng điều khiển */}
      <div className="min-w-0 flex flex-col gap-8">
        <header className="flex justify-between items-end">
          <div>
            <h2 className="text-3xl font-semibold text-textMain">Welcome Home</h2>
            <p className="text-textMuted mt-1">
              {currentTime.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          </div>
          <div className="text-right">
            <h3 className="text-2xl text-textMain">
              {currentTime.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true,
              })}
            </h3>
            <span className="text-xs bg-gray-200 text-gray-600 px-3 py-1 rounded-full flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span> All Systems Normal
            </span>
          </div>
        </header>

        {/* Mẫu Card tĩnh - Sau này em tách ra file InfoCard.jsx nhé */}
        <section>
          <h4 className="font-medium mb-3">Environment & Safety</h4>
          <EnvironmentCards />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex-1 bg-white p-4 rounded-xl flex justify-between items-center shadow-sm">
              <span className="text-sm font-medium text-textMain">Air Quality <br/><span className="text-textMuted font-normal">Good</span></span>
              <span className="text-green-500">✓</span>
            </div>
            <div className="flex-1 bg-white p-4 rounded-xl flex justify-between items-center shadow-sm">
              <span className="text-sm font-medium text-textMain">Gas Detection <br/><span className="text-textMuted font-normal">Safe</span></span>
              <span className="text-green-500">✓</span>
            </div>
          </div>
        </section>

        {/* Nút điều khiển - Sau này tách ra ControlCard.jsx */}
        <section>
          <h4 className="font-medium mb-3">Quick Controls</h4>
           <ControlCard />
        </section>
      </div>

      {/* Cột phải: Ai Assistant */}
      <div className="h-full min-h-[560px]">
        <AiAssistant />
      </div>
    </div>
  );
};

export default Home;