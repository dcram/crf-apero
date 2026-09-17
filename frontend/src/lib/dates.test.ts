import { describe, expect, it } from 'vitest';
import { formatLongDate, formatTuesday, groupByMonth, monthLabel } from './dates';

describe('dates', () => {
  it('formate un mardi pour une carte', () => {
    expect(formatTuesday('2026-10-06')).toBe('Mardi 6 octobre');
    expect(formatTuesday('2026-12-01')).toBe('Mardi 1er décembre');
  });

  it('formate une date longue', () => {
    expect(formatLongDate('2027-02-02')).toBe('mardi 2 février 2027');
  });

  it('libellé de mois capitalisé', () => {
    expect(monthLabel('2027-08-17')).toBe('Août 2027');
  });

  it('regroupe par mois en conservant l’ordre', () => {
    const items = [
      { date: '2026-09-22', theme: 'A' },
      { date: '2026-10-06', theme: 'B' },
      { date: '2026-10-20', theme: 'C' },
      { date: '2027-01-05', theme: 'D' },
    ];
    expect(groupByMonth(items)).toEqual([
      { key: '2026-09', label: 'Septembre 2026', items: [items[0]] },
      { key: '2026-10', label: 'Octobre 2026', items: [items[1], items[2]] },
      { key: '2027-01', label: 'Janvier 2027', items: [items[3]] },
    ]);
  });

  it('liste vide', () => {
    expect(groupByMonth([])).toEqual([]);
  });
});
