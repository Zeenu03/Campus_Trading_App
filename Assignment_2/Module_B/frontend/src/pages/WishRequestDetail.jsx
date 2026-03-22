import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import ListingImage from '../components/ListingImage';
import WishRequestImageManager from '../components/WishRequestImageManager';
import WishRequestForm, {
  validateWishRequestForm,
  buildWishRequestPayload,
  wishRequestToFormState,
} from '../components/WishRequestForm';

const STATUS_COLORS = {
  Active: 'badge-green',
  Fulfilled: 'badge-gray',
  Expired: 'badge-gray',
  Cancelled: 'badge-gray',
};

function fmtBudget(min, max) {
  if (min == null && max == null) return 'Budget not specified';
  if (min != null && max != null) return `₹${Number(min).toLocaleString()} - ₹${Number(max).toLocaleString()}`;
  if (min != null) return `From ₹${Number(min).toLocaleString()}`;
  return `Up to ₹${Number(max).toLocaleString()}`;
}

export default function WishRequestDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [wishRequest, setWishRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [imgIndex, setImgIndex] = useState(0);

  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState(null);
  const [editErrors, setEditErrors] = useState({});
  const [editLoading, setEditLoading] = useState(false);

  const [statusLoading, setStatusLoading] = useState(false);

  const loadWishRequest = useCallback(() => {
    return api.get(`/wishrequests/${id}`)
      .then(setWishRequest)
      .catch(() => navigate('/wishrequests'));
  }, [id, navigate]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      loadWishRequest(),
      api.get('/categories').then(setCategories).catch(() => setCategories([])),
    ]).finally(() => setLoading(false));
  }, [loadWishRequest]);

  useEffect(() => {
    setImgIndex(0);
  }, [id]);

  useEffect(() => {
    if (!wishRequest) return;
    const n = (wishRequest.images || []).length;
    setImgIndex((i) => (n === 0 ? 0 : Math.min(Math.max(0, i), n - 1)));
  }, [wishRequest?.wish_request_id, wishRequest?.images?.length]);

  useEffect(() => {
    if (!wishRequest) return;
    if (searchParams.get('edit') === '1') {
      setEditForm(wishRequestToFormState(wishRequest));
      setEditErrors({});
      setEditOpen(true);
      searchParams.delete('edit');
      setSearchParams(searchParams, { replace: true });
    }
  }, [wishRequest, searchParams, setSearchParams]);

  if (loading) return <LoadingSpinner />;
  if (!wishRequest) return null;

  const isOwn = String(user?.member_id) === String(wishRequest.requester_id);
  const images = wishRequest.images || [];
  const canEdit = isOwn && wishRequest.status === 'Active';

  const openEdit = () => {
    setEditForm(wishRequestToFormState(wishRequest));
    setEditErrors({});
    setEditOpen(true);
  };

  const handleEditChange = (e) => {
    const { name, value } = e.target;
    setEditForm((f) => ({ ...f, [name]: value }));
    setEditErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const errs = validateWishRequestForm(editForm);
    if (Object.keys(errs).length) {
      setEditErrors(errs);
      return;
    }

    setEditLoading(true);
    try {
      await api.put(`/wishrequests/${id}`, buildWishRequestPayload(editForm));
      await loadWishRequest();
      setEditOpen(false);
      toast.success('Wish request updated');
    } catch (err) {
      toast.error(err.message || 'Update failed');
    } finally {
      setEditLoading(false);
    }
  };

  const handleStatusChange = async (newStatus) => {
    setStatusLoading(true);
    try {
      await api.put(`/wishrequests/${id}`, { status: newStatus });
      await loadWishRequest();
      toast.success(`Status changed to ${newStatus}`);
    } catch (err) {
      toast.error(err.message || 'Status update failed');
    } finally {
      setStatusLoading(false);
    }
  };

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link to="/wishrequests" className="hover:underline">Wish Requests</Link>
          <span>/</span>
          <span className="text-gray-900">Details</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="card p-0 overflow-hidden">
              {images.length > 0 ? (
                <div>
                  <div className="aspect-video bg-gray-100 flex items-center justify-center relative">
                    <ListingImage
                      path={images[imgIndex]?.image_url}
                      alt={wishRequest.item_description}
                      variant="hero"
                      className="max-h-full max-w-full object-contain"
                    />
                  </div>
                  {images.length > 1 && (
                    <div className="flex gap-2 p-3 overflow-x-auto">
                      {images.map((img, i) => (
                        <button
                          key={img.image_id}
                          onClick={() => setImgIndex(i)}
                          className={`w-14 h-14 rounded-lg overflow-hidden border-2 flex-shrink-0 ${i === imgIndex ? 'border-blue-500' : 'border-gray-200'}`}
                        >
                          <ListingImage path={img.image_url} alt="" variant="thumb" className="w-full h-full object-cover" />
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

              {isOwn && wishRequest.status === 'Active' && (
                <div className="p-3 border-t">
                  <WishRequestImageManager wishRequest={wishRequest} onUpdate={setWishRequest} />
                </div>
              )}
            </div>

            <div className="card space-y-4">
              <div className="flex items-start justify-between gap-2">
                <h1 className="text-2xl font-bold text-gray-900">{wishRequest.item_description}</h1>
                <span className={STATUS_COLORS[wishRequest.status] || 'badge-gray'}>{wishRequest.status}</span>
              </div>

              <div className="text-2xl font-bold text-blue-700">
                {fmtBudget(wishRequest.min_budget, wishRequest.max_budget)}
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-gray-500">Category:</span> <span className="font-medium">{wishRequest.category_name}</span></div>
                <div><span className="text-gray-500">Condition:</span> <span className="font-medium">{wishRequest.preferred_condition || 'Any'}</span></div>
                <div><span className="text-gray-500">Posted:</span> <span className="font-medium">{new Date(wishRequest.created_date).toLocaleDateString()}</span></div>
                <div><span className="text-gray-500">Needed by:</span> <span className="font-medium">{wishRequest.needed_by_date ? new Date(wishRequest.needed_by_date).toLocaleDateString() : 'Not specified'}</span></div>
              </div>

              {wishRequest.additional_details && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-1">Additional Details</h3>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap">{wishRequest.additional_details}</p>
                </div>
              )}

              {wishRequest.linked_listing && (
                <div className="pt-3 border-t">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Linked Listing</h3>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-900">{wishRequest.linked_listing.title}</p>
                      <span className="badge-gray">{wishRequest.linked_listing.status}</span>
                    </div>
                    <p className="text-xs text-gray-500">by {wishRequest.linked_listing.seller_name}</p>
                    <p className="text-xs text-gray-600">Price: ₹{Number(wishRequest.linked_listing.asking_price || 0).toLocaleString()}</p>
                    <Link to={`/listings/${wishRequest.linked_listing.listing_id}`} className="text-xs text-blue-600 hover:underline">
                      View listing →
                    </Link>
                  </div>
                </div>
              )}

              {isOwn && (
                <div className="space-y-3 pt-2 border-t">
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={openEdit}
                      disabled={!canEdit || editLoading || statusLoading}
                      className={`btn-secondary btn-sm text-sm flex-1 ${!canEdit ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      Edit
                    </button>
                  </div>

                  {!canEdit && (
                    <p className="text-xs text-gray-600 text-center">Only active wish requests can be edited</p>
                  )}

                  {wishRequest.status === 'Active' && (
                    <div className="flex gap-2 flex-wrap">
                      <button
                        type="button"
                        onClick={() => handleStatusChange('Cancelled')}
                        disabled={statusLoading || editLoading}
                        className="btn-secondary btn-sm text-xs w-full"
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {wishRequest.status === 'Expired' && (
                    <div className="flex gap-2 flex-wrap">
                      <button
                        type="button"
                        onClick={() => handleStatusChange('Active')}
                        disabled={statusLoading || editLoading}
                        className="btn-primary btn-sm text-sm flex-1"
                      >
                        Reopen Request
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStatusChange('Cancelled')}
                        disabled={statusLoading || editLoading}
                        className="btn-secondary btn-sm text-sm flex-1"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="card space-y-3">
              <h2 className="font-semibold text-gray-800">Requester</h2>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold">
                  {wishRequest.requester_name?.[0]?.toUpperCase()}
                </div>
                <div>
                  <p className="font-medium text-sm">{wishRequest.requester_name}</p>
                  <Link to={`/portfolio/${wishRequest.requester_id}`} className="text-xs text-blue-600 hover:underline">
                    View profile →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {editOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl">
            <h2 className="font-semibold text-gray-800 mb-4">Edit Wish Request</h2>
            <WishRequestForm
              form={editForm}
              errors={editErrors}
              categories={categories}
              onChange={handleEditChange}
              onSubmit={handleEditSubmit}
              loading={editLoading}
              submitLabel="Save Changes"
              pendingLabel="Saving…"
              onCancel={() => setEditOpen(false)}
              cancelLabel="Cancel"
            />
          </div>
        </div>
      )}
    </>
  );
}
