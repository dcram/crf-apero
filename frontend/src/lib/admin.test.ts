import { describe, expect, it } from 'vitest';
import {
  deleteBooking,
  fetchAdminBookings,
  openSession,
  requestCode,
  saveBooking,
} from './admin';

function fakeFetch(status: number, body: unknown = {}, calls: RequestInit[] = []): typeof fetch {
  return (async (_url: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {});
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  }) as typeof fetch;
}

describe('requestCode', () => {
  it('renvoie ok sur 204', async () => {
    expect(await requestCode('a@b.org', fakeFetch(204))).toEqual({ kind: 'ok', value: null });
  });

  it('remonte le message sur 429', async () => {
    const outcome = await requestCode('a@b.org', fakeFetch(429, { detail: 'Trop de demandes' }));
    expect(outcome).toEqual({ kind: 'error', message: 'Trop de demandes' });
  });
});

describe('openSession', () => {
  it('envoie adresse et code', async () => {
    const calls: RequestInit[] = [];
    await openSession('a@b.org', '123456', fakeFetch(204, {}, calls));
    expect(JSON.parse(calls[0].body as string)).toEqual({ email: 'a@b.org', code: '123456' });
  });

  it('remonte le message sur 403', async () => {
    const outcome = await openSession('a@b.org', '000000', fakeFetch(403, { detail: 'Code incorrect ou expiré.' }));
    expect(outcome).toEqual({ kind: 'error', message: 'Code incorrect ou expiré.' });
  });
});

describe('fetchAdminBookings', () => {
  it('renvoie le calendrier', async () => {
    const calendar = { email: 'a@b.org', sessions: [], orphans: [] };
    expect(await fetchAdminBookings(fakeFetch(200, calendar))).toEqual({
      kind: 'ok',
      value: calendar,
    });
  });

  it('signale la déconnexion sur 401', async () => {
    expect(await fetchAdminBookings(fakeFetch(401))).toEqual({ kind: 'unauthorized' });
  });
});

describe('saveBooking', () => {
  it('fait un PUT sur la date', async () => {
    const calls: RequestInit[] = [];
    const booking = { date: '2026-10-06', theme: 'T', name: 'Jean', phone: null, created_at: '' };
    const outcome = await saveBooking(
      '2026-10-06',
      { name: 'Jean', phone: null },
      fakeFetch(200, booking, calls),
    );
    expect(calls[0].method).toBe('PUT');
    expect(outcome).toEqual({ kind: 'ok', value: booking });
  });
});

describe('deleteBooking', () => {
  it('renvoie ok sur 204', async () => {
    expect(await deleteBooking('2026-10-06', fakeFetch(204))).toEqual({ kind: 'ok', value: null });
  });

  it('signale la déconnexion sur 401', async () => {
    expect(await deleteBooking('2026-10-06', fakeFetch(401))).toEqual({ kind: 'unauthorized' });
  });
});
