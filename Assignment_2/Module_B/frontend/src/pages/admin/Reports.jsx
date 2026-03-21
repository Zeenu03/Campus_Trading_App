import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/Pagination';
import LoadingSpinner from '../../components/LoadingSpinner';
import toast from 'react-hot-toast';

export default function AdminReports() {
  const [reports, setReports]   = useState([]);
  const [total, setTotal]       = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage]         = useState(1);
  const [statusFilter, setStatus] = useState('');
  const [loading, setLoading]   = useState(true);
  const [resolving, setResolving] = useState(null);
  const [form, setForm]         = useState({ resolution: '', status: 'Resolved' });

  const load = () => {
    setLoading(true);
    const params = { page, page_size: 20 };
    if (statusFilter) params.status = statusFilter;
    api.get('/reports', params)
      .then(data => {
        setReports(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [page, statusFilter]);

  const handleResolve = async (reportId) => {
    if (!form.resolution.trim()) {
      toast.error('Resolution text is required');
      return;
    }
    try {
      await api.put(`/reports/${reportId}/resolve`, form);
      toast.success('Report resolved');
      setResolving(null);
      setForm({ resolution: '', status: 'Resolved' });
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const statusColors = {
    Submitted: 'badge-blue', UnderReview: 'badge-yellow',
    Resolved: 'badge-green', Dismissed: 'badge-gray',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Report Queue</h1>
        <span className="badge-blue">{total} reports</span>
      </div>

      <div className="card flex gap-4 items-center">
        <label className="text-sm font-medium text-gray-700">Filter by status:</label>
        {['', 'Submitted', 'UnderReview', 'Resolved', 'Dismissed'].map(s => (
          <button
            key={s || 'all'}
            onClick={() => { setStatus(s); setPage(1); }}
            className={`btn btn-sm text-xs ${statusFilter === s ? 'btn-primary' : 'btn-secondary'}`}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner /> : (
        <div className="space-y-4">
          {reports.map(r => (
            <div key={r.report_id} className="card space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={statusColors[r.status] || 'badge-gray'}>{r.status}</span>
                    <span className="badge-blue">{r.report_type}</span>
                  </div>
                  <p className="font-medium text-sm mt-1">{r.description}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Reported by: {r.reporter_name} •{' '}
                    {r.reported_member_id && `Member #${r.reported_member_id}`}
                    {r.reported_listing_id && `Listing #${r.reported_listing_id}`}
                    {' '}• {new Date(r.submitted_date).toLocaleDateString()}
                  </p>
                </div>
                {(r.status === 'Submitted' || r.status === 'UnderReview') && (
                  <button
                    onClick={() => setResolving(resolving === r.report_id ? null : r.report_id)}
                    className="btn-primary btn-sm text-xs flex-shrink-0"
                  >
                    {resolving === r.report_id ? 'Cancel' : 'Resolve'}
                  </button>
                )}
              </div>

              {r.resolution && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
                  <span className="font-medium">Resolution: </span>{r.resolution}
                </div>
              )}

              {resolving === r.report_id && (
                <div className="border-t pt-3 space-y-3">
                  <div>
                    <label className="label text-xs">Resolution Text</label>
                    <textarea
                      className="input resize-none text-sm" rows={2}
                      value={form.resolution}
                      onChange={e => setForm(f => ({ ...f, resolution: e.target.value }))}
                      placeholder="Describe how this report was handled…"
                    />
                  </div>
                  <div className="flex gap-2 items-center">
                    <select
                      value={form.status}
                      onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                      className="input text-sm max-w-xs"
                    >
                      <option value="Resolved">Resolved</option>
                      <option value="Dismissed">Dismissed</option>
                    </select>
                    <button onClick={() => handleResolve(r.report_id)} className="btn-primary btn-sm text-sm">
                      Submit
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {reports.length === 0 && (
            <div className="text-center py-16 text-gray-400">No reports found.</div>
          )}
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
