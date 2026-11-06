/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { LatLng, RouteTrip, TravelMode } from '../api/routes.ts';

/** One leg to request, or the reason it can't be shown. */
export type PlannedLeg = { mode: TravelMode; trip: RouteTrip } | { mode: TravelMode; skipped: string };

const hasPoint = (point: LatLng | null | undefined): point is LatLng =>
  !!point && Number.isFinite(point.latitude) && Number.isFinite(point.longitude);

export const NO_LOT_POINT = "This parking location has no verified map point yet, so directions aren't available.";
export const NO_START = 'Add a starting point to see driving directions.';
export const NO_DESTINATION = 'Pick a destination to see walking directions.';

/**
 * Plans the two legs for a chosen parking location: driving from the start to the
 * parking location, then walking from it to the destination. The parking end is the
 * lot's map point (a building point, not a verified vehicle entrance or pedestrian
 * exit), which the backend discloses in each route's limitations.
 */
export function planRoutes(
  lot: LatLng | null,
  destination: LatLng | null,
  start: LatLng | null
): { driving: PlannedLeg; walking: PlannedLeg } {
  if (!hasPoint(lot)) {
    return { driving: { mode: 'driving', skipped: NO_LOT_POINT }, walking: { mode: 'walking', skipped: NO_LOT_POINT } };
  }
  const parking = { latitude: lot.latitude, longitude: lot.longitude };
  return {
    driving: hasPoint(start)
      ? { mode: 'driving', trip: { mode: 'driving', origin: { latitude: start.latitude, longitude: start.longitude }, destination: parking } }
      : { mode: 'driving', skipped: NO_START },
    walking: hasPoint(destination)
      ? {
          mode: 'walking',
          trip: {
            mode: 'walking',
            origin: parking,
            destination: { latitude: destination.latitude, longitude: destination.longitude },
          },
        }
      : { mode: 'walking', skipped: NO_DESTINATION },
  };
}

/** Cache key for a trip; ~1 m precision so tiny GPS jitter reuses the same route. */
export function tripKey(trip: RouteTrip): string {
  const r = (n: number) => n.toFixed(5);
  return [trip.mode, r(trip.origin.latitude), r(trip.origin.longitude), r(trip.destination.latitude), r(trip.destination.longitude)].join('|');
}

/** "9 min" / "1 hr 5 min"; rounds up so a 0.4-minute walk never shows "0 min". */
export function formatDuration(minutes: number): string {
  const total = Math.max(1, Math.ceil(minutes));
  if (total < 60) return `${total} min`;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

/** "0.5 mi" for most trips, "450 ft" for very short walks. */
export function formatDistance(miles: number): string {
  const FEET_PER_MILE = 5280;
  if (miles < 0.1) return `${Math.max(10, Math.round((miles * FEET_PER_MILE) / 10) * 10)} ft`;
  return `${miles < 10 ? miles.toFixed(1) : Math.round(miles)} mi`;
}
