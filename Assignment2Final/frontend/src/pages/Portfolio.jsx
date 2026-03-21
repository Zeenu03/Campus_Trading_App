import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';

const TABS = ['listings', 'transactions', 'ratings', 'wish_requests', 'watchlist'];
const TAB_LABELS = { listings: 'Listings', transactions: 'Transactions', ratings: 'Ratings',
                     wish_requests: 'Wish Requests', watchlist: 'Watchlist' };

const TX_STATUS_COLORS = {
  Accepted:  'bg-green-100 text-green-700',
  Declined:  'bg-red-100 text-red-700',
  Withdrawn: 'bg-yellow-100 text-yellow-700',
};

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
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('listings');
  const [ratingModal, setRatingModal] = useState(null); // { txId }
  const [ratingStars, setRatingStars] = useState(5);
  const [ratingText, setRatingText]   = useState('');
  const [ratingLoading, setRatingLoading] = useState(false);

  const isOwn = user?.member_id && String(user.member_id) === String(id);

  useEffect(() => {
    api.get(`/members/${id}/portfolio`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const handleRate = async () => {
    setRatingLoading(true);
    try {
      await api.post(`/transactions/${ratingModal.txId}/rate`, {
        stars: ratingStars,
        review_text: ratingText || null,
      });
      toast.success('Rating submitted!');
      setRatingModal(null);
      setRatingStars(5);
      setRatingText('');
      const updated = await api.get(`/members/${id}/portfolio`);
      setData(updated);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRatingLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!data)   return <div className="text-center py-16 text-gray-400">Portfolio not found or access denied.</div>;

  const { member, listings, transactions, ratings, wish_requests, watchlist } = data;
  const visibleTabs = isOwn ? TABS : TABS.filter(t => t !== 'watchlist');

  return (
    <>
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
            <span className={`badge text-xs ${member.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
              {member.is_active ? 'Active' : 'Deactivated'}
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
            {transactions.map(tx => {
              const isSeller = user?.member_id === tx.seller_id;
              const role     = isSeller ? 'Sold' : 'Bought';
              const other    = isSeller ? tx.buyer_name : tx.seller_name;
              return (
                <div key={tx.transaction_id}
                  className={`card border-l-4 ${
                    tx.status === 'Accepted'  ? 'border-l-green-500'  :
                    tx.status === 'Withdrawn' ? 'border-l-yellow-500' : 'border-l-red-500'
                  }`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      {/* Clickable title → listing */}
                      <Link
                        to={`/listings/${tx.listing_id}`}
                        className="font-medium text-sm text-blue-700 hover:underline"
                      >
                        {tx.listing_title}
                      </Link>
                      <p className="text-xs text-gray-500 mt-0.5">
                        <span className="font-medium">{role}</span> • with {other} •{' '}
                        ₹{Number(tx.agreed_price).toLocaleString()} •{' '}
                        {new Date(tx.created_date).toLocaleDateString()}
                      </p>
                      {tx.reason && (
                        <p className="text-xs text-gray-500 mt-1 italic">"{tx.reason}"</p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${TX_STATUS_COLORS[tx.status] || 'bg-gray-100 text-gray-600'}`}>
                        {tx.status}
                      </span>
                      {tx.status === 'Accepted' && isOwn && (
                        tx.has_rated
                          ? <span className="text-xs text-gray-400 italic">Rated ✓</span>
                          : <button
                              onClick={() => setRatingModal({ txId: tx.transaction_id })}
                              className="btn-primary text-xs py-1 px-3"
                            >
                              Rate
                            </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
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

    {/* Rating modal */}
    {ratingModal && (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4">
          <h2 className="font-semibold text-gray-800">Rate this transaction</h2>
          <div className="flex gap-1">
            {[1,2,3,4,5].map(s => (
              <button key={s} onClick={() => setRatingStars(s)}
                className={`text-2xl ${s <= ratingStars ? 'text-yellow-400' : 'text-gray-300'}`}>
                ★
              </button>
            ))}
          </div>
          <textarea
            className="input w-full h-20 resize-none"
            placeholder="Write a review (optional)…"
            value={ratingText}
            onChange={e => setRatingText(e.target.value)}
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setRatingModal(null)} className="btn-secondary text-sm">Cancel</button>
            <button onClick={handleRate} disabled={ratingLoading} className="btn-primary text-sm">
              {ratingLoading ? 'Submitting…' : 'Submit Rating'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
