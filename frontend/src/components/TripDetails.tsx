/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Car, ChevronDown, CloudSun, Construction, Footprints, LocateFixed, Loader2, RefreshCw, X } from 'lucide-react';
import type { AlertSource } from '../api/tripAlerts.ts';
import type { AlertsState } from '../hooks/useTripAlerts.ts';
import type { LegState, RouteLegs } from '../hooks/useRoutes.ts';
import {
  constructionSummary,
  isCompleteAlerts,
  describeForecast,
  emptySourceMessage,
  formatAlertTime,
  matchLabel,
  NEARBY_DISTANCE_TEXT,
  sourceNote,
  weatherSummary,
} from '../utils/alertFormat.ts';
import { OSM_FIX_THE_MAP_URL } from '../api/routes.ts';
import { formatDistance, formatDuration, NO_START, ROUTE_COLORS } from '../utils/routePlan.ts';

interface TripDetailsProps {
  /** The first-choice card is navy; the others are white. */
  tone: 'dark' | 'light';
  destinationName: string;
  legs: RouteLegs;
  /** Walk time from the ranking estimate, shown if the mapped walking route is missing. */
  fallbackWalkMinutes: number | null;
  /** Label for the current driving start, or null when none is set. */
  startLabel: string | null;
  isLocating: boolean;
  locateError: string | null;
  onUseMyLocation: () => void;
  onClearStart: () => void;
  onRetryRoutes: () => void;
  alerts: AlertsState;
  onRetryAlerts: () => void;
}

/** Text only: source messages are never rendered as HTML. */
const SourceBlock: React.FC<{ kind: 'weather' | 'construction'; source: AlertSource }> = ({ kind, source }) => {
  const Icon = kind === 'weather' ? CloudSun : Construction;
  const forecastLine = kind === 'weather' && source.forecast ? describeForecast(source.forecast) : '';
  const forecastTime = source.forecast ? formatAlertTime(source.forecast.forecast_time) : null;
  const checked = formatAlertTime(source.last_checked_at);
  const showEmpty = source.alerts.length === 0 && !forecastLine;
  const note = sourceNote(source);
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-[12px] font-semibold text-navy">
        <Icon className="w-3.5 h-3.5" aria-hidden="true" />
        <span>{kind === 'weather' ? 'Weather' : 'Construction'}</span>
        {note && (
          <span className="ml-1 px-1.5 rounded bg-[#D98A00]/15 text-[#835300] font-medium">
            {note === 'older data' ? 'Older data' : 'Incomplete check'}
          </span>
        )}
      </div>
      {forecastLine && (
        <p className="text-[12px] text-navy leading-snug">
          {forecastTime ? `Around ${forecastTime}: ` : ''}
          {forecastLine}
        </p>
      )}
      {source.alerts.map((alert) => {
        const tag = kind === 'construction' ? matchLabel(alert.match_basis) : null;
        return (
          <p key={alert.alert_id} className="text-[12px] text-navy leading-snug">
            {tag && <span className="mr-1.5 px-1.5 rounded bg-[#D98A00]/15 text-[#835300] font-semibold">{tag}</span>}
            {alert.message}
          </p>
        );
      })}
      {source.status === 'partial' && !showEmpty && (
        <p className="text-[12px] text-muted leading-snug">
          Some of this check didn't finish, so the list above may be missing items.
        </p>
      )}
      {showEmpty && <p className="text-[12px] text-muted leading-snug">{emptySourceMessage(kind, source)}</p>}
      <p className="text-xs text-muted leading-snug">
        <a href={source.source_url} target="_blank" rel="noopener noreferrer" className="underline">
          {source.source_name}
        </a>
        {checked ? `, checked ${checked}` : ''}
      </p>
    </div>
  );
};

/**
 * What the selected parking card shows under its availability: driving and walking time
 * and distance, then weather and construction on one collapsed line that opens for the
 * full notices. Informational only; alert failures never affect the parking results.
 */
export const TripDetails: React.FC<TripDetailsProps> = ({
  tone,
  destinationName,
  legs,
  fallbackWalkMinutes,
  startLabel,
  isLocating,
  locateError,
  onUseMyLocation,
  onClearStart,
  onRetryRoutes,
  alerts,
  onRetryAlerts,
}) => {
  const dark = tone === 'dark';
  const muted = dark ? 'text-white/70' : 'text-muted';
  const strong = dark ? 'text-white' : 'text-navy';
  const link = dark ? 'text-sun hover:underline' : 'text-navy hover:underline';
  const routingOff = [legs.driving, legs.walking].some((leg) => leg.status === 'unavailable');
  const anyError = legs.driving.status === 'error' || legs.walking.status === 'error';

  return (
    // Taps inside the details must not re-select the card
    <div className="mt-3 space-y-3" onClick={(e) => e.stopPropagation()}>
      <div className="space-y-2">
        <Row
          icon={<Car className="w-5 h-5" aria-hidden="true" style={{ color: dark ? '#FFCD00' : ROUTE_COLORS.driving }} />}
          label={startLabel ? 'Drive from you' : 'Drive'}
          showSkipReason
          state={routingOff ? { status: 'idle' } : legs.driving}
          strong={strong}
          muted={muted}
          emptyHint={
            routingOff ? (
              <span className={`text-[12px] ${muted}`}>Not available right now</span>
            ) : (
              <button
                type="button"
                onClick={onUseMyLocation}
                disabled={isLocating}
                className={`text-[12px] font-semibold inline-flex items-center gap-1 cursor-pointer disabled:opacity-60 ${link}`}
              >
                {isLocating ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <LocateFixed className="w-3.5 h-3.5" aria-hidden="true" />
                )}
                {isLocating ? 'Finding you…' : 'Use my location for drive time'}
              </button>
            )
          }
          action={
            startLabel && !routingOff ? (
              <button
                type="button"
                onClick={onClearStart}
                aria-label="Clear starting point"
                className={`inline-flex items-center justify-center min-w-[32px] min-h-[32px] rounded cursor-pointer ${muted} hover:opacity-80`}
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            ) : null
          }
        />
        {locateError && (
          <p role="alert" className={`text-[12px] pl-7 ${dark ? 'text-[#FFB4AB]' : 'text-[#A12116]'}`}>
            {locateError}
          </p>
        )}
        <Row
          icon={<Footprints className="w-5 h-5" aria-hidden="true" style={{ color: dark ? '#FFCD00' : ROUTE_COLORS.walking }} />}
          label={`Walk to ${destinationName}`}
          state={routingOff ? { status: 'idle' } : legs.walking}
          strong={strong}
          muted={muted}
          emptyHint={
            fallbackWalkMinutes === null ? (
              <span className={`text-[12px] ${muted}`}>Walk time unavailable</span>
            ) : (
              <span className={`text-[13px] ${strong}`}>
                <span className="font-serif font-semibold tabular-nums text-[20px]">{fallbackWalkMinutes} min</span>
                <span className={muted}> estimate</span>
              </span>
            )
          }
        />
        {anyError && (
          <button
            type="button"
            onClick={onRetryRoutes}
            className={`text-[12px] font-semibold inline-flex items-center gap-1 pl-7 cursor-pointer ${link}`}
          >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Try directions again
          </button>
        )}
      </div>

      {(legs.driving.status === 'ok' || legs.walking.status === 'ok') && (
        <p className={`text-xs leading-snug ${muted}`}>
          Typical times, not live traffic. The parking end is the lot's map point, not a verified entrance.{' '}
          {okAttribution(legs)}{' '}
          <a href={OSM_FIX_THE_MAP_URL} target="_blank" rel="noopener noreferrer" className="underline">
            Fix the map
          </a>
        </p>
      )}

      <AlertsLine alerts={alerts} onRetry={onRetryAlerts} dark={dark} muted={muted} strong={strong} />
    </div>
  );
};

/** The OpenStreetMap credit from the first route that loaded, as its provider words it. */
function okAttribution(legs: RouteLegs): string {
  for (const leg of [legs.driving, legs.walking]) {
    if (leg.status === 'ok' && leg.route.attribution) return leg.route.attribution;
  }
  return '';
}

/** One leg: icon, label, and "12 min · 4.2 mi" (or its loading, error or empty state). */
const Row: React.FC<{
  icon: React.ReactNode;
  label: string;
  state: LegState;
  strong: string;
  muted: string;
  /** Shown when there is no route to show (not requested, or routing off). */
  emptyHint: React.ReactNode;
  action?: React.ReactNode;
  /** Say why a leg was skipped (no map point for the lot), unless a start point is simply missing. */
  showSkipReason?: boolean;
}> = ({ icon, label, state, strong, muted, emptyHint, action, showSkipReason = false }) => (
  <div className="flex items-start gap-2">
    <span className="mt-0.5 shrink-0">{icon}</span>
    <div className="min-w-0 flex-1">
      <div className="flex items-center justify-between gap-2">
        <span className={`text-[12px] truncate ${muted}`}>{label}</span>
        {action}
      </div>
      {state.status === 'ok' ? (
        <p className={`text-[13px] ${strong}`}>
          <span className="font-serif font-semibold tabular-nums text-[20px]">{formatDuration(state.route.duration_minutes)}</span>
          <span className={muted}> · {formatDistance(state.route.distance_miles)}</span>
        </p>
      ) : state.status === 'loading' ? (
        <p className={`text-[12px] inline-flex items-center gap-1 ${muted}`} role="status">
          <Loader2 className="w-3.5 h-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" /> Loading route…
        </p>
      ) : state.status === 'error' ? (
        <p className={`text-[12px] ${muted}`}>{state.message}</p>
      ) : showSkipReason && state.status === 'skipped' && state.message !== NO_START ? (
        <p className={`text-[12px] ${muted}`}>{state.message}</p>
      ) : (
        emptyHint
      )}
    </div>
  </div>
);

/** Weather and construction on one collapsed line; opens for the full notices and sources. */
const AlertsLine: React.FC<{
  alerts: AlertsState;
  onRetry: () => void;
  dark: boolean;
  muted: string;
  strong: string;
}> = ({ alerts, onRetry, dark, muted, strong }) => {
  if (alerts.status === 'idle') return null;
  const border = dark ? 'border-white/20' : 'border-line';
  if (alerts.status === 'unavailable') {
    return <p className={`pt-2.5 border-t text-[12px] ${border} ${muted}`}>{alerts.message}</p>;
  }
  if (alerts.status === 'loading') {
    return (
      <p className={`pt-2.5 border-t flex items-center gap-1.5 text-[12px] ${border} ${muted}`} role="status">
        <Loader2 className="w-3.5 h-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        Checking weather and construction…
      </p>
    );
  }
  if (alerts.status === 'error') {
    return (
      <div className={`pt-2.5 border-t flex items-center justify-between gap-2 text-[12px] ${border} ${muted}`}>
        <span>{alerts.message}</span>
        <button
          type="button"
          onClick={onRetry}
          className={`shrink-0 inline-flex items-center gap-1 px-2 min-h-[32px] rounded-lg border font-semibold cursor-pointer ${
            dark ? 'border-white/30 text-white hover:bg-white/10' : 'border-line text-navy hover:bg-paper'
          }`}
        >
          <RefreshCw className="w-3 h-3" aria-hidden="true" />
          Try again
        </button>
      </div>
    );
  }
  const { weather, construction, limitations } = alerts.alerts;
  const notes = [...limitations, ...weather.limitations, ...construction.limitations].filter(
    (note, i, all) => all.indexOf(note) === i
  );
  return (
    <details className={`group pt-2.5 border-t ${border}`}>
      <summary
        className={`flex items-center gap-2 min-h-[32px] cursor-pointer list-none text-[12px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-sky ${strong}`}
      >
        <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5 min-w-0 flex-1">
          <span className="inline-flex items-center gap-1">
            <CloudSun className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
            {weatherSummary(weather)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Construction className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
            {constructionSummary(construction)}
          </span>
        </span>
        <ChevronDown className="w-4 h-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="mt-2 p-2.5 rounded-lg bg-white space-y-2.5">
        <SourceBlock kind="weather" source={weather} />
        <SourceBlock kind="construction" source={construction} />
        <ul className="space-y-1 list-disc pl-4 text-xs text-muted leading-snug">
          <li>Weather tips are ParkSmart walking-comfort suggestions, not official warnings.</li>
          <li>Rain is for the hour before the time shown.</li>
          <li>
            Construction is listed when it is active at your arrival time and within {NEARBY_DISTANCE_TEXT} of the
            parking location or your destination, not along the whole route. Nearby does not mean a lot is closed or a
            route is blocked.
          </li>
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
        {!isCompleteAlerts(alerts.alerts) && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1 px-2 min-h-[32px] rounded-lg border border-line text-navy text-[12px] font-semibold cursor-pointer hover:bg-paper"
          >
            <RefreshCw className="w-3 h-3" aria-hidden="true" />
            Check again
          </button>
        )}
      </div>
    </details>
  );
};
