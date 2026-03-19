import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import toast from 'react-hot-toast';

const CONDITIONS  = ['New', 'Like New', 'Good', 'Fair', 'Poor'];

export default function ListingNew() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({
    title: '', description: '', asking_price: '', is_negotiable: true,
    condition: 'Good', category_id: '', course_code: '',
    expiry_date: '', is_donation: false, preferred_meeting_location: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch categories from a few listing queries to extract unique categories
    api.get('/listings', { status: 'Listed', page_size: 1 }).catch(() => {});
    // Hardcoded category list matching init.sql seeds
    setCategories([
      { id: 1,  name: 'Books & Textbooks' },
      { id: 2,  name: 'Electronics' },
      { id: 3,  name: 'Furniture' },
      { id: 4,  name: 'Sports & Fitness' },
      { id: 5,  name: 'Clothing' },
      { id: 6,  name: 'Engineering Books' },
      { id: 7,  name: 'Science Books' },
      { id: 8,  name: 'Computing' },
      { id: 9,  name: 'Mobile Phones' },
      { id: 10, name: 'Calculators' },
      { id: 11, name: 'Study Furniture' },
      { id: 12, name: 'Room Essentials' },
      { id: 13, name: 'Gym Equipment' },
      { id: 14, name: 'Racket Sports' },
      { id: 15, name: 'Donations' },
    ]);
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(f => ({ ...f, [name]: type === 'checkbox' ? checked : value }));
    setErrors(err => ({ ...err, [name]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.title.trim())     e.title      = 'Title is required';
    if (!form.category_id)      e.category_id = 'Category is required';
    if (!form.is_donation) {
      if (form.asking_price === '') e.asking_price = 'Price is required';
      else if (parseFloat(form.asking_price) < 0) e.asking_price = 'Price must be ≥ 0';
    }
    return e;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setLoading(true);
    try {
      const payload = {
        title: form.title,
        description: form.description || null,
        asking_price: form.is_donation ? 0 : parseFloat(form.asking_price),
        is_negotiable: form.is_negotiable,
        condition: form.condition || null,
        category_id: parseInt(form.category_id),
        course_code: form.course_code || null,
        expiry_date: form.expiry_date || null,
        is_donation: form.is_donation,
        preferred_meeting_location: form.preferred_meeting_location || null,
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

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Post a New Listing</h1>

      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="label">Title <span className="text-red-500">*</span></label>
            <input name="title" value={form.title} onChange={handleChange}
              className={`input ${errors.title ? 'border-red-400' : ''}`}
              placeholder="e.g. Engineering Mechanics Textbook by Meriam" />
            {errors.title && <p className="text-xs text-red-600 mt-1">{errors.title}</p>}
          </div>

          <div>
            <label className="label">Description</label>
            <textarea name="description" value={form.description} onChange={handleChange}
              className="input resize-none" rows={3}
              placeholder="Describe the item, any defects, what's included…" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Category <span className="text-red-500">*</span></label>
              <select name="category_id" value={form.category_id} onChange={handleChange}
                className={`input ${errors.category_id ? 'border-red-400' : ''}`}>
                <option value="">Select category</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {errors.category_id && <p className="text-xs text-red-600 mt-1">{errors.category_id}</p>}
            </div>
            <div>
              <label className="label">Condition</label>
              <select name="condition" value={form.condition} onChange={handleChange} className="input">
                {CONDITIONS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="label mb-0">Asking Price (₹) <span className="text-red-500">*</span></label>
                <label className="flex items-center gap-1 text-sm cursor-pointer">
                  <input type="checkbox" name="is_donation" checked={form.is_donation} onChange={handleChange}
                    className="w-4 h-4" />
                  <span className="text-gray-600">Free / Donation</span>
                </label>
              </div>
              <input type="number" name="asking_price" value={form.is_donation ? '0' : form.asking_price}
                onChange={handleChange} disabled={form.is_donation}
                className={`input ${errors.asking_price ? 'border-red-400' : ''}`}
                placeholder="0.00" min="0" step="0.01" />
              {errors.asking_price && <p className="text-xs text-red-600 mt-1">{errors.asking_price}</p>}
            </div>
            <div>
              <label className="label">Course Code</label>
              <input name="course_code" value={form.course_code} onChange={handleChange}
                className="input" placeholder="e.g. ME-201" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Preferred Meeting Location</label>
              <input name="preferred_meeting_location" value={form.preferred_meeting_location} onChange={handleChange}
                className="input" placeholder="e.g. Library entrance" />
            </div>
            <div>
              <label className="label">Listing Expiry Date</label>
              <input type="date" name="expiry_date" value={form.expiry_date} onChange={handleChange}
                className="input" min={new Date().toISOString().split('T')[0]} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" name="is_negotiable" id="negotiable"
              checked={form.is_negotiable} onChange={handleChange} className="w-4 h-4" />
            <label htmlFor="negotiable" className="text-sm text-gray-700 cursor-pointer">
              Price is negotiable
            </label>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Creating…' : 'Post Listing'}
            </button>
            <button type="button" onClick={() => navigate(-1)} className="btn-secondary flex-1">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
