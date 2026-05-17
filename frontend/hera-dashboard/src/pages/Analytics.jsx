import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
	ChevronLeft,
	ChevronRight,
	Droplets,
	RefreshCw,
	Search,
	Sun,
	Thermometer,
} from "lucide-react";
import {
	AreaChart,
	Area,
	XAxis,
	YAxis,
	Tooltip,
	ResponsiveContainer,
	CartesianGrid,
} from "recharts";
import {
	fetchActivityLogs,
	fetchTelemetrySeries,
	getSensorValue,
	subscribeTelemetrySeries,
} from "../services/api";

const CHART_BUCKET_MS = 5 * 1000;
const TELEMETRY_HISTORY_LIMIT = 10000;
const TELEMETRY_REFRESH_MS = 30 * 1000;
const AUDIT_PAGE_SIZE = 12;
const SHOW_AUDIT_LOGS = false;

const TIME_WINDOW_CONFIG = {
	"5m": {
		duration: 5 * 60 * 1000,
		tickStep: 60 * 1000,
	},
	"15m": {
		duration: 15 * 60 * 1000,
		tickStep: 3 * 60 * 1000,
	},
	"1h": {
		duration: 60 * 60 * 1000,
		tickStep: 10 * 60 * 1000,
	},
};

const DATA_TICK_STEPS = [
	10 * 1000,
	20 * 1000,
	30 * 1000,
	60 * 1000,
	2 * 60 * 1000,
	3 * 60 * 1000,
	5 * 60 * 1000,
	10 * 60 * 1000,
	15 * 60 * 1000,
	30 * 60 * 1000,
	60 * 60 * 1000,
];

const WINDOW_OPTIONS = [
	{ key: "5m", label: "5 minutes" },
	{ key: "15m", label: "15 minutes" },
	{ key: "1h", label: "1 hour" },
	{ key: "all", label: "All" },
];

const AUDIT_TYPE_OPTIONS = [
	{ value: "all", label: "All types" },
	{ value: "control", label: "Control" },
	{ value: "threshold", label: "Threshold" },
	{ value: "scene", label: "Scene" },
	{ value: "security", label: "Security" },
	{ value: "system", label: "System" },
];

const AUDIT_TRIGGER_OPTIONS = [
	{ value: "all", label: "All triggers" },
	{ value: "web_dashboard", label: "Web" },
	{ value: "hera_assistant", label: "H.E.R.A" },
	{ value: "automation", label: "Automation" },
	{ value: "scene", label: "Scene" },
	{ value: "auth", label: "Security" },
	{ value: "simulator", label: "Simulator" },
];

const AUDIT_ROOM_OPTIONS = [
	{ value: "all", label: "All rooms" },
	{ value: "Living Room", label: "Living Room" },
	{ value: "Bedroom", label: "Bedroom" },
	{ value: "Toilet", label: "Toilet" },
	{ value: "Main Room", label: "Main Room" },
	{ value: "Whole Home", label: "Whole Home" },
	{ value: "Security", label: "Security" },
	{ value: "System", label: "System" },
];

const auditSeverityClass = {
	danger: "bg-red-50 text-red-700 border-red-100",
	warning: "bg-[#FFF7ED] text-[#DF6D14] border-[#FED7AA]",
	success: "bg-[#E8F5E9] text-[#3A7D44] border-[#DDEEDD]",
	neutral: "bg-gray-100 text-gray-600 border-gray-200",
	info: "bg-sky-50 text-sky-700 border-sky-100",
};

const getStats = (series) => {
	if (!series.length) {
		return { min: 0, max: 0, avg: 0 };
	}

	const min = Math.min(...series);
	const max = Math.max(...series);
	const avg = series.reduce((sum, num) => sum + num, 0) / series.length;

	return { min, max, avg };
};

const formatMetric = (value) => Number(value).toFixed(1);

const formatFullDateTime = (value) => {
	if (!value) return "--";
	return new Date(value).toLocaleString("vi-VN", {
		hour12: false,
	});
};

const toDateInputValue = (value) => {
	if (!value) return "";
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return "";
	return date.toISOString().slice(0, 10);
};

const fromDateInputValue = (value, endOfDay = false) => {
	if (!value) return "";
	const suffix = endOfDay ? "T23:59:59.999" : "T00:00:00.000";
	const date = new Date(`${value}${suffix}`);
	return Number.isNaN(date.getTime()) ? "" : date.toISOString();
};

const formatAuditValue = (value) => {
	if (value === null || value === undefined || value === "") return "--";
	if (typeof value === "boolean") return value ? "ON" : "OFF";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
};

const formatAuditDetails = (log) => {
	if (log.oldValue !== null || log.newValue !== null) {
		return `${formatAuditValue(log.oldValue)} -> ${formatAuditValue(log.newValue)}`;
	}
	if (log.details?.threshold !== undefined) {
		return `${formatAuditValue(log.details.value)} / ${formatAuditValue(log.details.threshold)} ${log.details.unit || ""}`.trim();
	}
	if (log.details?.ip) return `IP: ${log.details.ip}`;
	if (log.details?.method) return log.details.method;
	return "--";
};

const getTimeValue = (value) => {
	if (value == null || value === "") return null;

	const numericValue = Number(value);
	if (Number.isFinite(numericValue)) return numericValue;

	const parsed = new Date(value).getTime();
	return Number.isNaN(parsed) ? null : parsed;
};

const floorToChartBucket = (timestamp) => {
	return Math.floor(timestamp / CHART_BUCKET_MS) * CHART_BUCKET_MS;
};

const ceilToChartBucket = (timestamp) => {
	return Math.ceil(timestamp / CHART_BUCKET_MS) * CHART_BUCKET_MS;
};

const formatAxisTime = (value) => {
	const timestamp = getTimeValue(value);
	if (timestamp == null) return "--";

	return new Date(timestamp).toLocaleTimeString("vi-VN", {
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hour12: false,
	});
};

const formatAxisMinute = (value) => {
	const timestamp = getTimeValue(value);
	if (timestamp == null) return "--";

	return new Date(timestamp).toLocaleTimeString("vi-VN", {
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	});
};

const createFixedTimeTicks = (start, end, step = CHART_BUCKET_MS) => {
	const ticks = [];
	for (let tick = start; tick <= end; tick += step) {
		ticks.push(tick);
	}
	return ticks;
};

const getChartTimestamp = (entry) => {
	const timestamp = getTimeValue(
		entry?.chartTimestamp ?? entry?.chart_timestamp ?? entry?.timestamp ?? entry?.recorded_at,
	);
	return timestamp == null ? null : floorToChartBucket(timestamp);
};

const getRecordedTimestamp = (entry) => {
	const timestamp = getTimeValue(
		entry?.timestamp ?? entry?.recorded_at ?? entry?.chartTimestamp ?? entry?.chart_timestamp,
	);
	return Number.isFinite(timestamp) ? timestamp : null;
};

const getCurrentChartTimestamp = () => {
	return floorToChartBucket(Date.now());
};

const getDataTickStep = (range) => {
	const target = Math.max(range / 6, DATA_TICK_STEPS[0]);
	return DATA_TICK_STEPS.find((step) => step >= target) || DATA_TICK_STEPS[DATA_TICK_STEPS.length - 1];
};

const getWindowRange = (windowKey, currentTimestamp) => {
	const config = TIME_WINDOW_CONFIG[windowKey];
	if (!config) return null;

	const end = floorToChartBucket(currentTimestamp ?? Date.now());

	return {
		start: end - config.duration,
		end,
		tickStep: config.tickStep,
		tickFormatter: formatAxisMinute,
	};
};

const getTelemetryFetchParams = (windowKey) => {
	const config = TIME_WINDOW_CONFIG[windowKey];
	const params = { limit: TELEMETRY_HISTORY_LIMIT };
	if (!config) return params;

	const end = getCurrentChartTimestamp();
	return {
		...params,
		from: end - config.duration,
		to: Date.now(),
	};
};

const sortTelemetryData = (series) => {
	return series
		.slice()
		.sort((a, b) => (getRecordedTimestamp(a) ?? 0) - (getRecordedTimestamp(b) ?? 0));
};

const mergeTelemetryPoint = (series, point, limit = TELEMETRY_HISTORY_LIMIT) => {
	const keyed = new Map();
	for (const entry of [...series, point]) {
		const key = getRecordedTimestamp(entry);
		if (key == null) continue;
		keyed.set(String(key), entry);
	}

	return sortTelemetryData(Array.from(keyed.values())).slice(-limit);
};

const getFixedTimeScale = (series, windowRange = null) => {
	if (windowRange) {
		return {
			domain: [windowRange.start, windowRange.end],
			ticks: createFixedTimeTicks(windowRange.start, windowRange.end, windowRange.tickStep),
			tickFormatter: windowRange.tickFormatter,
		};
	}

	const timestamps = series
		.map(getChartTimestamp)
		.filter((value) => Number.isFinite(value));

	if (!timestamps.length) {
		return { domain: ["auto", "auto"], ticks: [] };
	}

	const start = floorToChartBucket(Math.min(...timestamps));
	const rawEnd = Math.max(ceilToChartBucket(Math.max(...timestamps)), start + CHART_BUCKET_MS);
	const tickStep = getDataTickStep(rawEnd - start);
	const end = Math.max(rawEnd, start + tickStep);

	return {
		domain: [start, end],
		ticks: createFixedTimeTicks(start, end, tickStep),
	};
};

const buildFixedIntervalData = (series) => {
	const buckets = new Map();

	for (const entry of series) {
		const sourceTimestamp = getTimeValue(
			entry.chart_timestamp ?? entry.chartTimestamp ?? entry.timestamp ?? entry.recorded_at,
		);
		if (sourceTimestamp == null) continue;

		const chartTimestamp = floorToChartBucket(sourceTimestamp);
		const recordedTimestamp = getTimeValue(entry.timestamp ?? entry.recorded_at) ?? sourceTimestamp;
		const current = buckets.get(chartTimestamp);

		if (!current || recordedTimestamp >= current.__recordedTimestamp) {
			buckets.set(chartTimestamp, {
				...entry,
				chartTimestamp,
				chart_timestamp: chartTimestamp,
				chart_recorded_at: new Date(chartTimestamp).toISOString(),
				chart_time: formatAxisTime(chartTimestamp),
				__recordedTimestamp: recordedTimestamp,
			});
		}
	}

	return Array.from(buckets.values())
		.sort((a, b) => a.chartTimestamp - b.chartTimestamp)
		.map((entry) => {
			const { __recordedTimestamp: _recordedTimestamp, ...cleanEntry } = entry;
			return cleanEntry;
		});
};

const filterDataByWindow = (data, windowKey, windowRange) => {
	if (!data.length) return [];

	if (windowKey === "all") return data;

	if (!windowRange) return data;

	return data.filter((item) => {
		const timestamp = getChartTimestamp(item);
		return timestamp != null && timestamp >= windowRange.start && timestamp <= windowRange.end;
	});
};

const getTimeSpanLabel = (series, windowRange = null) => {
	if (windowRange) {
		return `${formatAxisTime(windowRange.start)} - ${formatAxisTime(windowRange.end)}`;
	}

	if (!series.length) return "--";

	const start = getChartTimestamp(series[0]);
	const end = getChartTimestamp(series[series.length - 1]);
	if (start == null || end == null) return "--";

	return `${formatAxisTime(start)} - ${formatAxisTime(end)}`;
};

const getTemperatureStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 25) return { label: "Low temperature", className: "bg-[#DCE9F8] text-[#427AB5]" };
	if (value > 35) return { label: "High temperature", className: "bg-[#FED7AA] text-[#DF6D14]" };
	return { label: "Normal", className: "bg-[#E8F5E9] text-[#3A7D44]" };
};

const getHumidityStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 60) return { label: "Low humidity", className: "bg-[#DCE9F8] text-[#427AB5]" };
	if (value > 80) return { label: "High humidity", className: "bg-[#FED7AA] text-[#DF6D14]" };
	return { label: "Normal", className: "bg-[#E8F5E9] text-[#3A7D44]" };
};

const getLightStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 100) return { label: "Low light", className: "bg-[#DCE9F8] text-[#427AB5]" };
	if (value > 500) return { label: "High light", className: "bg-[#FED7AA] text-[#DF6D14]" };
	return { label: "Normal", className: "bg-[#E8F5E9] text-[#3A7D44]" };
};

const withNestedSensorMetrics = (entry) => ({
	...entry,
	temp: getSensorValue(entry, "temperature"),
	humidity: getSensorValue(entry, "humidity"),
	light: getSensorValue(entry, "light"),
});

const CustomTooltip = ({ active, payload, label }) => {
	if (!active || !payload?.length) return null;

	const point = payload[0]?.payload;
	const chartTimestamp = point?.chartTimestamp ?? point?.chart_timestamp ?? label;
	const chartTime = point?.chart_time ?? point?.chartTime ?? formatAxisTime(chartTimestamp);

	return (
		<div className="rounded-xl border border-gray-200 bg-white px-3 py-2 shadow-md text-sm">
			<p className="font-medium text-textMain">{chartTime}</p>
			<p className="text-textMuted">{formatFullDateTime(point?.recorded_at)}</p>
			{payload.map((entry) => (
				<p key={entry.dataKey} className="mt-1 text-textMain">
					{entry.name}: {entry.value ?? "--"}
				</p>
			))}
		</div>
	);
};

const ChartCard = ({ title, value, unit, dataKey, color, data, stats, status, timeScale, ...props }) => {
	const Icon = props.Icon;
	const resolvedTimeScale = useMemo(() => timeScale || getFixedTimeScale(data), [data, timeScale]);

	return (
		<div className="rounded-2xl bg-white p-4 shadow-sm sm:p-6">
			<div className="flex flex-col gap-4 mb-6 md:flex-row md:items-start md:justify-between">
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-textMain">
						<Icon size={20} strokeWidth={1.9} />
					</div>
					<div>
						<div className="flex items-center gap-2 flex-wrap">
							<h3 className="text-lg font-medium text-textMain">{title}</h3>
							<span className={`px-2.5 py-1 rounded-full text-xs font-medium ${status.className}`}>
								{status.label}
							</span>
						</div>
						<p className="text-sm text-textMuted">Live data</p>
					</div>
				</div>

				<div className="text-left md:text-right">
					<h2 className="text-2xl font-normal text-textMain sm:text-3xl">{value}</h2>
					<p className="text-sm text-textMuted">{unit}</p>
				</div>
			</div>

			<div className="h-[230px] w-full sm:h-[280px]">
				<ResponsiveContainer width="100%" height="100%">
					<AreaChart data={data} margin={{ top: 10, right: 4, left: -18, bottom: 18 }}>
						<defs>
							<linearGradient id={`color${dataKey}`} x1="0" y1="0" x2="0" y2="1">
								<stop offset="5%" stopColor={color} stopOpacity={0.3} />
								<stop offset="95%" stopColor={color} stopOpacity={0} />
							</linearGradient>
						</defs>

						<CartesianGrid strokeDasharray="3 3" vertical={false} />

						<XAxis
							dataKey="chartTimestamp"
							type="number"
							scale="time"
							domain={resolvedTimeScale.domain}
							ticks={resolvedTimeScale.ticks}
							tickFormatter={resolvedTimeScale.tickFormatter || formatAxisTime}
							padding={{ left: 0, right: 0 }}
							allowDataOverflow
							interval="preserveStartEnd"
							axisLine={false}
							tickLine={false}
							tick={{ fill: "#888", fontSize: 11 }}
							minTickGap={18}
						/>

						<YAxis
							axisLine={false}
							tickLine={false}
							tick={{ fill: "#888", fontSize: 11 }}
							domain={["auto", "auto"]}
						/>

						<Tooltip content={<CustomTooltip />} />

						<Area
							type="monotone"
							name={title}
							dataKey={dataKey}
							stroke={color}
							fillOpacity={1}
							fill={`url(#color${dataKey})`}
							strokeWidth={2}
							connectNulls={false}
							isAnimationActive={false}
						/>
					</AreaChart>
				</ResponsiveContainer>
			</div>

			<div className="mt-4 grid grid-cols-3 gap-2 text-xs sm:gap-3">
				<div className="rounded-lg bg-gray-50 px-3 py-2">
					<p className="text-textMuted">Min</p>
					<p className="text-sm font-semibold text-textMain">
						{stats.min == null ? "--" : formatMetric(stats.min)}
					</p>
				</div>
				<div className="rounded-lg bg-gray-50 px-3 py-2">
					<p className="text-textMuted">Avg</p>
					<p className="text-sm font-semibold text-textMain">
						{stats.avg == null ? "--" : formatMetric(stats.avg)}
					</p>
				</div>
				<div className="rounded-lg bg-gray-50 px-3 py-2">
					<p className="text-textMuted">Max</p>
					<p className="text-sm font-semibold text-textMain">
						{stats.max == null ? "--" : formatMetric(stats.max)}
					</p>
				</div>
			</div>
		</div>
	);
};

const AuditLogTable = () => {
	const [logs, setLogs] = useState([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState("");
	const [filters, setFilters] = useState({
		eventType: "all",
		triggerSource: "all",
		room: "all",
		search: "",
		from: "",
		to: "",
	});

	const totalPages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE));

	const loadLogs = useCallback(async () => {
		setIsLoading(true);
		try {
			const result = await fetchActivityLogs({
				surface: "audit",
				page,
				pageSize: AUDIT_PAGE_SIZE,
				filters,
			});
			setLogs(result.items);
			setTotal(result.total);
			setError("");
		} catch (loadError) {
			setError(loadError.message || "Failed to load audit logs");
		} finally {
			setIsLoading(false);
		}
	}, [filters, page]);

	useEffect(() => {
		loadLogs();
	}, [loadLogs]);

	const updateFilter = (key, value) => {
		setFilters((prev) => ({ ...prev, [key]: value }));
		setPage(1);
	};

	return (
		<div className="flex flex-col gap-4">
			<div className="rounded-2xl bg-white p-4 shadow-sm">
				<div className="grid gap-3 md:grid-cols-[1.1fr_0.85fr_0.85fr_0.85fr] xl:grid-cols-[1.2fr_0.85fr_0.85fr_0.85fr_0.85fr_0.85fr_auto]">
					<label className="relative min-w-0">
						<Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
						<input
							type="search"
							value={filters.search}
							onChange={(event) => updateFilter("search", event.target.value)}
							placeholder="Search logs"
							className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-[#3A7D44]"
						/>
					</label>

					<select
						value={filters.eventType}
						onChange={(event) => updateFilter("eventType", event.target.value)}
						className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#3A7D44]"
					>
						{AUDIT_TYPE_OPTIONS.map((item) => (
							<option key={item.value} value={item.value}>{item.label}</option>
						))}
					</select>

					<select
						value={filters.triggerSource}
						onChange={(event) => updateFilter("triggerSource", event.target.value)}
						className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#3A7D44]"
					>
						{AUDIT_TRIGGER_OPTIONS.map((item) => (
							<option key={item.value} value={item.value}>{item.label}</option>
						))}
					</select>

					<select
						value={filters.room}
						onChange={(event) => updateFilter("room", event.target.value)}
						className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#3A7D44]"
					>
						{AUDIT_ROOM_OPTIONS.map((item) => (
							<option key={item.value} value={item.value}>{item.label}</option>
						))}
					</select>

					<input
						type="date"
						value={toDateInputValue(filters.from)}
						onChange={(event) => updateFilter("from", fromDateInputValue(event.target.value))}
						className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#3A7D44]"
					/>

					<input
						type="date"
						value={toDateInputValue(filters.to)}
						onChange={(event) => updateFilter("to", fromDateInputValue(event.target.value, true))}
						className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-[#3A7D44]"
					/>

					<button
						type="button"
						onClick={loadLogs}
						title="Refresh audit logs"
						className="grid h-10 w-10 place-items-center rounded-lg border border-gray-200 bg-white text-gray-500 hover:text-[#3A7D44]"
					>
						<RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
					</button>
				</div>
			</div>

			{error && (
				<div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
					{error}
				</div>
			)}

			<div className="overflow-hidden rounded-2xl bg-white shadow-sm">
				<div className="overflow-x-auto">
					<table className="min-w-[980px] w-full text-left text-sm">
						<thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-textMuted">
							<tr>
								<th className="px-4 py-3 font-semibold">Exact Time</th>
								<th className="px-4 py-3 font-semibold">Type</th>
								<th className="px-4 py-3 font-semibold">Device / Area</th>
								<th className="px-4 py-3 font-semibold">Action</th>
								<th className="px-4 py-3 font-semibold">Actor</th>
								<th className="px-4 py-3 font-semibold">Details</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-100">
							{isLoading && logs.length === 0 ? (
								<tr>
									<td colSpan="6" className="px-4 py-8 text-center text-textMuted">
										Loading audit logs...
									</td>
								</tr>
							) : logs.length === 0 ? (
								<tr>
									<td colSpan="6" className="px-4 py-8 text-center text-textMuted">
										No logs match the current filters.
									</td>
								</tr>
							) : (
								logs.map((log) => (
									<tr key={log.id} className="align-top hover:bg-gray-50/70">
										<td className="whitespace-nowrap px-4 py-3 text-textMain">
											{formatFullDateTime(log.createdAt)}
										</td>
										<td className="px-4 py-3">
											<span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${auditSeverityClass[log.severity] || auditSeverityClass.info}`}>
												{log.eventType}
											</span>
										</td>
										<td className="px-4 py-3">
											<p className="font-medium text-textMain">{log.deviceName || log.targetId || "--"}</p>
											<p className="text-xs text-textMuted">{log.room || "--"}</p>
										</td>
										<td className="px-4 py-3">
											<p className="font-medium text-textMain">{log.action || "--"}</p>
											<p className="max-w-[260px] text-xs text-textMuted">{log.message || "--"}</p>
										</td>
										<td className="px-4 py-3">
											<p className="font-medium text-textMain">{log.actorName || "--"}</p>
											<p className="text-xs text-textMuted">{log.triggerSource}</p>
										</td>
										<td className="px-4 py-3 text-textMuted">
											{formatAuditDetails(log)}
										</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>

				<div className="flex flex-col gap-3 border-t border-gray-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
					<p className="text-sm text-textMuted">
						{total} logs - Page {page} of {totalPages}
					</p>
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => setPage((prev) => Math.max(1, prev - 1))}
							disabled={page <= 1}
							className="grid h-9 w-9 place-items-center rounded-lg border border-gray-200 text-gray-600 disabled:opacity-40"
						>
							<ChevronLeft size={16} />
						</button>
						<button
							type="button"
							onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
							disabled={page >= totalPages}
							className="grid h-9 w-9 place-items-center rounded-lg border border-gray-200 text-gray-600 disabled:opacity-40"
						>
							<ChevronRight size={16} />
						</button>
					</div>
				</div>
			</div>
		</div>
	);
};

const Analytics = () => {
	const [data, setData] = useState([]);
	const [windowKey, setWindowKey] = useState("5m");
	const [currentChartTimestamp, setCurrentChartTimestamp] = useState(getCurrentChartTimestamp);
	const [activeTab, setActiveTab] = useState("charts");
	const isAuditVisible = SHOW_AUDIT_LOGS && activeTab === "audit";

	useEffect(() => {
		const interval = setInterval(() => {
			setCurrentChartTimestamp((previous) => {
				const next = getCurrentChartTimestamp();
				return next === previous ? previous : next;
			});
		}, CHART_BUCKET_MS);

		return () => clearInterval(interval);
	}, []);

	useEffect(() => {
		let cancelled = false;
		const fetchTelemetry = async () => {
			try {
				const json = await fetchTelemetrySeries(getTelemetryFetchParams(windowKey));
				if (!cancelled) {
					setData(sortTelemetryData(json).slice(-TELEMETRY_HISTORY_LIMIT));
				}
			} catch (error) {
				if (!cancelled) {
					console.error("Failed to fetch telemetry:", error);
				}
			}
		};

		fetchTelemetry();
		const interval = setInterval(fetchTelemetry, TELEMETRY_REFRESH_MS);

		return () => {
			cancelled = true;
			clearInterval(interval);
		};
	}, [windowKey]);

	useEffect(() => {
		let unsubscribe = null;
		try {
			unsubscribe = subscribeTelemetrySeries({
				limit: TELEMETRY_HISTORY_LIMIT,
				onData: (point, limit) => {
					setData((prev) => mergeTelemetryPoint(prev, point, limit));
				},
				onError: (error) => {
					console.error("Telemetry stream error:", error);
				},
			});
		} catch (error) {
			console.error("Failed to open telemetry stream:", error);
		}

		return () => {
			unsubscribe?.();
		};
	}, []);

	const windowRange = useMemo(() => {
		return getWindowRange(windowKey, currentChartTimestamp);
	}, [windowKey, currentChartTimestamp]);

	const visibleData = useMemo(() => {
		return filterDataByWindow(data, windowKey, windowRange);
	}, [data, windowKey, windowRange]);

	const chartSourceData = useMemo(() => {
		return visibleData.map(withNestedSensorMetrics);
	}, [visibleData]);

	const chartTimeScale = useMemo(() => {
		return getFixedTimeScale(chartSourceData, windowRange);
	}, [chartSourceData, windowRange]);

	const temperatureData = useMemo(() => {
		return buildFixedIntervalData(chartSourceData.filter((entry) => entry.temp != null));
	}, [chartSourceData]);
	const humidityData = useMemo(() => {
		return buildFixedIntervalData(chartSourceData.filter((entry) => entry.humidity != null));
	}, [chartSourceData]);
	const lightData = useMemo(() => {
		return buildFixedIntervalData(chartSourceData.filter((entry) => entry.light != null));
	}, [chartSourceData]);

	const tempSeries = temperatureData.map((entry) => entry.temp);
	const humiditySeries = humidityData.map((entry) => entry.humidity);
	const lightSeries = lightData.map((entry) => entry.light);
	const chartPointCount = Math.max(temperatureData.length, humidityData.length, lightData.length);
	const timeSpanLabel = getTimeSpanLabel(visibleData, windowRange);

	const tempStats = getStats(tempSeries);
	const humidityStats = getStats(humiditySeries);
	const lightStats = getStats(lightSeries);

	const latestTemperature = temperatureData[temperatureData.length - 1] || {};
	const latestHumidity = humidityData[humidityData.length - 1] || {};
	const latestLight = lightData[lightData.length - 1] || {};
	const latestRecord = visibleData[visibleData.length - 1] || {};

	const temperatureStatus = getTemperatureStatus(latestTemperature.temp);
	const humidityStatus = getHumidityStatus(latestHumidity.humidity);
	const lightStatus = getLightStatus(latestLight.light);

	return (
		<div className="min-h-full w-full p-3 sm:p-4 lg:p-8">
			<div className="mb-6 lg:mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
				<div className="min-w-0">
					<h2 className="text-2xl font-semibold text-textMain sm:text-3xl">
						{isAuditVisible ? "System Audit" : "Environmental Trends"}
					</h2>
					<p className="text-textMuted mt-1">
						{isAuditVisible
							? "Trace device controls, threshold warnings, scenes, security, and system changes"
							: "Monitor your home's climate and lighting conditions over the last 24 hours"}
					</p>
				</div>

				<div className="flex max-w-full flex-col gap-2 lg:items-end">
					{SHOW_AUDIT_LOGS && (
						<div className="flex gap-2 rounded-lg border border-gray-200 bg-white p-1 shadow-sm">
							<button
								type="button"
								onClick={() => setActiveTab("charts")}
								className={`rounded-md px-3 py-2 text-sm font-medium ${
									activeTab === "charts"
										? "bg-black text-white"
										: "text-textMuted hover:text-textMain"
								}`}
							>
								Charts
							</button>
							<button
								type="button"
								onClick={() => setActiveTab("audit")}
								className={`rounded-md px-3 py-2 text-sm font-medium ${
									activeTab === "audit"
										? "bg-black text-white"
										: "text-textMuted hover:text-textMain"
								}`}
							>
								Audit Logs
							</button>
						</div>
					)}

					{!isAuditVisible && (
						<div className="flex max-w-full gap-2 overflow-x-auto pb-1 md:flex-wrap md:overflow-visible">
							{WINDOW_OPTIONS.map((item) => (
								<button
									key={item.key}
									type="button"
									onClick={() => setWindowKey(item.key)}
									className={`shrink-0 rounded-lg border px-3 py-2 text-sm ${
										windowKey === item.key
											? "bg-[#3A7D44] text-white border-[#3A7D44]"
											: "bg-white text-textMain border-gray-200"
									}`}
								>
									{item.label}
								</button>
							))}
						</div>
					)}
				</div>
			</div>

			{!isAuditVisible ? (
				<>
					<div className="mb-4 rounded-2xl bg-white p-4 shadow-sm">
						<div className="grid gap-4 md:grid-cols-3">
							<div>
								<p className="text-sm text-textMuted">Latest Records</p>
								<p className="mt-1 text-base text-textMain">
									{latestRecord.recorded_at ? formatFullDateTime(latestRecord.recorded_at) : "--"}
								</p>
							</div>
							<div>
								<p className="text-sm text-textMuted">Selected Records</p>
								<p className="mt-1 text-base text-textMain">
									{visibleData.length} / {data.length}
								</p>
							</div>
							<div>
								<p className="text-sm text-textMuted">Chart Span</p>
								<p className="mt-1 text-base text-textMain">{timeSpanLabel}</p>
								<p className="mt-1 text-xs text-textMuted">{chartPointCount} chart points</p>
							</div>
						</div>
					</div>

					<div className="flex flex-col gap-6">
						<ChartCard
							title="Temperature"
							value={latestTemperature.temp == null ? "--" : formatMetric(latestTemperature.temp)}
							unit="Celsius"
							dataKey="temp"
							color="#DF6D14"
							data={temperatureData}
							Icon={Thermometer}
							stats={tempStats}
							status={temperatureStatus}
							timeScale={chartTimeScale}
						/>

						<ChartCard
							title="Humidity"
							value={latestHumidity.humidity == null ? "--" : formatMetric(latestHumidity.humidity)}
							unit="Relative Humidity"
							dataKey="humidity"
							color="#3A7D44"
							data={humidityData}
							Icon={Droplets}
							stats={humidityStats}
							status={humidityStatus}
							timeScale={chartTimeScale}
						/>

						<ChartCard
							title="Ambient Light"
							value={latestLight.light == null ? "--" : formatMetric(latestLight.light)}
							unit="Lux"
							dataKey="light"
							color="#F4D03F"
							data={lightData}
							Icon={Sun}
							stats={lightStats}
							status={lightStatus}
							timeScale={chartTimeScale}
						/>
					</div>
				</>
			) : (
				<AuditLogTable />
			)}
		</div>
	);
};

export default Analytics;
