import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/Pagination';
import LoadingSpinner from '../../components/LoadingSpinner';

export default function AdminAudit() {
  const [logs, setLogs]         = useState([]);
  const [total, setTotal]       = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage]         = useState(1);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/admin/audit-log', { page, page_size: 20 })
      .then(data => {
        setLogs(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  const isDirectWrite = (entry) => entry.session_id === null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500 mt-1">
            Rows highlighted in <span className="text-red-600 font-medium">red</span> indicate direct DB writes (session_id = NULL) — potential unauthorized access.
          </p>
        </div>
        <span className="badge-blue">{total} entries</span>
      </div>

      <div className="flex gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-red-100 border border-red-300" />
          <span className="text-gray-600">Direct DB write (session = NULL)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-yellow-50 border border-yellow-300" />
          <span className="text-gray-600">Failed request</span>
        </div>
      </div>

      {loading ? <LoadingSpinner /> : (
        <div className="card p-0 overflow-hidden overflow-x-auto">
          <table className="w-full text-xs min-w-[800px]">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Timestamp', 'Session ID', 'User ID', 'Action', 'Table', 'Target ID', 'IP', 'Status'].map(h => (
                  <th key={h} className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map(entry => {
                const isDirect  = isDirectWrite(entry);
                const isFail    = entry.status === 'fail';
                const rowClass  = isDirect
                  ? 'bg-red-50 text-red-900'
                  : isFail
                  ? 'bg-yellow-50'
                  : 'hover:bg-gray-50';

                return (
                  <tr key={entry.log_id} className={rowClass}>
                    <td className="px-3 py-2 whitespace-nowrap text-gray-600">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono max-w-[160px] truncate">
                      {isDirect
                        ? <span className="text-red-600 font-bold">NULL ⚠</span>
                        : <span title={entry.session_id} className="text-gray-500">
                            {entry.session_id?.slice(0, 12)}…
                          </span>
                      }
                    </td>
                    <td className="px-3 py-2 text-gray-600">{entry.user_id ?? '—'}</td>
                    <td className="px-3 py-2 font-medium">{entry.action}</td>
                    <td className="px-3 py-2 text-gray-600">{entry.target_table}</td>
                    <td className="px-3 py-2 text-gray-500">{entry.target_id ?? '—'}</td>
                    <td className="px-3 py-2 text-gray-400">{entry.ip_address ?? '—'}</td>
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
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">No audit log entries.</td>
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
