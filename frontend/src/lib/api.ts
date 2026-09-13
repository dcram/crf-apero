import type { BookingFailureKind, BookingOutcome, BookingRequest, Calendar } from './types';

export const UNAVAILABLE_MESSAGE = 'Le service est momentanément indisponible, réessayez plus tard.';

const KIND_BY_STATUS: Record<number, BookingFailureKind> = {
  409: 'taken',
  403: 'captcha',
  429: 'rate_limited',
  422: 'invalid',
  404: 'invalid',
};

export async function fetchCalendar(fetchFn: typeof fetch = fetch): Promise<Calendar> {
  const response = await fetchFn('/api/calendar', { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`GET /api/calendar → ${response.status}`);
  }
  return (await response.json()) as Calendar;
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

export async function createBooking(
  request: BookingRequest,
  fetchFn: typeof fetch = fetch,
): Promise<BookingOutcome> {
  let response: Response;
  try {
    response = await fetchFn('/api/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(request),
    });
  } catch {
    return { kind: 'unavailable', message: UNAVAILABLE_MESSAGE };
  }

  if (response.status === 201) {
    return { kind: 'ok', booking: await response.json() };
  }
  const kind = KIND_BY_STATUS[response.status];
  if (!kind) {
    return { kind: 'unavailable', message: UNAVAILABLE_MESSAGE };
  }
  return { kind, message: (await readDetail(response)) ?? UNAVAILABLE_MESSAGE };
}
