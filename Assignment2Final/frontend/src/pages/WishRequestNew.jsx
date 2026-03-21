import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import toast from 'react-hot-toast';
import WishRequestForm, { validateWishRequestForm, buildWishRequestPayload } from '../components/WishRequestForm';

export default function WishRequestNew() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({
    category_id: '',
    item_description: '',
    min_budget: '',
    max_budget: '',
    preferred_condition: '',
    needed_by_date: '',
    additional_details: '',
    status: 'Active',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get('/categories').then(setCategories).catch(() => setCategories([]));
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validateWishRequestForm(form);
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    try {
      const res = await api.post('/wishrequests', buildWishRequestPayload(form));
      toast.success('Wish request created!');
      navigate(`/wishrequests/${res.wish_request_id}`);
    } catch (err) {
      toast.error(err.message || 'Failed to create wish request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Post a New Wish Request</h1>
      <div className="card">
        <WishRequestForm
          form={form}
          errors={errors}
          categories={categories}
          onChange={handleChange}
          onSubmit={handleSubmit}
          loading={loading}
          submitLabel="Post Wish Request"
          pendingLabel="Creating…"
          onCancel={() => navigate(-1)}
          cancelLabel="Cancel"
        />
      </div>
    </div>
  );
}
