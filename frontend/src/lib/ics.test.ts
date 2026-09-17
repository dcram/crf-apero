import { describe, expect, it } from 'vitest';
import { buildIcs, icsFilename } from './ics';

const NOW = new Date(Date.UTC(2026, 8, 13, 12, 0, 0));

function unfold(ics: string): string[] {
  return ics.replace(/\r\n /g, '').split('\r\n');
}

describe('buildIcs', () => {
  const ics = buildIcs({
    date: '2026-10-06',
    startTime: '21:30',
    theme: 'La Création, la Chute; et le reste',
    eventInfo: 'Mardi 20h30 – Sainte-Élisabeth, 43 rue de Coulmiers',
    now: NOW,
  });
  const lines = unfold(ics);

  it('utilise CRLF et se termine par une fin de ligne', () => {
    expect(ics.endsWith('\r\n')).toBe(true);
    expect(ics.replace(/\r\n/g, '')).not.toContain('\n');
  });

  it('contient un événement de 30 minutes à Paris', () => {
    expect(lines).toContain('BEGIN:VCALENDAR');
    expect(lines).toContain('TZID:Europe/Paris');
    expect(lines).toContain('UID:crf-apero-2026-10-06@crf.fsspnantes.fr');
    expect(lines).toContain('DTSTAMP:20260913T120000Z');
    expect(lines).toContain('DTSTART;TZID=Europe/Paris:20261006T213000');
    expect(lines).toContain('DTEND;TZID=Europe/Paris:20261006T223000');
    expect(lines).toContain("SUMMARY:Moment convivial CRF – je m'en charge");
    expect(lines.at(-2)).toBe('END:VCALENDAR');
  });

  it('échappe la description', () => {
    expect(lines).toContain(
      'DESCRIPTION:Thème : La Création\\, la Chute\\; et le reste\\nMardi 20h30 – Sainte-Élisabeth\\, 43 rue de Coulmiers',
    );
  });

  it('plie les lignes à 75 octets maximum', () => {
    const encoder = new TextEncoder();
    for (const physical of ics.split('\r\n')) {
      expect(encoder.encode(physical).length).toBeLessThanOrEqual(75);
    }
  });

  it("ajoute LOCATION quand une adresse est fournie, et l'omet sinon", () => {
    const avec = unfold(
      buildIcs({
        date: '2026-10-06',
        startTime: '20:30',
        theme: 'T',
        eventInfo: '',
        address: '4 rue Lorette de la Refoulais, 44000 Nantes',
        now: NOW,
      }),
    );
    expect(avec).toContain('LOCATION:4 rue Lorette de la Refoulais\\, 44000 Nantes');

    const sans = unfold(
      buildIcs({ date: '2026-10-06', startTime: '20:30', theme: 'T', eventInfo: '', now: NOW }),
    );
    expect(sans.some((l) => l.startsWith('LOCATION:'))).toBe(false);
  });

  it('passe au lendemain si l’apéro finit après minuit', () => {
    const late = unfold(
      buildIcs({ date: '2026-10-06', startTime: '23:45', theme: 'T', eventInfo: '', now: NOW }),
    );
    expect(late).toContain('DTEND;TZID=Europe/Paris:20261007T004500');
    expect(late).toContain('DESCRIPTION:Thème : T');
  });
});

describe('icsFilename', () => {
  it('nomme le fichier avec la date', () => {
    expect(icsFilename('2026-10-06')).toBe('apero-crf-2026-10-06.ics');
  });
});
