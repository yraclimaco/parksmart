/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ParkingPlannerRequest } from '../types.ts';
import { parseArrival } from './permitRules.ts';

/** How far in the past an arrival can be before we flag it (covers "I filled this in a bit ago"). */
export const PAST_ARRIVAL_GRACE_MINUTES = 15;

/** Farthest ahead an arrival can be planned (the sample model has no data beyond this). */
export const MAX_ARRIVAL_DAYS_AHEAD = 365;

/** Latest allowed arrival date as "YYYY-MM-DD" (local time), for the date input's max. */
export function maxArrivalDate(now: Date = new Date()): string {
  const d = new Date(now);
  d.setDate(d.getDate() + MAX_ARRIVAL_DAYS_AHEAD);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Returns a user-facing problem with the arrival date/time, or null if it is fine. */
export function getArrivalError(
  request: Pick<ParkingPlannerRequest, 'arrivalDate' | 'arrivalTime'>,
  now: Date = new Date()
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
