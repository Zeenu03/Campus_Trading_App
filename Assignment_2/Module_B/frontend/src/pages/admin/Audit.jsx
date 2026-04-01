import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/Pagination';
import LoadingSpinner from '../../components/LoadingSpinner';
import { formatUtcDateTime } from '../../utils/datetime';

// A row written by the HTTP middleware always has an ip_address.
// A row written by a MySQL trigger never sets ip_address (NULL).
const rowSource = (entry) => entry.ip_address != null ? 'api' : 'trigger';

const isUnauthorized = (entry) =>
  entry.session_id === null && ['INSERT', 'UPDATE', 'DELETE'].includes(entry.action);

export default function AdminAudit() {
  const [logs, setLogs]             = useState([]);
  const [total, setTotal]           = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage]             = useState(1);
  const [loading, setLoading]       = useState(true);

  // Filters
  const [source, setSource]               = useState('');   // '' | 'api' | 'trigger'
  const [statusFilter, setStatusFilter]   = useState('');   // '' | 'success' | 'fail'
  const [unauthorized, setUnauthorized]   = useState(false);

  // Reset to page 1 whenever a filter changes
  useEffect(() => { setPage(1); }, [source, statusFilter, unauthorized]);

  useEffect(() => {
    setLoading(true);
    api.get('/admin/audit-log', {
      page,
      page_size: 50,
      source:       source       || undefined,
      status:       statusFilter || undefined,
      unauthorized: unauthorized ? '1' : undefined,
    })
      .then(data => {
        setLogs(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, source, statusFilter, unauthorized]);

  return (
    <div className="space-y-4">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500 mt-1">
            Sorted newest-first by insertion order.{' '}
            <span className="text-red-600 font-medium">Red rows</span> = direct DB write with no API session (unauthorized).{' '}
            <span className="text-yellow-700 font-medium">Yellow rows</span> = failed API request.
          </p>
        </div>
        <span className="badge-blue shrink-0">{total.toLocaleString()} entries</span>
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-red-100 border border-red-300" />
          <span className="text-gray-600">Unauthorized direct DB write (trigger, session = NULL)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-yellow-50 border border-yellow-300" />
          <span className="text-gray-600">Failed API request</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700">API</span>
          <span className="text-gray-600">Written by HTTP middleware (has IP)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-100 text-purple-700">Trigger</span>
          <span className="text-gray-600">Written by MySQL trigger (no IP)</span>
        </div>
      </div>

      {/* ── Filter bar ── */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={source}
          onChange={e => setSource(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All sources</option>
          <option value="api">API rows only</option>
          <option value="trigger">Trigger rows only</option>
        </select>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          <option value="success">Success</option>
          <option value="fail">Failed</option>
        </select>

        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={unauthorized}
            onChange={e => setUnauthorized(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-red-600 focus:ring-red-500"
          />
          Unauthorized writes only
        </label>

        {(source || statusFilter || unauthorized) && (
          <button
            onClick={() => { setSource(''); setStatusFilter(''); setUnauthorized(false); }}
            className="text-xs text-gray-500 underline hover:text-gray-700"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ── Table ── */}
      {loading ? <LoadingSpinner /> : (
        <div className="card p-0 overflow-hidden overflow-x-auto">
          <table className="w-full text-xs min-w-[900px]">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {/* ID column — active sort indicator */}
                <th className="px-3 py-3 text-left font-medium text-gray-700 uppercase tracking-wider whitespace-nowrap select-none">
                  <span className="inline-flex items-center gap-1">
                    # <span className="text-blue-500 text-base leading-none">↓</span>
                  </span>
                </th>
                {['Timestamp', 'Source', 'Session ID', 'User ID', 'Action', 'Table', 'Target ID', 'IP Address', 'Status'].map(h => (
                  <th key={h} className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {[...logs].sort((a, b) => b.log_id - a.log_id).map(entry => {
                const src    = rowSource(entry);
                const unauth = isUnauthorized(entry);
                const isFail = entry.status === 'fail';

                const rowClass = unauth
                  ? 'bg-red-50 text-red-900'
                  : isFail
                  ? 'bg-yellow-50'
                  : 'hover:bg-gray-50';

                return (
                  <tr key={entry.log_id} className={rowClass}>

                    {/* log_id — the true insertion order */}
                    <td className="px-3 py-2 text-gray-400 tabular-nums">{entry.log_id}</td>

                    {/* Timestamp */}
                    <td className="px-3 py-2 whitespace-nowrap text-gray-600 tabular-nums">
                      {formatUtcDateTime(entry.timestamp)}
                    </td>

                    {/* Source badge */}
                    <td className="px-3 py-2">
                      {src === 'api'
                        ? <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700">API</span>
                        : <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-100 text-purple-700">Trigger</span>
                      }
                    </td>

                    {/* Session ID */}
                    <td className="px-3 py-2 font-mono max-w-[140px] truncate">
                      {entry.session_id == null
                        ? <span className="text-red-600 font-bold">NULL {unauth ? '⚠' : ''}</span>
                        : <span title={entry.session_id} className="text-gray-500">
                            {entry.session_id.slice(0, 10)}…
                          </span>
                      }
                    </td>

                    {/* User ID */}
                    <td className="px-3 py-2 text-gray-600 tabular-nums">{entry.user_id ?? '—'}</td>

                    {/* Action */}
                    <td className="px-3 py-2 font-semibold">{entry.action}</td>

                    {/* Table */}
                    <td className="px-3 py-2 text-gray-600">{entry.target_table}</td>

                    {/* Target ID */}
                    <td className="px-3 py-2 font-mono text-gray-500">{entry.target_id ?? '—'}</td>

                    {/* IP */}
                    <td className="px-3 py-2 text-gray-400 tabular-nums">{entry.ip_address ?? '—'}</td>

                    {/* Status */}
                    <td className="px-3 py-2">
                      <span className={entry.status === 'success' ? 'badge-green' : 'badge-red'}>
                        {entry.status}
                      </span>
                    </td>

                  </tr>
                );
              })}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-gray-400">
                    No audit log entries match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
