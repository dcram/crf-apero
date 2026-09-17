export interface SessionItem {
  date: string;
  theme: string;
  available: boolean;
}

export interface Calendar {
  event_info: string;
  contact_email: string;
  apero_start_time: string;
  turnstile_site_key: string;
  sessions: SessionItem[];
}

export interface BookingRequest {
  date: string;
  name: string;
  phone: string;
  turnstile_token: string;
  website: string;
}

export interface BookingConfirmation {
  date: string;
  theme: string;
  name: string;
}

export type BookingFailureKind = 'taken' | 'captcha' | 'rate_limited' | 'invalid' | 'unavailable';

export type BookingOutcome =
  | { kind: 'ok'; booking: BookingConfirmation }
  | { kind: BookingFailureKind; message: string };
