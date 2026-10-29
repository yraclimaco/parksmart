/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { PermitType, SpaceCategory } from '../types.ts';

/**
 * When each permit may park in each stall category, from the team's
 * "UCSD Parking Domain Research v1.2" (Oct 11, 2026), section 2, which cites
 * https://transportation.ucsd.edu/commute/permits/index.html and
 * https://transportation.ucsd.edu/visit/parking.html
 *
 * Simplifications (all flagged as open questions in the research doc):
 * - Ordinary stalls only: no A 24/7, reserved, accessible, SuperSaver or lot-specific rules.
 * - University holidays are treated as normal weekdays (holiday category rules unresolved).
 * - D access for non-D permits follows the published permit privileges; the Sept 18, 2026
 *   D restriction's effect on other permits is unresolved.
 * - V means the pay-station visitor permit; ParkMobile equivalence is unresolved.
 * - Only the arrival moment is checked, not the whole intended stay.
 */

/** A rule for one permit in one stall category. Times are minutes after midnight. */
type AccessRule =
  | { kind: 'always' }
  /** Weekdays: from `start` overnight until `end` next morning. Weekends: all day. */
  | { kind: 'eveningsAndWeekends'; start: number; end: number }
  /** Every day (weekends included): from `start` overnight until `end` next morning. */
  | { kind: 'eveningsDaily'; start: number; end: number };

const minutes = (h: number, m = 0) => h * 60 + m;
const ALWAYS: AccessRule = { kind: 'always' };
const evenings = (start: number, end: number): AccessRule => ({ kind: 'eveningsAndWeekends', start, end });

/** 4 PM to 8 AM on weekdays, all day on weekends: the standard upgrade window. */
const STANDARD_UPGRADE = evenings(minutes(16), minutes(8));

const RULES: Record<PermitType, Partial<Record<SpaceCategory, AccessRule>>> = {
  A: { A: ALWAYS, B: ALWAYS, S: ALWAYS, D: ALWAYS },
  B: { B: ALWAYS, S: ALWAYS, D: ALWAYS, A: STANDARD_UPGRADE },
  S: { S: ALWAYS, D: ALWAYS, A: STANDARD_UPGRADE, B: STANDARD_UPGRADE },
  SR: { SR: ALWAYS, S: ALWAYS, D: ALWAYS, A: STANDARD_UPGRADE, B: STANDARD_UPGRADE },
  D: { D: ALWAYS, A: STANDARD_UPGRADE, B: STANDARD_UPGRADE, S: STANDARD_UPGRADE },
  V: {
    V: ALWAYS,
    D: ALWAYS,
    S: evenings(minutes(16), minutes(7, 30)),
    B: evenings(minutes(16), minutes(7, 30)),
    A: { kind: 'eveningsDaily', start: minutes(17), end: minutes(7, 30) },
  },
};

function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === 0 || day === 6;
}

function ruleAllows(rule: AccessRule, date: Date): boolean {
  if (rule.kind === 'always') return true;
  const t = date.getHours() * 60 + date.getMinutes();
  const inOvernightWindow = t >= rule.start || t < rule.end;
  if (rule.kind === 'eveningsDaily') return inOvernightWindow;
  return isWeekend(date) || inOvernightWindow;
}

/** Whether `permit` may park in an ordinary `category` stall at `date`. */
export function canPark(permit: PermitType, category: SpaceCategory, date: Date): boolean {
  const rule = RULES[permit][category];
  return rule ? ruleAllows(rule, date) : false;
}

export type LotAccess =
  | { status: 'always' }
  | { status: 'until'; until: Date }
  | { status: 'from'; from: Date }
  | { status: 'never' };

/** Search step and horizon when looking for the next change in access. */
const STEP_MINUTES = 15;
const HORIZON_DAYS = 7;

function allowedInAny(permit: PermitType, categories: SpaceCategory[], date: Date): boolean {
  return categories.some((category) => canPark(permit, category, date));
}

/** Steps forward from `start` until access flips; null if it never flips within the horizon. */
function nextChange(permit: PermitType, categories: SpaceCategory[], start: Date): Date | null {
  const initial = allowedInAny(permit, categories, start);
  const t = new Date(start);
  // Align to the next step boundary so results read as clean times (4:00 PM, not 4:07 PM)
  t.setSeconds(0, 0);
  t.setMinutes(Math.floor(t.getMinutes() / STEP_MINUTES) * STEP_MINUTES + STEP_MINUTES);
  const limit = start.getTime() + HORIZON_DAYS * 24 * 60 * 60 * 1000;
  for (; t.getTime() <= limit; t.setMinutes(t.getMinutes() + STEP_MINUTES)) {
    if (allowedInAny(permit, categories, t) !== initial) return new Date(t);
  }
  return null;
}

/**
 * Whether a permit can park anywhere in a structure (given its stall categories)
 * at `arrival`, and when that changes.
 */
export function lotAccess(permit: PermitType, categories: SpaceCategory[], arrival: Date): LotAccess {
  if (categories.some((category) => RULES[permit][category]?.kind === 'always')) {
    return { status: 'always' };
  }
  const change = nextChange(permit, categories, arrival);
  if (allowedInAny(permit, categories, arrival)) {
    // A window that never ends within a week only happens with 'always' rules (handled above)
    return change ? { status: 'until', until: change } : { status: 'always' };
  }
  return change ? { status: 'from', from: change } : { status: 'never' };
}

/** Stall categories `permit` can use at `date`, for highlighting on cards. */
export function usableCategories(permit: PermitType, categories: SpaceCategory[], date: Date): SpaceCategory[] {
  return categories.filter((category) => canPark(permit, category, date));
}

/** Formats a time like "4:00 PM", adding the weekday when it is not on `reference`'s day. */
export function formatAccessTime(date: Date, reference: Date): string {
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const sameDay = date.toDateString() === reference.toDateString();
  return sameDay ? time : `${date.toLocaleDateString('en-US', { weekday: 'short' })} ${time}`;
}

/**
 * Short human-readable label, e.g. "Open 24/7 in D stalls with your S permit" or
 * "Valid until 8:00 AM". Pass the lot's stall categories so a 24/7 label names the
 * stalls that are open (a permit is rarely valid in every stall of a structure).
 */
export function accessLabel(
  access: LotAccess,
  permit: PermitType,
  arrival: Date,
  categories?: SpaceCategory[]
): string {
  switch (access.status) {
    case 'always': {
      const open = (categories ?? []).filter((category) => RULES[permit][category]?.kind === 'always');
      return open.length > 0
        ? `Open 24/7 in ${open.join(', ')} stalls with your ${permit} permit`
        : `Open 24/7 with your ${permit} permit`;
    }
    case 'until':
      return `Valid until ${formatAccessTime(access.until, arrival)}`;
    case 'from':
      return `Your ${permit} permit works here from ${formatAccessTime(access.from, arrival)}`;
    case 'never':
      return `Not valid with your ${permit} permit`;
  }
}

/** Parses the form's date ("YYYY-MM-DD") and time ("HH:MM") as local time; null if invalid. */
export function parseArrival(date: string, time: string): Date | null {
  if (!date || !time) return null;
  const parsed = new Date(`${date}T${time}`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * True when a non-D permit gets into a structure only through its D stalls. The team's
 * research (v1.2) lists the Sept 18, 2026 D restriction's effect on other permits as an
 * open question, so the app shows these picks as "needs verification" instead of certain.
 */
export function relyOnUnverifiedDAccess(permit: PermitType, categories: SpaceCategory[], arrival: Date): boolean {
  if (permit === 'D') return false;
  const usable = usableCategories(permit, categories, arrival);
  return usable.length > 0 && usable.every((category) => category === 'D');
}

/** University holidays in the fall term (month is 1-12). Category rules on these days are unconfirmed. */
const HOLIDAYS: ReadonlyArray<{ month: number; day: number; name: string }> = [
  { month: 11, day: 11, name: "Veterans Day" },
  { month: 11, day: 26, name: 'Thanksgiving' },
  { month: 11, day: 27, name: 'the day after Thanksgiving' },
  { month: 12, day: 24, name: 'Christmas Eve' },
  { month: 12, day: 25, name: 'Christmas Day' },
  { month: 12, day: 31, name: "New Year's Eve" },
  { month: 1, day: 1, name: "New Year's Day" },
];

/**
 * Notice for a university holiday, or null. The research doc (v1.2) says the parking fee
 * is waived on these days but could not confirm how stall categories are enforced, so
 * the results still use the normal weekday rules.
 */
export function holidayNotice(date: Date): string | null {
  const holiday = HOLIDAYS.find((h) => h.month === date.getMonth() + 1 && h.day === date.getDate());
  if (!holiday) return null;
  return `${holiday.name} is a university holiday. Parking fees are waived, but we could not confirm the stall category rules, so these results use normal weekday rules. Check UCSD Transportation.`;
}
