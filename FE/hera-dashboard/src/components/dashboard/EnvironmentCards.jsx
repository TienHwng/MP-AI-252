import React from 'react';
import { getSensorValue } from '../../services/api';
import { Thermometer, Droplets, Sun } from 'lucide-react';

const formatMetric = (value, decimals = 1) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(decimals) : '--';
};

// --- Evaluation functions with English status and descriptions ---

const getTempInfo = (val) => {
	const num = Number(val);
	if (!Number.isFinite(num)) return { status: 'Unknown', desc: 'Updating...', color: 'text-gray-500', bg: 'bg-gray-100' };
	if (num < 20) return { status: 'Cold', desc: 'Below standard temperature', color: 'text-[#427AB5]', bg: 'bg-[#DCE9F8]' };
	if (num > 24) return { status: 'Hot', desc: 'Above standard temperature', color: 'text-[#DF6D14]', bg: 'bg-[#FED7AA]' };
	return { status: 'Optimal', desc: 'Comfortable temperature', color: 'text-[#3A7D44]', bg: 'bg-[#E8F5E9]' };
};

const getHumidInfo = (val) => {
	const num = Number(val);
	if (!Number.isFinite(num)) return { status: 'Unknown', desc: 'Updating...', color: 'text-gray-500', bg: 'bg-gray-100' };
	if (num < 40) return { status: 'Dry', desc: 'Too dry: May cause irritation', color: 'text-[#427AB5]', bg: 'bg-[#DCE9F8]' };
	if (num > 60) return { status: 'Humid', desc: 'Too humid', color: 'text-[#DF6D14]', bg: 'bg-[#FED7AA]' };
	return { status: 'Optimal', desc: 'Ideal humidity levels', color: 'text-[#3A7D44]', bg: 'bg-[#E8F5E9]' };
};

const getLightInfo = (val) => {
	const num = Number(val);
	if (!Number.isFinite(num)) return { status: 'Unknown', desc: 'Updating...', color: 'text-gray-500', bg: 'bg-gray-100' };
	if (num < 150) return { status: 'Low', desc: 'Insufficient light levels', color: 'text-[#427AB5]', bg: 'bg-[#DCE9F8]' };
	if (num > 300) return { status: 'High', desc: 'Light is too bright', color: 'text-[#DF6D14]', bg: 'bg-[#FED7AA]' };
	return { status: 'Optimal', desc: 'Standard illumination', color: 'text-[#3A7D44]', bg: 'bg-[#E8F5E9]' };
};

const EnvironmentCards = ({ data }) => {
  const currentEnv = {
    temperature: getSensorValue(data, 'temperature'),
    humidity: getSensorValue(data, 'humidity'),
    light: getSensorValue(data, 'light') || getSensorValue(data, 'light living room'),
  };

  const tempInfo = getTempInfo(currentEnv.temperature);
  const humidInfo = getHumidInfo(currentEnv.humidity);
  const lightInfo = getLightInfo(currentEnv.light);

  return (
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 lg:gap-4">
      {/* Temperature Card */}
      <div className="flex w-full flex-col justify-between rounded-xl border border-gray-50 bg-white p-4 shadow-sm transition-shadow hover:shadow-md sm:p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2 text-textMuted">
            <Thermometer size={18} />
            <span className="text-sm font-medium">Temperature</span>
          </div>
          <span className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full ${tempInfo.bg} ${tempInfo.color}`}>
            {tempInfo.status}
          </span>
        </div>
        <div>
          <h3 className="text-3xl font-semibold text-textMain">
            {formatMetric(currentEnv.temperature)}<span className="text-lg font-normal text-textMuted ml-1">°C</span>
          </h3>
          <p className={`text-xs mt-2 font-medium ${tempInfo.color}`}>{tempInfo.desc}</p>
        </div>
      </div>

      {/* Humidity Card */}
      <div className="flex w-full flex-col justify-between rounded-xl border border-gray-50 bg-white p-4 shadow-sm transition-shadow hover:shadow-md sm:p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2 text-textMuted">
            <Droplets size={18} />
            <span className="text-sm font-medium">Humidity</span>
          </div>
          <span className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full ${humidInfo.bg} ${humidInfo.color}`}>
            {humidInfo.status}
          </span>
        </div>
        <div>
          <h3 className="text-3xl font-semibold text-textMain">
            {formatMetric(currentEnv.humidity)}<span className="text-lg font-normal text-textMuted ml-1">%</span>
          </h3>
          <p className={`text-xs mt-2 font-medium ${humidInfo.color}`}>{humidInfo.desc}</p>
        </div>
      </div>

      {/* Light Card */}
      <div className="flex w-full flex-col justify-between rounded-xl border border-gray-50 bg-white p-4 shadow-sm transition-shadow hover:shadow-md sm:p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2 text-textMuted">
            <Sun size={18} />
            <span className="text-sm font-medium">Light</span>
          </div>
          <span className={`text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full ${lightInfo.bg} ${lightInfo.color}`}>
            {lightInfo.status}
          </span>
        </div>
        <div>
          <h3 className="text-3xl font-semibold text-textMain">
            {formatMetric(currentEnv.light, 0)}<span className="text-lg font-normal text-textMuted ml-1">lux</span>
          </h3>
          <p className={`text-xs mt-2 font-medium ${lightInfo.color}`}>{lightInfo.desc}</p>
        </div>
      </div>
    </div>
  );
};

export default EnvironmentCards;
