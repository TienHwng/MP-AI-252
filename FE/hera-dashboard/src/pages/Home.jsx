import React, { useEffect, useState } from 'react';
import AiAssistant from '../components/chat/AI';
import ControlCard from '../components/dashboard/ControlCard';
import EnvironmentCards from '../components/dashboard/EnvironmentCards';
import SceneCards from '../components/dashboard/SceneCards';
import ActivityLog from '../components/dashboard/ActivityLog';
import FloorPlan from '../components/FloorPlan'; 

import {
  controlDeviceState,
  fetchLatestSensorData,
  getDeviceStatus,
  subscribeLatestSensorData,
  logoutUser,
  sendRpcCommand 
} from '../services/api';

const getRelativeUpdatedLabel = (timestamp) => {
  const updated = new Date(timestamp).getTime();
  if (Number.isNaN(updated)) return 'just now';

  const diffSeconds = Math.max(0, Math.floor((Date.now() - updated) / 1000));
  if (diffSeconds < 60) return 'just now';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  return `${diffHours}h ago`;
};

const Home = ({ user, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [sensorData, setSensorData] = useState(null);
  const [telemetryError, setTelemetryError] = useState('');
  const [isSubmittingControl, setIsSubmittingControl] = useState(false);
  
  // State mới để quản lý Tab ở cột phải
  const [activeRightTab, setActiveRightTab] = useState('assistant');

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

  const handleActivateScene = async (sceneId) => {
    setIsSubmittingControl(true);
    try {
      if (sceneId === 'movie') {
        await Promise.all([
          controlDeviceState('main_led', false),
          controlDeviceState('neo_led', false),
          controlDeviceState('ws2812', false),
          controlDeviceState('mini_fan', true),
          controlDeviceState('relay', true),
          // Set light intensity to 0
          sendRpcCommand('setMainLedBrightness', 0),
          sendRpcCommand('setStripBrightness', 0),
          sendRpcCommand('setWS2812Brightness', 0)
        ]);
      } 
      else if (sceneId === 'sleep') {
        await Promise.all([
          controlDeviceState('main_led', false),
          controlDeviceState('neo_led', false),
          controlDeviceState('ws2812', false),
          // Set light intensity to 0
          sendRpcCommand('setMainLedBrightness', 0),
          sendRpcCommand('setStripBrightness', 0),
          sendRpcCommand('setWS2812Brightness', 0)
        ]);
      } 
      else if (sceneId === 'away') {
        await Promise.all([
          controlDeviceState('main_led', false),
          controlDeviceState('neo_led', false),
          controlDeviceState('ws2812', false),
          controlDeviceState('mini_fan', false),
          controlDeviceState('relay', false),
          // Set intensity to 0
          sendRpcCommand('setMainLedBrightness', 0),
          sendRpcCommand('setStripBrightness', 0),
          sendRpcCommand('setWS2812Brightness', 0),
          sendRpcCommand('setFanSpeed', 0)
        ]);
      }
    } catch (error) {
      console.error(`Failed to activate scene ${sceneId}:`, error);
      setTelemetryError(error.message || `Failed to activate ${sceneId}`);
    } finally {
      setIsSubmittingControl(false);
    }
  };

  const handleIntensityChange = async (deviceId, percentValue, pwmValue, rpcMethod) => {
    if (!rpcMethod) return;
    try {
      await sendRpcCommand(rpcMethod, pwmValue);
    } catch (error) {
      console.error(`Lỗi khi điều chỉnh cường độ cho ${deviceId}:`, error);
      setTelemetryError(error.message || `Không thể điều chỉnh cường độ cho ${deviceId}`);
    }
  };

  const handleLogout = () => {
    logoutUser();
    onLogout();
  };

  return (
    <div className="grid min-h-screen w-full grid-cols-1 gap-4 bg-background p-3 sm:p-4 lg:p-6 xl:h-screen xl:grid-cols-[minmax(0,1fr)_350px] xl:gap-6 xl:overflow-hidden">
      {/* CỘT TRÁI: Dashboard chính */}
      <div className="min-w-0 flex flex-col gap-5 xl:overflow-y-auto xl:pr-1 custom-scrollbar">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="break-words text-2xl font-semibold leading-tight text-textMain sm:text-3xl">
              Welcome Home, {user?.full_name || 'User'}!
            </h2>
            <p className="text-textMuted mt-1">
              {currentTime.toLocaleDateString('en-US', {
                weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
              })}
            </p>
          </div>

          <div className="shrink-0 text-left sm:text-right">
            <h3 className="text-xl text-textMain sm:text-2xl">
              {currentTime.toLocaleTimeString('en-US', {
                hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
              })}
            </h3>
            <div className="mt-2 flex items-center gap-2 sm:justify-end">
              <button onClick={handleLogout} className="rounded-full bg-[#E8F5E9] px-3 py-1.5 text-xs font-medium text-[#3A7D44] transition-colors hover:bg-[#DF6D14] hover:text-white">
                Logout
              </button>
            </div>
          </div>
        </header>

        <section>
          <h4 className="font-medium mb-3">Environment & Safety</h4>
          {telemetryError && <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{telemetryError}</div>}
          <EnvironmentCards data={sensorData} />
        </section>

        <section>
          <h4 className="font-medium mb-3">Smart Scenes</h4>
          <SceneCards isSubmitting={isSubmittingControl} onActivateScene={handleActivateScene} />
        </section>

        <section>
          <h4 className="font-medium mb-3">House Floor Plan</h4>
          <div className="rounded-lg border border-gray-100 bg-white overflow-hidden">
            <FloorPlan />
          </div>
        </section>

        <section>
          <h4 className="font-medium mb-3">Quick Controls</h4>
          <ControlCard data={sensorData} isSubmitting={isSubmittingControl} onToggleDevice={handleToggleDevice} onChangeIntensity={handleIntensityChange} />
        </section>
      </div>

      {/* CỘT PHẢI: AI Assistant & Activity Log */}
      <div className="flex min-h-[70svh] flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white/70 shadow-sm backdrop-blur-sm sm:min-h-[560px] xl:h-full xl:min-h-0">
        {/* Tab Switcher */}
        <div className="flex gap-2 bg-gray-50/50 p-2">
          <button 
            onClick={() => setActiveRightTab('assistant')}
            className={`min-w-0 flex-1 rounded-xl px-2 py-2.5 text-sm font-semibold transition-all duration-200 ${activeRightTab === 'assistant' ? 'bg-white text-[#3A7D44] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
          >
            H.E.R.A Assistant
          </button>
          <button 
            onClick={() => setActiveRightTab('logs')}
            className={`min-w-0 flex-1 rounded-xl px-2 py-2.5 text-sm font-semibold transition-all duration-200 ${activeRightTab === 'logs' ? 'bg-white text-[#3A7D44] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
          >
            Activity Log
          </button>
        </div>

        {/* Nội dung Tab */}
        <div className="flex-1 overflow-hidden relative">
          {activeRightTab === 'assistant' ? (
            <div className="h-full animate-fadeIn">
              <AiAssistant />
            </div>
          ) : (
            <div className="h-full animate-fadeIn">
              {/* Truyền sensorData vào nếu bé Mận muốn log cập nhật realtime từ state */}
              <ActivityLog data={sensorData} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Home;
