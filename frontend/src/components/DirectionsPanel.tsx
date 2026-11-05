/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Car, Footprints, LocateFixed, Loader2, RefreshCw, X } from 'lucide-react';
import type { LegState, RouteLegs } from '../hooks/useRoutes.ts';
import { formatDistance, formatDuration } from '../utils/routePlan.ts';

interface DirectionsPanelProps {
  /** Parking location the routes go to and from. */
  lotName: string;
  destinationName: string;
  legs: RouteLegs;
  /** Label for the current starting point, or null when none is set. */
  startLabel: string | null;
  isLocating: boolean;
  locateError: string | null;
  onUseMyLocation: () => void;
  onClearStart: () => void;
  onRetry: () => void;
}

/** Route colors, shared with the map's line layers. */
export const ROUTE_COLORS = { driving: '#182B49', walking: '#C69214' } as const;

/**
 * Driving and walking summary for the chosen parking location: distance and typical
 * time for each leg, the starting-point control, and every reason a leg is missing.
 */
export const DirectionsPanel: React.FC<DirectionsPanelProps> = ({
  lotName,
  destinationName,
  legs,
  startLabel,
  isLocating,
  locateError,
  onUseMyLocation,
  onClearStart,
  onRetry,
}) => {
  const unavailable = [legs.driving, legs.walking].find((leg) => leg.status === 'unavailable');
  if (unavailable && unavailable.status === 'unavailable') {
    return (
      <section aria-label="Directions" className="px-3 py-2.5 rounded-xl bg-white border border-line text-[12px] text-muted">
        {unavailable.message} Use “Open in Google Maps” for turn-by-turn directions.
      </section>
    );
  }
  const anyError = legs.driving.status === 'error' || legs.walking.status === 'error';
  const attribution = [legs.driving, legs.walking].find(
    (leg): leg is Extract<LegState, { status: 'ok' }> => leg.status === 'ok'
  )?.route.attribution;

  return (
    <section aria-label={`Directions for ${lotName}`} className="p-3 rounded-xl bg-white border border-line space-y-2.5">
      <h3 className="text-[13px] font-semibold text-navy leading-snug">Directions via {lotName}</h3>

      <Leg
        icon={<Car className="w-4 h-4" aria-hidden="true" style={{ color: ROUTE_COLORS.driving }} />}
        label={startLabel ? `Drive from ${startLabel}` : 'Drive'}
        state={legs.driving}
        action={
          startLabel ? (
            <button
              type="button"
              onClick={onClearStart}
              className="text-[12px] text-muted hover:text-navy inline-flex items-center gap-1 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" aria-hidden="true" /> Clear start
            </button>
          ) : (
            <button
              type="button"
              onClick={onUseMyLocation}
              disabled={isLocating}
              className="text-[12px] font-semibold text-navy hover:underline inline-flex items-center gap-1 cursor-pointer disabled:opacity-60"
            >
              {isLocating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <LocateFixed className="w-3.5 h-3.5" aria-hidden="true" />
              )}
              {isLocating ? 'Finding you…' : 'Use my location'}
            </button>
          )
        }
      />
      {locateError && (
        <p role="alert" className="text-[12px] text-[#A12116] pl-6">
          {locateError}
        </p>
      )}

      <Leg
        icon={<Footprints className="w-4 h-4" aria-hidden="true" style={{ color: ROUTE_COLORS.walking }} />}
        label={`Walk to ${destinationName}`}
        state={legs.walking}
      />

      {anyError && (
        <button
          type="button"
          onClick={onRetry}
          className="text-[12px] font-semibold text-navy hover:underline inline-flex items-center gap-1 pl-6 cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Try directions again
        </button>
      )}

      <p className="text-[11px] text-muted leading-snug">
        Typical travel times without live traffic. Routes use the parking location’s map point, which may not be
        its entrance. {attribution ?? ''}
      </p>
    </section>
  );
};

const Leg: React.FC<{ icon: React.ReactNode; label: string; state: LegState; action?: React.ReactNode }> = ({
  icon,
  label,
  state,
  action,
}) => (
  <div className="flex items-start gap-2">
    <span className="mt-0.5 shrink-0">{icon}</span>
    <div className="min-w-0 flex-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-ink truncate">{label}</span>
        {action}
      </div>
      <LegDetail state={state} />
    </div>
  </div>
);

const LegDetail: React.FC<{ state: LegState }> = ({ state }) => {
  switch (state.status) {
    case 'ok':
      return (
        <p className="text-[13px] text-ink">
          <span className="font-semibold">{formatDuration(state.route.duration_minutes)}</span>
          <span className="text-muted"> · {formatDistance(state.route.distance_miles)}</span>
        </p>
      );
    case 'loading':
      return (
        <p className="text-[12px] text-muted inline-flex items-center gap-1" role="status">
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" /> Loading route…
        </p>
      );
    case 'skipped':
    case 'error':
    case 'unavailable':
      return <p className={`text-[12px] ${state.status === 'error' ? 'text-[#A12116]' : 'text-muted'}`}>{state.message}</p>;
    default:
      return null;
  }
};
