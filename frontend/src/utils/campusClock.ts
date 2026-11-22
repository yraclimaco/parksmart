/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

const CAMPUS_ZONE = 'America/Los_Angeles';

const formatter = new Intl.DateTimeFormat('en-US', {
  timeZone: CAMPUS_ZONE,
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

/**
 * "Now" on the UCSD campus, as a Date whose local getters (getHours, getDate, ...) read campus time.
 * Arrival times in the planner, the backend and the weather request are all campus time, so a visitor
 * planning from another time zone must not get their own clock as the default. Only for reading the
 * fields: do not use its getTime() as an instant.
 */
export function campusNow(now: Date = new Date()): Date {
  const p: Record<string, string> = {};
  formatter.formatToParts(now).forEach((part) => {
    p[part.type] = part.value;
  });
  return new Date(Number(p.year), Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute), Number(p.second));
}
