import { describe, expect, it } from 'vitest';
import { classesOn, parseIcs } from './icsSchedule.ts';

/** Small seeded generator so the "random" cases are the same every run. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const CODES = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'];
const pad = (n: number) => String(n).padStart(2, '0');
const dateOf = (dayNumber: number) => {
  const d = new Date(dayNumber * 86_400_000);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
};
const dayNumberOf = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number);
  return Math.round(Date.UTC(y, m - 1, d) / 86_400_000);
};

/**
 * The simplest possible reference: walk every day from the start and apply the rule by definition.
 * (Weeks start on Monday; the start date always counts as the first session.)
 */
function referenceDays(opts: {
  start: number;
  byDay: number[];
  interval: number;
  until: number | null;
  count: number | null;
  exdates: Set<number>;
  horizon: number;
}): Set<number> {
  const out = new Set<number>();
  const mondayOf = (d: number) => d - ((new Date(d * 86_400_000).getUTCDay() + 6) % 7);
  const startMonday = mondayOf(opts.start);
  let produced = 0;
  for (let d = opts.start; d <= opts.horizon; d += 1) {
    const weekday = new Date(d * 86_400_000).getUTCDay();
    const inWeek = Math.floor((mondayOf(d) - startMonday) / 7) % opts.interval === 0;
    const isStart = d === opts.start;
    if (!(isStart || (opts.byDay.includes(weekday) && inWeek))) continue;
    if (opts.until !== null && d > opts.until) break;
    produced += 1;
    if (opts.count !== null && produced > opts.count) break;
    if (!opts.exdates.has(d)) out.add(d);
  }
  return out;
}

describe('weekly repeat rules agree with a day-by-day reference', () => {
  it('matches on 400 random rules (campus time zone, no shift)', () => {
    const rand = mulberry32(20261119);
    const start = dayNumberOf('2026-09-28'); // a Monday
    const mismatches: string[] = [];
    for (let i = 0; i < 400; i += 1) {
      const startDay = start + Math.floor(rand() * 14);
      const byDay = CODES.map((_, n) => n).filter(() => rand() < 0.35);
      if (byDay.length === 0) byDay.push(1);
      const interval = 1 + Math.floor(rand() * 3);
      const useUntil = rand() < 0.5;
      const until = useUntil ? startDay + 14 + Math.floor(rand() * 60) : null;
      const count = !useUntil && rand() < 0.6 ? 1 + Math.floor(rand() * 12) : null;
      const exdates = new Set<number>();
      for (let k = 0; k < 3; k += 1) if (rand() < 0.5) exdates.add(startDay + Math.floor(rand() * 70));

      const rule = [
        'FREQ=WEEKLY',
        `INTERVAL=${interval}`,
        `BYDAY=${byDay.map((n) => CODES[n]).join(',')}`,
        until !== null ? `UNTIL=${dateOf(until).replace(/-/g, '')}T235959` : '',
        count !== null ? `COUNT=${count}` : '',
      ]
        .filter(Boolean)
        .join(';');
      const ics = [
        'BEGIN:VCALENDAR',
        'BEGIN:VEVENT',
        'UID:fuzz',
        'SUMMARY:Fuzz',
        `DTSTART;TZID=America/Los_Angeles:${dateOf(startDay).replace(/-/g, '')}T093000`,
        `DTEND;TZID=America/Los_Angeles:${dateOf(startDay).replace(/-/g, '')}T104000`,
        `RRULE:${rule}`,
        ...[...exdates].map((d) => `EXDATE;TZID=America/Los_Angeles:${dateOf(d).replace(/-/g, '')}T093000`),
        'END:VEVENT',
        'END:VCALENDAR',
      ].join('\r\n');

      const events = parseIcs(ics);
      const horizon = startDay + 120;
      const expected = referenceDays({ start: startDay, byDay, interval, until, count, exdates, horizon });
      for (let d = startDay - 3; d <= horizon; d += 1) {
        const got = classesOn(events, dateOf(d)).length > 0;
        if (got !== expected.has(d)) {
          mismatches.push(`${rule} start=${dateOf(startDay)} day=${dateOf(d)} got=${got} expected=${expected.has(d)}`);
          break;
        }
      }
    }
    expect(mismatches.slice(0, 5)).toEqual([]);
  });
});
