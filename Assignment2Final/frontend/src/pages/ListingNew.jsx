import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import toast from 'react-hot-toast';
import ListingForm, { validateListingForm, buildListingPayload } from '../components/ListingForm';

export default function ListingNew() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: '',
    description: '',
    asking_price: '',
    is_negotiable: true,
    condition: 'Good',
    category_id: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorLoading, setSelectorLoading] = useState(false);
  const [wishRequests, setWishRequests] = useState([]);
  const [selectedWishRequest, setSelectedWishRequest] = useState(null);
  const [selectorChoice, setSelectorChoice] = useState(null);
  const [filters, setFilters] = useState({
    q: '',
    min_budget: '',
    max_budget: '',
    category_id: '',
    condition: '',
    sort: 'newest',
  });

  const loadWishRequests = async (override = filters) => {
    setSelectorLoading(true);
    try {
      const params = {
        page: 1,
        page_size: 100,
        sort: override.sort || 'newest',
        include_own: 1,
      };
      if (override.q.trim()) params.q = override.q.trim();
      if (override.min_budget !== '') params.min_budget = override.min_budget;
      if (override.max_budget !== '') params.max_budget = override.max_budget;
      if (override.category_id) params.category_id = [Number(override.category_id)];
      if (override.condition) params.condition = [override.condition];

      const res = await api.get('/wishrequests', params);
      setWishRequests(res?.data || []);
    } catch {
      setWishRequests([]);
      toast.error('Failed to load wish requests');
    } finally {
      setSelectorLoading(false);
    }
  };

  useEffect(() => {
    if (!selectorOpen) return;
    loadWishRequests();
  }, [selectorOpen]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((f) => ({ ...f, [name]: type === 'checkbox' ? checked : value }));
    setErrors((err) => ({ ...err, [name]: undefined }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validateListingForm(form);
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    try {
      const payload = {
        ...buildListingPayload(form),
        wish_request_id: selectedWishRequest?.wish_request_id || null,
        wish_request_ids: selectedWishRequest?.wish_request_id ? [selectedWishRequest.wish_request_id] : [],
      };
      const res = await api.post('/listings', payload);
      toast.success('Listing created!');
      navigate(`/listings/${res.listing_id}`);
    } catch (err) {
      toast.error(err.message || 'Failed to create listing');
    } finally {
      setLoading(false);
    }
  };

  const openSelector = () => {
    setSelectorChoice(selectedWishRequest?.wish_request_id || null);
    setSelectorOpen(true);
  };

  const applyWishRequestChoice = () => {
    const chosen = wishRequests.find((wr) => wr.wish_request_id === selectorChoice) || null;
    setSelectedWishRequest(chosen);
    setSelectorOpen(false);
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((f) => ({ ...f, [name]: value }));
  };

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    loadWishRequests(filters);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Post a New Listing</h1>

      <div className="card">
        <div className="mb-5 pb-5 border-b space-y-3">
          <h2 className="text-sm font-semibold text-gray-800">Wish Request Link (Optional)</h2>
          <p className="text-xs text-gray-500">Choose a wish request only if you want this listing to fulfill it.</p>

          {selectedWishRequest ? (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-gray-800">{selectedWishRequest.item_description}</p>
                <p className="text-xs text-gray-600 mt-1">Requested by {selectedWishRequest.requester_name}</p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={openSelector} className="btn-secondary btn-sm text-xs">Change</button>
                <button type="button" onClick={() => setSelectedWishRequest(null)} className="btn-secondary btn-sm text-xs">Remove</button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={openSelector} className="btn-secondary btn-sm text-sm">
              Select Wish Request
            </button>
          )}
        </div>

        <ListingForm
          form={form}
          errors={errors}
          onChange={handleChange}
          onSubmit={handleSubmit}
          loading={loading}
          submitLabel="Post Listing"
          pendingLabel="Creating…"
          onCancel={() => navigate(-1)}
          cancelLabel="Cancel"
        />
      </div>

      {selectorOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl p-5 w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <h2 className="font-semibold text-gray-800 mb-3">Select Active Wish Request</h2>

            <form onSubmit={handleFilterSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
              <input
                name="q"
                value={filters.q}
                onChange={handleFilterChange}
                className="input"
                placeholder="Search description"
              />
              <input
                type="number"
                name="min_budget"
                value={filters.min_budget}
                onChange={handleFilterChange}
                className="input"
                placeholder="Min budget"
              />
              <input
                type="number"
                name="max_budget"
                value={filters.max_budget}
                onChange={handleFilterChange}
                className="input"
                placeholder="Max budget"
              />

              <select name="category_id" value={filters.category_id} onChange={handleFilterChange} className="input">
                <option value="">All categories</option>
                {[
                  { id: 1, name: 'Books & Textbooks' },
                  { id: 2, name: 'Electronics' },
                  { id: 3, name: 'Furniture' },
                  { id: 4, name: 'Sports & Fitness' },
                  { id: 5, name: 'Clothing' },
                  { id: 6, name: 'Engineering Books' },
                  { id: 7, name: 'Science Books' },
                  { id: 8, name: 'Computing' },
                  { id: 9, name: 'Mobile Phones' },
                  { id: 10, name: 'Calculators' },
                  { id: 11, name: 'Study Furniture' },
                  { id: 12, name: 'Room Essentials' },
                  { id: 13, name: 'Gym Equipment' },
                  { id: 14, name: 'Racket Sports' },
                  { id: 15, name: 'Miscellaneous' },
                ].map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>

              <select name="condition" value={filters.condition} onChange={handleFilterChange} className="input">
                <option value="">Any condition</option>
                {['New', 'Like New', 'Good', 'Fair', 'Poor'].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>

              <div className="flex gap-2">
                <select name="sort" value={filters.sort} onChange={handleFilterChange} className="input">
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="budget_asc">Budget Low-High</option>
                  <option value="budget_desc">Budget High-Low</option>
                </select>
                <button type="submit" className="btn-secondary btn-sm px-4">Filter</button>
              </div>
            </form>

            <div className="flex-1 overflow-auto space-y-2 border rounded-lg p-2 bg-gray-50">
              {selectorLoading ? (
                <p className="text-sm text-gray-500 p-2">Loading...</p>
              ) : wishRequests.length === 0 ? (
                <p className="text-sm text-gray-500 p-2">No active wish requests found.</p>
              ) : (
                wishRequests.map((wr) => (
                  <label key={wr.wish_request_id} className="flex items-start gap-2 p-3 rounded-lg border bg-white cursor-pointer">
                    <input
                      type="radio"
                      name="wish_request_choice"
                      checked={selectorChoice === wr.wish_request_id}
                      onChange={() => setSelectorChoice(wr.wish_request_id)}
                      className="mt-1"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800">{wr.item_description}</p>
                      <p className="text-xs text-gray-500 mt-1">{wr.requester_name} • {wr.category_name}</p>
                    </div>
                  </label>
                ))
              )}
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button type="button" onClick={() => setSelectorOpen(false)} className="btn-secondary text-sm">Cancel</button>
              <button type="button" onClick={applyWishRequestChoice} className="btn-primary text-sm">OK</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
