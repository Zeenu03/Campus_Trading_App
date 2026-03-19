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

  const handleAction = async (memberId, action) => {
    setActionId(memberId);
    try {
      if (action === 'delete') {
        if (!confirm('Remove this member? This will deactivate the account, revoke sessions, and withdraw listings.')) return;
        await api.delete(`/members/${memberId}`);
        toast.success('Member removed');
      } else {
        const isActive = action === 'activate';
        await api.put(`/members/${memberId}`, { is_active: isActive });
        toast.success(isActive ? 'Member activated' : 'Member deactivated');
      }
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
                          onClick={() => handleAction(m.member_id, 'deactivate')}
                          disabled={actionId === m.member_id}
                          className="btn-secondary btn-sm text-xs"
                        >
                          Deactivate
                        </button>
                      )}
                      {!m.is_active && (
                        <button
                          onClick={() => handleAction(m.member_id, 'activate')}
                          disabled={actionId === m.member_id}
                          className="btn-primary btn-sm text-xs"
                        >
                          Activate
                        </button>
                      )}
                      <button
                        onClick={() => handleAction(m.member_id, 'delete')}
                        disabled={actionId === m.member_id}
                        className="btn-danger btn-sm text-xs"
                      >
                        Remove
                      </button>
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
    </div>
  );
}
