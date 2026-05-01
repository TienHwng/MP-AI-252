import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Droplets,
  Fan,
  Lightbulb,
  Plug,
  RefreshCw,
  SunMedium,
  Thermometer,
  WifiOff,
} from 'lucide-react';
import {
  controlDeviceState,
  fetchRuntimeStatus,
  fetchLatestSensorData,
  getDeviceStatus,
  getSensorValue,
  subscribeLatestSensorData,
  writeSensorValue,
} from '../services/api';

const TELEMETRY_STALE_MS = 30_000;
const COMMAND_CONFIRM_TIMEOUT_MS = 8_000;

const markerDefinitions = [
  {
    id: 'main_led',
    name: 'LED',
    type: 'light',
    room: 'toilet',
    x: 85,
    y: 15,
    target: 'main_led',
    Icon: Lightbulb,
  },
  {
    id: 'ws2812',
    name: 'LED',
    type: 'light',
    room: 'Bedroom',
    x: 83,
    y: 47,
    target: 'ws2812',
    Icon: Lightbulb,
  },
  {
    id: 'neo_led',
    name: 'LED',
    type: 'light',
    room: 'Living Room',
    x: 46,
    y: 26,
    target: 'neo_led',
    Icon: Lightbulb,
  },
  {
    id: 'Fan',
    name: 'Mini Fan',
    type: 'fan',
    room: 'Living Room',
    x: 35,
    y: 6,
    target: 'mini_fan',
    Icon: Fan,
  },
  {
    id: 'relay',
    name: 'TV',
    type: 'relay',
    room: 'Living Room',
    x: 32,
    y: 25,
    target: 'relay',
    Icon: Plug,
  },
  {
    id: 'temperature',
    name: 'Temperature',
    type: 'sensor',
    sensor: 'temperature',
    unit: 'C',
    room: 'Living Room',
    x: 55,
    y: 93,
    Icon: Thermometer,
  },
  {
    id: 'humidity',
    name: 'Humidity',
    type: 'sensor',
    sensor: 'humidity',
    unit: '%',
    room: 'Living Room',
    x: 50,
    y: 93,
    Icon: Droplets,
  },
// Cảm biến ánh sáng, correct later  
  {
    id: 'photon',
    name: 'Photon',
    type: 'sensor',
    sensor: 'photon',
    unit: '%',
    room: 'Living Room',
    x: 53,
    y: 7,
    Icon: SunMedium,
  },
];

const boolLabel = (value) => {
  if (value === true) return 'ON';
  if (value === false) return 'OFF';
  return 'UNKNOWN';
};

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'UNKNOWN';
  return Number(value).toFixed(Number.isInteger(Number(value)) ? 0 : 1);
};

const toTimeMs = (value) => {
  if (!value) return 0;
  if (typeof value === 'number') return value;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const buildMarkers = (telemetry) =>
  markerDefinitions.map((definition) => {
    if (definition.type === 'sensor') {
      return {
        ...definition,
        value: getSensorValue(telemetry, definition.sensor),
      };
    }

    return {
      ...definition,
      status: getDeviceStatus(telemetry, definition.target),
    };
  });

const getMarkerLabel = (marker) => {
  if (marker.type === 'sensor') {
    return `${formatNumber(marker.value)} ${marker.unit}`;
  }
  return boolLabel(marker.status);
};

function DeviceMarker({ marker, selected, stale, pending, onClick }) {
  const isSensor = marker.type === 'sensor';
  const isOn = marker.status === true;
  const Icon = marker.Icon;

  return (
    <button
      type="button"
      onClick={onClick}
      title={`${marker.name} - ${getMarkerLabel(marker)}`}
      style={{
        ...styles.marker,
        left: `${marker.x}%`,
        top: `${marker.y}%`,
        width: selected ? 'clamp(40px, 8vw, 58px)' : 'clamp(34px, 7vw, 48px)',
        height: selected ? 'clamp(40px, 8vw, 58px)' : 'clamp(34px, 7vw, 48px)',
        border: selected ? '3px solid #DF6D14' : '2px solid white',
        background: isSensor
          ? 'rgba(66, 122, 181, 0.95)'
          : isOn
            ? 'rgba(58, 125, 68, 0.96)'
            : 'rgba(107, 114, 128, 0.9)',
        color: isSensor || isOn ? '#ffffff' : 'white',
        opacity: stale ? 0.65 : 1,
        boxShadow: isOn
          ? '0 0 28px rgba(58, 125, 68, 0.96), 0 8px 20px rgba(0,0,0,0.35)'
          : '0 8px 20px rgba(0,0,0,0.35)',
      }}
    >
      <Icon size={22} strokeWidth={2.2} />
      {pending && <span style={styles.pendingDot} />}
    </button>
  );
}

function LightGlow({ marker, stale }) {
  if (marker.type !== 'light' || marker.status !== true || stale) return null;

  return (
    <div
      style={{
        ...styles.glow,
        left: `${marker.x}%`,
        top: `${marker.y}%`,
        width: 'clamp(120px, 34vw, 220px)',
        height: 'clamp(120px, 34vw, 220px)',
      }}
    />
  );
}

function Notice({ tone = 'info', children }) {
  if (!children) return null;
  return (
    <div
      style={{
        ...styles.notice,
        borderColor: tone === 'error' ? '#DF6D14' : '#3A7D44',
        background: tone === 'error' ? '#FED7AA' : '#E8F5E9',
        color: tone === 'error' ? '#DF6D14' : '#3A7D44',
      }}
    >
      <AlertTriangle size={18} />
      <span>{children}</span>
    </div>
  );
}

function SensorWriteControls({ marker, disabled, onWriteSensor }) {
  const [sensorValue, setSensorValue] = useState(
    marker.value === null || marker.value === undefined ? '' : String(marker.value),
  );

  const submitSensorWrite = () => {
    const parsed = Number(sensorValue);
    if (!Number.isFinite(parsed)) return;
    onWriteSensor(marker.sensor, parsed);
  };

  return (
    <div style={styles.sensorWrite}>
      <input
        type="number"
        value={sensorValue}
        onChange={(event) => setSensorValue(event.target.value)}
        style={styles.input}
        disabled={disabled}
      />
      <button
        type="button"
        style={{
          ...styles.secondaryButton,
          opacity: disabled ? 0.55 : 1,
        }}
        onClick={submitSensorWrite}
        disabled={disabled}
      >
        Write
      </button>
    </div>
  );
}

function DevicePanel({
  marker,
  telemetry,
  stale,
  runtimeAvailable,
  pendingCommand,
  onToggle,
  onWriteSensor,
}) {
  if (!telemetry) {
    return (
      <div style={styles.panel}>
        <h3 style={styles.panelTitle}>Digital Twin Offline</h3>
        <p style={styles.muted}>No telemetry has been received from MQTT.</p>
      </div>
    );
  }

  if (!marker) {
    return (
      <div style={styles.panel}>
        <h3 style={styles.panelTitle}>Smart Home Twin</h3>
        <p style={styles.muted}>Select a live marker to inspect MQTT state.</p>
      </div>
    );
  }

  const isControllable = marker.target;
  const mode = telemetry.mode || 'unknown';
  const isSimMode = mode === 'sim';
  const controlDisabled = stale || !runtimeAvailable;
  const writeDisabled = marker.type !== 'sensor' || !isSimMode || controlDisabled;
  const pendingThisMarker = pendingCommand?.id === marker.id;

  return (
    <div style={styles.panel}>
      <div style={styles.panelHeader}>
        <div>
          <h3 style={styles.panelTitle}>{marker.name}</h3>
          <p style={styles.muted}>{marker.room}</p>
        </div>
        <span style={styles.modeBadge}>{mode.toUpperCase()}</span>
      </div>

      <p style={styles.row}>
        <b>Type:</b> {marker.type}
      </p>
      <p style={styles.row}>
        <b>State:</b> {getMarkerLabel(marker)}
      </p>
      <p style={styles.row}>
        <b>Source:</b> {telemetry.source || 'mqtt'}
      </p>
      <p style={styles.row}>
        <b>Updated:</b>{' '}
        {telemetry.updatedAt ? new Date(telemetry.updatedAt).toLocaleTimeString() : 'unknown'}
      </p>

      {isControllable && (
        <button
          type="button"
          style={{
            ...styles.primaryButton,
            opacity: controlDisabled || pendingThisMarker ? 0.55 : 1,
          }}
          onClick={() => onToggle(marker)}
          disabled={controlDisabled || pendingThisMarker}
        >
          {pendingThisMarker ? (
            <RefreshCw size={16} style={styles.spinIcon} />
          ) : (
            null
          )}
          Set {marker.status === true ? 'OFF' : 'ON'}
        </button>
      )}

      {marker.type === 'sensor' && (
        <SensorWriteControls
          key={marker.id}
          marker={marker}
          disabled={writeDisabled}
          onWriteSensor={onWriteSensor}
        />
      )}
    </div>
  );
}

export default function FloorPlan() {
  const [telemetry, setTelemetry] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('info');
  const [pendingCommand, setPendingCommand] = useState(null);
  const [now, setNow] = useState(0);
  const [runtimeError, setRuntimeError] = useState('');
  const pendingCommandRef = useRef(null);

  const setPending = useCallback((value) => {
    pendingCommandRef.current = value;
    setPendingCommand(value);
  }, []);

  const handleTelemetry = useCallback((next) => {
    setTelemetry(next);
    setNotice('');
    const current = pendingCommandRef.current;
    if (!current) return;

    const marker = buildMarkers(next).find((item) => item.id === current.id);
    if (marker && marker.status === current.expectedState) {
      setPending(null);
      setNotice(`${marker.name} confirmed ${boolLabel(marker.status)} from telemetry.`);
      setNoticeTone('info');
    }
  }, [setPending]);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe = null;

    const load = async () => {
      try {
        const latest = await fetchLatestSensorData();
        if (!cancelled) {
          handleTelemetry(latest);
        }
      } catch (error) {
        if (!cancelled) {
          setNotice(error.message || 'Unable to receive MQTT telemetry.');
          setNoticeTone('error');
        }
      }

      try {
        unsubscribe = subscribeLatestSensorData({
          onData: (next) => {
            handleTelemetry(next);
          },
          onError: () => {
            setNotice('Telemetry stream disconnected. Waiting for MQTT data.');
            setNoticeTone('error');
          },
        });
      } catch (error) {
        setNotice(error.message || 'Unable to open telemetry stream.');
        setNoticeTone('error');
      }
    };

    load();

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [handleTelemetry]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const checkRuntime = async () => {
      try {
        await fetchRuntimeStatus();
        if (!cancelled) setRuntimeError('');
      } catch (error) {
        if (!cancelled) {
          setRuntimeError(
            `${error.message || 'HERA dashboard API is unavailable'} Start BE\\HERA\\api_server.py for MQTT controls and assistant commands.`,
          );
        }
      }
    };

    checkRuntime();
    const interval = window.setInterval(checkRuntime, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const markers = useMemo(() => buildMarkers(telemetry), [telemetry]);
  const selectedMarker = useMemo(
    () => markers.find((marker) => marker.id === selectedId),
    [markers, selectedId],
  );
  const updatedAtMs = toTimeMs(telemetry?.updatedAt || telemetry?.last_seen_at);
  const stale = !telemetry || !updatedAtMs || now - updatedAtMs > TELEMETRY_STALE_MS;

  const toggleDevice = async (marker) => {
    if (runtimeError) {
      setNotice(runtimeError);
      setNoticeTone('error');
      return;
    }

    const expectedState = marker.status !== true;
    const pending = {
      id: marker.id,
      expectedState,
      startedAt: Date.now(),
    };
    setPending(pending);
    setNotice(`Sending MQTT command for ${marker.name}...`);
    setNoticeTone('info');

    window.setTimeout(() => {
      const current = pendingCommandRef.current;
      if (current?.id !== pending.id || current?.startedAt !== pending.startedAt) return;
      setPending(null);
      setNotice('MQTT command was sent, but telemetry did not confirm the requested state.');
      setNoticeTone('error');
    }, COMMAND_CONFIRM_TIMEOUT_MS);

    try {
      await controlDeviceState(marker.target, expectedState);
    } catch (error) {
      setPending(null);
      setNotice(error.message || `Failed to control ${marker.name}.`);
      setNoticeTone('error');
    }
  };

  const writeSensor = async (sensor, value) => {
    if (runtimeError) {
      setNotice(runtimeError);
      setNoticeTone('error');
      return;
    }

    setNotice(`Writing ${sensor} through MQTT simulator...`);
    setNoticeTone('info');
    try {
      await writeSensorValue(sensor, value);
    } catch (error) {
      setNotice(error.message || `Failed to write ${sensor}.`);
      setNoticeTone('error');
    }
  };

  const visibleNotice = stale
    ? 'Telemetry is stale or unavailable. Controls are disabled until MQTT data resumes.'
    : runtimeError || notice;
  const visibleNoticeTone = stale || runtimeError ? 'error' : noticeTone;

  return (
    <div className={`grid min-h-screen w-full gap-4 bg-background p-3 sm:p-4 lg:gap-5 lg:p-6 ${selectedMarker ? 'grid-cols-1 lg:grid-cols-[minmax(0,1fr)_150px]' : 'grid-cols-1'}`}>
      <div className="min-w-0">
        <Notice tone={visibleNoticeTone}>{visibleNotice}</Notice>

        <div className="relative mx-auto w-full max-w-[1100px] overflow-hidden rounded-lg bg-white shadow-[0_14px_44px_rgba(15,23,42,0.16)] lg:shadow-[0_20px_60px_rgba(15,23,42,0.18)]">
          <img
            src="/floor plan.png"
            alt="Smart home floor plan"
            style={styles.floorImage}
            draggable={false}
            onError={(event) => {
              event.currentTarget.src = '/floorplan.png';
            }}
          />

          {telemetry &&
            markers.map((marker) => (
              <LightGlow key={`glow-${marker.id}`} marker={marker} stale={stale} />
            ))}

          {telemetry &&
            markers.map((marker) => (
              <DeviceMarker
                key={marker.id}
                marker={marker}
                selected={marker.id === selectedMarker?.id}
                stale={stale}
                pending={pendingCommand?.id === marker.id}
                onClick={() => setSelectedId(selectedId === marker.id ? null : marker.id)}
              />
            ))}

          {!telemetry && (
            <div style={styles.noDataOverlay}>
              <WifiOff size={34} />
              <span>No MQTT telemetry</span>
            </div>
          )}
        </div>
      </div>

      {selectedMarker && (
        <DevicePanel
          marker={selectedMarker}
          telemetry={telemetry}
          stale={stale}
          runtimeAvailable={!runtimeError}
          pendingCommand={pendingCommand}
          onToggle={toggleDevice}
          onWriteSensor={writeSensor}
        />
      )}
    </div>
  );
}

const styles = {
  page: {
    width: '100%',
    minHeight: '100vh',
    background: '#F8F5E9',
    display: 'grid',
    gridTemplateColumns: 'minmax(640px, 1fr) 340px',
    gap: 20,
    padding: 24,
    boxSizing: 'border-box',
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
  },
  mainColumn: {
    minWidth: 0,
  },
  floorWrapper: {
    position: 'relative',
    width: '100%',
    maxWidth: 1100,
    margin: '0 auto',
    background: 'white',
    borderRadius: 8,
    overflow: 'hidden',
    boxShadow: '0 20px 60px rgba(15, 23, 42, 0.18)',
  },
  floorImage: {
    width: '100%',
    display: 'block',
    userSelect: 'none',
  },
  marker: {
    position: 'absolute',
    transform: 'translate(-50%, -50%)',
    borderRadius: '999px',
    cursor: 'pointer',
    zIndex: 5,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 160ms ease',
  },
  pendingDot: {
    position: 'absolute',
    right: 2,
    top: 2,
    width: 11,
    height: 11,
    borderRadius: '999px',
    background: '#3A7D44',
    border: '2px solid white',
  },
  glow: {
    position: 'absolute',
    transform: 'translate(-50%, -50%)',
    width: 220,
    height: 220,
    borderRadius: '999px',
    background:
      'radial-gradient(circle, rgba(223,109,20,0.55) 0%, rgba(223,109,20,0.22) 35%, rgba(223,109,20,0) 70%)',
    pointerEvents: 'none',
    zIndex: 2,
  },
  panel: {
    background: 'white',
    borderRadius: 8,
    padding: 18,
    boxShadow: '0 20px 60px rgba(15, 23, 42, 0.14)',
    alignSelf: 'start',
  },
  panelHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  panelTitle: {
    margin: '0 0 4px',
    fontSize: 20,
  },
  muted: {
    color: '#64748b',
    lineHeight: 1.5,
    margin: 0,
  },
  row: {
    margin: '8px 0',
    color: '#334155',
  },
  modeBadge: {
    borderRadius: 999,
    padding: '5px 9px',
    background: '#E8F5E9',
    color: '#3A7D44',
    fontSize: 12,
    fontWeight: 800,
  },
  primaryButton: {
    width: '100%',
    marginTop: 12,
    padding: '11px 12px',
    border: 'none',
    borderRadius: 8,
    background: '#3A7D44',
    color: 'white',
    fontWeight: 700,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  secondaryButton: {
    padding: '10px 12px',
    border: 'none',
    borderRadius: 8,
    background: '#0f172a',
    color: 'white',
    fontWeight: 700,
    cursor: 'pointer',
  },
  sensorWrite: {
    display: 'grid',
    gridTemplateColumns: '1fr 84px',
    gap: 8,
    marginTop: 12,
  },
  input: {
    width: '100%',
    minWidth: 0,
    border: '1px solid #cbd5e1',
    borderRadius: 8,
    padding: '10px 12px',
    boxSizing: 'border-box',
  },
  notice: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    border: '1px solid',
    borderRadius: 8,
    padding: '10px 12px',
    marginBottom: 12,
    fontSize: 14,
  },
  statusBar: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 12,
  },
  statusItem: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '7px 10px',
    borderRadius: 8,
    background: 'white',
    color: '#334155',
    fontSize: 13,
    boxShadow: '0 6px 16px rgba(15, 23, 42, 0.08)',
  },
  noDataOverlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    background: 'rgba(248, 250, 252, 0.88)',
    color: '#334155',
    fontWeight: 800,
    zIndex: 10,
  },
  spinIcon: {
    animation: 'spin 1s linear infinite',
  },
};
