import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api, uploadsUrl } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import ImageManager from '../components/ImageManager';
import ListingForm, { validateListingForm, buildListingPayload, listingToFormState } from '../components/ListingForm';
import ChatPanel from '../components/ChatPanel';
import { normalizeListingPayload, isListingDetailShape } from '../utils/listingApi';
import toast from 'react-hot-toast';

const fmtPrice = (p) =>
  p != null ? `₹${Number(p).toLocaleString()}` : '—';

const STATUS_COLORS = {
  Listed: 'badge-green', Sold: 'badge-gray', Expired: 'badge-gray', Withdrawn: 'badge-gray',
};

const OFFER_STATUS_COLORS = {
  Submitted: 'text-yellow-700 bg-yellow-50',
  Accepted:  'text-green-700 bg-green-50',
  Declined:  'text-red-700 bg-red-50',
  Withdrawn: 'text-red-700 bg-red-50',
  Expired:   'text-gray-600 bg-gray-100',
};

// ── ReasonModal ────────────────────────────────────────────────
function ReasonModal({ title, onConfirm, onClose, loading }) {
  const [reason, setReason] = useState('');
  return (
    <div
      className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/50"
      onClick={() => !loading && onClose()}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <div>
          <label className="label text-xs">Reason (required)</label>
          <textarea
            className="input text-sm h-24 resize-none"
            placeholder="Please provide a reason…"
            value={reason}
            onChange={e => setReason(e.target.value)}
          />
        </div>
        <div className="flex gap-3 justify-end">
          <button type="button" className="btn-secondary btn-sm text-sm" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger btn-sm text-sm"
            disabled={loading || !reason.trim()}
            onClick={() => onConfirm(reason.trim())}
          >
            {loading ? 'Submitting…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ListingDetail() {
  const { id } = useParams();
  const { user, isMember } = useAuth();
  const navigate = useNavigate();

  // Core listing state
  const [listing, setListing]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [imgIndex, setImgIndex]   = useState(0);

  // Offer form (new offer submission)
  const [offerForm, setOfferForm]   = useState({ offered_price: '' });
  const [submitting, setSubmitting] = useState(false);
  const [offerError, setOfferError] = useState('');

  // Buyer's own offer on this listing
  const [myOffer, setMyOffer] = useState(undefined); // undefined = not yet loaded

  // Update price (buyer)
  const [updatePriceVal, setUpdatePriceVal] = useState('');
  const [updatingPrice, setUpdatingPrice]   = useState(false);

  // Watchlist
  const [watchLoading, setWatchLoading] = useState(false);

  // Edit listing modal
  const [editOpen, setEditOpen]     = useState(false);
  const [editForm, setEditForm]     = useState(null);
  const [editErrors, setEditErrors] = useState({});
  const [editLoading, setEditLoading] = useState(false);

  // Reason modal (decline / withdraw)
  const [reasonModal, setReasonModal] = useState(null); // { title, action }
  const [reasonLoading, setReasonLoading] = useState(false);

  // Seller interactions panel
  const [interactions, setInteractions]         = useState([]);
  const [interactionsLoading, setInteractionsLoading] = useState(false);

  // Chat panel
  const [chatThreadId, setChatThreadId]     = useState(null);
  const [chatThreadLoading, setChatThreadLoading] = useState(false);

  // ── Load listing ──────────────────────────────────────────────
  const loadListing = useCallback(() => {
    return api.get(`/listings/${id}`)
      .then((data) => {
        if (!isListingDetailShape(data)) { navigate('/listings'); return; }
        setListing(normalizeListingPayload(data));
      })
      .catch(() => navigate('/listings'));
  }, [id, navigate]);

  useEffect(() => {
    setLoading(true);
    loadListing().finally(() => setLoading(false));
  }, [loadListing]);

  // Reset image index on listing change
  useEffect(() => { setImgIndex(0); }, [id]);
  useEffect(() => {
    if (!listing) return;
    const n = (listing.images || []).length;
    setImgIndex(i => n === 0 ? 0 : Math.min(Math.max(0, i), n - 1));
  }, [listing?.listing_id, listing?.images?.length]);

  // ── Load buyer's own offer & thread once listing is known ─────
  useEffect(() => {
    if (!listing || !isMember()) return;
    const isSeller = String(user?.member_id) === String(listing.seller_id);
    if (isSeller) return;

    api.get(`/listings/${id}/my-offer`)
      .then(data => setMyOffer(data || null))
      .catch(() => setMyOffer(null));

    api.get(`/listings/${id}/my-thread`)
      .then(data => { if (data?.thread_id) setChatThreadId(data.thread_id); })
      .catch(() => {});
  }, [listing?.listing_id, id, isMember, user?.member_id, listing?.seller_id]);

  // Pre-fill update-price field when myOffer loads
  useEffect(() => {
    if (myOffer?.offered_price != null) {
      setUpdatePriceVal(String(myOffer.offered_price));
    }
  }, [myOffer?.offer_id]);

  // ── Load interactions (seller) ────────────────────────────────
  useEffect(() => {
    if (!listing) return;
    const isSeller = String(user?.member_id) === String(listing.seller_id);
    if (!isSeller) return;
    setInteractionsLoading(true);
    api.get(`/listings/${id}/interactions`)
      .then(data => setInteractions(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setInteractionsLoading(false));
  }, [listing?.listing_id, id, user?.member_id, listing?.seller_id]);

  if (loading) return <LoadingSpinner />;
  if (!listing) return null;

  const isOwn = String(user?.member_id) === String(listing.seller_id);
  const images = listing.images || [];
  const hasActiveOffer = myOffer?.offer_status === 'Submitted';

  // ── Handlers ──────────────────────────────────────────────────

  const handleOffer = async (e) => {
    e.preventDefault();
    if (!offerForm.offered_price || parseFloat(offerForm.offered_price) <= 0) {
      setOfferError('Please enter a valid price');
      return;
    }
    setSubmitting(true);
    setOfferError('');
    try {
      const res = await api.post(`/listings/${id}/offers`, {
        offered_price: parseFloat(offerForm.offered_price),
      });
      toast.success('Offer submitted!');
      setOfferForm({ offered_price: '' });
      // Reload listing, offer, and thread
      await loadListing();
      const [offerData, threadData] = await Promise.all([
        api.get(`/listings/${id}/my-offer`).catch(() => null),
        api.get(`/listings/${id}/my-thread`).catch(() => null),
      ]);
      setMyOffer(offerData || null);
      if (threadData?.thread_id) setChatThreadId(threadData.thread_id);
      else if (res.offer_id) setChatThreadId(null); // will be available shortly
    } catch (err) {
      setOfferError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdatePrice = async () => {
    const price = parseFloat(updatePriceVal);
    if (!price || price <= 0) { toast.error('Enter a valid price'); return; }
    setUpdatingPrice(true);
    try {
      await api.put(`/offers/${myOffer.offer_id}/price`, { offered_price: price });
      toast.success('Offer price updated');
      const fresh = await api.get(`/listings/${id}/my-offer`);
      setMyOffer(fresh || null);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setUpdatingPrice(false);
    }
  };

  const handleBuyerAccept = async () => {
    if (!confirm(`Accept the asking price of ${fmtPrice(listing.asking_price)}?`)) return;
    try {
      await api.put(`/offers/${myOffer.offer_id}/buyer-accept`, {});
      toast.success('You accepted the asking price!');
      await loadListing();
      const fresh = await api.get(`/listings/${id}/my-offer`);
      setMyOffer(fresh || null);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleBuyerDecline = () => {
    setReasonModal({ title: 'Decline Offer', action: 'buyer-decline' });
  };

  const handleWithdrawOffer = () => {
    setReasonModal({ title: 'Withdraw Your Offer', action: 'withdraw' });
  };

  const handleReasonConfirm = async (reason) => {
    setReasonLoading(true);
    try {
      const action = reasonModal.action;
      if (action === 'buyer-decline') {
        await api.put(`/offers/${myOffer.offer_id}/buyer-decline`, { reason });
        toast.success('Offer declined');
      } else if (action === 'withdraw') {
        await api.put(`/offers/${myOffer.offer_id}/withdraw`, { reason });
        toast.success('Offer withdrawn');
      } else if (action === 'seller-decline') {
        await api.put(`/offers/${reasonModal.offerId}/decline`, { reason });
        toast.success('Offer declined');
        setInteractionsLoading(true);
        api.get(`/listings/${id}/interactions`)
          .then(data => setInteractions(Array.isArray(data) ? data : []))
          .finally(() => setInteractionsLoading(false));
      } else if (action === 'seller-withdraw') {
        await api.put(`/offers/${reasonModal.offerId}/withdraw`, { reason });
        toast.success('Offer withdrawn');
        setInteractionsLoading(true);
        api.get(`/listings/${id}/interactions`)
          .then(data => setInteractions(Array.isArray(data) ? data : []))
          .finally(() => setInteractionsLoading(false));
      }
      setReasonModal(null);
      if (action === 'buyer-decline' || action === 'withdraw') {
        await loadListing();
        const fresh = await api.get(`/listings/${id}/my-offer`);
        setMyOffer(fresh || null);
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setReasonLoading(false);
    }
  };

  const handleSellerAccept = async (offerId) => {
    if (!confirm('Accept this offer?')) return;
    try {
      await api.put(`/offers/${offerId}/accept`, {});
      toast.success('Offer accepted!');
      await loadListing();
      const data = await api.get(`/listings/${id}/interactions`);
      setInteractions(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleSellerDecline = (offerId) => {
    setReasonModal({ title: 'Decline this offer', action: 'seller-decline', offerId });
  };

  const handleDelete = async () => {
    if (!confirm('Withdraw this listing?')) return;
    try {
      await api.delete(`/listings/${id}`);
      toast.success('Listing withdrawn');
      navigate('/listings');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleWatchToggle = async () => {
    if (watchLoading) return;
    if (hasActiveOffer) {
      toast.error('Cannot remove from watchlist while an offer is active');
      return;
    }
    setWatchLoading(true);
    try {
      if (listing.my_watchlist_id != null) {
        await api.delete(`/watchlist/listing/${listing.listing_id}`);
        setListing(l => ({ ...l, my_watchlist_id: null, watcher_count: Math.max(0, l.watcher_count - 1) }));
        toast.success('Removed from watchlist');
      } else {
        const res = await api.post('/watchlist', { listing_id: listing.listing_id });
        setListing(l => ({ ...l, my_watchlist_id: res.watchlist_id, watcher_count: l.watcher_count + 1 }));
        toast.success('Added to watchlist');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setWatchLoading(false);
    }
  };

  const handleChatWithSeller = async () => {
    if (chatThreadId) { return; } // already have thread, ChatPanel will open via state
    setChatThreadLoading(true);
    try {
      const res = await api.post(`/listings/${id}/threads`, {});
      setChatThreadId(res.thread_id);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setChatThreadLoading(false);
    }
  };

  const openEditModal = () => {
    setEditForm(listingToFormState(listing));
    setEditErrors({});
    setEditOpen(true);
  };

  const handleEditChange = (e) => {
    const { name, value, type, checked } = e.target;
    setEditForm(f => ({ ...f, [name]: type === 'checkbox' ? checked : value }));
    setEditErrors(err => ({ ...err, [name]: undefined }));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const errs = validateListingForm(editForm);
    if (Object.keys(errs).length) { setEditErrors(errs); return; }
    setEditLoading(true);
    try {
      const raw = await api.put(`/listings/${id}`, buildListingPayload(editForm));
      let next = isListingDetailShape(raw) ? normalizeListingPayload(raw) : null;
      if (!next) {
        const fresh = await api.get(`/listings/${id}`);
        if (!isListingDetailShape(fresh)) { toast.error('Could not load listing after update'); return; }
        next = normalizeListingPayload(fresh);
      }
      setListing(next);
      setEditOpen(false);
      toast.success('Listing updated');
      // Refresh interactions after price change
      if (isOwn) {
        api.get(`/listings/${id}/interactions`)
          .then(data => setInteractions(Array.isArray(data) ? data : []))
          .catch(() => {});
      }
    } catch (err) {
      toast.error(err.message || 'Update failed');
    } finally {
      setEditLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/listings" className="hover:underline">Listings</Link>
        <span>/</span>
        <span className="text-gray-900">{listing.title}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: Images + Listing Info ── */}
        <div className="lg:col-span-2 space-y-4">
          {/* Image carousel */}
          <div className="card p-0 overflow-hidden">
            {images.length > 0 ? (
              <div>
                <div className="aspect-video bg-gray-100 flex items-center justify-center">
                  <img
                    src={uploadsUrl(images[imgIndex]?.image_url)}
                    alt={listing.title}
                    className="max-h-full max-w-full object-contain"
                    onError={e => { e.target.src = 'https://via.placeholder.com/400x300?text=No+Image'; }}
                  />
                </div>
                {images.length > 1 && (
                  <div className="flex gap-2 p-3 overflow-x-auto">
                    {images.map((img, i) => (
                      <button key={img.image_id} onClick={() => setImgIndex(i)}
                        className={`w-14 h-14 rounded-lg overflow-hidden border-2 flex-shrink-0 ${i === imgIndex ? 'border-blue-500' : 'border-gray-200'}`}>
                        <img src={uploadsUrl(img.image_url)} alt="" className="w-full h-full object-cover"
                          onError={e => { e.target.src = 'https://via.placeholder.com/56?text=?'; }} />
                      </button>
                    ))}
                  </div>
                )}
                {isOwn && (
                  <div className="p-3 border-t">
                    <ImageManager listing={listing} onUpdate={setListing} />
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div className="aspect-video bg-gray-100 flex items-center justify-center text-gray-400">
                  <p>No images</p>
                </div>
                {isOwn && (
                  <div className="p-3 border-t">
                    <ImageManager listing={listing} onUpdate={setListing} />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Listing info card */}
          <div className="card space-y-4">
            <div className="flex items-start justify-between gap-2">
              <h1 className="text-2xl font-bold text-gray-900">{listing.title}</h1>
              <span className={STATUS_COLORS[listing.status] || 'badge-gray'}>{listing.status}</span>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-3xl font-bold text-blue-700">
                {listing.is_donation ? 'FREE'
                  : `₹${(Number.isFinite(Number(listing.asking_price)) ? Number(listing.asking_price) : 0).toLocaleString()}`}
              </span>
              {listing.is_negotiable && !listing.is_donation && (
                <span className="badge-yellow">Negotiable</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-gray-500">Category:</span> <span className="font-medium">{listing.category_name}</span></div>
              <div><span className="text-gray-500">Condition:</span> <span className="font-medium">{listing.condition || 'N/A'}</span></div>
              {listing.expiry_date && (
                <div><span className="text-gray-500">Expires:</span> <span className="font-medium">{new Date(listing.expiry_date).toLocaleDateString()}</span></div>
              )}
              <div><span className="text-gray-500">Listed:</span> <span className="font-medium">{new Date(listing.created_date).toLocaleDateString()}</span></div>
              <div>
                <span className="text-gray-500">Interested:</span>{' '}
                <span className="font-medium">{listing.watcher_count} {listing.watcher_count === 1 ? 'person' : 'people'}</span>
              </div>
            </div>

            {listing.description && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-1">Description</h3>
                <p className="text-sm text-gray-600 whitespace-pre-wrap">{listing.description}</p>
              </div>
            )}

            {isOwn && (
              <div className="flex gap-3 pt-2 border-t">
                <button type="button" onClick={openEditModal} className="btn-secondary btn-sm text-sm">Edit</button>
                <button type="button" onClick={handleDelete} className="btn-danger btn-sm text-sm">Withdraw</button>
              </div>
            )}
          </div>
        </div>

        {/* ── Right Sidebar ── */}
        <div className="space-y-4">
          {/* Seller card */}
          <div className="card space-y-3">
            <h2 className="font-semibold text-gray-800">Seller</h2>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold">
                {listing.seller_name?.[0]?.toUpperCase()}
              </div>
              <div>
                <p className="font-medium text-sm">{listing.seller_name}</p>
                <Link to={`/portfolio/${listing.seller_id}`} className="text-xs text-blue-600 hover:underline">
                  View profile →
                </Link>
              </div>
            </div>
          </div>

          {/* ── Buyer: Offer + Chat controls ── */}
          {!isOwn && isMember() && listing.status === 'Listed' && (
            <div className="card space-y-4">

              {/* Chat with Seller button (always visible for buyer) */}
              <button
                onClick={() => {
                  if (chatThreadId) {
                    // Toggle panel off/on
                    setChatThreadId(t => t ? null : chatThreadId);
                  } else {
                    handleChatWithSeller();
                  }
                }}
                disabled={chatThreadLoading}
                className="btn-secondary w-full text-sm"
              >
                {chatThreadLoading ? 'Opening chat…' : chatThreadId ? '💬 Chat with Seller (open)' : '💬 Chat with Seller'}
              </button>

              {/* Chat panel inline (buyer side) */}
              {chatThreadId && (
                <ChatPanel
                  threadId={chatThreadId}
                  currentUserId={user?.member_id}
                  onClose={() => setChatThreadId(null)}
                />
              )}

              {/* Active offer management */}
              {myOffer != null && myOffer.offer_status === 'Submitted' && (
                <div className="space-y-3 pt-1 border-t">
                  <h2 className="font-semibold text-gray-800 text-sm">Your Active Offer</h2>

                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Asking price:</span>
                    <span className="font-medium">{fmtPrice(listing.asking_price)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Your offer:</span>
                    <span className="font-medium">{fmtPrice(myOffer.offered_price)}</span>
                  </div>

                  {/* Update offered price */}
                  <div className="flex gap-2 items-end">
                    <div className="flex-1">
                      <label className="label text-xs">Update Your Price (₹)</label>
                      <input
                        type="number" min="0.01" step="0.01"
                        className="input text-sm"
                        value={updatePriceVal}
                        onChange={e => setUpdatePriceVal(e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-secondary btn-sm text-sm whitespace-nowrap"
                      disabled={updatingPrice}
                      onClick={handleUpdatePrice}
                    >
                      {updatingPrice ? 'Updating…' : 'Update'}
                    </button>
                  </div>

                  {/* Accept asking price */}
                  <button
                    type="button"
                    className="btn-primary w-full text-sm"
                    onClick={handleBuyerAccept}
                  >
                    ✓ Accept Asking Price ({fmtPrice(listing.asking_price)})
                  </button>

                  {/* Buyer decline / withdraw */}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-danger flex-1 text-sm"
                      onClick={handleBuyerDecline}
                    >
                      Decline
                    </button>
                    <button
                      type="button"
                      className="btn-danger flex-1 text-sm"
                      onClick={handleWithdrawOffer}
                    >
                      Withdraw
                    </button>
                  </div>
                </div>
              )}

              {/* Show offer status if not Submitted */}
              {myOffer != null && myOffer.offer_status !== 'Submitted' && (
                <div className={`text-xs px-3 py-2 rounded-md font-medium ${OFFER_STATUS_COLORS[myOffer.offer_status] || ''}`}>
                  Your offer is <strong>{myOffer.offer_status}</strong>
                  {myOffer.agreed_price != null && ` at ${fmtPrice(myOffer.agreed_price)}`}
                  {myOffer.reason && ` — "${myOffer.reason}"`}
                </div>
              )}

              {/* Make new offer (only if no existing offer) */}
              {(myOffer === null || myOffer === undefined) && (
                <div className="space-y-3 pt-1 border-t">
                  <h2 className="font-semibold text-gray-800 text-sm">Make an Offer</h2>
                  {offerError && <p className="text-xs text-red-600">{offerError}</p>}
                  <form onSubmit={handleOffer} className="space-y-3">
                    <div>
                      <label className="label text-xs">Your Price (₹)</label>
                      <input
                        type="number" min="0.01" step="0.01"
                        className="input text-sm"
                        placeholder={`e.g. ${listing.asking_price}`}
                        value={offerForm.offered_price}
                        onChange={e => setOfferForm(f => ({ ...f, offered_price: e.target.value }))}
                      />
                    </div>
                    <button type="submit" className="btn-primary w-full text-sm" disabled={submitting}>
                      {submitting ? 'Submitting…' : 'Submit Offer'}
                    </button>
                  </form>
                </div>
              )}

              {/* Watchlist toggle */}
              <div className="pt-1 border-t">
                {hasActiveOffer ? (
                  <button
                    disabled
                    title="Cannot remove while an offer is active"
                    className="w-full text-sm btn-secondary opacity-50 cursor-not-allowed"
                  >
                    ★ Watching (offer active)
                  </button>
                ) : (
                  <button
                    onClick={handleWatchToggle}
                    disabled={watchLoading}
                    className={`w-full text-sm ${listing.my_watchlist_id != null ? 'btn-danger' : 'btn-secondary'}`}
                  >
                    {watchLoading
                      ? (listing.my_watchlist_id != null ? 'Removing…' : 'Adding…')
                      : listing.my_watchlist_id != null
                        ? '✕ Remove from Watchlist'
                        : '+ Add to Watchlist'}
                  </button>
                )}
              </div>
            </div>
          )}

          {listing.status !== 'Listed' && !isOwn && (
            <div className="card text-center text-gray-500 text-sm">
              <p>This listing is no longer accepting offers.</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Seller: Interactions Panel ── */}
      {isOwn && (
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Buyer Interactions
            {interactions.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({interactions.length} {interactions.length === 1 ? 'interaction' : 'interactions'})
              </span>
            )}
          </h2>

          {interactionsLoading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : interactions.length === 0 ? (
            <p className="text-sm text-gray-400">No interactions yet. Buyers will appear here after submitting offers or opening a chat.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b text-xs uppercase tracking-wide">
                    <th className="pb-2 pr-4">Buyer</th>
                    <th className="pb-2 pr-4">Asked Price</th>
                    <th className="pb-2 pr-4">Offered Price</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2 pr-4">Last Message</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {interactions.map((row) => {
                    const isAccepted  = row.offer_status === 'Accepted';
                    const isClosed    = row.offer_status && row.offer_status !== 'Submitted';
                    const rowBg = isAccepted
                      ? 'bg-green-50'
                      : isClosed
                        ? 'bg-red-50'
                        : '';

                    return (
                      <tr key={row.thread_id} className={rowBg}>
                        <td className="py-3 pr-4 font-medium text-gray-900">{row.buyer_name}</td>
                        <td className="py-3 pr-4 text-gray-700">{fmtPrice(row.asking_price)}</td>
                        <td className="py-3 pr-4 text-gray-700">
                          {row.offered_price != null ? fmtPrice(row.offered_price) : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="py-3 pr-4">
                          {row.offer_status ? (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${OFFER_STATUS_COLORS[row.offer_status] || ''}`}>
                              {row.offer_status}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">Chat only</span>
                          )}
                          {row.offer_reason && (
                            <p className="text-xs text-gray-500 mt-1 max-w-[12rem] truncate" title={row.offer_reason}>
                              "{row.offer_reason}"
                            </p>
                          )}
                        </td>
                        <td className="py-3 pr-4 text-gray-500 max-w-[10rem] truncate">
                          {row.last_message_preview || <span className="text-gray-300">—</span>}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            {/* Chat button */}
                            <SellerChatButton
                              threadId={row.thread_id}
                              currentUserId={user?.member_id}
                            />
                            {/* Offer actions — only when Submitted */}
                            {row.offer_status === 'Submitted' && (
                              <>
                                <button
                                  type="button"
                                  className="btn-primary btn-sm text-xs"
                                  onClick={() => handleSellerAccept(row.offer_id)}
                                >
                                  Accept
                                </button>
                                <button
                                  type="button"
                                  className="btn-danger btn-sm text-xs"
                                  onClick={() => handleSellerDecline(row.offer_id)}
                                >
                                  Decline
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Edit listing modal ── */}
      {editOpen && editForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 overflow-y-auto"
          role="dialog" aria-modal="true" aria-labelledby="edit-listing-title"
          onClick={() => !editLoading && setEditOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 my-8"
            onClick={e => e.stopPropagation()}
          >
            <h2 id="edit-listing-title" className="text-xl font-bold text-gray-900 mb-4">Edit listing</h2>
            <ListingForm
              idPrefix="edit-"
              form={editForm}
              errors={editErrors}
              onChange={handleEditChange}
              onSubmit={handleEditSubmit}
              loading={editLoading}
              submitLabel="Save changes"
              pendingLabel="Saving…"
              onCancel={() => !editLoading && setEditOpen(false)}
              cancelLabel="Cancel"
            />
          </div>
        </div>
      )}

      {/* ── Reason modal ── */}
      {reasonModal && (
        <ReasonModal
          title={reasonModal.title}
          onConfirm={handleReasonConfirm}
          onClose={() => !reasonLoading && setReasonModal(null)}
          loading={reasonLoading}
        />
      )}
    </div>
  );
}

// Small helper component for the per-row chat button in the seller table
function SellerChatButton({ threadId, currentUserId }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="btn-secondary btn-sm text-xs"
        onClick={() => setOpen(o => !o)}
      >
        {open ? 'Close Chat' : '💬 Chat'}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-end sm:justify-end p-4 pointer-events-none">
          <div className="pointer-events-auto w-full max-w-sm">
            <ChatPanel
              threadId={threadId}
              currentUserId={currentUserId}
              onClose={() => setOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}
