import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

const INITIAL_FORM = {
  name: '',
  email: '',
  password: '',
  confirm_password: '',
  contact_number: '',
  department: '',
  year_of_study: '',
  hostel: '',
  room_number: '',
  bio: '',
};

/** Pure validation — same rules as before, with explicit trimming and numeric year checks. */
function validateRegisterForm(form) {
  const e = {};
  const name = String(form.name ?? '').trim();
  const email = String(form.email ?? '').trim();
  const contact = String(form.contact_number ?? '').trim();

  if (!name) e.name = 'Name is required';
  if (!email) e.email = 'Email is required';
  else if (!email.toLowerCase().endsWith('@iitgn.ac.in')) e.email = 'Must be an @iitgn.ac.in email';

  if (!form.password) e.password = 'Password is required';
  else if (form.password.length < 8) e.password = 'Password must be at least 8 characters';

  if (form.password !== form.confirm_password) e.confirm_password = 'Passwords do not match';

  if (!contact) e.contact_number = 'Contact number is required';

  const yearRaw = form.year_of_study;
  if (yearRaw !== '' && yearRaw != null) {
    const y = parseInt(String(yearRaw), 10);
    if (Number.isNaN(y) || y < 1 || y > 5) e.year_of_study = 'Year must be between 1 and 5';
  }

  const hasHostel = Boolean(String(form.hostel ?? '').trim());
  const roomStr = String(form.room_number ?? '').trim();
  const roomNum = roomStr === '' ? NaN : parseInt(roomStr, 10);
  if (hasHostel && roomStr === '') e.room_number = 'Room number is required when hostel is selected';
  if (!hasHostel && roomStr !== '') e.hostel = 'Select a hostel when entering a room number';
  if (roomStr !== '' && (Number.isNaN(roomNum) || roomNum < 100 || roomNum > 499)) {
    e.room_number = 'Room number must be between 100 and 499';
  }

  return e;
}

/** Build API body — matches backend RegisterRequest and prior payload shape. */
function buildRegisterPayload(form) {
  const email = String(form.email ?? '').trim().toLowerCase();
  const yearRaw = form.year_of_study;
  const yearParsed = yearRaw !== '' && yearRaw != null ? parseInt(String(yearRaw), 10) : NaN;
  const roomTrim = String(form.room_number ?? '').trim();

  return {
    name: String(form.name ?? '').trim(),
    email,
    password: form.password,
    contact_number: String(form.contact_number ?? '').trim(),
    department: String(form.department ?? '').trim() || null,
    year_of_study: !Number.isNaN(yearParsed) ? yearParsed : null,
    hostel: String(form.hostel ?? '').trim() || null,
    room_number: roomTrim || null,
    bio: String(form.bio ?? '').trim() || null,
  };
}

/** Defined outside Register — inner components remount each render and inputs lose focus. */
function RegisterField({
  name,
  label,
  type = 'text',
  placeholder,
  required,
  form,
  errors,
  onChange,
  autoComplete,
}) {
  const id = name;
  const err = errors[name];
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        id={id}
        name={name}
        type={type}
        value={form[name]}
        onChange={onChange}
        className={`input ${err ? 'border-red-400 ring-1 ring-red-400' : ''}`}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={err ? true : undefined}
        aria-describedby={err ? `${id}-error` : undefined}
      />
      {err && (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-600" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}

export default function Register() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const mountedRef = useRef(true);

  const [departments, setDepartments] = useState([]);
  const [hostels, setHostels] = useState([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

  const [form, setForm] = useState(() => ({ ...INITIAL_FORM }));
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setOptionsLoading(true);
    (async () => {
      try {
        const [deptList, hostelList] = await Promise.all([
          api.get('/common/departments'),
          api.get('/common/hostels'),
        ]);
        if (cancelled) return;
        setDepartments(Array.isArray(deptList) ? deptList : []);
        setHostels(Array.isArray(hostelList) ? hostelList : []);
      } catch (err) {
        if (!cancelled) {
          const msg = err?.message || 'Could not load departments or hostels';
          toast.error(msg);
          setDepartments([]);
          setHostels([]);
        }
      } finally {
        if (!cancelled) setOptionsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!authLoading && user) navigate('/dashboard', { replace: true });
  }, [authLoading, user, navigate]);

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      if (!(name in prev) || prev[name] == null) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
    setSubmitError('');
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    const errs = validateRegisterForm(form);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    try {
      const payload = buildRegisterPayload(form);
      await api.post('/auth/register', payload);
      if (!mountedRef.current) return;
      toast.success('Account created! Please log in.');
      navigate('/login');
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err?.message || 'Registration failed';
      setSubmitError(msg);
      toast.error(msg);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  const fieldProps = { form, errors, onChange: handleChange };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="spinner" />
      </div>
    );
  }

  if (user) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4 py-8">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-6">
          <span className="text-4xl">🎓</span>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">Create your account</h1>
          <p className="text-sm text-gray-500">Campus Trading — IIT Gandhinagar</p>
        </div>

        <div className="card">
          {submitError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
              {submitError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <RegisterField
                {...fieldProps}
                name="name"
                label="Full Name"
                required
                placeholder="Your name"
                autoComplete="name"
              />
              <RegisterField
                {...fieldProps}
                name="email"
                label="IITGN Email"
                required
                type="email"
                placeholder="you@iitgn.ac.in"
                autoComplete="email"
              />
              <RegisterField
                {...fieldProps}
                name="password"
                label="Password"
                required
                type="password"
                placeholder="Min. 8 characters"
                autoComplete="new-password"
              />
              <RegisterField
                {...fieldProps}
                name="confirm_password"
                label="Confirm Password"
                required
                type="password"
                placeholder="Repeat password"
                autoComplete="new-password"
              />
              <RegisterField
                {...fieldProps}
                name="contact_number"
                label="Contact Number"
                required
                placeholder="+91 98765 43210"
                autoComplete="tel"
              />

              <div>
                <label className="label" htmlFor="register-department">Department</label>
                <select
                  id="register-department"
                  name="department"
                  value={form.department}
                  onChange={handleChange}
                  className="input"
                  disabled={optionsLoading}
                  aria-busy={optionsLoading || undefined}
                >
                  <option value="">{optionsLoading ? 'Loading departments…' : 'Select department'}</option>
                  {departments.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label" htmlFor="register-year">Year of Study</label>
                <select
                  id="register-year"
                  name="year_of_study"
                  value={form.year_of_study}
                  onChange={handleChange}
                  className={`input ${errors.year_of_study ? 'border-red-400 ring-1 ring-red-400' : ''}`}
                  aria-invalid={errors.year_of_study ? true : undefined}
                  aria-describedby={errors.year_of_study ? 'register-year-error' : undefined}
                >
                  <option value="">Select year</option>
                  {[1, 2, 3, 4, 5].map((y) => (
                    <option key={y} value={y}>
                      Year {y}
                    </option>
                  ))}
                </select>
                {errors.year_of_study && (
                  <p id="register-year-error" className="mt-1 text-xs text-red-600" role="alert">
                    {errors.year_of_study}
                  </p>
                )}
              </div>

              <div>
                <label className="label" htmlFor="register-hostel">Hostel</label>
                <select
                  id="register-hostel"
                  name="hostel"
                  value={form.hostel}
                  onChange={handleChange}
                  className={`input ${errors.hostel ? 'border-red-400 ring-1 ring-red-400' : ''}`}
                  disabled={optionsLoading}
                  aria-busy={optionsLoading || undefined}
                  aria-invalid={errors.hostel ? true : undefined}
                  aria-describedby={errors.hostel ? 'register-hostel-error' : undefined}
                >
                  <option value="">{optionsLoading ? 'Loading hostels…' : 'Not specified'}</option>
                  {hostels.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
                {errors.hostel && (
                  <p id="register-hostel-error" className="mt-1 text-xs text-red-600" role="alert">
                    {errors.hostel}
                  </p>
                )}
              </div>

              <div>
                <label className="label" htmlFor="register-room">Room number</label>
                <input
                  id="register-room"
                  name="room_number"
                  type="number"
                  min={100}
                  max={499}
                  step={1}
                  value={form.room_number}
                  onChange={handleChange}
                  className={`input ${errors.room_number ? 'border-red-400 ring-1 ring-red-400' : ''}`}
                  placeholder="100–499"
                  autoComplete="off"
                  aria-invalid={errors.room_number ? true : undefined}
                  aria-describedby={errors.room_number ? 'register-room-error' : undefined}
                />
                {errors.room_number && (
                  <p id="register-room-error" className="mt-1 text-xs text-red-600" role="alert">
                    {errors.room_number}
                  </p>
                )}
              </div>
            </div>

            <div>
              <label className="label" htmlFor="register-bio">Bio (optional)</label>
              <textarea
                id="register-bio"
                name="bio"
                value={form.bio}
                onChange={handleChange}
                className="input resize-none"
                rows={2}
                placeholder="Tell other students about yourself…"
              />
            </div>

            <button type="submit" className="btn-primary w-full" disabled={loading || optionsLoading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
