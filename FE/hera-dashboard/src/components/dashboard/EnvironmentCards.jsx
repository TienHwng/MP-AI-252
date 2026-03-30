import React from 'react';

const formatMetric = (value) => Number(value || 0).toFixed(1);

const EnvironmentCards = ({ data }) => {
  const currentEnv = {
    temperature: data?.temperature ?? 0,
    humidity: data?.humidity ?? 0,
    light: data?.light ?? 0,
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
        <p className="text-2xl font-medium">{Math.round(currentEnv.light)} lux</p>
      </div>
    </div>
  );
};

export default EnvironmentCards;