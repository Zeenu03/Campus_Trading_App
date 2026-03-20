export const LISTING_CATEGORIES = [
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
  { id: 15, name: 'Donations' },
];

const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];

export function validateListingForm(form) {
  const e = {};
  if (!form.title?.trim()) e.title = 'Title is required';
  if (!form.category_id) e.category_id = 'Category is required';
  if (!form.is_donation) {
    if (form.asking_price === '') e.asking_price = 'Price is required';
    else if (parseFloat(form.asking_price) < 0) e.asking_price = 'Price must be ≥ 0';
  }
  return e;
}

export function buildListingPayload(form) {
  return {
    title: form.title,
    description: form.description || null,
    asking_price: form.is_donation ? 0 : parseFloat(form.asking_price),
    is_negotiable: form.is_negotiable,
    condition: form.condition || null,
    category_id: parseInt(form.category_id, 10),
    expiry_date: form.expiry_date || null,
    is_donation: form.is_donation,
  };
}

/** Shape listing API response into form state */
export function listingToFormState(listing) {
  let expiryDate = '';
  if (listing.expiry_date) {
    const s = String(listing.expiry_date);
    expiryDate = s.length >= 10 ? s.slice(0, 10) : s;
  }
  return {
    title: listing.title || '',
    description: listing.description ?? '',
    asking_price: listing.is_donation ? '' : String(listing.asking_price ?? ''),
    is_negotiable: Boolean(listing.is_negotiable),
    condition: listing.condition || 'Good',
    category_id: listing.category_id != null ? String(listing.category_id) : '',
    expiry_date: expiryDate,
    is_donation: Boolean(listing.is_donation),
  };
}

/**
 * Shared fields for create / edit listing (same layout as “Post a New Listing”).
 * @param {string} [props.idPrefix] — prefix for input ids (e.g. "edit-") when multiple forms could exist
 */
export default function ListingForm({
  form,
  errors,
  onChange,
  onSubmit,
  loading,
  submitLabel,
  pendingLabel = 'Saving…',
  onCancel,
  cancelLabel = 'Cancel',
  idPrefix = '',
}) {
  const nid = (s) => (idPrefix ? `${idPrefix}${s}` : s);

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div>
        <label className="label">Title <span className="text-red-500">*</span></label>
        <input
          name="title"
          value={form.title}
          onChange={onChange}
          className={`input ${errors.title ? 'border-red-400' : ''}`}
          placeholder="e.g. Engineering Mechanics Textbook by Meriam"
        />
        {errors.title && <p className="text-xs text-red-600 mt-1">{errors.title}</p>}
      </div>

      <div>
        <label className="label">Description</label>
        <textarea
          name="description"
          value={form.description}
          onChange={onChange}
          className="input resize-none"
          rows={3}
          placeholder="Describe the item, any defects, what's included…"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="label">Category <span className="text-red-500">*</span></label>
          <select
            name="category_id"
            value={form.category_id}
            onChange={onChange}
            className={`input ${errors.category_id ? 'border-red-400' : ''}`}
          >
            <option value="">Select category</option>
            {LISTING_CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {errors.category_id && <p className="text-xs text-red-600 mt-1">{errors.category_id}</p>}
        </div>
        <div>
          <label className="label">Condition</label>
          <select name="condition" value={form.condition} onChange={onChange} className="input">
            {CONDITIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <label className="label mb-0">Asking Price (₹) <span className="text-red-500">*</span></label>
          <label className="flex items-center gap-1 text-sm cursor-pointer">
            <input
              type="checkbox"
              name="is_donation"
              checked={form.is_donation}
              onChange={onChange}
              className="w-4 h-4"
            />
            <span className="text-gray-600">Free / Donation</span>
          </label>
        </div>
        <input
          type="number"
          name="asking_price"
          value={form.is_donation ? '0' : form.asking_price}
          onChange={onChange}
          disabled={form.is_donation}
          className={`input ${errors.asking_price ? 'border-red-400' : ''}`}
          placeholder="0.00"
          min="0"
          step="0.01"
        />
        {errors.asking_price && <p className="text-xs text-red-600 mt-1">{errors.asking_price}</p>}
      </div>

      <div>
        <label className="label">Listing Expiry Date</label>
        <input
          type="date"
          name="expiry_date"
          value={form.expiry_date}
          onChange={onChange}
          className="input max-w-xs"
          min={new Date().toISOString().split('T')[0]}
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          name="is_negotiable"
          id={nid('negotiable')}
          checked={form.is_negotiable}
          onChange={onChange}
          className="w-4 h-4"
        />
        <label htmlFor={nid('negotiable')} className="text-sm text-gray-700 cursor-pointer">
          Price is negotiable
        </label>
      </div>

      <div className="flex gap-3 pt-2">
        <button type="submit" className="btn-primary flex-1" disabled={loading}>
          {loading ? pendingLabel : submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="btn-secondary flex-1">
            {cancelLabel}
          </button>
        )}
      </div>
    </form>
  );
}
