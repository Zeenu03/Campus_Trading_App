import { useState } from 'react';
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
    expiry_date: '',
    is_donation: false,
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

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
      const res = await api.post('/listings', buildListingPayload(form));
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
    </div>
  );
}
