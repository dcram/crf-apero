const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];
const WEEKDAYS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];

export interface MonthGroup<T> {
  key: string;
  label: string;
  items: T[];
}

// Les dates ISO sont découpées à la main : new Date('2026-10-06') serait interprété en UTC
// et pourrait afficher la veille selon le fuseau du navigateur.
function parts(iso: string): { year: number; month: number; day: number } {
  const [year, month, day] = iso.split('-').map(Number);
  return { year, month, day };
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function dayAndMonth(iso: string): string {
  const { year, month, day } = parts(iso);
  const weekday = WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
  return `${weekday} ${day === 1 ? '1er' : day} ${MONTHS[month - 1]}`;
}

export function formatTuesday(iso: string): string {
  return capitalize(dayAndMonth(iso));
}

export function formatLongDate(iso: string): string {
  return `${dayAndMonth(iso)} ${parts(iso).year}`;
}

export function monthLabel(iso: string): string {
  const { year, month } = parts(iso);
  return `${capitalize(MONTHS[month - 1])} ${year}`;
}

export function groupByMonth<T extends { date: string }>(items: T[]): MonthGroup<T>[] {
  const groups: MonthGroup<T>[] = [];
  for (const item of items) {
    const key = item.date.slice(0, 7);
    const last = groups.at(-1);
    if (last && last.key === key) {
      last.items.push(item);
    } else {
      groups.push({ key, label: monthLabel(item.date), items: [item] });
    }
  }
  return groups;
}
