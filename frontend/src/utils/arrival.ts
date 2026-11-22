/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ParkingPlannerRequest } from '../types.ts';
import { campusNow } from './campusClock.ts';
import { parseArrival } from './permitRules.ts';

/** How far in the past an arrival can be before we flag it (covers "I filled this in a bit ago"). */
export const PAST_ARRIVAL_GRACE_MINUTES = 15;

/** Farthest ahead an arrival can be planned (the sample model has no data beyond this). */
export const MAX_ARRIVAL_DAYS_AHEAD = 365;

/** Latest allowed arrival date as "YYYY-MM-DD" (local time), for the date input's max. */
export function maxArrivalDate(now: Date = campusNow()): string {
  const d = new Date(now);
  d.setDate(d.getDate() + MAX_ARRIVAL_DAYS_AHEAD);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Returns a user-facing problem with the arrival date/time, or null if it is fine. */
export function getArrivalError(
  request: Pick<ParkingPlannerRequest, 'arrivalDate' | 'arrivalTime'>,
  now: Date = campusNow()
): string | null {
  if (!request.arrivalDate) return 'Pick an arrival date.';
  if (!request.arrivalTime) return 'Pick an arrival time.';
  const arrival = parseArrival(request.arrivalDate, request.arrivalTime);
  if (!arrival) return 'That date or time is not valid.';
  if (arrival.getTime() < now.getTime() - PAST_ARRIVAL_GRACE_MINUTES * 60_000) {
    return 'That time has already passed. Pick a time from now on.';
  }
  if (arrival.getTime() > now.getTime() + MAX_ARRIVAL_DAYS_AHEAD * 24 * 60 * 60 * 1000) {
    return 'Pick a date within the next year.';
  }
  return null;
}

/**
 * How far ahead of the current time weather and construction are asked about when the
 * arrival is "now" or already a few minutes old. The weather source refuses past
 * arrivals ("past arrivals are not supported"), and the planner's default "Now" is the
 * current minute, which is seconds old by the time the request arrives.
 */
export const ALERT_MIN_LEAD_MINUTES = 2;

/**
 * The arrival to send to the trip-alerts backend, as local "YYYY-MM-DDTHH:mm:00". It is the
 * chosen arrival, except that a time that is already past (or about to be) is moved to just
 * ahead of now, so a trip for now still gets a forecast. Later arrivals are never changed.
 */
export function alertArrivalTime(date: string, time: string, now: Date = campusNow()): string {
  const arrival = parseArrival(date, time);
  if (!arrival) return `${date}T${time}:00`;
  const earliest = new Date(now.getTime() + ALERT_MIN_LEAD_MINUTES * 60_000);
  const use = arrival.getTime() < earliest.getTime() ? earliest : arrival;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${use.getFullYear()}-${pad(use.getMonth() + 1)}-${pad(use.getDate())}T${pad(use.getHours())}:${pad(use.getMinutes())}:00`;
}

/** A reused alert arrival must still be at least this far ahead of now, or the weather source may refuse it. */
export const ALERT_REUSE_MARGIN_MINUTES = 1;

/**
 * The arrival to send to the trip-alerts backend, keeping the one already worked out for this
 * search while it is still ahead of now (so unrelated re-renders never change the request) and
 * working it out again once it has slipped into the past. Without this, tapping another result
 * card, or retrying, minutes after a "now" search would send a past arrival, and the weather
 * source would answer "no forecast yet".
 */
export function reuseAlertArrival(
  previous: string | null,
  date: string,
  time: string,
  now: Date = campusNow()
): string {
  if (previous) {
    const at = new Date(previous).getTime(); // local time, no zone marker
    if (Number.isFinite(at) && at >= now.getTime() + ALERT_REUSE_MARGIN_MINUTES * 60_000) return previous;
  }
  return alertArrivalTime(date, time, now);
}
