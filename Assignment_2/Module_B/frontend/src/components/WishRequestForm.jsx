const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];
const STATUSES = ['Active', 'Fulfilled', 'Expired', 'Cancelled'];

export function validateWishRequestForm(form) {
  const errors = {};
  if (!form.item_description?.trim()) errors.item_description = 'Item description is required';
  if (!form.category_id) errors.category_id = 'Category is required';

  const min = form.min_budget === '' ? null : parseFloat(form.min_budget);
  const max = form.max_budget === '' ? null : parseFloat(form.max_budget);

  if (min != null && Number.isNaN(min)) errors.min_budget = 'Invalid minimum budget';
  if (max != null && Number.isNaN(max)) errors.max_budget = 'Invalid maximum budget';
  if (min != null && max != null && max < min) errors.max_budget = 'Max budget must be ≥ min budget';

  return errors;
}

export function buildWishRequestPayload(form) {
  return {
    category_id: parseInt(form.category_id, 10),
    item_description: form.item_description?.trim() || '',
    min_budget: form.min_budget === '' ? null : parseFloat(form.min_budget),
    max_budget: form.max_budget === '' ? null : parseFloat(form.max_budget),
    preferred_condition: form.preferred_condition || null,
    needed_by_date: form.needed_by_date || null,
    additional_details: form.additional_details?.trim() || null,
  };
}

export function wishRequestToFormState(wishRequest) {
  const formatDate = (value) => {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
    return d.toISOString().slice(0, 10);
  };

  return {
    category_id: wishRequest.category_id != null ? String(wishRequest.category_id) : '',
    item_description: wishRequest.item_description || '',
    min_budget: wishRequest.min_budget != null ? String(wishRequest.min_budget) : '',
    max_budget: wishRequest.max_budget != null ? String(wishRequest.max_budget) : '',
    preferred_condition: wishRequest.preferred_condition || '',
    needed_by_date: formatDate(wishRequest.needed_by_date),
    additional_details: wishRequest.additional_details || '',
    status: wishRequest.status || 'Active',
  };
}

export default function WishRequestForm({
  form,
  errors,
  categories,
  onChange,
  onSubmit,
  loading,
  submitLabel,
  pendingLabel = 'Saving…',
  onCancel,
  cancelLabel = 'Cancel',
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div>
        <label className="label">Item Description <span className="text-red-500">*</span></label>
        <input
          name="item_description"
          value={form.item_description}
          onChange={onChange}
          className={`input ${errors.item_description ? 'border-red-400' : ''}`}
          placeholder="e.g. Looking for a used calculator or mechanics textbook"
        />
        {errors.item_description && <p className="text-xs text-red-600 mt-1">{errors.item_description}</p>}
      </div>

      <div>
        <label className="label">Additional Details</label>
        <textarea
          name="additional_details"
          value={form.additional_details}
          onChange={onChange}
          className="input resize-none"
          rows={3}
          placeholder="Any preferences, urgency, expected accessories, etc."
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
            {categories.map((c) => (
              <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
            ))}
          </select>
          {errors.category_id && <p className="text-xs text-red-600 mt-1">{errors.category_id}</p>}
        </div>
        <div>
          <label className="label">Preferred Condition</label>
          <select name="preferred_condition" value={form.preferred_condition} onChange={onChange} className="input">
            <option value="">Any</option>
            {CONDITIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="label">Min Budget (₹)</label>
          <input
            type="number"
            name="min_budget"
            value={form.min_budget}
            onChange={onChange}
            className={`input ${errors.min_budget ? 'border-red-400' : ''}`}
            placeholder="0.00"
            min="0"
            step="0.01"
          />
          {errors.min_budget && <p className="text-xs text-red-600 mt-1">{errors.min_budget}</p>}
        </div>
        <div>
          <label className="label">Max Budget (₹)</label>
          <input
            type="number"
            name="max_budget"
            value={form.max_budget}
            onChange={onChange}
            className={`input ${errors.max_budget ? 'border-red-400' : ''}`}
            placeholder="0.00"
            min="0"
            step="0.01"
          />
          {errors.max_budget && <p className="text-xs text-red-600 mt-1">{errors.max_budget}</p>}
        </div>
      </div>

      <div>
        <label className="label">Needed By Date</label>
        <input
          type="date"
          name="needed_by_date"
          value={form.needed_by_date}
          onChange={onChange}
          className="input"
        />
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
