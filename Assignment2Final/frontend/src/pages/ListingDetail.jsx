import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import ListingForm, { validateListingForm, buildListingPayload, listingToFormState } from '../components/ListingForm';
import { normalizeListingPayload, isListingDetailShape } from '../utils/listingApi';
import toast from 'react-hot-toast';

export default function ListingDetail() {
  const { id } = useParams();
  const { user, isMember } = useAuth();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [imgIndex, setImgIndex] = useState(0);
  const [offerForm, setOfferForm] = useState({ offered_price: '', offer_message: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState(null);
  const [editErrors, setEditErrors] = useState({});
  const [editLoading, setEditLoading] = useState(false);

  useEffect(() => {
    api.get(`/listings/${id}`)
      .then((data) => {
        if (!isListingDetailShape(data)) {
          navigate('/listings');
          return;
        }
        setListing(normalizeListingPayload(data));
      })
      .catch(() => navigate('/listings'))
      .finally(() => setLoading(false));
  }, [id, navigate]);

  if (loading) return <LoadingSpinner />;
  if (!listing)  return null;

  const isOwn = String(user?.member_id) === String(listing.seller_id);
  const images   = listing.images || [];
  const statusColors = {
    Listed: 'badge-green', Pending: 'badge-yellow', Reserved: 'badge-blue',
    Sold: 'badge-gray', Withdrawn: 'badge-gray',
  };

  const handleOffer = async (e) => {
    e.preventDefault();
    if (!offerForm.offered_price || parseFloat(offerForm.offered_price) <= 0) {
      setError('Please enter a valid price');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await api.post(`/listings/${id}/offers`, {
        offered_price: parseFloat(offerForm.offered_price),
        offer_message: offerForm.offer_message || null,
      });
      toast.success('Offer submitted!');
      setOfferForm({ offered_price: '', offer_message: '' });
      const updated = await api.get(`/listings/${id}`);
      if (isListingDetailShape(updated)) setListing(normalizeListingPayload(updated));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
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

  const handleWatch = async () => {
    try {
      await api.post('/watchlist', { listing_id: listing.listing_id });
      toast.success('Added to watchlist');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const openEditModal = () => {
    setEditForm(listingToFormState(listing));
    setEditErrors({});
    setEditOpen(true);
  };

  const handleEditChange = (e) => {
    const { name, value, type, checked } = e.target;
    setEditForm((f) => ({ ...f, [name]: type === 'checkbox' ? checked : value }));
    setEditErrors((err) => ({ ...err, [name]: undefined }));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const errs = validateListingForm(editForm);
    if (Object.keys(errs).length) {
      setEditErrors(errs);
      return;
    }
    setEditLoading(true);
    try {
      const raw = await api.put(`/listings/${id}`, buildListingPayload(editForm));
      let next = isListingDetailShape(raw) ? normalizeListingPayload(raw) : null;
      if (!next) {
        const fresh = await api.get(`/listings/${id}`);
        if (!isListingDetailShape(fresh)) {
          toast.error('Could not load listing after update');
          return;
        }
        next = normalizeListingPayload(fresh);
      }
      setListing(next);
      setEditOpen(false);
      toast.success('Listing updated');
    } catch (err) {
      toast.error(err.message || 'Update failed');
    } finally {
      setEditLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/listings" className="hover:underline">Listings</Link>
        <span>/</span>
        <span className="text-gray-900">{listing.title}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Images + Details */}
        <div className="lg:col-span-2 space-y-4">
          {/* Image carousel */}
          <div className="card p-0 overflow-hidden">
            {images.length > 0 ? (
              <div>
                <div className="aspect-video bg-gray-100 flex items-center justify-center">
                  <img
                    src={images[imgIndex]?.image_url}
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
                        <img src={img.image_url} alt="" className="w-full h-full object-cover"
                          onError={e => { e.target.src = 'https://via.placeholder.com/56?text=?'; }} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="aspect-video bg-gray-100 flex items-center justify-center text-gray-400">
                <p>No images</p>
              </div>
            )}
          </div>

          {/* Listing info */}
          <div className="card space-y-4">
            <div className="flex items-start justify-between gap-2">
              <h1 className="text-2xl font-bold text-gray-900">{listing.title}</h1>
              <span className={statusColors[listing.status] || 'badge-gray'}>{listing.status}</span>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-3xl font-bold text-blue-700">
                {listing.is_donation
                  ? 'FREE'
                  : `₹${(Number.isFinite(Number(listing.asking_price)) ? Number(listing.asking_price) : 0).toLocaleString()}`}
              </span>
              {listing.is_negotiable && !listing.is_donation && (
                <span className="badge-yellow">Negotiable</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-gray-500">Category:</span> <span className="font-medium">{listing.category_name}</span></div>
              <div><span className="text-gray-500">Condition:</span> <span className="font-medium">{listing.condition || 'N/A'}</span></div>
              {listing.expiry_date && <div><span className="text-gray-500">Expires:</span> <span className="font-medium">{new Date(listing.expiry_date).toLocaleDateString()}</span></div>}
              <div><span className="text-gray-500">Listed:</span> <span className="font-medium">{new Date(listing.created_date).toLocaleDateString()}</span></div>
            </div>

            {listing.description && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-1">Description</h3>
                <p className="text-sm text-gray-600 whitespace-pre-wrap">{listing.description}</p>
              </div>
            )}

            {isOwn && (
              <div className="flex gap-3 pt-2 border-t">
                <button type="button" onClick={openEditModal} className="btn-secondary btn-sm text-sm">
                  Edit
                </button>
                <button type="button" onClick={handleDelete} className="btn-danger btn-sm text-sm">Withdraw</button>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
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
                <Link to={`/portfolio/${listing.seller_id}`}
                  className="text-xs text-blue-600 hover:underline">View profile →</Link>
              </div>
            </div>
          </div>

          {/* Actions */}
          {!isOwn && isMember() && listing.status === 'Listed' && (
            <div className="card space-y-3">
              <h2 className="font-semibold text-gray-800">Make an Offer</h2>
              {error && <p className="text-xs text-red-600">{error}</p>}
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
                <div>
                  <label className="label text-xs">Message (optional)</label>
                  <textarea
                    className="input text-sm resize-none" rows={2}
                    placeholder="Any message for the seller…"
                    value={offerForm.offer_message}
                    onChange={e => setOfferForm(f => ({ ...f, offer_message: e.target.value }))}
                  />
                </div>
                <button type="submit" className="btn-primary w-full text-sm" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit Offer'}
                </button>
              </form>
              <button onClick={handleWatch} className="btn-secondary w-full text-sm">
                👁 Watch Listing
              </button>
            </div>
          )}

          {listing.status !== 'Listed' && !isOwn && (
            <div className="card text-center text-gray-500 text-sm">
              <p>This listing is no longer accepting offers.</p>
            </div>
          )}
        </div>
      </div>

      {editOpen && editForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-listing-title"
          onClick={() => !editLoading && setEditOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 my-8"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="edit-listing-title" className="text-xl font-bold text-gray-900 mb-4">
              Edit listing
            </h2>
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
    </div>
  );
}
