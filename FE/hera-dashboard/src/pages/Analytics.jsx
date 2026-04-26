import React, { useEffect, useMemo, useState } from "react";
import { Droplets, Sun, Thermometer } from "lucide-react";
import {
	AreaChart,
	Area,
	XAxis,
	YAxis,
	Tooltip,
	ResponsiveContainer,
	CartesianGrid,
} from "recharts";
import { subscribeTelemetrySeries } from "../services/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001';
const CHART_BUCKET_MS = 5 * 1000;
const DEFAULT_POINT_LIMIT = 40;
const EXTENDED_POINT_LIMIT = 60;

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
	{ key: "all", label: "All" },
	{ key: "last60", label: "60 latest points" },
	{ key: "5m", label: "5 minutes" },
	{ key: "15m", label: "15 minutes" },
	{ key: "1h", label: "1 hour" },
];

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

const getLatestChartTimestamp = (data) => {
	const timestamps = data
		.map(getChartTimestamp)
		.filter((value) => Number.isFinite(value));

	if (!timestamps.length) return null;

	return Math.max(...timestamps);
};

const getDataTickStep = (range) => {
	const target = Math.max(range / 6, DATA_TICK_STEPS[0]);
	return DATA_TICK_STEPS.find((step) => step >= target) || DATA_TICK_STEPS[DATA_TICK_STEPS.length - 1];
};

const getWindowRange = (data, windowKey) => {
	const config = TIME_WINDOW_CONFIG[windowKey];
	if (!config) return null;

	const end = getLatestChartTimestamp(data);
	if (end == null) return null;

	return {
		start: end - config.duration,
		end,
		tickStep: config.tickStep,
		tickFormatter: formatAxisMinute,
	};
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

	if (windowKey === "all") return data.slice(-DEFAULT_POINT_LIMIT);
	if (windowKey === "last60") return data.slice(-EXTENDED_POINT_LIMIT);

	if (!windowRange) return data.slice(-DEFAULT_POINT_LIMIT);

	return data.filter((item) => {
		const timestamp = getChartTimestamp(item);
		return timestamp != null && timestamp >= windowRange.start && timestamp <= windowRange.end;
	});
};

const getTimeSpanLabel = (series) => {
	if (!series.length) return "--";

	const start = getChartTimestamp(series[0]);
	const end = getChartTimestamp(series[series.length - 1]);
	if (start == null || end == null) return "--";

	return `${formatAxisTime(start)} - ${formatAxisTime(end)}`;
};

const getTemperatureStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 25) return { label: "Low temperature", className: "bg-blue-100 text-blue-700" };
	if (value > 35) return { label: "High temperature", className: "bg-red-100 text-red-700" };
	return { label: "Normal", className: "bg-green-100 text-green-700" };
};

const getHumidityStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 60) return { label: "Low humidity", className: "bg-yellow-100 text-yellow-700" };
	if (value > 80) return { label: "High humidity", className: "bg-cyan-100 text-cyan-700" };
	return { label: "Normal", className: "bg-green-100 text-green-700" };
};

const getLightStatus = (value) => {
	if (value == null) return { label: "No data", className: "bg-gray-100 text-gray-600" };
	if (value < 100) return { label: "Low light", className: "bg-indigo-100 text-indigo-700" };
	if (value > 500) return { label: "High light", className: "bg-orange-100 text-orange-700" };
	return { label: "Normal", className: "bg-green-100 text-green-700" };
};

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
		<div className="bg-white p-6 rounded-2xl shadow-sm">
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

				<div className="text-right">
					<h2 className="text-3xl font-normal text-textMain">{value}</h2>
					<p className="text-sm text-textMuted">{unit}</p>
				</div>
			</div>

			<div className="h-[280px] w-full">
				<ResponsiveContainer width="100%" height="100%">
					<AreaChart data={data} margin={{ top: 10, right: 0, left: -12, bottom: 18 }}>
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
							tick={{ fill: "#888", fontSize: 12 }}
							minTickGap={24}
						/>

						<YAxis
							axisLine={false}
							tickLine={false}
							tick={{ fill: "#888", fontSize: 12 }}
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

			<div className="mt-4 grid grid-cols-3 gap-3 text-xs">
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

const Analytics = () => {
	const [data, setData] = useState([]);
	const [windowKey, setWindowKey] = useState("all");

	useEffect(() => {
		const fetchTelemetry = async () => {
            // Lấy thông tin User hiện tại từ LocalStorage
            const storedUser = localStorage.getItem('hera_user');
            if (!storedUser) return;
            const user = JSON.parse(storedUser);

			try {
                // Truyền user_id vào URL để Backend chỉ trả về data của user này
				const res = await fetch(
					`${API_BASE_URL}/api/telemetry?device_id=device_0001&limit=500&user_id=${user.user_id}`
				);
				const json = await res.json();
				setData(Array.isArray(json) ? json : []);
			} catch (error) {
				console.error("Failed to fetch telemetry:", error);
			}
		};

		fetchTelemetry();
		let unsubscribe = null;
		try {
			unsubscribe = subscribeTelemetrySeries({
				limit: 500,
				onData: (point, limit) => {
					setData((prev) => {
						const next = [...prev, point];
						const deduped = next.filter(
							(item, index, arr) =>
								arr.findIndex((candidate) => candidate.timestamp === item.timestamp) === index,
						);
						return deduped.slice(-limit);
					});
				},
				onError: (error) => {
					console.error("Telemetry stream error:", error);
				},
			});
		} catch (error) {
			console.error("Failed to open telemetry stream:", error);
		}
		const interval = setInterval(fetchTelemetry, 30000);

		return () => {
			unsubscribe?.();
			clearInterval(interval);
		};
	}, []);

	const windowRange = useMemo(() => {
		return getWindowRange(data, windowKey);
	}, [data, windowKey]);

	const visibleData = useMemo(() => {
		return filterDataByWindow(data, windowKey, windowRange);
	}, [data, windowKey, windowRange]);

	const chartTimeScale = useMemo(() => {
		return getFixedTimeScale(visibleData, windowRange);
	}, [visibleData, windowRange]);

	const temperatureData = useMemo(() => {
		return buildFixedIntervalData(visibleData.filter((entry) => entry.temp != null));
	}, [visibleData]);
	const humidityData = useMemo(() => {
		return buildFixedIntervalData(visibleData.filter((entry) => entry.humidity != null));
	}, [visibleData]);
	const lightData = useMemo(() => {
		return buildFixedIntervalData(visibleData.filter((entry) => entry.light != null));
	}, [visibleData]);

	const tempSeries = temperatureData.map((entry) => entry.temp);
	const humiditySeries = humidityData.map((entry) => entry.humidity);
	const lightSeries = lightData.map((entry) => entry.light);
	const chartPointCount = Math.max(temperatureData.length, humidityData.length, lightData.length);
	const timeSpanLabel = getTimeSpanLabel(visibleData);

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
		<div className="p-6 lg:p-8 w-full h-full min-h-full">
			<div className="mb-6 lg:mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
				<div>
					<h2 className="text-3xl font-semibold text-textMain">
						Environmental Trends
					</h2>
					<p className="text-textMuted mt-1">
						Monitor your home's climate and lighting conditions over the last 24 hours
					</p>
				</div>

				<div className="flex flex-wrap gap-2">
					{WINDOW_OPTIONS.map((item) => (
						<button
							key={item.key}
							type="button"
							onClick={() => setWindowKey(item.key)}
							className={`rounded-xl px-3 py-2 text-sm border ${
								windowKey === item.key
									? "bg-black text-white border-black"
									: "bg-white text-textMain border-gray-200"
							}`}
						>
							{item.label}
						</button>
					))}
				</div>
			</div>

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
					color="#D6AFA6"
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
					color="#8B9A84"
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
		</div>
	);
};

export default Analytics;
