import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/Pagination';
import LoadingSpinner from '../../components/LoadingSpinner';
import toast from 'react-hot-toast';

export default function AdminMembers() {
  const [members, setMembers]   = useState([]);
  const [total, setTotal]       = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage]         = useState(1);
  const [search, setSearch]     = useState('');
  const [loading, setLoading]   = useState(true);
  const [actionId, setActionId] = useState(null);
  const [deactivateConfirm, setDeactivateConfirm] = useState(null); // { member_id, name }

  const load = () => {
    setLoading(true);
    const params = { page, page_size: 20 };
    if (search) params.search = search;
    api.get('/members', params)
      .then(data => {
        setMembers(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [page, search]);

  const handleActivate = async (memberId) => {
    setActionId(memberId);
    try {
      await api.put(`/members/${memberId}`, { is_active: true });
      toast.success('Member activated');
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setActionId(null);
    }
  };

  const handleDeactivateConfirmed = async () => {
    if (!deactivateConfirm) return;
    const { member_id: memberId } = deactivateConfirm;
    setDeactivateConfirm(null);
    setActionId(memberId);
    try {
      await api.put(`/members/${memberId}`, { is_active: false });
      toast.success('Member deactivated');
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setActionId(null);
    }
  };

  const statusBadge = (isActive) =>
    isActive ? { className: 'badge-green', label: 'Active' } : { className: 'badge-gray', label: 'Deactivated' };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Member Management</h1>
        <span className="badge-blue">{total} members</span>
      </div>

      <div className="card">
        <input
          className="input max-w-sm text-sm"
          placeholder="Search by name or email…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
        />
      </div>

      {loading ? <LoadingSpinner /> : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['ID', 'Name', 'Email', 'Department', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {members.map(m => (
                <tr key={m.member_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500">{m.member_id}</td>
                  <td className="px-4 py-3 font-medium">
                    <a href={`/portfolio/${m.member_id}`} className="text-blue-600 hover:underline">{m.name}</a>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{m.email}</td>
                  <td className="px-4 py-3 text-gray-500">{m.department || '—'}</td>
                  <td className="px-4 py-3">
                    {(() => {
                      const { className, label } = statusBadge(m.is_active);
                      return <span className={className}>{label}</span>;
                    })()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      {m.is_active && (
                        <button
                          type="button"
                          onClick={() => setDeactivateConfirm({ member_id: m.member_id, name: m.name })}
                          disabled={actionId === m.member_id}
                          className="btn-secondary btn-sm text-xs"
                        >
                          Deactivate
                        </button>
                      )}
                      {!m.is_active && (
                        <button
                          type="button"
                          onClick={() => handleActivate(m.member_id)}
                          disabled={actionId === m.member_id}
                          className="btn-primary btn-sm text-xs"
                        >
                          Activate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {members.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No members found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />

      {deactivateConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-labelledby="deactivate-title"
          onClick={() => setDeactivateConfirm(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <h2 id="deactivate-title" className="text-lg font-semibold text-gray-900">
              Deactivate member?
            </h2>
            <p className="text-sm text-gray-600">
              This will deactivate <span className="font-medium text-gray-900">{deactivateConfirm.name}</span>.
              They will not be able to sign in until reactivated.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => setDeactivateConfirm(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger btn-sm"
                onClick={handleDeactivateConfirmed}
              >
                Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
