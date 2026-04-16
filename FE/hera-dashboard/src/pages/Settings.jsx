import React, { useEffect, useMemo, useState } from 'react';
import { fetchModelSettings, updateModelSettings } from '../services/api';

const PROVIDER_OPTIONS = [
	{ value: 'openrouter', label: 'OpenRouter' },
	{ value: 'ollama', label: 'Ollama' },
];

const FIELD_DEFINITIONS = [
	{ key: 'orchestratorModel', label: 'Orchestrator Model' },
	{ key: 'deviceControlModel', label: 'Device Control Agent Model' },
	{ key: 'sensorAnalysisModel', label: 'Sensor Analysis Agent Model' },
	{ key: 'anomalyExpertModel', label: 'Anomaly Expert Agent Model' },
];

const EMPTY_SETTINGS = {
	provider: 'openrouter',
	models: {
		ollama: {
			orchestratorModel: '',
			deviceControlModel: '',
			sensorAnalysisModel: '',
			anomalyExpertModel: '',
		},
		openrouter: {
			orchestratorModel: '',
			deviceControlModel: '',
			sensorAnalysisModel: '',
			anomalyExpertModel: '',
		},
	},
};

const TabButton = ({ active, children, onClick }) => (
	<button
		type="button"
		onClick={onClick}
		className={`rounded-xl px-4 py-2 text-sm border transition ${
			active
				? 'bg-black text-white border-black'
				: 'bg-white text-textMain border-gray-200 hover:border-gray-300'
		}`}
	>
		{children}
	</button>
);

const formatWithDashboardClock = (value) => {
	if (!value) return 'N/A';
	const parsed = new Date(value);
	if (Number.isNaN(parsed.getTime())) return 'N/A';
	const date = parsed.toLocaleDateString('en-US', {
		weekday: 'long',
		month: 'long',
		day: 'numeric',
		year: 'numeric',
	});
	const time = parsed.toLocaleTimeString('en-US', {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: true,
	});
	return `${date}, ${time}`;
};

const Settings = () => {
	const [activeTab, setActiveTab] = useState('model');
	const [settings, setSettings] = useState(EMPTY_SETTINGS);
	const [isLoading, setIsLoading] = useState(true);
	const [isSaving, setIsSaving] = useState(false);
	const [error, setError] = useState('');
	const [success, setSuccess] = useState('');

	useEffect(() => {
		let cancelled = false;
		const loadSettings = async () => {
			setIsLoading(true);
			setError('');
			try {
				const payload = await fetchModelSettings();
				if (!cancelled) {
					setSettings(payload);
				}
			} catch (loadError) {
				if (!cancelled) {
					setError(loadError.message || 'Failed to load model settings');
				}
			} finally {
				if (!cancelled) {
					setIsLoading(false);
				}
			}
		};
		loadSettings();
		return () => {
			cancelled = true;
		};
	}, []);

	const activeProvider = settings.provider;
	const activeProviderLabel = useMemo(
		() => PROVIDER_OPTIONS.find((item) => item.value === activeProvider)?.label || activeProvider,
		[activeProvider],
	);

	const setModelValue = (provider, field, value) => {
		setSettings((prev) => ({
			...prev,
			models: {
				...prev.models,
				[provider]: {
					...prev.models[provider],
					[field]: value,
				},
			},
		}));
	};

	const handleProviderChange = (provider) => {
		setSettings((prev) => ({ ...prev, provider }));
		setSuccess('');
	};

	const handleSave = async () => {
		setError('');
		setSuccess('');
		setIsSaving(true);
		try {
			const saved = await updateModelSettings(settings);
			setSettings(saved);
			setSuccess('Model settings saved and applied to runtime.');
		} catch (saveError) {
			setError(saveError.message || 'Failed to save model settings');
		} finally {
			setIsSaving(false);
		}
	};

	return (
		<div className="p-6 lg:p-8 w-full h-full min-h-full">
			<div className="mb-6">
				<h2 className="text-3xl font-semibold text-textMain">Settings</h2>
				<p className="text-textMuted mt-1">
					Configure project runtime options from dashboard.
				</p>
			</div>

			<div className="mb-5 flex items-center gap-2">
				<TabButton active={activeTab === 'model'} onClick={() => setActiveTab('model')}>
					Model Setting
				</TabButton>
			</div>

			{activeTab === 'model' && (
				<div className="bg-white rounded-2xl shadow-sm p-5 lg:p-6 space-y-6">
					<div>
						<h3 className="text-lg font-semibold text-textMain">Model Setting</h3>
						<p className="text-sm text-textMuted mt-1">
							Set provider and models for orchestrator + each agent. You can enter any model code.
						</p>
					</div>

					{isLoading ? (
						<p className="text-sm text-textMuted">Loading model settings...</p>
					) : (
						<>
							<div>
								<p className="text-sm font-medium text-textMain mb-2">Active Provider</p>
								<div className="flex flex-wrap gap-2">
									{PROVIDER_OPTIONS.map((option) => (
										<TabButton
											key={option.value}
											active={settings.provider === option.value}
											onClick={() => handleProviderChange(option.value)}
										>
											{option.label}
										</TabButton>
									))}
								</div>
							</div>

							<div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
								{PROVIDER_OPTIONS.map((provider) => {
									const providerModels = settings.models[provider.value];
									const isSelected = activeProvider === provider.value;
									return (
										<div
											key={provider.value}
											className={`rounded-xl border p-4 ${
												isSelected ? 'border-black' : 'border-gray-200'
											}`}
										>
											<div className="mb-3 flex items-center justify-between">
												<h4 className="font-semibold text-textMain">{provider.label}</h4>
												<span
													className={`text-xs px-2 py-1 rounded-full ${
														isSelected
															? 'bg-black text-white'
															: 'bg-gray-100 text-textMuted'
													}`}
												>
													{isSelected ? 'Active' : 'Inactive'}
												</span>
											</div>
											<div className="space-y-3">
												{FIELD_DEFINITIONS.map((field) => (
													<label key={field.key} className="block">
														<span className="block text-xs font-medium text-textMuted mb-1">
															{field.label}
														</span>
														<input
															type="text"
															value={providerModels[field.key]}
															onChange={(event) =>
																setModelValue(provider.value, field.key, event.target.value)
															}
															placeholder={`Enter ${provider.label} model code`}
															className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-black"
														/>
													</label>
												))}
											</div>
										</div>
									);
								})}
							</div>

							<div className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-sm text-textMuted">
								Current active provider: <span className="font-semibold text-textMain">{activeProviderLabel}</span>
								<br />
								Last updated:{' '}
								<span className="font-semibold text-textMain">
									{formatWithDashboardClock(settings.updatedAt)}
								</span>
							</div>

							{error ? <p className="text-sm text-red-600">{error}</p> : null}
							{success ? <p className="text-sm text-green-600">{success}</p> : null}

							<div>
								<button
									type="button"
									onClick={handleSave}
									disabled={isSaving}
									className="rounded-xl bg-black text-white px-5 py-2.5 text-sm font-medium disabled:opacity-60"
								>
									{isSaving ? 'Saving...' : 'Save Model Settings'}
								</button>
							</div>
						</>
					)}
				</div>
			)}
		</div>
	);
};

export default Settings;
