import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';

const TABS = ['listings', 'transactions', 'ratings', 'wish_requests', 'watchlist'];
const TAB_LABELS = { listings: 'Listings', transactions: 'Transactions', ratings: 'Ratings',
                     wish_requests: 'Wish Requests', watchlist: 'Watchlist' };

function StarRating({ stars }) {
  return (
    <span className="text-yellow-400 text-sm">
      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
    </span>
  );
}

export default function Portfolio() {
  const { id } = useParams();
  const { user } = useAuth();
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('listings');
  const [txAction, setTxAction] = useState({});

  const isOwn = user?.member_id && String(user.member_id) === String(id);

  useEffect(() => {
    api.get(`/members/${id}/portfolio`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const handleConfirmTx = async (txId) => {
    try {
      await api.put(`/transactions/${txId}/confirm`);
      toast.success('Transaction confirmed!');
      const updated = await api.get(`/members/${id}/portfolio`);
      setData(updated);
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!data)   return <div className="text-center py-16 text-gray-400">Portfolio not found or access denied.</div>;

  const { member, listings, transactions, ratings, wish_requests, watchlist } = data;
  const visibleTabs = isOwn ? TABS : TABS.filter(t => t !== 'watchlist');

  return (
    <div className="space-y-6">
      {/* Member header */}
      <div className="card flex flex-col sm:flex-row items-start sm:items-center gap-6">
        <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center text-3xl font-bold text-blue-700 flex-shrink-0">
          {member.name?.[0]?.toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{member.name}</h1>
            {member.is_verified && <span className="badge-green text-xs">Verified</span>}
            <span className={`badge text-xs ${member.account_status === 'Active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {member.account_status}
            </span>
          </div>
          <p className="text-gray-500 text-sm mt-1">{member.email}</p>
          {member.department && (
            <p className="text-sm text-gray-600 mt-1">{member.department} • Year {member.year_of_study}</p>
          )}
          {member.hostel && (
            <p className="text-sm text-gray-500">{member.hostel} {member.room_number && `• ${member.room_number}`}</p>
          )}
          {member.bio && <p className="text-sm text-gray-700 mt-2">{member.bio}</p>}
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-blue-700">
            {ratings.length > 0
              ? (ratings.reduce((s, r) => s + r.stars, 0) / ratings.length).toFixed(1)
              : '—'}
          </p>
          <p className="text-xs text-gray-500">Avg rating</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-0 overflow-x-auto" aria-label="Tabs">
          {visibleTabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
                ${activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              {TAB_LABELS[tab]}
              <span className="ml-1.5 text-xs text-gray-400">
                ({data[tab]?.length ?? 0})
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'listings' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {listings.map(l => (
              <a key={l.listing_id} href={`/listings/${l.listing_id}`} className="card hover:shadow-md transition-shadow">
                <p className="font-medium text-sm">{l.title}</p>
                <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                  <span>₹{Number(l.asking_price).toLocaleString()}</span>
                  <span className={`badge-${l.status === 'Listed' ? 'green' : 'gray'}`}>{l.status}</span>
                </div>
              </a>
            ))}
            {listings.length === 0 && <p className="text-gray-400 col-span-3 text-center py-8">No listings yet.</p>}
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="space-y-3">
            {transactions.map(tx => (
              <div key={tx.transaction_id} className="card flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-sm">{tx.listing_title}</p>
                  <p className="text-xs text-gray-500 mt-1">₹{Number(tx.agreed_price).toLocaleString()} • {tx.status}</p>
                </div>
                {tx.status === 'Scheduled' && isOwn && (
                  <button onClick={() => handleConfirmTx(tx.transaction_id)}
                    className="btn-primary btn-sm text-xs">
                    Confirm
                  </button>
                )}
                {tx.status === 'Completed' && (
                  <span className="badge-green text-xs">Completed</span>
                )}
              </div>
            ))}
            {transactions.length === 0 && <p className="text-gray-400 text-center py-8">No transactions yet.</p>}
          </div>
        )}

        {activeTab === 'ratings' && (
          <div className="space-y-3">
            {ratings.map(r => (
              <div key={r.rating_id} className="card">
                <StarRating stars={r.stars} />
                {r.review_text && <p className="text-sm text-gray-700 mt-1">{r.review_text}</p>}
                <p className="text-xs text-gray-400 mt-2">{new Date(r.rating_date).toLocaleDateString()}</p>
              </div>
            ))}
            {ratings.length === 0 && <p className="text-gray-400 text-center py-8">No ratings yet.</p>}
          </div>
        )}

        {activeTab === 'wish_requests' && (
          <div className="space-y-3">
            {wish_requests.map(wr => (
              <div key={wr.wish_request_id} className="card flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{wr.item_description}</p>
                  <p className="text-xs text-gray-500 mt-1">{wr.status}</p>
                </div>
                <span className={`badge-${wr.status === 'Active' ? 'green' : 'gray'}`}>{wr.status}</span>
              </div>
            ))}
            {wish_requests.length === 0 && <p className="text-gray-400 text-center py-8">No wish requests.</p>}
          </div>
        )}

        {activeTab === 'watchlist' && isOwn && (
          <div className="space-y-3">
            {watchlist.map(w => (
              <a key={w.watchlist_id} href={`/listings/${w.listing_id}`}
                className="card flex items-center justify-between hover:shadow-md transition-shadow">
                <div>
                  <p className="font-medium text-sm">{w.title}</p>
                  <p className="text-xs text-gray-500">₹{Number(w.asking_price).toLocaleString()} • {w.status}</p>
                </div>
              </a>
            ))}
            {watchlist.length === 0 && <p className="text-gray-400 text-center py-8">Watchlist is empty.</p>}
          </div>
        )}
      </div>
    </div>
  );
}
