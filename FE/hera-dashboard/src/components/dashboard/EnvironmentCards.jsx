import React from 'react';
import { getSensorValue } from '../../services/api';

const formatMetric = (value, decimals = 1) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(decimals) : '--';
};

const EnvironmentCards = ({ data }) => {
  const currentEnv = {
    temperature: getSensorValue(data, 'temperature'),
    humidity: getSensorValue(data, 'humidity'),
    light: getSensorValue(data, 'light'),
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
      {/* Hiển thị data thật ra UI */}
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Temperature</p>
        <p className="text-2xl font-medium">{formatMetric(currentEnv.temperature)}°C</p>
      </div>
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Humidity</p>
        <p className="text-2xl font-medium">{formatMetric(currentEnv.humidity)}%</p>
      </div>
      <div className="bg-white p-4 rounded-xl shadow-sm w-full">
        <p className="text-textMuted text-sm">Light</p>
        <p className="text-2xl font-medium">{formatMetric(currentEnv.light, 0)} lux</p>
      </div>
    </div>
  );
};

export default EnvironmentCards;
