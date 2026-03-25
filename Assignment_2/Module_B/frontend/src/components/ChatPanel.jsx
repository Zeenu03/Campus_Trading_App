import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../api/client';
import { formatTimeUTC } from '../utils/datetime';

const POLL_INTERVAL_MS = 5000;

export default function ChatPanel({ threadId, currentUserId, onClose }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [text, setText]         = useState('');
  const [sending, setSending]   = useState(false);
  const bottomRef               = useRef(null);
  const intervalRef             = useRef(null);

  const fetchMessages = useCallback(async () => {
    try {
      const res = await api.get(`/threads/${threadId}/messages`, { page: 1, page_size: 200 });
      if (Array.isArray(res?.data)) setMessages(res.data);
    } catch {
      // silent — polling will retry
    }
  }, [threadId]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    setMessages([]);
    fetchMessages().finally(() => setLoading(false));
  }, [fetchMessages]);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  // Poll for new messages every 5 s
  useEffect(() => {
    intervalRef.current = setInterval(fetchMessages, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [fetchMessages]);

  // Re-poll immediately when window gains focus
  useEffect(() => {
    const onFocus = () => fetchMessages();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [fetchMessages]);

  const handleSend = async (e) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      await api.post(`/threads/${threadId}/messages`, { message_text: trimmed });
      setText('');
      await fetchMessages();
    } catch {
      // toast handled by parent / api client
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  return (
    <div className="flex flex-col bg-white rounded-xl shadow-2xl border border-gray-200 h-96 w-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50 rounded-t-xl">
        <span className="text-sm font-semibold text-gray-800">Chat</span>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
            aria-label="Close chat"
          >
            ×
          </button>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {loading && (
          <p className="text-center text-xs text-gray-400 py-4">Loading messages…</p>
        )}
        {!loading && messages.length === 0 && (
          <p className="text-center text-xs text-gray-400 py-4">No messages yet. Say hi!</p>
        )}
        {messages.map((msg) => {
          const isMe = String(msg.sender_id) === String(currentUserId);
          return (
            <div key={msg.message_id} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] rounded-2xl px-3 py-2 text-sm ${
                isMe
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-gray-100 text-gray-900 rounded-bl-sm'
              }`}>
                {!isMe && (
                  <p className="text-xs font-semibold mb-0.5 text-gray-600">{msg.sender_name}</p>
                )}
                <p className="whitespace-pre-wrap break-words">{msg.message_text}</p>
                <p className={`text-xs mt-1 ${isMe ? 'text-blue-200' : 'text-gray-400'}`}>
                  {formatTimeUTC(msg.sent_date)}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSend} className="flex gap-2 p-3 border-t">
        <textarea
          className="flex-1 input text-sm resize-none h-10 min-h-[2.5rem] py-2"
          placeholder="Type a message… (Enter to send)"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          className="btn-primary px-4 text-sm whitespace-nowrap self-end"
        >
          {sending ? '…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
