/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { MAX_EVENTS, type ScheduleEvent } from './icsSchedule.ts';

/**
 * The imported class schedule, kept in this browser only (localStorage) so a returning
 * student does not upload it again. It is never sent anywhere. Only the fields the planner
 * needs are stored: class title, room and times, not the rest of the calendar file.
 */
const STORAGE_KEY = 'parksmart.schedule.v1';

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

const isString = (v: unknown): v is string => typeof v === 'string';
const isNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Keeps an event only if every field has the expected shape, so bad data never reaches the planner. */
function sanitizeEvent(value: unknown): ScheduleEvent | null {
  if (typeof value !== 'object' || value === null) return null;
  const e = value as Record<string, unknown>;
  if (
    !isString(e.id) ||
    !isString(e.title) ||
    !isString(e.location) ||
    !isString(e.date) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(e.date) ||
    !isNumber(e.startMinutes) ||
    !isNumber(e.durationMinutes) ||
    !Array.isArray(e.exdates)
  ) {
    return null;
  }
  let rule: ScheduleEvent['rule'] = null;
  if (e.rule !== null && e.rule !== undefined) {
    const r = e.rule as Record<string, unknown>;
    if (
      typeof r !== 'object' ||
      !isNumber(r.interval) ||
      !Array.isArray(r.byDay) ||
      !r.byDay.every(isNumber) ||
      !(r.untilTotal === null || isNumber(r.untilTotal)) ||
      !(r.count === null || isNumber(r.count))
    ) {
      return null;
    }
    rule = { interval: r.interval, byDay: r.byDay, untilTotal: r.untilTotal as number | null, count: r.count as number | null };
  }
  // A repeating class written in another zone keeps its zone, so it stays right across daylight saving
  let source: ScheduleEvent['source'];
  if (rule && typeof e.source === 'object' && e.source !== null) {
    const s = e.source as Record<string, unknown>;
    if (isString(s.zone) && isString(s.date) && /^\d{4}-\d{2}-\d{2}$/.test(s.date) && isNumber(s.minutes)) {
      source = { zone: s.zone, date: s.date, minutes: s.minutes };
    }
  }
  return {
    id: e.id,
    title: e.title,
    location: e.location,
    date: e.date,
    startMinutes: e.startMinutes,
    durationMinutes: e.durationMinutes,
    rule,
    exdates: e.exdates.filter(isString),
    ...(source ? { source } : {}),
  };
}

/** The saved schedule, or an empty list if none was saved or the data is unreadable. */
export function loadSchedule(store: KeyValueStore | null = defaultStore()): ScheduleEvent[] {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(sanitizeEvent)
      .filter((e): e is ScheduleEvent => e !== null)
      .slice(0, MAX_EVENTS);
  } catch {
    return [];
  }
}

/** Remembers the schedule. Returns false if the browser would not store it (the import still works this visit). */
export function saveSchedule(events: ScheduleEvent[], store: KeyValueStore | null = defaultStore()): boolean {
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(events.slice(0, MAX_EVENTS)));
    return store !== null;
  } catch {
    return false;
  }
}

/** Forgets the saved schedule. */
export function clearSchedule(store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do if storage is blocked
  }
}
