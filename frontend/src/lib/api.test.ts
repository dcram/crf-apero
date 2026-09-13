import { describe, expect, it } from 'vitest';
import { UNAVAILABLE_MESSAGE, createBooking, fetchCalendar } from './api';
import type { BookingRequest } from './types';

const REQUEST: BookingRequest = {
  date: '2026-10-06',
  name: 'Jean Dupont',
  phone: '',
  turnstile_token: 'tok',
  website: '',
};

function fakeFetch(status: number, body: unknown, calls: RequestInit[] = []): typeof fetch {
  return (async (_url: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {});
    return new Response(typeof body === 'string' ? body : JSON.stringify(body), { status });
  }) as typeof fetch;
}

describe('fetchCalendar', () => {
  it('renvoie le calendrier', async () => {
    const calendar = { event_info: '', contact_email: '', apero_start_time: '21:30', turnstile_site_key: 'k', sessions: [] };
    await expect(fetchCalendar(fakeFetch(200, calendar))).resolves.toEqual(calendar);
  });

  it('lève une erreur si le serveur échoue', async () => {
    await expect(fetchCalendar(fakeFetch(500, {}))).rejects.toThrow();
  });
});

describe('createBooking', () => {
  it('envoie le JSON et renvoie la confirmation', async () => {
    const calls: RequestInit[] = [];
    const booking = { date: '2026-10-06', theme: 'T', name: 'Jean Dupont' };
    const outcome = await createBooking(REQUEST, fakeFetch(201, booking, calls));
    expect(outcome).toEqual({ kind: 'ok', booking });
    expect(calls[0].method).toBe('POST');
    expect(JSON.parse(calls[0].body as string)).toEqual(REQUEST);
  });

  it.each([
    [409, 'taken'],
    [403, 'captcha'],
    [429, 'rate_limited'],
    [422, 'invalid'],
    [404, 'invalid'],
  ] as const)('statut %i → %s avec le message du serveur', async (status, kind) => {
    const outcome = await createBooking(REQUEST, fakeFetch(status, { detail: 'Message serveur' }));
    expect(outcome).toEqual({ kind, message: 'Message serveur' });
  });

  it('503 → indisponible', async () => {
    const outcome = await createBooking(REQUEST, fakeFetch(503, { detail: 'x' }));
    expect(outcome).toEqual({ kind: 'unavailable', message: UNAVAILABLE_MESSAGE });
  });

  it('corps non JSON → message générique', async () => {
    const outcome = await createBooking(REQUEST, fakeFetch(429, '<html>'));
    expect(outcome).toEqual({ kind: 'rate_limited', message: UNAVAILABLE_MESSAGE });
  });

  it('réseau coupé → indisponible', async () => {
    const broken = (async () => {
      throw new TypeError('Failed to fetch');
    }) as typeof fetch;
    expect(await createBooking(REQUEST, broken)).toEqual({
      kind: 'unavailable',
      message: UNAVAILABLE_MESSAGE,
    });
  });
});
