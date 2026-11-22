/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Reads a class schedule from an iCalendar (.ics) file, entirely in the browser: no upload,
 * no dependency. Supports what student calendars export: timed events, TZID or UTC times,
 * and weekly repeats (INTERVAL, BYDAY, UNTIL, COUNT, EXDATE). All-day events are ignored
 * (they are holidays and deadlines, not classes). Any other repeat rule is read as a
 * single class on its first date rather than guessed at. A change to "this and all future"
 * sessions (RANGE=THISANDFUTURE) is not supported.
 *
 * Times are converted to campus time (America/Los_Angeles), because that is the time the
 * planner's arrival fields use.
 */

/** Campus time zone; the planner's arrival date and time are in this zone. */
export const CAMPUS_TIME_ZONE = 'America/Los_Angeles';

/** A class with no end time in the file is assumed to last this long. */
const DEFAULT_DURATION_MINUTES = 60;
const MINUTES_PER_DAY = 24 * 60;
/** How far back from a date a COUNT-limited repeat is counted (a few terms is plenty). */
const MAX_COUNT_SCAN_DAYS = 800;
/** Upper bound on events kept from one file, so a huge calendar cannot fill storage. */
export const MAX_EVENTS = 400;
/** When a file has more events than that, single events older than this many days are dropped first. */
export const STALE_EVENT_DAYS = 60;

/** iCalendar weekday codes by JavaScript getUTCDay() index (0 = Sunday). */
const WEEKDAY_CODES = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'] as const;

export interface WeeklyRule {
  interval: number;
  /** Weekdays as getUTCDay() numbers (0 = Sunday). */
  byDay: number[];
  /** Last allowed start, as day number * 1440 + minutes (campus time); null if open ended. */
  untilTotal: number | null;
  count: number | null;
}

/** One calendar event as stored: the first occurrence plus how it repeats. */
export interface ScheduleEvent {
  id: string;
  title: string;
  location: string;
  /** First occurrence, "YYYY-MM-DD" in campus time. */
  date: string;
  startMinutes: number;
  durationMinutes: number;
  /** Null for a single class. */
  rule: WeeklyRule | null;
  /** Skipped dates, "YYYY-MM-DD". */
  exdates: string[];
  /**
   * Only for a repeating class whose start was written in another zone (UTC or a TZID). Such a
   * class keeps its time in that zone, so its campus time moves when daylight saving changes
   * and is worked out again for each week.
   */
  source?: { zone: string; date: string; minutes: number };
}

/** One class on one specific day. */
export interface ClassSession {
  id: string;
  title: string;
  location: string;
  date: string;
  startMinutes: number;
  endMinutes: number;
}

interface Line {
  name: string;
  params: Record<string, string>;
  value: string;
}

interface Local {
  date: string;
  minutes: number;
}

/* ---------- Date helpers (UTC day numbers keep daylight saving out of the arithmetic) ---------- */

function dayNumber(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return Math.round(Date.UTC(y, m - 1, d) / 86_400_000);
}

function dateOfDayNumber(day: number): string {
  const d = new Date(day * 86_400_000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}

function weekdayOf(day: number): number {
  return new Date(day * 86_400_000).getUTCDay();
}

/** Day number of the Monday that starts the week containing `day` (RFC 5545 default week start). */
function mondayOf(day: number): number {
  return day - ((weekdayOf(day) + 6) % 7);
}

const formatterCache = new Map<string, Intl.DateTimeFormat>();

function formatterFor(timeZone: string): Intl.DateTimeFormat {
  let f = formatterCache.get(timeZone);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
    formatterCache.set(timeZone, f);
  }
  return f;
}

/** The wall-clock reading of an instant in a zone. Throws for an unknown zone name. */
function wallClock(utcMs: number, timeZone: string): Local {
  const parts: Record<string, string> = {};
  formatterFor(timeZone)
    .formatToParts(new Date(utcMs))
    .forEach((p) => {
      parts[p.type] = p.value;
    });
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    minutes: Number(parts.hour) * 60 + Number(parts.minute),
  };
}

/** The instant for a wall-clock time in a zone (one correction handles daylight saving). */
function instantOf(local: Local, timeZone: string): number {
  const [y, m, d] = local.date.split('-').map(Number);
  const guess = Date.UTC(y, m - 1, d, 0, local.minutes);
  const offset = (at: number) => {
    const w = wallClock(at, timeZone);
    return dayNumber(w.date) * MINUTES_PER_DAY * 60_000 + w.minutes * 60_000 - at;
  };
  return guess - offset(guess - offset(guess));
}

/* ---------- Reading the file ---------- */

function unescapeText(text: string): string {
  return text.replace(/\\n/gi, ' ').replace(/\\([,;\\])/g, '$1').trim();
}

/** Unfolds continuation lines and splits each into name, parameters and value. */
function readLines(text: string): Line[] {
  const lines: Line[] = [];
  for (const raw of text.replace(/\r\n|\r/g, '\n').replace(/\n[ \t]/g, '').split('\n')) {
    const colon = raw.indexOf(':');
    if (colon <= 0) continue;
    const [name, ...paramParts] = raw.slice(0, colon).split(';');
    const params: Record<string, string> = {};
    paramParts.forEach((p) => {
      const eq = p.indexOf('=');
      if (eq > 0) params[p.slice(0, eq).toUpperCase()] = p.slice(eq + 1).replace(/"/g, '');
    });
    lines.push({ name: name.toUpperCase(), params, value: raw.slice(colon + 1) });
  }
  return lines;
}

/** Windows zone names (Outlook exports) for the US zones, as IANA names. */
const WINDOWS_ZONES: Record<string, string> = {
  'pacific standard time': 'America/Los_Angeles',
  'mountain standard time': 'America/Denver',
  'us mountain standard time': 'America/Phoenix',
  'central standard time': 'America/Chicago',
  'eastern standard time': 'America/New_York',
  'alaskan standard time': 'America/Anchorage',
  'hawaiian standard time': 'Pacific/Honolulu',
  'utc': 'UTC',
};

/** The IANA name for a TZID, reading common Windows names too. */
function zoneOf(tzid: string): string {
  return WINDOWS_ZONES[tzid.trim().toLowerCase()] ?? tzid;
}

/**
 * Where a start time was written, when that is not campus time: "UTC" for a trailing Z, or the
 * TZID's zone. Null when the time is already campus time (or the zone name is not understood).
 */
function readSource(value: string, params: Record<string, string>): ScheduleEvent['source'] | null {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z?)$/.exec(value.trim());
  if (!m || params.VALUE === 'DATE') return null;
  const zone = m[7] === 'Z' ? 'UTC' : params.TZID ? zoneOf(params.TZID) : null;
  if (!zone || zone === CAMPUS_TIME_ZONE) return null;
  try {
    wallClock(0, zone); // throws for a zone name the browser does not know
  } catch {
    return null;
  }
  return { zone, date: `${m[1]}-${m[2]}-${m[3]}`, minutes: Number(m[4]) * 60 + Number(m[5]) };
}

/**
 * A DATE-TIME value as a campus-time reading, or null for date-only or unreadable values.
 * "Z" means UTC, a TZID names its zone, and no marker means the time is already campus time.
 */
function readDateTime(value: string, params: Record<string, string>): Local | null {
  if (params.VALUE === 'DATE') return null;
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z?)$/.exec(value.trim());
  if (!m) return null;
  const local: Local = { date: `${m[1]}-${m[2]}-${m[3]}`, minutes: Number(m[4]) * 60 + Number(m[5]) };
  try {
    if (m[7] === 'Z') return wallClock(instantOf(local, 'UTC'), CAMPUS_TIME_ZONE);
    const zone = params.TZID ? zoneOf(params.TZID) : null;
    if (zone && zone !== CAMPUS_TIME_ZONE) return wallClock(instantOf(local, zone), CAMPUS_TIME_ZONE);
  } catch {
    // Unknown zone name: read the time as campus time
  }
  return local;
}

/** "20261125" as "2026-11-25", or null if the value is not a bare date. */
function readDateOnly(value: string): string | null {
  const m = /^(\d{4})(\d{2})(\d{2})$/.exec(value.trim());
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null;
}

/** A date for an EXDATE or RECURRENCE-ID value, which may be a bare date or a date-time. */
function readDateValue(value: string, params: Record<string, string>): string | null {
  return readDateOnly(value) ?? readDateTime(value, params)?.date ?? null;
}

/**
 * How many days converting a date-time to campus time moved its date (for example -1 when
 * 01:00 UTC on a Tuesday is Monday evening in California). A repeat rule's weekdays are written
 * in the same zone as the start time, so they move by the same amount.
 */
function campusDayShift(value: string, params: Record<string, string>): number {
  const sourceDate = readDateOnly(value.trim().slice(0, 8));
  const campus = readDateTime(value, params);
  if (!sourceDate || !campus) return 0;
  return dayNumber(campus.date) - dayNumber(sourceDate);
}

function total(local: Local): number {
  return dayNumber(local.date) * MINUTES_PER_DAY + local.minutes;
}

function readRule(value: string, start: Local, weekdayShift: number): WeeklyRule | null {
  const parts: Record<string, string> = {};
  value.split(';').forEach((kv) => {
    const eq = kv.indexOf('=');
    if (eq > 0) parts[kv.slice(0, eq).toUpperCase()] = kv.slice(eq + 1);
  });
  if (parts.FREQ !== 'WEEKLY') return null;

  const byDay = (parts.BYDAY ?? '')
    .split(',')
    .map((code) => WEEKDAY_CODES.indexOf(code.slice(-2).toUpperCase() as (typeof WEEKDAY_CODES)[number]))
    .filter((n) => n >= 0)
    // Weekdays are in the start time's own zone; move them to campus time with the start
    .map((n) => (((n + weekdayShift) % 7) + 7) % 7);
  let untilTotal: number | null = null;
  if (parts.UNTIL) {
    const dateOnly = /^(\d{4})(\d{2})(\d{2})$/.exec(parts.UNTIL);
    const until = dateOnly
      ? { date: `${dateOnly[1]}-${dateOnly[2]}-${dateOnly[3]}`, minutes: MINUTES_PER_DAY - 1 }
      : readDateTime(parts.UNTIL, {});
    if (until) untilTotal = total(until);
  }
  const interval = Number(parts.INTERVAL);
  const count = Number(parts.COUNT);
  return {
    interval: Number.isInteger(interval) && interval > 0 ? interval : 1,
    byDay: byDay.length > 0 ? byDay : [weekdayOf(dayNumber(start.date))],
    untilTotal,
    count: Number.isInteger(count) && count > 0 ? count : null,
  };
}

/** The timed events in an .ics file (empty if it is not a calendar or has none). */
export function parseIcs(text: string, now: Date = new Date()): ScheduleEvent[] {
  const events: ScheduleEvent[] = [];
  /** Dates of single sessions that were changed or cancelled, keyed by the repeating class's UID. */
  const skipped: Array<{ uid: string; date: string }> = [];
  let current: Line[] | null = null;
  for (const line of readLines(text)) {
    if (line.name === 'BEGIN' && line.value.toUpperCase() === 'VEVENT') {
      current = [];
    } else if (line.name === 'END' && line.value.toUpperCase() === 'VEVENT') {
      const parsed = current ? readEvent(current, events.length) : null;
      if (parsed) {
        // A changed or cancelled session replaces that day's normal one in the repeating class
        if (parsed.replacesDate) skipped.push({ uid: parsed.event?.id ?? parsed.uid, date: parsed.replacesDate });
        if (parsed.event) events.push(parsed.event);
      }
      current = null;
    } else if (current) {
      current.push(line);
    }
  }
  skipped.forEach(({ uid, date }) =>
    events.filter((e) => e.id === uid && e.rule).forEach((e) => e.exdates.push(date))
  );
  return events.length > MAX_EVENTS ? withoutOldEvents(events, now).slice(0, MAX_EVENTS) : events;
}

/**
 * For a huge calendar (personal exports hold many non-class events): drop the single events and
 * finished repeats from well before today, so the cap never cuts this term's classes.
 */
function withoutOldEvents(events: ScheduleEvent[], now: Date): ScheduleEvent[] {
  const cutoff = dayNumber(wallClock(now.getTime(), CAMPUS_TIME_ZONE).date) - STALE_EVENT_DAYS;
  return events.filter((e) =>
    e.rule ? e.rule.untilTotal === null || Math.floor(e.rule.untilTotal / MINUTES_PER_DAY) >= cutoff : dayNumber(e.date) >= cutoff
  );
}

interface ReadEvent {
  /** Null for a cancelled event, which only removes a session. */
  event: ScheduleEvent | null;
  uid: string;
  /** For a changed or cancelled single session: the day it replaces in the repeating class. */
  replacesDate: string | null;
}

function readEvent(lines: Line[], index: number): ReadEvent | null {
  const get = (name: string) => lines.find((l) => l.name === name);
  const dtstart = get('DTSTART');
  const start = dtstart ? readDateTime(dtstart.value, dtstart.params) : null;
  if (!start) return null;

  const dtend = get('DTEND');
  const end = dtend ? readDateTime(dtend.value, dtend.params) : null;
  const length = end ? total(end) - total(start) : 0;

  const exdates: string[] = [];
  lines
    .filter((l) => l.name === 'EXDATE')
    .forEach((l) =>
      l.value.split(',').forEach((v) => {
        const d = readDateValue(v, l.params);
        if (d) exdates.push(d);
      })
    );
  const rrule = get('RRULE');
  const uid = get('UID')?.value.trim() || `event-${index}`;
  const recurrenceId = get('RECURRENCE-ID');
  const replacesDate = recurrenceId ? readDateValue(recurrenceId.value, recurrenceId.params) : null;
  if (get('STATUS')?.value.trim().toUpperCase() === 'CANCELLED') {
    return { event: null, uid, replacesDate };
  }

  const event: ScheduleEvent = {
    id: uid,
    title: unescapeText(get('SUMMARY')?.value ?? '') || 'Class',
    location: unescapeText(get('LOCATION')?.value ?? ''),
    date: start.date,
    startMinutes: start.minutes,
    durationMinutes: length > 0 ? length : DEFAULT_DURATION_MINUTES,
    rule: rrule ? readRule(rrule.value, start, dtstart ? campusDayShift(dtstart.value, dtstart.params) : 0) : null,
    exdates,
  };
  const source = rrule && dtstart ? readSource(dtstart.value, dtstart.params) : null;
  if (event.rule && source) event.source = source;
  return { event, uid, replacesDate };
}

/* ---------- Expanding to a day ---------- */

function occursOn(event: ScheduleEvent, day: number): boolean {
  const first = dayNumber(event.date);
  if (!event.rule) return day === first;
  if (day < first) return false;

  const { interval, byDay, untilTotal, count } = event.rule;
  const matches = (d: number) =>
    byDay.includes(weekdayOf(d)) && Math.floor((mondayOf(d) - mondayOf(first)) / 7) % interval === 0;

  if (!matches(day) && day !== first) return false;
  if (event.exdates.includes(dateOfDayNumber(day))) return false;
  if (untilTotal !== null && day * MINUTES_PER_DAY + event.startMinutes > untilTotal) return false;
  if (count !== null) {
    if (day - first > MAX_COUNT_SCAN_DAYS) return false;
    let seen = 0;
    for (let d = first; d <= day; d += 1) if (d === first || matches(d)) seen += 1;
    if (seen > count) return false;
  }
  return true;
}

/**
 * When the class starts on this campus day. A repeating class written in UTC or another zone keeps
 * its time there, so after daylight saving changes its campus time shifts by an hour.
 */
export function startOn(event: ScheduleEvent, date: string): number {
  const { source } = event;
  if (!source || !event.rule) return event.startMinutes;
  try {
    // The week's source-zone date is the campus date moved by the same days as the first session
    const shift = dayNumber(event.date) - dayNumber(source.date);
    const sourceDate = dateOfDayNumber(dayNumber(date) - shift);
    return wallClock(instantOf({ date: sourceDate, minutes: source.minutes }, source.zone), CAMPUS_TIME_ZONE).minutes;
  } catch {
    return event.startMinutes;
  }
}

/** The classes on one day ("YYYY-MM-DD"), earliest first. */
export function classesOn(events: ScheduleEvent[], date: string): ClassSession[] {
  const day = dayNumber(date);
  if (Number.isNaN(day)) return [];
  const seen = new Set<string>();
  return events
    .filter((e) => occursOn(e, day))
    .map((e) => ({ e, start: startOn(e, date) }))
    .filter(({ e, start }) => {
      // The same class listed twice (copied calendars) is shown once
      const key = `${e.title}|${start}|${e.location}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(({ e, start }) => ({
      id: e.id,
      title: e.title,
      location: e.location,
      date,
      startMinutes: start,
      endMinutes: start + e.durationMinutes,
    }))
    .sort((a, b) => a.startMinutes - b.startMinutes || a.title.localeCompare(b.title));
}
