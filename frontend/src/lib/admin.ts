import type { AdminBooking, AdminCalendar, AdminFields, AdminResult } from './types';

export const UNAVAILABLE_MESSAGE = 'Le service est momentanément indisponible, réessayez plus tard.';

async function call<T>(
  url: string,
  init: RequestInit,
  fetchFn: typeof fetch,
): Promise<AdminResult<T>> {
  let response: Response;
  try {
    response = await fetchFn(url, { ...init, headers: { Accept: 'application/json', ...init.headers } });
  } catch {
    return { kind: 'error', message: UNAVAILABLE_MESSAGE };
  }
  if (response.status === 401) {
    return { kind: 'unauthorized' };
  }
  if (response.status === 204) {
    return { kind: 'ok', value: null as T };
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    return { kind: 'error', message: typeof detail === 'string' ? detail : UNAVAILABLE_MESSAGE };
  }
  return { kind: 'ok', value: body as T };
}

function json(method: string, payload: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) };
}

export function requestCode(email: string, fetchFn: typeof fetch = fetch) {
  return call<null>('/api/admin/login', json('POST', { email }), fetchFn);
}

export function openSession(email: string, code: string, fetchFn: typeof fetch = fetch) {
  return call<null>('/api/admin/session', json('POST', { email, code }), fetchFn);
}

export async function closeSession(fetchFn: typeof fetch = fetch): Promise<void> {
  await call<null>('/api/admin/session', { method: 'DELETE' }, fetchFn);
}

export function fetchAdminBookings(fetchFn: typeof fetch = fetch) {
  return call<AdminCalendar>('/api/admin/bookings', { method: 'GET' }, fetchFn);
}

export function saveBooking(date: string, fields: AdminFields, fetchFn: typeof fetch = fetch) {
  return call<AdminBooking & { date: string; theme: string }>(
    `/api/admin/bookings/${date}`,
    json('PUT', fields),
    fetchFn,
  );
}

export function deleteBooking(date: string, fetchFn: typeof fetch = fetch) {
  return call<null>(`/api/admin/bookings/${date}`, { method: 'DELETE' }, fetchFn);
}
