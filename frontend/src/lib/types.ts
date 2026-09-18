export interface SessionItem {
  date: string;
  theme: string;
  available: boolean;
}

export interface Calendar {
  event_info: string;
  event_address: string;
  event_map_url: string;
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

export interface AdminBooking {
  name: string;
  phone: string | null;
  created_at: string;
}

export interface AdminSessionItem {
  date: string;
  theme: string;
  booking: AdminBooking | null;
}

export interface AdminOrphan extends AdminBooking {
  date: string;
}

export interface AdminCalendar {
  email: string;
  sessions: AdminSessionItem[];
  orphans: AdminOrphan[];
}

export interface AdminFields {
  name: string;
  phone: string | null;
}

export type AdminResult<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'unauthorized' }
  | { kind: 'error'; message: string };
