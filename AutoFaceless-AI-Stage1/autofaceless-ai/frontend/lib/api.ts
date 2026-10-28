const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export async function api(path: string, token?: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...init, headers, cache: 'no-store' });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
  return data;
}
