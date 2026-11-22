/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from 'react';
import type { LatLng, TravelMode } from '../api/routes.ts';
import { planRoutes, tripKey, type PlannedLeg } from '../utils/routePlan.ts';
import { initialLegState, loadLeg, needsRequest, type LegState } from '../utils/routeLoader.ts';

export type { LegState };
export type RouteLegs = Record<TravelMode, LegState>;

/**
 * Loads driving and walking routes for the chosen parking location. Changing the lot or
 * destination cancels the walking request for the old choice; changing the lot or the start
 * cancels the driving one. Each leg has its own request, so a start point arriving late (the
 * browser's location) never cancels and resends the walking route.
 *
 * @param enabled false keeps everything idle (sample mode has no backend).
 * @param lot chosen parking location's map point, or null when nothing is chosen.
 */
export function useRoutes(
  enabled: boolean,
  lot: LatLng | null,
  destination: LatLng | null,
  start: LatLng | null,
  retryToken = 0
): RouteLegs {
  const plan = enabled && lot ? planRoutes(lot, destination, start) : null;
  return {
    driving: useLeg(plan?.driving ?? null, retryToken),
    walking: useLeg(plan?.walking ?? null, retryToken),
  };
}

const IDLE_LEG: LegState = { status: 'idle' };

/** One leg's state. It asks again only when this leg's own trip changes (or on a retry). */
function useLeg(leg: PlannedLeg | null, retryToken: number): LegState {
  const [state, setState] = useState<LegState>(IDLE_LEG);
  // Primitive key, so a new object for the same trip never refetches
  const key = leg === null ? '' : 'trip' in leg ? tripKey(leg.trip) : `skipped:${leg.skipped}`;

  useEffect(() => {
    if (leg === null) {
      setState(IDLE_LEG);
      return;
    }
    setState(initialLegState(leg));
    if (!needsRequest(leg)) return;
    const controller = new AbortController();
    loadLeg(leg.trip, { signal: controller.signal })
      .then((next) => {
        if (!controller.signal.aborted) setState(next);
      })
      .catch(() => {
        // Cancelled by a newer choice; that choice owns the state.
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` covers this leg's trip
  }, [key, retryToken]);

  return state;
}
