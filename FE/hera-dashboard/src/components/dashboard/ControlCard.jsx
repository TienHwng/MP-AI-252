import React from 'react';
import { Fan, Lightbulb, Plug, Square } from 'lucide-react';

const controls = [
	{ id: 'main_led', key: 'led_state', label: 'Main LED', Icon: Lightbulb },
	{ id: 'neo_led', key: 'neo_led_state', label: 'NeoPixel', Icon: Square },
	{ id: 'ws2812', key: 'ws2812_status', label: 'WS2812', Icon: Lightbulb },
	{ id: 'mini_fan', key: 'mini_fan_status', label: 'Mini Fan', Icon: Fan },
	{ id: 'relay', key: 'relay_status', label: 'Relay', Icon: Plug },
];

const stateLabel = (value) => {
	if (value === true) return 'Active';
	if (value === false) return 'Inactive';
	return 'Unknown';
};

const ControlCard = ({ data, isSubmitting, onToggleDevice }) => {
	return (
		<div className="grid grid-cols-2 md:grid-cols-5 gap-4">
			{controls.map((control) => {
				const Icon = control.Icon;
				const active = data?.[control.key] === true;
				const known = typeof data?.[control.key] === 'boolean';
				const disabled = isSubmitting || !known;
				const cardClass = active
					? 'bg-cardDark text-white'
					: 'bg-white text-textMain';

				const subTextClass = active ? 'text-white/80' : 'text-textMuted';
				const iconClass = active ? '' : 'text-textMuted';

				return (
					<button
						key={control.id}
						type="button"
						onClick={() => onToggleDevice(control.id, control.key)}
						disabled={disabled}
						className={`p-5 rounded-lg relative shadow-sm text-left transition-colors duration-200 ${cardClass} ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
					>
						{active && (
							<span className="absolute top-4 right-4 w-3 h-3 bg-white rounded-full"></span>
						)}
						<div className={`mb-4 ${iconClass}`}>
							<Icon size={24} strokeWidth={1.9} className="shrink-0" />
						</div>
						<h5 className="font-medium leading-tight">{control.label}</h5>
						<p className={`text-xs mt-1 ${subTextClass}`}>
							{isSubmitting ? 'Sending...' : stateLabel(data?.[control.key])}
						</p>
					</button>
				);
			})}
		</div>
	);
};

export default ControlCard;
