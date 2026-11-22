/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from 'react';
import type { LatLng, TravelMode } from '../api/routes.ts';
import { planRoutes } from '../utils/routePlan.ts';
import { initialLegState, loadLeg, needsRequest, type LegState } from '../utils/routeLoader.ts';

export type { LegState };
export type RouteLegs = Record<TravelMode, LegState>;

const IDLE: RouteLegs = { driving: { status: 'idle' }, walking: { status: 'idle' } };

/**
 * Loads driving and walking routes for the chosen parking location. Changing the
 * lot, destination or start cancels requests for the old choice.
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
  const [legs, setLegs] = useState<RouteLegs>(IDLE);
  // Primitive deps so a new object with the same coordinates does not refetch
  const key = [lot, destination, start].map((p) => (p ? `${p.latitude},${p.longitude}` : '-')).join(';');

  useEffect(() => {
    if (!enabled || !lot) {
      setLegs(IDLE);
      return;
    }
    const plan = planRoutes(lot, destination, start);
    const controller = new AbortController();
    const next: RouteLegs = { driving: initialLegState(plan.driving), walking: initialLegState(plan.walking) };
    setLegs(next);

    for (const leg of [plan.driving, plan.walking]) {
      if (!needsRequest(leg)) continue;
      loadLeg(leg.trip, { signal: controller.signal })
        .then((state) => {
          if (controller.signal.aborted) return;
          setLegs((prev) => ({ ...prev, [leg.mode]: state }));
        })
        .catch(() => {
          // Cancelled by a newer choice; that choice owns the state.
        });
    }
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` covers the coordinates
  }, [enabled, key, retryToken]);

  return legs;
}
