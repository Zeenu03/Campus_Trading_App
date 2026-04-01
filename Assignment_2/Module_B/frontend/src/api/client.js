const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8080';

/** Full URL for uploaded image path (e.g. /uploads/listings/1/abc.jpg) */
export function uploadsUrl(path) {
  if (!path) return '';
  return API_ORIGIN + (path.startsWith('/') ? path : '/' + path);
}

/** Build query string; array values become repeated keys (e.g. category_id=1&category_id=2). */
function serializeQueryParams(params) {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item === undefined || item === null || item === '') continue;
        usp.append(key, String(item));
      }
    } else {
      usp.append(key, String(value));
    }
  }
  return usp.toString();
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
      ? path + '?' + serializeQueryParams(params)
      : path;
    // Avoid stale audit/admin lists when query string changes (browser HTTP cache).
    return request(url, { cache: 'no-store' });
  },
  post:   (path, body)   => request(path, { method: 'POST',   body: JSON.stringify(body) }),
  put:    (path, body)   => request(path, { method: 'PUT',    body: JSON.stringify(body) }),
  delete: (path, body)   => request(path, { method: 'DELETE', body: body ? JSON.stringify(body) : undefined }),
  /** POST multipart form with file (field name: image) */
  postImage: (path, file) => {
    const form = new FormData();
    form.append('image', file);
    return request(path, { method: 'POST', body: form });
  },
};
