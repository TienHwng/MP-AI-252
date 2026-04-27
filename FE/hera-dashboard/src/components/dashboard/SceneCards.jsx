import React from 'react';
import { Clapperboard, Moon, LogOut } from 'lucide-react';

const scenes = [
  { 
    id: 'movie', 
    label: 'Movie Mode', 
    Icon: Clapperboard, 
    desc: 'Dim lights, fan & TV on',
    bgColor: 'bg-[#E8F5E9] text-[#3A7D44]',
    iconColor: 'text-[#9DC08B]'
  },
  { 
    id: 'sleep', 
    label: 'Sleep Mode', 
    Icon: Moon, 
    desc: 'All lights off',
    bgColor: 'bg-slate-50 text-slate-700',
    iconColor: 'text-slate-600'
  },
  { 
    id: 'away', 
    label: 'Away Mode', 
    Icon: LogOut, 
    desc: 'Turn off everything',
    bgColor: 'bg-[#E8F5E9] text-[#3A7D44]',
    iconColor: 'text-[#9DC08B]'
  },
];

const SceneCards = ({ isSubmitting, onActivateScene }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {scenes.map((scene) => {
        const { Icon } = scene;
        return (
          <button
            key={scene.id}
            type="button"
            disabled={isSubmitting}
            onClick={() => onActivateScene(scene.id)}
            className={`flex items-center gap-4 p-4 rounded-xl shadow-sm text-left transition-all duration-200 hover:shadow-md border border-gray-50 bg-white ${isSubmitting ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer active:scale-[0.98]'}`}
          >
            <div className={`p-3 rounded-full ${scene.bgColor}`}>
              <Icon size={22} strokeWidth={2} className={scene.iconColor} />
            </div>
            <div>
              <h5 className="font-semibold text-textMain">{scene.label}</h5>
              <p className="text-xs text-textMuted mt-0.5">{scene.desc}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default SceneCards;