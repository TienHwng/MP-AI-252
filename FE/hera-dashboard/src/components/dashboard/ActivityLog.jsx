import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Info,
  Power,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  XCircle,
} from 'lucide-react';
import { ACTIVITY_LOG_UPDATED_EVENT, fetchActivityLogs } from '../../services/api';

const QUICK_LOG_LIMIT = 15;
const REFRESH_MS = 15000;
const MANUAL_REFRESH_SPIN_MS = 650;

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

const severityStyles = {
  danger: {
    bg: 'bg-red-50',
    border: 'border-red-100',
    text: 'text-red-700',
    iconBg: 'bg-red-100',
    iconText: 'text-red-700',
  },
  warning: {
    bg: 'bg-[#FFF7ED]',
    border: 'border-[#FED7AA]',
    text: 'text-[#DF6D14]',
    iconBg: 'bg-[#FED7AA]',
    iconText: 'text-[#9A4A0F]',
  },
  success: {
    bg: 'bg-[#F0F9F1]',
    border: 'border-[#DDEEDD]',
    text: 'text-[#3A7D44]',
    iconBg: 'bg-[#E8F5E9]',
    iconText: 'text-[#3A7D44]',
  },
  neutral: {
    bg: 'bg-gray-50',
    border: 'border-gray-100',
    text: 'text-gray-600',
    iconBg: 'bg-gray-100',
    iconText: 'text-gray-500',
  },
  info: {
    bg: 'bg-sky-50',
    border: 'border-sky-100',
    text: 'text-sky-700',
    iconBg: 'bg-sky-100',
    iconText: 'text-sky-700',
  },
};

const triggerLabels = {
  web_dashboard: 'Web',
  hera_assistant: 'H.E.R.A',
  automation: 'Automation',
  schedule: 'Schedule',
  auth: 'Security',
  scene: 'Scene',
  simulator: 'Simulator',
  system: 'System',
};

const DEVICE_TARGET_LABELS = {
  main_led: 'LED living room',
  neo_led: 'LED bedroom',
  ws2812: 'LED toilet',
  mini_fan: 'Fan living room',
  relay: 'TV',
};

const DEVICE_TARGET_ROOMS = {
  main_led: 'Living Room',
  neo_led: 'Bedroom',
  ws2812: 'Toilet',
  mini_fan: 'Living Room',
  relay: 'Living Room',
};

const escapeRegExp = (value = '') => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const fullTimestamp = (value) => {
  if (!value) return '';
  return new Date(value).toLocaleString('vi-VN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const relativeTime = (value) => {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return 'Just now';

  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (diffSeconds < 60) return 'Just now';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes} min${diffMinutes > 1 ? 's' : ''} ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
};

const getLogIcon = (log) => {
  if (log.severity === 'danger' || log.eventType === 'security') return ShieldAlert;
  if (log.severity === 'warning' || log.eventType === 'threshold') return AlertTriangle;
  if (log.triggerSource === 'hera_assistant') return Bot;
  if (log.action?.toLowerCase().includes('off') || log.severity === 'neutral') return XCircle;
  if (log.eventType === 'scene') return SlidersHorizontal;
  if (log.eventType === 'control') return Power;
  if (log.severity === 'success') return CheckCircle2;
  return Info;
};

const getLogTimestamp = (log = {}) => {
  const value = log.createdAt || log.created_at || log.timestamp || 0;
  const timestamp = typeof value === 'number' ? value : new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
};

const getLogId = (log = {}) => log.id || log.logId || log.log_id || '';

const getLogTargetId = (log = {}) =>
  log.targetId ||
  log.target_id ||
  log.details?.targetId ||
  log.details?.target_id ||
  '';

const getLogDeviceLabel = (log = {}) => {
  const targetId = getLogTargetId(log);
  return DEVICE_TARGET_LABELS[targetId] || log.deviceName || targetId;
};

const getLogRoom = (log = {}) => {
  const targetId = getLogTargetId(log);
  return log.room || DEVICE_TARGET_ROOMS[targetId] || '';
};

const getDisplayMessage = (log = {}) => {
  const message = log.message || '';
  const targetId = getLogTargetId(log);
  const canonicalLabel = DEVICE_TARGET_LABELS[targetId];

  if (!message || !canonicalLabel) return message;

  return Object.values(DEVICE_TARGET_LABELS).reduce((text, label) => {
    if (label === canonicalLabel) return text;
    return text.replace(new RegExp(escapeRegExp(label), 'gi'), canonicalLabel);
  }, message);
};

const getLogIdentity = (log = {}) =>
  getLogId(log) ||
  [
    log.createdAt || log.created_at || log.timestamp || '',
    log.eventType || log.event_type || '',
    log.action || '',
    log.message || '',
  ].join('|');

const sortLogsByRecency = (items = []) =>
  items.slice().sort((a, b) => getLogTimestamp(b) - getLogTimestamp(a));

const appendNewLogs = (incomingLogs = [], currentLogs = []) => {
  const seen = new Set(currentLogs.map(getLogIdentity).filter(Boolean));
  const freshLogs = incomingLogs.filter((log) => {
    const identity = getLogIdentity(log);
    if (!identity) return true;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });

  return sortLogsByRecency([...freshLogs, ...currentLogs]);
};

const ActivityLog = () => {
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState('');
  const fetchBatchRef = useRef(0);
  const loadRequestRef = useRef(0);

  const createRenderableLogs = useCallback((items = []) => {
    const batchId = `${Date.now()}_${fetchBatchRef.current}`;
    fetchBatchRef.current += 1;

    return sortLogsByRecency(items.map((log, index) => ({
      ...log,
      renderKey: `${batchId}_${index}_${log.id || log.logId || log.createdAt || 'activity'}`,
    })));
  }, []);

  const createRenderableLog = useCallback((log) => createRenderableLogs([log])[0], [createRenderableLogs]);

  const loadLogs = useCallback(async ({
    append = false,
    excludeIds = [],
    filters = {},
    forceFresh = false,
    minSpinMs = 0,
    silent = false,
  } = {}) => {
    const requestId = loadRequestRef.current + 1;
    loadRequestRef.current = requestId;
    const startedAt = Date.now();
    if (!silent) setIsLoading(true);
    if (append) setIsRefreshing(true);

    try {
      const result = await fetchActivityLogs({
        surface: 'sidebar',
        limit: QUICK_LOG_LIMIT,
        filters,
        excludeIds,
        forceFresh,
      });
      const nextLogs = createRenderableLogs(result.items);

      if (requestId === loadRequestRef.current) {
        setLogs((currentLogs) => {
          if (append) return appendNewLogs(nextLogs, currentLogs);
          return nextLogs;
        });
        setError('');
      }
    } catch (loadError) {
      if (requestId === loadRequestRef.current) {
        setError(loadError.message || 'Unable to load activity logs.');
      }
    } finally {
      const remainingSpinMs = minSpinMs - (Date.now() - startedAt);
      if (remainingSpinMs > 0) {
        await wait(remainingSpinMs);
      }

      if (append) setIsRefreshing(false);
      if (!silent) setIsLoading(false);
    }
  }, [createRenderableLogs]);

  const handleManualRefresh = () => {
    const excludeIds = logs.map(getLogId).filter(Boolean);
    const latestTimestamp = Math.max(0, ...logs.map(getLogTimestamp));

    loadLogs({
      append: true,
      excludeIds,
      filters: latestTimestamp > 0 ? { from: new Date(latestTimestamp).toISOString() } : {},
      forceFresh: true,
      minSpinMs: MANUAL_REFRESH_SPIN_MS,
    });
  };

  useEffect(() => {
    loadLogs();
    const intervalId = window.setInterval(() => loadLogs({ silent: true }), REFRESH_MS);
    const handleLogUpdated = (event) => {
      if (event.detail?.showOnSidebar !== false) {
        const updatedLog = createRenderableLog(event.detail);
        if (updatedLog) {
          setLogs((currentLogs) => appendNewLogs([updatedLog], currentLogs).slice(0, QUICK_LOG_LIMIT));
          setError('');
        }
      }
      loadLogs({ forceFresh: true, silent: true });
    };
    window.addEventListener(ACTIVITY_LOG_UPDATED_EVENT, handleLogUpdated);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener(ACTIVITY_LOG_UPDATED_EVENT, handleLogUpdated);
    };
  }, [createRenderableLog, loadLogs]);

  return (
    <div className="flex h-full flex-col p-4">
      <div className="mb-4 flex items-center justify-between gap-3 px-1">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-semibold text-gray-800">Recent Activity</h3>
          <p className="text-xs text-gray-400">Latest system events</p>
        </div>
        <button
          type="button"
          onClick={handleManualRefresh}
          aria-label="Refresh activity logs"
          title="Refresh activity logs"
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border bg-white text-gray-500 transition-all duration-200 hover:text-[#3A7D44] ${isRefreshing ? 'border-[#3A7D44]/30 bg-[#F0F9F1] text-[#3A7D44] shadow-[0_0_0_4px_rgba(58,125,68,0.12)]' : 'border-gray-100'}`}
        >
          <RefreshCw size={16} className={isLoading || isRefreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="custom-scrollbar flex-1 overflow-y-auto pr-2">
        {isLoading && logs.length === 0 ? (
          <div className="space-y-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-[78px] animate-pulse rounded-lg bg-gray-100" />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-gray-400">
            <Clock3 size={42} strokeWidth={1.5} className="mb-3 text-gray-300" />
            <p className="text-sm">No recent activity.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {logs.map((log) => {
              const styles = severityStyles[log.severity] || severityStyles.info;
              const Icon = getLogIcon(log);
              const source = triggerLabels[log.triggerSource] || log.triggerSource || 'System';
              const displayMessage = getDisplayMessage(log);
              const deviceLabel = getLogDeviceLabel(log);
              const room = getLogRoom(log);
              const metaItems = [
                log.actorName || source,
                source,
                deviceLabel,
                room,
                relativeTime(log.createdAt),
              ].filter((item, index, items) => item && items.indexOf(item) === index);

              return (
                <article
                  key={log.renderKey}
                  title={fullTimestamp(log.createdAt)}
                  className={`rounded-lg border p-3 shadow-[0_2px_10px_-6px_rgba(15,23,42,0.25)] transition-shadow hover:shadow-sm ${styles.bg} ${styles.border}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${styles.iconBg} ${styles.iconText}`}>
                      <Icon size={16} strokeWidth={2} />
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-sm font-medium leading-snug text-gray-800">
                        <span className={styles.text}>{log.action || log.eventType}</span>
                        {displayMessage ? `: ${displayMessage}` : ''}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-gray-500">
                        {metaItems.map((item, index) => (
                          <React.Fragment key={`${log.renderKey}-meta-${item}`}>
                            {index > 0 && <span className="h-1 w-1 rounded-full bg-gray-300" />}
                            <span className="max-w-full truncate">{item}</span>
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityLog;
