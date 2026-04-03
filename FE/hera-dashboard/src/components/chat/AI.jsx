import React, { useState } from 'react';
import { Mic, Send, X } from 'lucide-react';

const AiAssistant = () => {
  const [messages, setMessages] = useState([
    { text: "Good evening! Your home is at a comfortable 22°C. How can I help you today?", isBot: true, time: "09:52 PM" },
    { text: "Turn on the living room lights", isBot: false, time: "09:53 PM" },
    { text: "I've turned on the RGB lights in the living room for you.", isBot: true, time: "09:54 PM" },
  ]);
  const [isRecording, setIsRecording] = useState(false);

  const handleStartVoiceCommand = () => {
    setIsRecording(true);
  };

  const handleCancelVoiceCommand = () => {
    setIsRecording(false);
  };

  const handleSend = () => {
    setIsRecording(false);
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm h-full min-h-[560px] flex flex-col">
      <div className="p-6 border-b border-gray-100">
        <h3 className="text-lg font-semibold">H.E.R.A. Assistant</h3>
        <p className="text-sm text-textMuted">Your AI home companion</p>
      </div>
      
      <div className="flex-1 p-6 overflow-y-auto space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex flex-col ${msg.isBot ? 'items-start' : 'items-end'}`}>
            <div className={`p-4 max-w-[80%] rounded-2xl ${
              msg.isBot ? 'bg-background text-textMain rounded-tl-sm' : 'bg-primary text-white rounded-tr-sm'
            }`}>
              <p className="text-sm">{msg.text}</p>
            </div>
            <span className="text-xs text-gray-400 mt-1">{msg.time}</span>
          </div>
        ))}
      </div>

      <div className="p-6 bg-white border-t border-[#eae5dc] flex flex-col gap-4">
          <div className="flex gap-2">
            <input 
              type="text" 
              placeholder={isRecording ? 'Recording voice command...' : 'Ask H.E.R.A. anything...'} 
              className="flex-1 bg-[#f7f5f0] border border-[#eae5dc] rounded-full px-5 py-3 text-sm focus:outline-none focus:border-[#9bb096] text-[#4a3f35]"
            />
            <button
              type="button"
              onClick={handleSend}
              className="bg-[#8ba089] text-white p-3 rounded-full hover:bg-[#7a8f78] transition-colors shadow-sm"
            >
              <Send size={18} />
            </button>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleStartVoiceCommand}
              className={`flex-1 text-white py-4 rounded-2xl flex items-center justify-center gap-2 font-medium transition-all shadow-sm ${
                isRecording ? 'bg-[#d98080] hover:bg-[#c96e6e]' : 'bg-[#a3b19c] hover:bg-[#8ba089]'
              }`}
            >
              <Mic size={20} className={isRecording ? 'animate-pulse' : ''} />
              {isRecording ? 'Recording...' : 'Voice Command'}
            </button>

            {isRecording && (
              <button
                type="button"
                onClick={handleCancelVoiceCommand}
                className="bg-white border border-[#e2d7cb] text-[#7b6655] px-4 py-4 rounded-2xl flex items-center justify-center gap-2 hover:bg-[#f8f4ee] transition-colors"
              >
                <X size={18} /> Cancel
              </button>
            )}
          </div>
        </div>
    </div>
  );
};

export default AiAssistant;