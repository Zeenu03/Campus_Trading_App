const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8080';

/** Full URL for uploaded image path (e.g. /uploads/listings/1/abc.jpg) */
export function uploadsUrl(path) {
  if (!path) return '';
  return API_ORIGIN + (path.startsWith('/') ? path : '/' + path);
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const isFormData = options.body instanceof FormData;
  const config = {
    credentials: 'include',
    headers: isFormData ? { ...options.headers } : { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  };

  const res = await fetch(url, config);

  if (res.status === 204) return null;

  let data;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const msg = data?.error || `Request failed: ${res.status}`;
    throw new Error(msg);
  }

  return data;
}

export const api = {
  get:    (path, params) => {
    const url = params
      ? path + '?' + new URLSearchParams(params).toString()
      : path;
    return request(url);
  },
  post:   (path, body)   => request(path, { method: 'POST',   body: JSON.stringify(body) }),
  put:    (path, body)   => request(path, { method: 'PUT',    body: JSON.stringify(body) }),
  delete: (path)         => request(path, { method: 'DELETE' }),
  /** POST multipart form with file (field name: image) */
  postImage: (path, file) => {
    const form = new FormData();
    form.append('image', file);
    return request(path, { method: 'POST', body: form });
  },
};
