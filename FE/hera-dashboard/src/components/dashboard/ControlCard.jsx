import React, { useState, useEffect, useRef } from 'react';
import { Fan, Lightbulb, Plug, Square } from 'lucide-react';
import { getDeviceStatus } from '../../services/api';

const controls = [
	{ id: 'main_led', label: 'LED living room', Icon: Lightbulb, hasSlider: true },
	{ id: 'neo_led', label: 'LED bedroom', Icon: Square, hasSlider: true },
	{ id: 'ws2812', label: 'LED toilet', Icon: Lightbulb, hasSlider: true },
	{ id: 'mini_fan', label: 'Fan living room', Icon: Fan, hasSlider: true },
	{ id: 'relay', label: 'TV', Icon: Plug, hasSlider: false },
];

const stateLabel = (value) => {
	if (value === true) return 'Active';
	if (value === false) return 'Inactive';
	return 'Unknown';
};

const DeviceItem = ({ control, data, isSubmitting, disabled, onToggleDevice, onChangeIntensity }) => {
	const Icon = control.Icon;
	const status = getDeviceStatus(data, control.id);
	const active = status === true;

	const serverIntensity = data?.[control.id]?.intensity || 50;
	const [localVal, setLocalVal] = useState(serverIntensity);
	const [initialVal, setInitialVal] = useState(serverIntensity);
	const prevIntensityRef = useRef(serverIntensity);

	useEffect(() => {
		// Only update if server intensity actually changed (not on active status change)
		if (serverIntensity !== prevIntensityRef.current) {
			setLocalVal(serverIntensity);
			setInitialVal(serverIntensity);
			prevIntensityRef.current = serverIntensity;
		}
	}, [serverIntensity]);

	// Show 0% UI when device is off, but keep localVal unchanged
	const displayValue = active ? localVal : 0;

	const cardClass = active
		? 'bg-[#3A7D44] text-white hover:bg-[#9DC08B]'
		: 'bg-white text-textMain hover:shadow-md';

	const subTextClass = active ? 'text-white/90' : 'text-textMuted';
	const iconClass = active ? 'text-white' : 'text-[#3A7D44]';

	const handleSliderChange = (e) => {
		setLocalVal(parseInt(e.target.value));
	};

	const handleSliderRelease = () => {
		// Helper function to send intensity command
		const sendIntensityCommand = (value) => {
			if (!onChangeIntensity) return;
			
			let bitRef = 2**8 - 1;
			if (control.id === "mini_fan") {
				bitRef = 2**10 - 1;
			}
			
			const pwmValue = Math.round((value / 100) * bitRef);
			
			let rpcMethod = "";
			switch (control.id) {
				case 'ws2812': rpcMethod = 'setWS2812Brightness'; break;
				case 'neo_led': rpcMethod = 'setStripBrightness'; break;
				case 'mini_fan': rpcMethod = 'setFanSpeed'; break;
				case 'main_led': rpcMethod = 'setMainLedBrightness'; break;
				default: rpcMethod = '';
			}
			
			if (rpcMethod) {
				onChangeIntensity(control.id, value, pwmValue, rpcMethod);
			}
		};

		// Handle device on/off based on slider value
		if (localVal === 0) {
			// Turn device off if slider is at 0%
			if (active) {
				onToggleDevice(control.id);
			}
			// Send intensity 0% command
			sendIntensityCommand(0);
		} else {
			// Turn device on if slider > 0% and device is off
			if (!active) {
				onToggleDevice(control.id);
			}
			
			// Always send intensity command for any non-zero value
			sendIntensityCommand(localVal);
		}
	};

	return (
		<div
			className={`relative flex min-h-[132px] flex-col rounded-lg p-4 shadow-sm transition-colors duration-200 sm:p-5 ${cardClass} ${disabled ? 'opacity-60' : ''}`}
		>
			{active && (
				<span className="absolute right-4 top-4 h-3 w-3 rounded-full bg-[#faf2f2] shadow-sm"></span>
			)}

			<button
				type="button"
				onClick={control.hasSlider ? undefined : () => onToggleDevice(control.id)}
				disabled={control.hasSlider || disabled}
				className={`text-left outline-none w-full flex-grow ${(control.hasSlider || disabled) ? 'cursor-not-allowed' : 'cursor-pointer'}`}
			>
				<div className={`mb-4 ${iconClass}`}>
					<Icon size={24} strokeWidth={1.9} className="shrink-0" />
				</div>
				<h5 className="break-words font-medium leading-tight">{control.label}</h5>
				<p className={`text-xs mt-1 ${subTextClass}`}>
					{isSubmitting ? 'Sending...' : stateLabel(status)}
				</p>
			</button>

			{/* Khu vực thanh cuộn */}
			{control.hasSlider && (
				<div className={`mt-1 transition-all duration-300 ease-in-out overflow-hidden flex flex-col justify-end h-[3rem] opacity-100`}>
					
					{/* Hiển thị % */}
					<div className="flex justify-end mb-1 px-0.5">
						<span className="text-[11px] font-bold text-[#faf2f2] drop-shadow-sm tracking-wide">
							{displayValue}%
						</span>
					</div>

					{/* Bọc thanh cuộn trong div có padding dọc (py-1.5) để không bị cắt xén nút tròn */}
					<div className="py-1.5 flex items-center">
						<input
							type="range"
							min="0"
							max="100"
							value={displayValue}
							disabled={disabled}
							onChange={handleSliderChange}
							onMouseUp={handleSliderRelease}
							onTouchEnd={handleSliderRelease}
							style={{
								background: `linear-gradient(to right, #faf2f2 ${displayValue}%, rgba(255, 255, 255, 0.25) ${displayValue}%)`
							}}
							className="w-full h-1.5 rounded-lg appearance-none cursor-pointer focus:outline-none 
							[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:bg-[#faf2f2] [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-sm
							[&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:bg-[#faf2f2] [&::-moz-range-thumb]:border-none [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:shadow-sm"
						/>
					</div>
				</div>
			)}
		</div>
	);
};

const ControlCard = ({ data, isSubmitting, onToggleDevice, onChangeIntensity }) => {
	return (
		<div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 lg:gap-4">
			{controls.map((control) => {
				const status = getDeviceStatus(data, control.id);
				const known = typeof status === 'boolean';
				const disabled = isSubmitting || !known;

				return (
					<DeviceItem
						key={control.id}
						control={control}
						data={data}
						isSubmitting={isSubmitting}
						disabled={disabled}
						onToggleDevice={onToggleDevice}
						onChangeIntensity={onChangeIntensity}
					/>
				);
			})}
		</div>
	);
};

export default ControlCard;
