import React, { useState } from 'react';
import { Mic, Send, X } from 'lucide-react';
import { sendAssistantMessage } from '../../services/api';

const formatTime = () =>
  new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

const AiAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const handleStartVoiceCommand = () => {
    setIsRecording(true);
  };

  const handleCancelVoiceCommand = () => {
    setIsRecording(false);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;

    const userMessage = { text, isBot: false, time: formatTime() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsRecording(false);
    setIsSending(true);

    try {
      const response = await sendAssistantMessage(text);
      setMessages((prev) => [
        ...prev,
        {
          text: response.text || 'HERA completed the request.',
          isBot: true,
          time: formatTime(),
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          text: error.message || 'HERA runtime is unavailable.',
          isBot: true,
          time: formatTime(),
          isError: true,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm h-full min-h-[560px] flex flex-col">
      <div className="p-6 border-b border-gray-100">
        <h3 className="text-lg font-semibold">H.E.R.A. Assistant</h3>
        <p className="text-sm text-textMuted">Runtime command channel</p>
      </div>

      <div className="flex-1 p-6 overflow-y-auto space-y-4">
        {messages.length === 0 && (
          <div className="rounded-lg border border-gray-100 bg-background p-4 text-sm text-textMuted">
            No assistant messages in this session.
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={`${msg.time}-${idx}`} className={`flex flex-col ${msg.isBot ? 'items-start' : 'items-end'}`}>
            <div className={`p-4 max-w-[80%] rounded-lg ${
              msg.isBot
                ? msg.isError
                  ? 'bg-red-50 text-red-700'
                  : 'bg-background text-textMain'
                : 'bg-primary text-white'
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
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') handleSend();
            }}
            placeholder={isRecording ? 'Recording voice command...' : 'Ask H.E.R.A. anything...'}
            className="flex-1 bg-[#f7f5f0] border border-[#eae5dc] rounded-lg px-5 py-3 text-sm focus:outline-none focus:border-[#9bb096] text-[#4a3f35]"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending}
            className="bg-[#8ba089] text-white p-3 rounded-lg hover:bg-[#7a8f78] transition-colors shadow-sm disabled:opacity-60"
          >
            <Send size={18} />
          </button>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleStartVoiceCommand}
            className={`flex-1 text-white py-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all shadow-sm ${
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
              className="bg-white border border-[#e2d7cb] text-[#7b6655] px-4 py-4 rounded-lg flex items-center justify-center gap-2 hover:bg-[#f8f4ee] transition-colors"
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
