import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
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
  recordActivityLog,
  sendRpcCommand 
} from '../services/api';

const DEVICE_LABELS = {
  main_led: 'LED living room',
  neo_led: 'LED bedroom',
  ws2812: 'LED toilet',
  mini_fan: 'Fan living room',
  relay: 'TV',
};

const SCENE_LABELS = {
  movie: 'Movie Mode',
  sleep: 'Sleep Mode',
  away: 'Away Mode',
};

const RIGHT_SIDEBAR_TRANSITION_MS = 300;

const readEnvNumber = (keys, fallback) => {
  for (const key of keys) {
    const value = import.meta.env[key];
    if (value === undefined || value === null || value === '') continue;

    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }

  return fallback;
};

const ENVIRONMENT_THRESHOLDS = {
  temperature: {
    min: readEnvNumber(['NORMAL_TEMP_MIN', 'VITE_NORMAL_TEMP_MIN'], 25),
    max: readEnvNumber(['NORMAL_TEMP_MAX', 'VITE_NORMAL_TEMP_MAX'], 35),
  },
  humidity: {
    min: readEnvNumber(['NORMAL_HUMI_MIN', 'NORMAL_HUMIDITY_MIN', 'VITE_NORMAL_HUMI_MIN', 'VITE_NORMAL_HUMIDITY_MIN'], 60),
    max: readEnvNumber(['NORMAL_HUMI_MAX', 'NORMAL_HUMIDITY_MAX', 'VITE_NORMAL_HUMI_MAX', 'VITE_NORMAL_HUMIDITY_MAX'], 80),
  },
};

const Home = ({ user, onLogout }) => {
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [sensorData, setSensorData] = useState(null);
  const [telemetryError, setTelemetryError] = useState('');
  const [isSubmittingControl, setIsSubmittingControl] = useState(false);
  
  // State mới để quản lý Tab ở cột phải
  const [activeRightTab, setActiveRightTab] = useState('assistant');
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  const [shouldRenderRightSidebar, setShouldRenderRightSidebar] = useState(true);

  useEffect(() => {
    const timerId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    if (isRightSidebarOpen) {
      setShouldRenderRightSidebar(true);
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setShouldRenderRightSidebar(false);
    }, RIGHT_SIDEBAR_TRANSITION_MS);

    return () => window.clearTimeout(timeoutId);
  }, [isRightSidebarOpen]);

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
      await controlDeviceState(target, nextValue, {
        oldValue: currentStatus,
        triggerSource: 'web_dashboard',
        actorName: user?.full_name || 'Dashboard',
      });
    } catch (error) {
      console.error(`Failed to toggle ${target}:`, error);
      setTelemetryError(error.message || `Failed to toggle ${target}`);
    } finally {
      setIsSubmittingControl(false);
    }
  };

  const handleActivateScene = async (sceneId) => {
    setIsSubmittingControl(true);
    const sceneLabel = SCENE_LABELS[sceneId] || sceneId;
    const sceneActivity = {
      triggerSource: 'scene',
      actorType: 'scene',
      actorName: sceneLabel,
      details: { scene_id: sceneId },
    };
    const sceneRpcActivity = (targetId, percentValue = 0) => ({
      triggerSource: 'scene',
      activity: {
        targetId,
        actorType: 'scene',
        actorName: sceneLabel,
        percentValue,
        displayValue: percentValue,
        unit: '%',
        details: { scene_id: sceneId },
        showOnSidebar: false,
      },
    });
    const sceneLogPromise = recordActivityLog({
      target_id: sceneId,
      device_name: sceneLabel,
      room: 'Whole Home',
      event_type: 'scene',
      trigger_source: 'web_dashboard',
      severity: 'info',
      action: 'Scene Activated',
      message: `${user?.full_name || 'Dashboard'} activated ${sceneLabel}.`,
      actor_type: 'user',
      actor_name: user?.full_name || 'Dashboard',
      details: { scene_id: sceneId },
      show_on_sidebar: true,
    }).catch((logError) => {
      console.warn('Failed to record scene activity:', logError);
    });

    try {
      if (sceneId === 'movie') {
        await Promise.all([
          controlDeviceState('main_led', false, sceneActivity),
          controlDeviceState('neo_led', false, sceneActivity),
          controlDeviceState('ws2812', false, sceneActivity),
          controlDeviceState('mini_fan', true, sceneActivity),
          controlDeviceState('relay', true, sceneActivity),
          // Set light intensity to 0
          sendRpcCommand('setMainLedBrightness', 0, sceneRpcActivity('main_led')),
          sendRpcCommand('setStripBrightness', 0, sceneRpcActivity('neo_led')),
          sendRpcCommand('setWS2812Brightness', 0, sceneRpcActivity('ws2812'))
        ]);
      } 
      else if (sceneId === 'sleep') {
        await Promise.all([
          controlDeviceState('main_led', false, sceneActivity),
          controlDeviceState('neo_led', false, sceneActivity),
          controlDeviceState('ws2812', false, sceneActivity),
          // Set light intensity to 0
          sendRpcCommand('setMainLedBrightness', 0, sceneRpcActivity('main_led')),
          sendRpcCommand('setStripBrightness', 0, sceneRpcActivity('neo_led')),
          sendRpcCommand('setWS2812Brightness', 0, sceneRpcActivity('ws2812'))
        ]);
      } 
      else if (sceneId === 'away') {
        await Promise.all([
          controlDeviceState('main_led', false, sceneActivity),
          controlDeviceState('neo_led', false, sceneActivity),
          controlDeviceState('ws2812', false, sceneActivity),
          controlDeviceState('mini_fan', false, sceneActivity),
          controlDeviceState('relay', false, sceneActivity),
          // Set intensity to 0
          sendRpcCommand('setMainLedBrightness', 0, sceneRpcActivity('main_led')),
          sendRpcCommand('setStripBrightness', 0, sceneRpcActivity('neo_led')),
          sendRpcCommand('setWS2812Brightness', 0, sceneRpcActivity('ws2812')),
          sendRpcCommand('setFanSpeed', 0, sceneRpcActivity('mini_fan'))
        ]);
      }
      await sceneLogPromise;
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
      await sendRpcCommand(rpcMethod, pwmValue, {
        triggerSource: 'web_dashboard',
        activity: {
          targetId: deviceId,
          deviceName: DEVICE_LABELS[deviceId] || deviceId,
          percentValue,
          displayValue: percentValue,
          unit: '%',
          action: 'Intensity Changed',
          message: `${user?.full_name || 'Dashboard'} set ${DEVICE_LABELS[deviceId] || deviceId} to ${percentValue}%.`,
          actorName: user?.full_name || 'Dashboard',
        },
      });
    } catch (error) {
      console.error(`Lỗi khi điều chỉnh cường độ cho ${deviceId}:`, error);
      setTelemetryError(error.message || `Không thể điều chỉnh cường độ cho ${deviceId}`);
    }
  };

  const handleLogout = () => {
    logoutUser();
    onLogout();
  };

  const openRightSidebar = () => {
    setShouldRenderRightSidebar(true);
    window.requestAnimationFrame(() => {
      setIsRightSidebarOpen(true);
    });
  };

  const closeRightSidebar = () => {
    setIsRightSidebarOpen(false);
  };

  return (
    <div className={`relative grid min-h-screen w-full grid-cols-1 gap-4 overflow-x-hidden bg-background p-3 transition-[grid-template-columns] duration-300 sm:p-4 lg:p-6 xl:h-screen xl:overflow-hidden ${shouldRenderRightSidebar ? 'xl:grid-cols-[minmax(0,1fr)_350px] xl:gap-6' : 'xl:grid-cols-1'}`}>
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
          <EnvironmentCards data={sensorData} thresholds={ENVIRONMENT_THRESHOLDS} />
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

      <button
        type="button"
        onClick={openRightSidebar}
        aria-label="Expand right sidebar"
        title="Open H.E.R.A panel"
        className={`fixed right-3 top-3 z-40 inline-flex h-10 items-center gap-2 rounded-full border border-gray-100 bg-white/95 px-3 text-sm font-semibold text-[#3A7D44] shadow-md backdrop-blur transition-all duration-300 hover:bg-[#E8F5E9] sm:right-4 sm:top-4 ${shouldRenderRightSidebar ? 'pointer-events-none translate-x-3 scale-95 opacity-0' : 'translate-x-0 scale-100 opacity-100'}`}
      >
        <ChevronLeft size={16} />
        <span>H.E.R.A</span>
      </button>

      {/* CỘT PHẢI: AI Assistant & Activity Log */}
      {shouldRenderRightSidebar && (
        <aside className={`relative flex min-h-[70svh] transform flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white/70 shadow-sm backdrop-blur-sm transition-transform duration-300 sm:min-h-[560px] xl:h-full xl:min-h-0 ${isRightSidebarOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <button
            type="button"
            onClick={closeRightSidebar}
            aria-label="Collapse right sidebar"
            title="Collapse sidebar"
            className="absolute right-2 top-2 z-20 grid h-9 w-9 place-items-center rounded-lg border border-gray-100 bg-white text-gray-500 shadow-sm transition-colors hover:text-[#3A7D44]"
          >
            <ChevronRight size={17} />
          </button>

            {/* Tab Switcher */}
            <div className="flex gap-2 bg-gray-50/50 p-2 pr-12">
              <button
                type="button"
                onClick={() => setActiveRightTab('assistant')}
                className={`min-w-0 flex-1 rounded-xl px-2 py-2.5 text-sm font-semibold transition-all duration-200 ${activeRightTab === 'assistant' ? 'bg-white text-[#3A7D44] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
              >
                H.E.R.A Assistant
              </button>
              <button
                type="button"
                onClick={() => setActiveRightTab('logs')}
                className={`min-w-0 flex-1 rounded-xl px-2 py-2.5 text-sm font-semibold transition-all duration-200 ${activeRightTab === 'logs' ? 'bg-white text-[#3A7D44] shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
              >
                Activity Log
              </button>
            </div>

            {/* Nội dung Tab */}
            <div className="relative flex-1 overflow-hidden">
              {activeRightTab === 'assistant' ? (
                <div className="h-full animate-fadeIn">
                  <AiAssistant />
                </div>
              ) : (
                <div className="h-full animate-fadeIn">
                  <ActivityLog data={sensorData} />
                </div>
              )}
            </div>
        </aside>
      )}
    </div>
  );
};

export default Home;
