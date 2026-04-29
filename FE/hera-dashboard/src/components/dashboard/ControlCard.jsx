import React, { useState, useEffect } from 'react';
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

	useEffect(() => {
		setLocalVal(serverIntensity);
	}, [serverIntensity]);

	const cardClass = active
		? 'bg-[#3A7D44] text-white hover:bg-[#9DC08B]'
		: 'bg-white text-textMain hover:shadow-md';

	const subTextClass = active ? 'text-white/90' : 'text-textMuted';
	const iconClass = active ? 'text-white' : 'text-[#3A7D44]';

	const handleSliderChange = (e) => {
		setLocalVal(parseInt(e.target.value));
	};

	const handleSliderRelease = () => {
		if (onChangeIntensity && localVal !== serverIntensity) {
			// 1023 === 2^10 - 1 for mini_fan
			// 255 === 2^8 - 1 for others
			let bitRef = 2**8 - 1;

			if (control.id === "mini_fan") {
				bitRef = 2**10 - 1;
			}

			// Quy đổi % (0-100) sang dải PWM tương ứng
			// mini_fan: 0-1023
			// các thiết bị khác: 0-255
			const pwmValue = Math.round((localVal / 100) * bitRef);
			
			// Map đúng tên method dựa trên mqtt_manager.py
			let rpcMethod = "";
			switch (control.id) {
				case 'ws2812': rpcMethod = 'setWS2812Brightness'; break;
				case 'neo_led': rpcMethod = 'setStripBrightness'; break;
				case 'mini_fan': rpcMethod = 'setFanSpeed'; break;
				case 'main_led': rpcMethod = 'setMainLedBrightness'; break; // Anh giả định tên hàm này
				default: rpcMethod = '';
			}

			// Gửi dữ liệu lên component cha
			onChangeIntensity(control.id, localVal, pwmValue, rpcMethod);
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
				onClick={() => onToggleDevice(control.id)}
				disabled={disabled}
				className={`text-left outline-none w-full flex-grow ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
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
				<div className={`mt-1 transition-all duration-300 ease-in-out overflow-hidden flex flex-col justify-end ${active ? 'h-[3rem] opacity-100' : 'h-0 opacity-0'}`}>
					
					{/* Hiển thị % */}
					<div className="flex justify-end mb-1 px-0.5">
						<span className="text-[11px] font-bold text-[#faf2f2] drop-shadow-sm tracking-wide">
							{localVal}%
						</span>
					</div>

					{/* Bọc thanh cuộn trong div có padding dọc (py-1.5) để không bị cắt xén nút tròn */}
					<div className="py-1.5 flex items-center">
						<input
							type="range"
							min="0"
							max="100"
							value={localVal}
							disabled={disabled || !active}
							onChange={handleSliderChange}
							onMouseUp={handleSliderRelease}
							onTouchEnd={handleSliderRelease}
							style={{
								background: `linear-gradient(to right, #faf2f2 ${localVal}%, rgba(255, 255, 255, 0.25) ${localVal}%)`
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
