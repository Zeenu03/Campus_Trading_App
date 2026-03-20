import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import toast from 'react-hot-toast';

const DEPARTMENTS = [
  'Chemical Engineering', 'Civil Engineering', 'Computer Science',
  'Electrical Engineering', 'Mathematics', 'Mechanical Engineering', 'Physics', 'Other',
];

const HOSTELS = [
  'Aaiban', 'Buqni', 'Chimar', 'Duven', 'Emiet', 'Ijoka', 'Jurqia', 'Kyzeal', 'Lakhag', 'Firpel', 'Hiqom',
];

/** Must be defined outside Register — an inner component is recreated each render and React remounts inputs (loses focus). */
function RegisterField({ name, label, type = 'text', placeholder, required, form, errors, onChange }) {
  return (
    <div>
      <label className="label">{label}{required && <span className="text-red-500 ml-1">*</span>}</label>
      <input
        name={name} type={type} value={form[name]} onChange={onChange}
        className={`input ${errors[name] ? 'border-red-400 ring-1 ring-red-400' : ''}`}
        placeholder={placeholder}
      />
      {errors[name] && <p className="mt-1 text-xs text-red-600">{errors[name]}</p>}
    </div>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '', email: '', password: '', confirm_password: '',
    contact_number: '', department: '', year_of_study: '',
    hostel: '', room_number: '', bio: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e = {};
    if (!form.name.trim())          e.name           = 'Name is required';
    if (!form.email)                e.email          = 'Email is required';
    else if (!form.email.endsWith('@iitgn.ac.in'))
                                    e.email          = 'Must be an @iitgn.ac.in email';
    if (!form.password)             e.password       = 'Password is required';
    else if (form.password.length < 8)
                                    e.password       = 'Password must be at least 8 characters';
    if (form.password !== form.confirm_password)
                                    e.confirm_password = 'Passwords do not match';
    if (!form.contact_number)       e.contact_number = 'Contact number is required';
    if (form.year_of_study && (form.year_of_study < 1 || form.year_of_study > 5))
                                    e.year_of_study  = 'Year must be between 1 and 5';

    const hasHostel = Boolean(form.hostel);
    const roomStr = String(form.room_number ?? '').trim();
    const roomNum = roomStr === '' ? NaN : parseInt(roomStr, 10);
    if (hasHostel && roomStr === '') e.room_number = 'Room number is required when hostel is selected';
    if (!hasHostel && roomStr !== '') e.hostel = 'Select a hostel when entering a room number';
    if (roomStr !== '' && (Number.isNaN(roomNum) || roomNum < 100 || roomNum > 499))
      e.room_number = 'Room number must be between 100 and 499';

    return e;
  };

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setErrors({ ...errors, [e.target.name]: undefined });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setLoading(true);
    try {
      const payload = {
        name: form.name,
        email: form.email,
        password: form.password,
        contact_number: form.contact_number,
        department: form.department || null,
        year_of_study: form.year_of_study ? parseInt(form.year_of_study) : null,
        hostel: form.hostel || null,
        room_number: form.room_number.trim() ? form.room_number.trim() : null,
        bio: form.bio || null,
      };
      await api.post('/auth/register', payload);
      toast.success('Account created! Please log in.');
      navigate('/login');
    } catch (err) {
      toast.error(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const fieldProps = { form, errors, onChange: handleChange };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4 py-8">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-6">
          <span className="text-4xl">🎓</span>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-sm text-gray-500">Campus Trading — IIT Gandhinagar</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <RegisterField {...fieldProps} name="name"           label="Full Name"       required placeholder="Your name" />
              <RegisterField {...fieldProps} name="email"          label="IITGN Email"     required type="email" placeholder="you@iitgn.ac.in" />
              <RegisterField {...fieldProps} name="password"       label="Password"        required type="password" placeholder="Min. 8 characters" />
              <RegisterField {...fieldProps} name="confirm_password" label="Confirm Password" required type="password" placeholder="Repeat password" />
              <RegisterField {...fieldProps} name="contact_number" label="Contact Number"  required placeholder="+91 98765 43210" />

              <div>
                <label className="label">Department</label>
                <select name="department" value={form.department} onChange={handleChange} className="input">
                  <option value="">Select department</option>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>

              <div>
                <label className="label">Year of Study</label>
                <select name="year_of_study" value={form.year_of_study} onChange={handleChange} className="input">
                  <option value="">Select year</option>
                  {[1,2,3,4,5].map(y => <option key={y} value={y}>Year {y}</option>)}
                </select>
                {errors.year_of_study && <p className="mt-1 text-xs text-red-600">{errors.year_of_study}</p>}
              </div>

              <div>
                <label className="label">Hostel</label>
                <select
                  name="hostel"
                  value={form.hostel}
                  onChange={handleChange}
                  className={`input ${errors.hostel ? 'border-red-400 ring-1 ring-red-400' : ''}`}
                >
                  <option value="">Not specified</option>
                  {HOSTELS.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
                {errors.hostel && <p className="mt-1 text-xs text-red-600">{errors.hostel}</p>}
              </div>

              <div>
                <label className="label">Room number</label>
                <input
                  name="room_number"
                  type="number"
                  min={100}
                  max={499}
                  step={1}
                  value={form.room_number}
                  onChange={handleChange}
                  className={`input ${errors.room_number ? 'border-red-400 ring-1 ring-red-400' : ''}`}
                  placeholder="100–499"
                />
                {errors.room_number && <p className="mt-1 text-xs text-red-600">{errors.room_number}</p>}
              </div>
            </div>

            <div>
              <label className="label">Bio (optional)</label>
              <textarea
                name="bio" value={form.bio} onChange={handleChange}
                className="input resize-none" rows={2}
                placeholder="Tell other students about yourself…"
              />
            </div>

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-600 hover:underline font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
