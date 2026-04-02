import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/Pagination';
import LoadingSpinner from '../../components/LoadingSpinner';
import { formatUtcDateTime } from '../../utils/datetime';

const rowSource = (entry) => (entry.ip_address != null ? 'api' : 'trigger');

const isUnauthorized = (entry) =>
  entry.session_id === null && ['INSERT', 'UPDATE', 'DELETE'].includes(entry.action);

const ACTION_HINTS = ['POST', 'PUT', 'PATCH', 'DELETE', 'INSERT', 'UPDATE', 'DELETE'];

export default function AdminAudit() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [source, setSource] = useState('');
  const [ipFilter, setIpFilter] = useState('');
  const [userIdFilter, setUserIdFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [unauthorized, setUnauthorized] = useState(false);

  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (source) n += 1;
    if (ipFilter.trim()) n += 1;
    if (userIdFilter.trim()) n += 1;
    if (actionFilter.trim()) n += 1;
    if (unauthorized) n += 1;
    return n;
  }, [source, ipFilter, userIdFilter, actionFilter, unauthorized]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get('/admin/audit-log', {
        page,
        page_size: 50,
        source: source || undefined,
        ip: ipFilter.trim() || undefined,
        user_id: userIdFilter.trim() || undefined,
        action: actionFilter.trim() || undefined,
        unauthorized: unauthorized ? '1' : undefined,
      })
      .then((data) => {
        if (cancelled) return;
        setLogs(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => {
        if (!cancelled) {
          setLogs([]);
          setTotal(0);
          setTotalPages(1);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, source, ipFilter, userIdFilter, actionFilter, unauthorized]);

  /** Reset page together with filter updates so the fetch effect never runs with stale page + new filters. */
  const clearFilters = () => {
    setPage(1);
    setSource('');
    setIpFilter('');
    setUserIdFilter('');
    setActionFilter('');
    setUnauthorized(false);
  };

  return (
    <div className="min-w-0 max-w-[1400px] mx-auto space-y-8 pb-10">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-900 px-6 py-10 sm:px-10 text-white shadow-xl shadow-slate-900/20">
        <div
          className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-cyan-500/10 blur-3xl"
          aria-hidden
        />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-indigo-200 text-sm font-medium tracking-wide uppercase mb-1">
              Security & compliance
            </p>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Audit log</h1>
            <p className="mt-2 text-slate-300 text-sm max-w-xl leading-relaxed">
              Newest events first. API rows include a client IP; trigger rows have no IP. Rows with no
              session on write operations may indicate direct database access.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-2xl bg-white/10 backdrop-blur px-5 py-3 border border-white/10">
              <p className="text-xs text-indigo-200 uppercase tracking-wider font-semibold">Total entries</p>
              <p className="text-2xl font-bold tabular-nums">{total.toLocaleString()}</p>
            </div>
            {activeFilterCount > 0 && (
              <span className="inline-flex items-center rounded-full bg-amber-400/20 text-amber-100 border border-amber-400/30 px-3 py-1 text-xs font-semibold">
                {activeFilterCount} filter{activeFilterCount === 1 ? '' : 's'} active
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-2xl border border-slate-200/80 bg-white/90 backdrop-blur-sm shadow-lg shadow-slate-200/50 p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <h2 className="text-lg font-semibold text-slate-800">Filters</h2>
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-sm font-medium text-indigo-600 hover:text-indigo-800 underline-offset-2 hover:underline"
            >
              Clear all
            </button>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
              Source
            </span>
            <select
              value={source}
              onChange={(e) => {
                setPage(1);
                setSource(e.target.value);
              }}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2.5 text-sm text-slate-800 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition"
            >
              <option value="">All sources</option>
              <option value="api">HTTP API (has IP)</option>
              <option value="trigger">DB trigger (no IP)</option>
            </select>
          </label>

          <label className="block">
            <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
              IP contains
            </span>
            <input
              type="text"
              value={ipFilter}
              onChange={(e) => {
                setPage(1);
                setIpFilter(e.target.value);
              }}
              placeholder="e.g. 127.0.0.1"
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2.5 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition font-mono"
            />
          </label>

          <label className="block">
            <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
              User ID
            </span>
            <input
              type="number"
              value={userIdFilter}
              onChange={(e) => {
                setPage(1);
                setUserIdFilter(e.target.value);
              }}
              placeholder="Exact match"
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2.5 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition tabular-nums"
            />
          </label>

          <label className="block">
            <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
              Action
            </span>
            <input
              type="text"
              list="audit-action-hints"
              value={actionFilter}
              onChange={(e) => {
                setPage(1);
                setActionFilter(e.target.value);
              }}
              placeholder="e.g. POST, INSERT"
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2.5 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition"
            />
            <datalist id="audit-action-hints">
              {ACTION_HINTS.map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide mr-1">Quick action</span>
          {['POST', 'PUT', 'DELETE', 'INSERT', 'UPDATE'].map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => {
                setPage(1);
                setActionFilter(a);
              }}
              className={`rounded-full px-3 py-1 text-xs font-semibold border transition ${
                actionFilter === a
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-600/25'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-700'
              }`}
            >
              {a}
            </button>
          ))}
        </div>

        <label className="mt-6 flex cursor-pointer select-none items-center gap-3 rounded-xl border border-rose-100 bg-rose-50/40 px-4 py-3 hover:bg-rose-50/70 transition">
          <input
            type="checkbox"
            checked={unauthorized}
            onChange={(e) => {
              setPage(1);
              setUnauthorized(e.target.checked);
            }}
            className="h-4 w-4 rounded border-rose-300 text-rose-600 focus:ring-rose-500"
          />
          <span className="text-sm text-slate-700">
            <span className="font-semibold text-rose-800">Unauthorized writes only</span>
            <span className="text-slate-500"> — trigger path with null session (INSERT / UPDATE / DELETE)</span>
          </span>
        </label>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="rounded-2xl border border-slate-200/80 bg-white shadow-xl shadow-slate-200/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[960px]">
              <thead>
                <tr className="bg-slate-900 text-left text-xs font-semibold uppercase tracking-wider text-slate-300">
                  <th className="px-4 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1 text-white">
                      ID
                      <span className="text-indigo-400 font-normal normal-case">↓ newest</span>
                    </span>
                  </th>
                  <th className="px-4 py-4 whitespace-nowrap">Timestamp (UTC)</th>
                  <th className="px-4 py-4 whitespace-nowrap">Source</th>
                  <th className="px-4 py-4 whitespace-nowrap">Session</th>
                  <th className="px-4 py-4 whitespace-nowrap">User</th>
                  <th className="px-4 py-4 whitespace-nowrap">Action</th>
                  <th className="px-4 py-4 whitespace-nowrap">Table</th>
                  <th className="px-4 py-4 whitespace-nowrap">Target</th>
                  <th className="px-4 py-4 whitespace-nowrap">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((entry, i) => {
                  const src = rowSource(entry);
                  const unauth = isUnauthorized(entry);
                  const rowClass = unauth
                    ? 'bg-rose-50/90 hover:bg-rose-50'
                    : i % 2 === 0
                      ? 'bg-white hover:bg-slate-50/80'
                      : 'bg-slate-50/40 hover:bg-slate-50';

                  return (
                    <tr key={entry.log_id} className={`${rowClass} transition-colors`}>
                      <td className="px-4 py-3 tabular-nums text-slate-400 font-mono text-xs">{entry.log_id}</td>
                      <td className="px-4 py-3 whitespace-nowrap text-slate-600 tabular-nums text-xs font-mono">
                        {formatUtcDateTime(entry.timestamp)}
                      </td>
                      <td className="px-4 py-3">
                        {src === 'api' ? (
                          <span className="inline-flex items-center rounded-lg bg-sky-100 px-2.5 py-1 text-xs font-bold text-sky-800 ring-1 ring-sky-200/60">
                            API
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-lg bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-800 ring-1 ring-violet-200/60">
                            Trigger
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs max-w-[140px]">
                        {entry.session_id == null ? (
                          <span className="text-rose-700 font-bold">
                            NULL{unauth ? ' ⚠' : ''}
                          </span>
                        ) : (
                          <span className="text-slate-500 truncate block" title={entry.session_id}>
                            {entry.session_id.slice(0, 12)}…
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-slate-600">{entry.user_id ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span className="font-semibold text-slate-800">{entry.action}</span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{entry.target_table}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{entry.target_id ?? '—'}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500 tabular-nums">
                        {entry.ip_address ?? '—'}
                      </td>
                    </tr>
                  );
                })}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-6 py-16 text-center">
                      <p className="text-slate-500 text-base">No entries match your filters.</p>
                      <p className="text-slate-400 text-sm mt-2">Try clearing filters or broadening the IP / action search.</p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
