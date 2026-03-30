import React, { useState } from 'react';

const initialControls = [
	{ id: 'led', label: 'LED Light', icon: '💡', active: true },
	{ id: 'neon', label: 'Neon Light', icon: '🟨', active: false },
	{ id: 'fan', label: 'Mini Fan', icon: '🪭', active: false },
	{ id: 'relay', label: 'Relay Switch', icon: '🔌', active: true },
];

const ControlCard = () => {
	const [controls, setControls] = useState(initialControls);

	const toggleControl = (id) => {
		setControls((prev) =>
			prev.map((control) =>
				control.id === id ? { ...control, active: !control.active } : control
			)
		);
	};

	return (
		<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
			{controls.map((control) => {
				const cardClass = control.active
					? 'bg-cardDark text-white'
					: 'bg-white text-textMain';

				const subTextClass = control.active ? 'text-white/80' : 'text-textMuted';
				const iconClass = control.active ? '' : 'text-textMuted';

				return (
					<button
						key={control.id}
						type="button"
						onClick={() => toggleControl(control.id)}
						className={`p-6 rounded-2xl relative shadow-sm text-left transition-colors duration-200 ${cardClass}`}
					>
						{control.active && (
							<span className="absolute top-4 right-4 w-3 h-3 bg-white rounded-full"></span>
						)}
						<div className={`text-2xl mb-4 ${iconClass}`}>{control.icon}</div>
						<h5 className="font-medium">{control.label}</h5>
						<p className={`text-xs mt-1 ${subTextClass}`}>
							{control.active ? 'Active' : 'Inactive'}
						</p>
					</button>
				);
			})}
		</div>
	);
};

export default ControlCard;
