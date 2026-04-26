import React, { useEffect, useState } from 'react';
import AiAssistant from '../components/chat/AI';
import ControlCard from '../components/dashboard/ControlCard';
import EnvironmentCards from '../components/dashboard/EnvironmentCards';
import SafetyStatusCards from '../components/dashboard/SafetyStatusCards';
import {
  controlDeviceState,
  fetchLatestSensorData,
  getDeviceStatus,
  getSensorValue,
  subscribeLatestSensorData,
  logoutUser,
} from '../services/api';

const getRelativeUpdatedLabel = (timestamp) => {
  const updated = new Date(timestamp).getTime();
  if (Number.isNaN(updated)) {
    return 'just now';
  }

  const diffSeconds = Math.max(0, Math.floor((Date.now() - updated) / 1000));
  if (diffSeconds < 60) {
    return 'just now';
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  return `${diffHours}h ago`;
};

const getAirQualityState = (aqi, temperature, humidity) => {
  const hasAqi = Number.isFinite(aqi) && aqi > 0;
  const hasEnvironment = Number.isFinite(temperature) && Number.isFinite(humidity);
  if (!hasAqi && !hasEnvironment) return { level: 'unknown', progress: 0 };
  const safeTemperature = Number.isFinite(temperature) ? temperature : 25;
  const safeHumidity = Number.isFinite(humidity) ? humidity : 60;

  const score = hasAqi
    ? aqi
    : Math.max(0, Math.min(100, (safeTemperature - 20) * 3 + (safeHumidity - 45) * 1.2));

  if (score >= 70) return { level: 'danger', progress: 90 };
  if (score >= 40) return { level: 'warning', progress: 60 };
  return { level: 'good', progress: 30 };
};

const getGasState = (gasPpm, gasDetected) => {
  if (!gasDetected && !Number.isFinite(gasPpm)) return { level: 'unknown', progress: 0 };
  if (gasDetected || gasPpm >= 300) return { level: 'danger', progress: 95 };
  if (gasPpm >= 120) return { level: 'warning', progress: 65 };
  return { level: 'good', progress: 20 };
};

const Home = ({ user, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [sensorData, setSensorData] = useState(null);
  const [telemetryError, setTelemetryError] = useState('');
  const [isSubmittingControl, setIsSubmittingControl] = useState(false);

  useEffect(() => {
    const timerId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe = null;

    const loadLatestData = async () => {
      try {
        // Hàm này bên api.js đã được cấu hình tự lấy user_id của user đang login
        const latest = await fetchLatestSensorData();
        if (!cancelled) {
          setSensorData(latest);
          setTelemetryError('');
        }
      } catch (error) {
        console.error('Failed to fetch sensor data:', error);
        if (!cancelled) {
          setTelemetryError(error.message || 'Failed to fetch sensor data');
        }
      }
    };

    loadLatestData();
    try {
      unsubscribe = subscribeLatestSensorData({
        onData: (latest) => {
          if (!cancelled) {
            setSensorData(latest);
            setTelemetryError('');
          }
        },
        onError: (error) => {
          console.error('Sensor stream error:', error);
          setTelemetryError('Sensor stream error. Waiting for MQTT telemetry.');
        },
      });
    } catch (error) {
      console.error('Failed to open sensor stream:', error);
      setTelemetryError(error.message || 'Failed to open sensor stream');
    }
    const intervalId = setInterval(loadLatestData, 15000);

    return () => {
      cancelled = true;
      unsubscribe?.();
      clearInterval(intervalId);
    };
  }, []);

  const handleToggleDevice = async (target) => {
    const currentStatus = getDeviceStatus(sensorData, target);
    if (typeof currentStatus !== 'boolean') return;
    const nextValue = !currentStatus;
    setIsSubmittingControl(true);

    try {
      await controlDeviceState(target, nextValue);
    } catch (error) {
      console.error(`Failed to toggle ${target}:`, error);
      setTelemetryError(error.message || `Failed to toggle ${target}`);
    } finally {
      setIsSubmittingControl(false);
    }
  };

  const handleLogout = () => {
    logoutUser();
    onLogout();
  };

  const updatedLabel = sensorData ? getRelativeUpdatedLabel(sensorData.updatedAt) : 'unavailable';
  const temperature = getSensorValue(sensorData, 'temperature');
  const humidity = getSensorValue(sensorData, 'humidity');
  const gasPpm = getSensorValue(sensorData, 'gas_ppm');
  const gasDetected = getSensorValue(sensorData, 'gas_detected');
  const airState = getAirQualityState(
    getSensorValue(sensorData, 'air_quality'),
    temperature,
    humidity,
  );
  const gasState = getGasState(gasPpm, gasDetected);

  return (
    <div className="p-6 lg:p-8 w-full h-full min-h-full grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-6 lg:gap-8">
      <div className="min-w-0 flex flex-col gap-8">
        <header className="flex justify-between items-end">
          <div>
            <h2 className="text-3xl font-semibold text-textMain">
              Welcome Home, {user?.full_name || 'User'} !
            </h2>
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
                second: '2-digit',
                hour12: true,
              })}
            </h3>
            <div className="mt-2 flex items-center justify-end gap-2">
              <span className="text-xs bg-gray-200 text-gray-600 px-3 py-1 rounded-full flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${sensorData?.mqtt_connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
                {sensorData?.mqtt_connected ? 'MQTT Live' : 'MQTT Offline'}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="text-xs bg-cardDark text-white px-3 py-1 rounded-full"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        <section>
          <h4 className="font-medium mb-3">Environment & Safety</h4>
          {telemetryError && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {telemetryError}
            </div>
          )}
          <EnvironmentCards data={sensorData} />
          <SafetyStatusCards
            airQuality={{
              value: getSensorValue(sensorData, 'air_quality') == null ? '--' : Number(getSensorValue(sensorData, 'air_quality')).toFixed(0),
              unit: 'AQI',
              level: airState.level,
              progress: airState.progress,
              updatedAt: updatedLabel,
            }}
            gasDetection={{
              value: gasPpm == null ? '--' : Number(gasPpm).toFixed(0),
              unit: 'ppm',
              level: gasState.level,
              progress: gasState.progress,
              updatedAt: updatedLabel,
            }}
          />
        </section>

        <section>
          <h4 className="font-medium mb-3">Quick Controls</h4>
          <ControlCard
            data={sensorData}
            isSubmitting={isSubmittingControl}
            onToggleDevice={handleToggleDevice}
          />
        </section>
      </div>

      <div className="h-full min-h-[560px]">
        <AiAssistant />
      </div>
    </div>
  );
};

export default Home;
