export interface IcsInput {
  date: string;
  startTime: string;
  theme: string;
  eventInfo: string;
  now?: Date;
}

const DURATION_MINUTES = 30;

const VTIMEZONE_PARIS = [
  'BEGIN:VTIMEZONE',
  'TZID:Europe/Paris',
  'BEGIN:DAYLIGHT',
  'TZOFFSETFROM:+0100',
  'TZOFFSETTO:+0200',
  'TZNAME:CEST',
  'DTSTART:19700329T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU',
  'END:DAYLIGHT',
  'BEGIN:STANDARD',
  'TZOFFSETFROM:+0200',
  'TZOFFSETTO:+0100',
  'TZNAME:CET',
  'DTSTART:19701025T030000',
  'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU',
  'END:STANDARD',
  'END:VTIMEZONE',
];

const pad = (n: number) => String(n).padStart(2, '0');

// Heure locale « flottante » calculée via UTC pour gérer le passage de minuit sans fuseau.
function localStamp(date: string, time: string, addMinutes = 0): string {
  const [year, month, day] = date.split('-').map(Number);
  const [hours, minutes] = time.split(':').map(Number);
  const d = new Date(Date.UTC(year, month - 1, day, hours, minutes + addMinutes));
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00`
  );
}

function utcStamp(d: Date): string {
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
  );
}

function escapeText(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

function fold(line: string): string {
  const encoder = new TextEncoder();
  const physical: string[] = [];
  let current = '';
  let bytes = 0;
  for (const char of line) {
    const size = encoder.encode(char).length;
    const limit = physical.length === 0 ? 75 : 74; // les lignes de continuation commencent par une espace
    if (bytes + size > limit) {
      physical.push(current);
      current = char;
      bytes = size;
    } else {
      current += char;
      bytes += size;
    }
  }
  physical.push(current);
  return physical.join('\r\n ');
}

export function buildIcs({ date, startTime, theme, eventInfo, now = new Date() }: IcsInput): string {
  const description = [`Thème : ${theme}`, eventInfo].filter(Boolean).join('\n');
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//FSSP Nantes//CRF Apero//FR',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    ...VTIMEZONE_PARIS,
    'BEGIN:VEVENT',
    `UID:crf-apero-${date}@crf.fsspnantes.fr`,
    `DTSTAMP:${utcStamp(now)}`,
    `DTSTART;TZID=Europe/Paris:${localStamp(date, startTime)}`,
    `DTEND;TZID=Europe/Paris:${localStamp(date, startTime, DURATION_MINUTES)}`,
    "SUMMARY:Apéro CRF – je m'en charge",
    `DESCRIPTION:${escapeText(description)}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  return lines.map(fold).join('\r\n') + '\r\n';
}

export function icsFilename(date: string): string {
  return `apero-crf-${date}.ics`;
}
