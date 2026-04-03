import React from 'react';
import { CircleAlert, CircleCheck, ShieldAlert } from 'lucide-react';

const statusConfig = {
  good: {
    label: 'Good',
    ToneIcon: CircleCheck,
    toneClass: 'text-emerald-600',
    chipClass: 'bg-emerald-100 text-emerald-700',
    progressClass: 'bg-emerald-500',
  },
  warning: {
    label: 'Warning',
    ToneIcon: CircleAlert,
    toneClass: 'text-amber-600',
    chipClass: 'bg-amber-100 text-amber-700',
    progressClass: 'bg-amber-500',
  },
  danger: {
    label: 'Danger',
    ToneIcon: ShieldAlert,
    toneClass: 'text-rose-600',
    chipClass: 'bg-rose-100 text-rose-700',
    progressClass: 'bg-rose-500',
  },
};

const SafetyStatusCards = ({
  airQuality = { value: 38, unit: 'AQI', level: 'good', updatedAt: 'just now' },
  gasDetection = { value: 112, unit: 'ppm', level: 'good', updatedAt: 'just now' },
}) => {
  const cards = [
    {
      id: 'air-quality',
      title: 'Air Quality',
      subtitle: 'Indoor particles estimate',
      metric: airQuality,
    },
    {
      id: 'gas-detection',
      title: 'Gas Detection',
      subtitle: 'Combustible gas monitor',
      metric: gasDetection,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {cards.map((card) => {
        const tone = statusConfig[card.metric.level] || statusConfig.good;
        const ToneIcon = tone.ToneIcon;
        const progressSource = card.metric.progress ?? card.metric.value;
        const progress = Math.max(0, Math.min(100, progressSource));

        return (
          <article key={card.id} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h5 className="text-sm font-semibold text-textMain">{card.title}</h5>
                <p className="text-xs text-textMuted mt-1">{card.subtitle}</p>
              </div>
              <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${tone.chipClass}`}>
                <ToneIcon size={14} strokeWidth={2} />
                {tone.label}
              </span>
            </div>

            <div className="mt-4 flex items-end justify-between">
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-semibold text-textMain">{card.metric.value}</span>
                <span className="text-xs text-textMuted">{card.metric.unit}</span>
              </div>
              <span className="text-xs text-textMuted">Updated {card.metric.updatedAt}</span>
            </div>

            <div className="mt-3 h-2 w-full rounded-full bg-gray-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${tone.progressClass}`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </article>
        );
      })}
    </div>
  );
};

export default SafetyStatusCards;
