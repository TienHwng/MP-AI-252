import React, { useState, useEffect } from 'react';

// Dữ liệu mẫu tạm thời để test UI
const MOCK_LOGS = [
  {
    id: 1,
    type: 'scene',
    action: 'Activated',
    target: 'Movie Mode',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 phút trước
    status: 'info',
  },
  {
    id: 2,
    type: 'device',
    action: 'Turned ON',
    target: 'Living Room Fan (50%)',
    timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(), // 12 phút trước
    status: 'success',
  },
  {
    id: 3,
    type: 'device',
    action: 'Turned OFF',
    target: 'All LEDs',
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(), // 45 phút trước
    status: 'neutral',
  },
  {
    id: 4,
    type: 'alert',
    action: 'Warning',
    target: 'High Temperature Detected (32°C)',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 tiếng trước
    status: 'warning',
  },
];

// Hàm format thời gian hiển thị gọn gàng
const formatLogTime = (isoString) => {
  const date = new Date(isoString);
  const today = new Date();
  const isToday = date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear();
  
  const timeString = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  
  if (isToday) {
    return `Today, ${timeString}`;
  }
  return `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${timeString}`;
};

const ActivityLog = ({ data }) => {
  const [logs, setLogs] = useState(MOCK_LOGS);

  // Sau này em có thể dùng useEffect lắng nghe data (sensorData)
  // để push thêm log mới vào mảng logs khi có sự kiện thay đổi thiết bị nhé.
  /*
  useEffect(() => {
    if (data && data.lastAction) {
       setLogs(prev => [data.lastAction, ...prev]);
    }
  }, [data]);
  */

  const getStatusStyles = (status) => {
    switch (status) {
      case 'success':
        return { bg: 'bg-[#E8F5E9]', text: 'text-[#3A7D44]', icon: 'bg-[#3A7D44]' }; // Xanh lá
      case 'warning':
        return { bg: 'bg-[#FED7AA]', text: 'text-[#DF6D14]', icon: 'bg-[#DF6D14]' }; // Cam
      case 'info':
        return { bg: 'bg-[#E0F2FE]', text: 'text-[#0284C7]', icon: 'bg-[#0284C7]' }; // Xanh dương
      default:
        return { bg: 'bg-gray-100', text: 'text-gray-600', icon: 'bg-gray-400' };    // Xám
    }
  };

  return (
    <div className="flex flex-col h-full p-4">
      <div className="flex justify-between items-center mb-5 px-1">
        <h3 className="text-lg font-semibold text-gray-800">Recent Activity</h3>
        <button 
          onClick={() => setLogs([])}
          className="text-xs font-medium text-gray-400 hover:text-red-500 transition-colors px-2 py-1 rounded-md hover:bg-red-50"
        >
          Clear All
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 flex flex-col gap-3">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-2">
            <svg className="w-12 h-12 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>
            <p className="text-sm">No recent activity.</p>
          </div>
        ) : (
          logs.map((log) => {
            const styles = getStatusStyles(log.status);
            return (
              <div 
                key={log.id} 
                className="flex items-start gap-3 p-3 bg-white rounded-2xl border border-gray-100 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] hover:shadow-md transition-shadow duration-200"
              >
                {/* Icon Marker */}
                <div className={`mt-1 w-8 h-8 shrink-0 rounded-full flex items-center justify-center ${styles.bg}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${styles.icon}`}></div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 font-medium truncate">
                    <span className={styles.text}>{log.action}</span> {log.target}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {formatLogTime(log.timestamp)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ActivityLog;