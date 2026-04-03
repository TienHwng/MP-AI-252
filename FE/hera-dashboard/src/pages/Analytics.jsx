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

const filterDataByWindow = (data, windowKey) => {
	if (!data.length) return [];

	if (windowKey === "all") return data;
	if (windowKey === "last30") return data.slice(-30);

	const now = data[data.length - 1]?.timestamp ?? Date.now();

	const windows = {
		"5m": 5 * 60 * 1000,
		"15m": 15 * 60 * 1000,
		"1h": 60 * 60 * 1000,
	};

	const duration = windows[windowKey];
	if (!duration) return data;

	return data.filter((item) => now - item.timestamp <= duration);
};

const CustomTooltip = ({ active, payload, label }) => {
	if (!active || !payload?.length) return null;

	const point = payload[0]?.payload;

	return (
		<div className="rounded-xl border border-gray-200 bg-white px-3 py-2 shadow-md text-sm">
			<p className="font-medium text-textMain">{label}</p>
			<p className="text-textMuted">{formatFullDateTime(point?.recorded_at)}</p>
			{payload.map((entry) => (
				<p key={entry.dataKey} className="mt-1 text-textMain">
					{entry.name}: {entry.value ?? "--"}
				</p>
			))}
		</div>
	);
};

const ChartCard = ({
	title,
	value,
	unit,
	dataKey,
	color,
	data,
	Icon,
	stats,
}) => {
	return (
		<div className="bg-white p-6 rounded-2xl shadow-sm">
			<div className="flex flex-col gap-4 mb-6 md:flex-row md:items-start md:justify-between">
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-textMain">
						<Icon size={20} strokeWidth={1.9} />
					</div>
					<div>
						<h3 className="text-lg font-medium text-textMain">{title}</h3>
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
					<AreaChart
						data={data}
						margin={{ top: 10, right: 12, left: -20, bottom: 18 }}
					>
						<defs>
							<linearGradient
								id={`color${dataKey}`}
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop offset="5%" stopColor={color} stopOpacity={0.3} />
								<stop offset="95%" stopColor={color} stopOpacity={0} />
							</linearGradient>
						</defs>

						<CartesianGrid strokeDasharray="3 3" vertical={false} />

						<XAxis
							dataKey="time"
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
						{formatMetric(stats.min)}
					</p>
				</div>
				<div className="rounded-lg bg-gray-50 px-3 py-2">
					<p className="text-textMuted">Avg</p>
					<p className="text-sm font-semibold text-textMain">
						{formatMetric(stats.avg)}
					</p>
				</div>
				<div className="rounded-lg bg-gray-50 px-3 py-2">
					<p className="text-textMuted">Max</p>
					<p className="text-sm font-semibold text-textMain">
						{formatMetric(stats.max)}
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
			try {
				const res = await fetch(
					"http://localhost:3001/api/telemetry?device_id=device_0001&limit=500",
				);
				const json = await res.json();
				setData(Array.isArray(json) ? json : []);
			} catch (error) {
				console.error("Failed to fetch telemetry:", error);
			}
		};

		fetchTelemetry();
		const interval = setInterval(fetchTelemetry, 5000);

		return () => clearInterval(interval);
	}, []);

	const visibleData = useMemo(() => {
		return filterDataByWindow(data, windowKey);
	}, [data, windowKey]);

	const tempSeries = visibleData
		.map((entry) => entry.temp)
		.filter((v) => v != null);
	const humiditySeries = visibleData
		.map((entry) => entry.humidity)
		.filter((v) => v != null);
	const lightSeries = visibleData
		.map((entry) => entry.light)
		.filter((v) => v != null);

	const tempStats = getStats(tempSeries);
	const humidityStats = getStats(humiditySeries);
	const lightStats = getStats(lightSeries);

	const latest = visibleData[visibleData.length - 1] || {};

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
					{[
						{ key: "last30", label: "30 closet points" },
						{ key: "5m", label: "5 minutes" },
						{ key: "15m", label: "15 minutes" },
						{ key: "1h", label: "1 hour" },
						{ key: "all", label: "All" },
					].map((item) => (
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
				<p className="text-sm text-textMuted">Latest Records</p>
				<p className="mt-1 text-base text-textMain">
					{latest.recorded_at ? formatFullDateTime(latest.recorded_at) : "--"}
				</p>
			</div>

			<div className="flex flex-col gap-6">
				<ChartCard
					title="Temperature"
					value={latest.temp ?? "--"}
					unit="Celsius"
					dataKey="temp"
					color="#D6AFA6"
					data={visibleData}
					Icon={Thermometer}
					stats={tempStats}
				/>

				<ChartCard
					title="Humidity"
					value={latest.humidity ?? "--"}
					unit="Relative Humidity"
					dataKey="humidity"
					color="#8B9A84"
					data={visibleData}
					Icon={Droplets}
					stats={humidityStats}
				/>

				<ChartCard
					title="Ambient Light"
					value={latest.light ?? "--"}
					unit="Lux"
					dataKey="light"
					color="#F4D03F"
					data={visibleData}
					Icon={Sun}
					stats={lightStats}
				/>
			</div>
		</div>
	);
};

export default Analytics;