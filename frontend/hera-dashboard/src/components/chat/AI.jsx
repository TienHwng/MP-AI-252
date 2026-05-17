import React, { useState, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { Mic, Send, Volume2, VolumeX, X } from 'lucide-react';
import {
  fetchAssistantChatHistory,
  saveAssistantInteraction,
  sendAssistantMessage,
  sendAssistantMessageStreaming,
  synthesizeAssistantSpeech,
} from '../../services/api';

const formatTime = (value = new Date()) => {
  const date = value instanceof Date ? value : new Date(value);
  const safeDate = Number.isNaN(date.getTime()) ? new Date() : date;
  return safeDate.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
};

const chatHistoryToMessages = (items = []) =>
  items
    .filter((item) => item?.text)
    .map((item) => ({
      text: item.text,
      isBot: item.role !== 'user',
      time: formatTime(item.createdAt || item.timestamp),
      createdAt: item.createdAt || new Date(item.timestamp || Date.now()).toISOString(),
      isError: Boolean(item.isError || item.metadata?.is_error),
    }));

const VOICE_REPLY_STORAGE_KEY = 'hera_voice_reply_enabled';

const getStoredVoiceReplyPreference = () => {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(VOICE_REPLY_STORAGE_KEY) === 'true';
};

const AiAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [streamError, setStreamError] = useState('');
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const [isVoiceReplyEnabled, setIsVoiceReplyEnabled] = useState(getStoredVoiceReplyPreference);
  const recognitionRef = useRef(null);
  const audioReplyRef = useRef(null);
  const audioUrlRef = useRef('');
  const speechVoicesRef = useRef([]);
  const voiceReplyEnabledRef = useRef(isVoiceReplyEnabled);
  const voiceCanceledRef = useRef(false);
  const abortControllerRef = useRef(null);
  const streamingMessageIdRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let isMounted = true;

    const loadChatHistory = async () => {
      try {
        const history = await fetchAssistantChatHistory();
        if (isMounted) {
          setMessages(chatHistoryToMessages(history.messages));
        }
      } catch (error) {
        console.warn('Failed to load assistant chat history:', error);
      } finally {
        if (isMounted) {
          setIsLoadingHistory(false);
        }
      }
    };

    loadChatHistory();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort?.();
      stopVoiceReply();
    };
  }, []);

  useEffect(() => {
    voiceReplyEnabledRef.current = isVoiceReplyEnabled;
    localStorage.setItem(VOICE_REPLY_STORAGE_KEY, String(isVoiceReplyEnabled));
    if (!isVoiceReplyEnabled) {
      stopVoiceReply();
    }
  }, [isVoiceReplyEnabled]);

  useEffect(() => {
    if (!window.speechSynthesis) return undefined;

    const updateVoices = () => {
      speechVoicesRef.current = window.speechSynthesis.getVoices();
    };

    updateVoices();
    window.speechSynthesis.addEventListener?.('voiceschanged', updateVoices);

    return () => {
      window.speechSynthesis.removeEventListener?.('voiceschanged', updateVoices);
    };
  }, []);

  const stopVoiceReply = () => {
    window.speechSynthesis?.cancel?.();
    if (audioReplyRef.current) {
      audioReplyRef.current.pause();
      audioReplyRef.current.src = '';
      audioReplyRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = '';
    }
  };

  const speakWithBrowserVoice = (text) => {
    if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance === 'undefined') {
      setVoiceError('Voice reply is not supported in this browser.');
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const vietnameseVoice = speechVoicesRef.current.find((voice) =>
      voice.lang?.toLowerCase().startsWith('vi'),
    );

    utterance.lang = 'vi-VN';
    utterance.rate = 1;
    utterance.pitch = 1;
    if (vietnameseVoice) {
      utterance.voice = vietnameseVoice;
    }

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };

  const speakAssistantResponse = async (text) => {
    if (!voiceReplyEnabledRef.current || !text) return;
    stopVoiceReply();

    try {
      const audioBlob = await synthesizeAssistantSpeech(text, { lang: 'vi' });
      if (!voiceReplyEnabledRef.current) return;

      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioUrlRef.current = audioUrl;
      audioReplyRef.current = audio;
      audio.onended = () => {
        if (audioReplyRef.current === audio) {
          audioReplyRef.current = null;
        }
        URL.revokeObjectURL(audioUrl);
        if (audioUrlRef.current === audioUrl) {
          audioUrlRef.current = '';
        }
      };
      audio.onerror = () => {
        speakWithBrowserVoice(text);
      };
      await audio.play();
    } catch (error) {
      console.warn('gTTS voice reply failed, falling back to browser voice:', error);
      speakWithBrowserVoice(text);
    }
  };

  const handleToggleVoiceReply = () => {
    setVoiceError('');
    setIsVoiceReplyEnabled((enabled) => !enabled);
  };

  const updateStreamingMessage = (messageId, updates) => {
    setMessages((prev) => {
      const index = prev.findIndex((message) => message.id === messageId);
      if (index === -1) return prev;

      const next = [...prev];
      next[index] = { ...next[index], ...updates };
      return next;
    });
  };

  const submitAssistantText = async (rawText, { source = 'rest' } = {}) => {
    const text = rawText.trim();
    if (!text || isSending || isLoadingHistory) return;

    const userCreatedAt = new Date().toISOString();
    const userMessage = {
      text,
      isBot: false,
      time: formatTime(userCreatedAt),
      createdAt: userCreatedAt,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsRecording(false);
    setVoiceError('');
    setStreamError('');
    setThinkingCollapsed(false);
    setIsSending(true);
    setIsStreaming(true);

    const assistantCreatedAt = new Date().toISOString();
    const messageId = `${assistantCreatedAt}-${Math.random()}`;
    streamingMessageIdRef.current = messageId;
    let streamedContent = '';

    setMessages((prev) => [
      ...prev,
      {
        id: messageId,
        text: '',
        isBot: true,
        time: formatTime(assistantCreatedAt),
        createdAt: assistantCreatedAt,
        isStreaming: true,
        thinking: '',
      },
    ]);

    try {
      abortControllerRef.current = new AbortController();
      const response = await sendAssistantMessageStreaming(
        text,
        (chunk, fullContent) => {
          streamedContent = fullContent;
          if (streamingMessageIdRef.current !== messageId) return;
          flushSync(() => {
            updateStreamingMessage(messageId, { text: fullContent });
          });
        },
        (thinking) => {
          if (streamingMessageIdRef.current !== messageId) return;
          flushSync(() => {
            updateStreamingMessage(messageId, { thinking });
          });
        },
        (error) => {
          setStreamError(error);
        },
        abortControllerRef.current.signal,
        { source },
      );
      const assistantText = response.text || streamedContent || 'HERA completed the request.';
      updateStreamingMessage(messageId, {
        text: assistantText,
        isStreaming: false,
      });
      streamingMessageIdRef.current = null;
      speakAssistantResponse(assistantText);
      saveAssistantInteraction({
        userText: text,
        assistantText,
        response,
        userCreatedAt,
        assistantCreatedAt,
        userMetadata: {
          source: source === 'voice' ? 'voice' : 'dashboard',
        },
      }).catch((error) => {
        console.warn('Failed to save assistant chat history:', error);
      });
    } catch (error) {
      streamingMessageIdRef.current = null;

      if (error.name === 'AbortError') {
        updateStreamingMessage(messageId, {
          text: streamedContent || 'Response paused.',
          isStreaming: false,
        });
        saveAssistantInteraction({
          userText: text,
          assistantText: streamedContent,
          response: { ok: true, text: streamedContent, paused: true },
          userCreatedAt,
          assistantCreatedAt,
          userMetadata: {
            source: source === 'voice' ? 'voice' : 'dashboard',
          },
        }).catch((saveError) => {
          console.warn('Failed to save paused assistant chat history:', saveError);
        });
      } else {
        try {
          const response = await sendAssistantMessage(text, { source });
          const assistantText = response.text || 'HERA completed the request.';
          updateStreamingMessage(messageId, {
            text: assistantText,
            isStreaming: false,
          });
          speakAssistantResponse(assistantText);
          saveAssistantInteraction({
            userText: text,
            assistantText,
            response,
            userCreatedAt,
            assistantCreatedAt,
            userMetadata: {
              source: source === 'voice' ? 'voice' : 'dashboard',
            },
          }).catch((saveError) => {
            console.warn('Failed to save assistant chat history:', saveError);
          });
        } catch (fallbackError) {
          const assistantText = fallbackError.message || 'HERA runtime is unavailable.';
          updateStreamingMessage(messageId, {
            text: assistantText,
            isStreaming: false,
            isError: true,
          });
          saveAssistantInteraction({
            userText: text,
            assistantText,
            response: { ok: false },
            userCreatedAt,
            assistantCreatedAt,
            userMetadata: {
              source: source === 'voice' ? 'voice' : 'dashboard',
            },
            assistantMetadata: {
              is_error: true,
              error_message: assistantText,
            },
          }).catch((saveError) => {
            console.warn('Failed to save assistant chat history:', saveError);
          });
        }
      }
    } finally {
      setIsSending(false);
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleStartVoiceCommand = () => {
    if (isSending || isLoadingHistory) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError('Voice recognition is not supported in this browser.');
      return;
    }

    recognitionRef.current?.abort?.();
    voiceCanceledRef.current = false;
    setVoiceError('');
    setInput('');

    const recognition = new SpeechRecognition();
    recognition.lang = 'vi-VN';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    let latestTranscript = '';

    recognition.onresult = (event) => {
      latestTranscript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .trim();
      setInput(latestTranscript);
    };

    recognition.onerror = (event) => {
      if (voiceCanceledRef.current) return;
      const messagesByError = {
        'not-allowed': 'Microphone permission was denied.',
        'no-speech': 'No speech was detected.',
        network: 'Voice recognition network request failed.',
      };
      setVoiceError(messagesByError[event.error] || 'Voice recognition failed.');
      setIsRecording(false);
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setIsRecording(false);
      if (voiceCanceledRef.current) return;
      if (latestTranscript) {
        submitAssistantText(latestTranscript, { source: 'voice' });
      }
    };

    setIsRecording(true);
    recognition.start();
  };

  const handleCancelVoiceCommand = () => {
    voiceCanceledRef.current = true;
    recognitionRef.current?.abort?.();
    recognitionRef.current = null;
    setIsRecording(false);
    setVoiceError('');
  };

  const handleSend = async () => {
    voiceCanceledRef.current = true;
    recognitionRef.current?.abort?.();
    await submitAssistantText(input, { source: 'rest' });
  };

  const handlePauseStream = () => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  };

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg bg-white shadow-sm">
      <div className="border-b border-gray-100 p-4 sm:p-6">
        <h3 className="text-lg font-semibold">H.E.R.A. Assistant</h3>
        <p className="text-sm text-textMuted">Runtime command channel</p>
      </div>

      <div 
        ref={scrollRef}
        className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-4 sm:p-6"
      >
        {messages.length === 0 && (
          <div className="rounded-lg border border-gray-100 bg-background p-4 text-sm text-textMuted">
            {isLoadingHistory ? 'Loading assistant messages...' : 'No assistant messages in this session.'}
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={`${msg.time}-${idx}`} className={`flex flex-col ${msg.isBot ? 'items-start' : 'items-end'}`}>
            {msg.isBot && msg.thinking && (
              <div className="mb-2 w-full max-w-[88%] sm:max-w-[80%]">
                <div className="rounded-lg border border-blue-200 bg-blue-50">
                  <button
                    type="button"
                    onClick={() => setThinkingCollapsed((collapsed) => !collapsed)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-blue-100"
                  >
                    <span className={`text-blue-600 transition-transform ${thinkingCollapsed ? '-rotate-90' : ''}`}>
                      ▼
                    </span>
                    <span className="text-xs font-semibold text-blue-600">Thinking</span>
                  </button>
                  {!thinkingCollapsed && (
                    <div className="whitespace-pre-wrap px-3 pb-2 text-xs text-blue-700 opacity-80">
                      {msg.thinking}
                    </div>
                  )}
                </div>
              </div>
            )}
            <div className={`max-w-[88%] rounded-lg p-3 sm:max-w-[80%] sm:p-4 ${
              msg.isBot
                ? msg.isError
                  ? 'bg-red-50 text-red-700'
                  : 'bg-background text-textMain'
                : 'bg-primary text-white'
            }`}>
              {msg.isStreaming && !msg.text ? (
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-[#3A7D44]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-[#3A7D44] [animation-delay:0.15s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-[#3A7D44] [animation-delay:0.3s]" />
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm">{msg.text}</p>
              )}
            </div>
            <span className="text-xs text-gray-400 mt-1">{msg.time}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3 border-t border-[#e0ddd0] bg-white p-4 sm:gap-4 sm:p-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !isSending) handleSend();
            }}
            placeholder={isRecording ? 'Listening...' : 'Ask H.E.R.A. anything...'}
            disabled={isSending}
            className="min-w-0 flex-1 rounded-lg border border-[#e0ddd0] bg-[#f8f5e9] px-4 py-3 text-sm text-[#4a3f35] focus:border-[#3A7D44] focus:outline-none disabled:opacity-60 sm:px-5"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending || isLoadingHistory || !input.trim()}
            className="grid min-h-11 min-w-11 place-items-center rounded-lg bg-[#3A7D44] p-3 text-white shadow-sm transition-colors hover:bg-[#9DC08B] disabled:opacity-60"
          >
            <Send size={18} />
          </button>
          {isStreaming && (
            <button
              type="button"
              onClick={handlePauseStream}
              className="grid min-h-11 min-w-11 place-items-center rounded-lg bg-orange-500 p-3 text-white shadow-sm transition-colors hover:bg-orange-600"
              title="Pause streaming"
            >
              <X size={18} />
            </button>
          )}
        </div>
        <div className="flex flex-col gap-2 min-[380px]:flex-row">
          <button
            type="button"
            onClick={handleStartVoiceCommand}
            disabled={isSending || isLoadingHistory}
            className={`flex min-h-12 flex-1 items-center justify-center gap-2 rounded-lg px-3 py-3 font-medium text-white shadow-sm transition-all sm:py-4 ${
              isRecording ? 'bg-[#d98080] hover:bg-[#c96e6e]' : 'bg-[#9DC08B] hover:bg-[#3A7D44]'
            } disabled:opacity-60`}
          >
            <Mic size={20} className={isRecording ? 'animate-pulse' : ''} />
            {isRecording ? 'Recording...' : 'Voice Command'}
          </button>

          <button
            type="button"
            onClick={handleToggleVoiceReply}
            aria-pressed={isVoiceReplyEnabled}
            title={isVoiceReplyEnabled ? 'Turn off voice replies' : 'Turn on voice replies'}
            className={`flex min-h-12 items-center justify-center gap-2 rounded-lg border px-4 py-3 font-medium transition-colors sm:py-4 ${
              isVoiceReplyEnabled
                ? 'border-[#3A7D44] bg-[#ecf5ec] text-[#2d6336] hover:bg-[#dfeedd]'
                : 'border-[#e2d7cb] bg-white text-[#7b6655] hover:bg-[#f8f4ee]'
            }`}
          >
            {isVoiceReplyEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
            <span>{isVoiceReplyEnabled ? 'Voice Reply On' : 'Voice Reply Off'}</span>
          </button>

          {isRecording && (
            <button
              type="button"
              onClick={handleCancelVoiceCommand}
              className="flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#e2d7cb] bg-white px-4 py-3 text-[#7b6655] transition-colors hover:bg-[#f8f4ee] sm:py-4"
            >
              <X size={18} /> Cancel
            </button>
          )}
        </div>
        {voiceError && (
          <p className="text-sm text-red-600">{voiceError}</p>
        )}
        {streamError && (
          <p className="text-sm text-red-600">{streamError}</p>
        )}
      </div>
    </div>
  );
};

export default AiAssistant;
