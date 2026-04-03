import React from 'react';
import { Droplets, Sun, Thermometer } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

// Data mẫu giả lập (Mock Data) để test giao diện
const mockData = [
  { time: '22:00', temp: 21.5, humidity: 52, light: 120 },
  { time: '00:00', temp: 22.8, humidity: 55, light: 80 },
  { time: '02:00', temp: 23.5, humidity: 58, light: 50 },
  { time: '04:00', temp: 24.2, humidity: 64, light: 45 },
  { time: '06:00', temp: 24.5, humidity: 67, light: 150 },
  { time: '08:00', temp: 23.8, humidity: 63, light: 300 },
  { time: '10:00', temp: 22.5, humidity: 55, light: 450 },
  { time: '12:00', temp: 21.0, humidity: 48, light: 500 },
  { time: '14:00', temp: 20.1, humidity: 45, light: 480 },
];

// Component dùng chung cho các biểu đồ
const getStats = (series) => {
  const min = Math.min(...series);
  const max = Math.max(...series);
  const avg = series.reduce((sum, num) => sum + num, 0) / series.length;

  return {
    min,
    max,
    avg,
  };
};

const formatMetric = (value) => Number(value).toFixed(1);

const ChartCard = ({ title, value, unit, dataKey, color, data, Icon, stats }) => {
  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm">
      <div className="flex justify-between items-start mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-textMain">
            <Icon size={20} strokeWidth={1.9} />
          </div>
          <div>
            <h3 className="text-lg font-medium text-textMain">{title}</h3>
            <p className="text-sm text-textMuted">Last 24 hours</p>
          </div>
        </div>
        <div className="text-right">
          <h2 className="text-3xl font-normal text-textMain">{value}</h2>
          <p className="text-sm text-textMuted">{unit}</p>
        </div>
      </div>

      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id={`color${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fill: '#888', fontSize: 12}} />
            <YAxis axisLine={false} tickLine={false} tick={{fill: '#888', fontSize: 12}} />
            <Tooltip 
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}
            />
            {/* type="monotone" chính là bí quyết để đường line cong mượt */}
            <Area type="monotone" dataKey={dataKey} stroke={color} fillOpacity={1} fill={`url(#color${dataKey})`} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
        <div className="rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-textMuted">24h Min</p>
          <p className="text-sm font-semibold text-textMain">{formatMetric(stats.min)}</p>
        </div>
        <div className="rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-textMuted">24h Avg</p>
          <p className="text-sm font-semibold text-textMain">{formatMetric(stats.avg)}</p>
        </div>
        <div className="rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-textMuted">24h Max</p>
          <p className="text-sm font-semibold text-textMain">{formatMetric(stats.max)}</p>
        </div>
      </div>
    </div>
  );
};

const Analytics = () => {
  const tempStats = getStats(mockData.map((entry) => entry.temp));
  const humidityStats = getStats(mockData.map((entry) => entry.humidity));
  const lightStats = getStats(mockData.map((entry) => entry.light));

  return (
    <div className="p-6 lg:p-8 w-full h-full min-h-full">
      <div className="mb-6 lg:mb-8">
        <h2 className="text-3xl font-semibold text-textMain">Environmental Trends</h2>
        <p className="text-textMuted mt-1">Monitor your home's climate and lighting conditions over the last 24 hours</p>
      </div>

      <div className="flex flex-col gap-6">
        <ChartCard 
          title="Temperature" value="20.1" unit="Celsius" 
          dataKey="temp" color="#D6AFA6" data={mockData} Icon={Thermometer} stats={tempStats}
        />
        <ChartCard 
          title="Humidity" value="48.3" unit="Relative Humidity" 
          dataKey="humidity" color="#8B9A84" data={mockData} Icon={Droplets} stats={humidityStats}
        />
        <ChartCard 
          title="Ambient Light" value="335.1" unit="Lux" 
          dataKey="light" color="#F4D03F" data={mockData} Icon={Sun} stats={lightStats}
        />
      </div>
    </div>
  );
};

export default Analytics;