import React, { useEffect, useState } from 'react';
import AiAssistant from '../components/chat/AI';
import ControlCard from '../components/dashboard/ControlCard';
import EnvironmentCards from '../components/dashboard/EnvironmentCards';
import SafetyStatusCards from '../components/dashboard/SafetyStatusCards';
import { fetchLatestSensorData, toggleLedLight, toggleNeoLight, logoutUser } from '../services/api';

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
  if (gasDetected || gasPpm >= 300) return { level: 'danger', progress: 95 };
  if (gasPpm >= 120) return { level: 'warning', progress: 65 };
  return { level: 'good', progress: 20 };
};

const Home = ({ user, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [sensorData, setSensorData] = useState({
    temperature: null,
    humidity: null,
    light: null,
    airQualityIndex: null,
    gasPpm: null,
    gasDetected: false,
    updatedAt: Date.now(),
    led_state: false,
    neo_led_state: false,
    ws2812_status: false,
    relay_status: false,
    mini_fan_status: false,
    wifi_connected: false,
    mqtt_connected: false,
    wifi_rssi: null,
    uptime_ms: null,
    inference_result: null,
  });
  const [isSubmittingControl, setIsSubmittingControl] = useState(false);

  useEffect(() => {
    const timerId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadLatestData = async () => {
      try {
        // Hàm này bên api.js đã được cấu hình tự lấy user_id của user đang login
        const latest = await fetchLatestSensorData();
        if (!cancelled) {
          setSensorData(latest);
        }
      } catch (error) {
        console.error('Failed to fetch sensor data:', error);
      }
    };

    loadLatestData();
    const intervalId = setInterval(loadLatestData, 5000);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  const handleToggleLed = async () => {
    const nextValue = !sensorData.led_state;
    setIsSubmittingControl(true);

    try {
      await toggleLedLight(nextValue);
      setSensorData((prev) => ({
        ...prev,
        led_state: nextValue,
        updatedAt: Date.now(),
      }));
    } catch (error) {
      console.error('Failed to toggle LED light:', error);
    } finally {
      setIsSubmittingControl(false);
    }
  };

  const handleToggleNeo = async () => {
    const nextValue = !sensorData.neo_led_state;
    setIsSubmittingControl(true);

    try {
      await toggleNeoLight(nextValue);
      setSensorData((prev) => ({
        ...prev,
        neo_led_state: nextValue,
        updatedAt: Date.now(),
      }));
    } catch (error) {
      console.error('Failed to toggle neon light:', error);
    } finally {
      setIsSubmittingControl(false);
    }
  };

  const handleLogout = () => {
    logoutUser();
    onLogout();
  };

  const updatedLabel = getRelativeUpdatedLabel(sensorData.updatedAt);
  const airState = getAirQualityState(
    sensorData.airQualityIndex,
    sensorData.temperature,
    sensorData.humidity,
  );
  const gasState = getGasState(sensorData.gasPpm, sensorData.gasDetected);

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
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                All Systems Normal
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
          <EnvironmentCards data={sensorData} />
          <SafetyStatusCards
            airQuality={{
              value: sensorData.airQualityIndex == null ? '--' : Number(sensorData.airQualityIndex).toFixed(0),
              unit: 'AQI',
              level: airState.level,
              progress: airState.progress,
              updatedAt: updatedLabel,
            }}
            gasDetection={{
              value: sensorData.gasPpm == null ? '--' : Number(sensorData.gasPpm).toFixed(0),
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
            ledState={sensorData.led_state}
            neoLedState={sensorData.neo_led_state}
            isSubmitting={isSubmittingControl}
            onToggleLed={handleToggleLed}
            onToggleNeoLed={handleToggleNeo}
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