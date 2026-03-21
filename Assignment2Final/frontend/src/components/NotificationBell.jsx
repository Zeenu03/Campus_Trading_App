import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import toast from 'react-hot-toast';

const PAGE_SIZE = 50;

function formatWhen(d) {
  if (!d) return '';
  try {
    const date = new Date(d);
    return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [pendingId, setPendingId] = useState(null);
  const panelRef = useRef(null);
  const btnRef = useRef(null);

  const memberId = user?.member_id;
  const enabled = !!memberId;

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const res = await api.get('/notifications', { page: 1, page_size: PAGE_SIZE });
      const list = res?.data || [];
      const unread = list.filter((n) => !n.is_read);
      setItems(unread);
      setUnreadCount(unread.length);
    } catch {
      // silent — bell still usable on retry
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    load();
    const onFocus = () => load();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [enabled, load]);

  useEffect(() => {
    if (!open || !enabled) return;
    load();
  }, [open, enabled, load]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (panelRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const markRead = async (id) => {
    if (pendingId != null) return;
    setPendingId(id);
    try {
      await api.put(`/notifications/${id}/read`, {});
      setItems((prev) => prev.filter((n) => n.notification_id !== id));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (e) {
      toast.error(e?.message || 'Could not mark as read');
    } finally {
      setPendingId(null);
    }
  };

  if (!enabled) return null;

  const badge = unreadCount > 0 ? (unreadCount > 99 ? '99+' : String(unreadCount)) : null;

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={badge ? `Notifications, ${unreadCount} unread` : 'Notifications'}
      >
        <span className="sr-only">Notifications</span>
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {badge && (
          <span className="absolute top-0 right-0 min-w-[1.125rem] h-[1.125rem] px-0.5 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-semibold leading-none">
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute right-0 mt-2 w-[min(100vw-2rem,20rem)] max-h-[24rem] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg z-50 flex flex-col"
          role="dialog"
          aria-label="Notifications"
        >
          <div className="px-3 py-2 border-b border-gray-100 flex items-center justify-between bg-gray-50">
            <span className="text-sm font-semibold text-gray-900">Notifications</span>
            {loading && <span className="text-xs text-gray-400">Updating…</span>}
          </div>
          <div className="overflow-y-auto flex-1">
            {loading && items.length === 0 ? (
              <p className="text-sm text-gray-500 px-3 py-6 text-center">Loading…</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-gray-500 px-3 py-6 text-center">No unread notifications.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {items.map((n) => {
                  const title = n.title?.trim?.() ? n.title : null;
                  const busy = pendingId === n.notification_id;
                  return (
                    <li key={n.notification_id} className="px-3 py-2.5 text-sm bg-blue-50/50">
                      <div className="text-gray-900">
                        {title && <span className="font-medium">{title}: </span>}
                        <span className="text-gray-700">{n.message}</span>
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-2">
                        <span className="text-xs text-gray-400">{formatWhen(n.created_date)}</span>
                        <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none shrink-0">
                          <input
                            type="checkbox"
                            checked={false}
                            disabled={busy}
                            onChange={(e) => {
                              if (e.target.checked) markRead(n.notification_id);
                            }}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          Mark as read
                        </label>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
