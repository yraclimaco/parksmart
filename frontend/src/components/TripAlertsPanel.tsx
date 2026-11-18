/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CloudSun, Construction, Loader2, RefreshCw } from 'lucide-react';
import type { AlertSource } from '../api/tripAlerts.ts';
import type { AlertsState } from '../hooks/useTripAlerts.ts';
import { describeForecast, emptySourceMessage, formatAlertTime } from '../utils/alertFormat.ts';

interface TripAlertsPanelProps {
  lotName: string;
  state: AlertsState;
  onRetry: () => void;
}

/** Text only: source messages are never rendered as HTML. */
const SourceBlock: React.FC<{ kind: 'weather' | 'construction'; source: AlertSource }> = ({ kind, source }) => {
  const Icon = kind === 'weather' ? CloudSun : Construction;
  const forecastLine =
    kind === 'weather' && source.forecast ? describeForecast(source.forecast) : '';
  const forecastTime = source.forecast ? formatAlertTime(source.forecast.forecast_time) : null;
  const checked = formatAlertTime(source.last_checked_at);
  const showEmpty = source.alerts.length === 0 && !forecastLine;
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-[12px] font-semibold text-navy">
        <Icon className="w-3.5 h-3.5" aria-hidden="true" />
        <span>{kind === 'weather' ? 'Weather' : 'Construction'}</span>
        {source.status === 'stale' && (
          <span className="ml-1 px-1.5 rounded bg-[#D98A00]/15 text-[#835300] font-medium">Older data</span>
        )}
      </div>
      {forecastLine && (
        <p className="text-[12px] text-navy leading-snug">
          {forecastTime ? `Around ${forecastTime}: ` : ''}
          {forecastLine}
        </p>
      )}
      {source.alerts.map((alert) => (
        <p key={alert.alert_id} className="text-[12px] text-navy leading-snug">
          {alert.message}
        </p>
      ))}
      {showEmpty && <p className="text-[12px] text-muted leading-snug">{emptySourceMessage(kind, source)}</p>}
      <p className="text-[11px] text-muted leading-snug">
        <a href={source.source_url} target="_blank" rel="noopener noreferrer" className="underline">
          {source.source_name}
        </a>
        {checked ? `, checked ${checked}` : ''}
      </p>
    </div>
  );
};

/**
 * Forecast weather and published construction notices for the chosen parking location.
 * Informational only: it never changes the ranking, and every state that is not a fresh
 * result says so instead of reading as "all clear".
 */
export const TripAlertsPanel: React.FC<TripAlertsPanelProps> = ({ lotName, state, onRetry }) => {
  if (state.status === 'idle') return null;
  if (state.status === 'unavailable') {
    return (
      <section aria-label="Trip alerts" className="px-3 py-2.5 rounded-xl bg-white border border-line text-[12px] text-muted">
        {state.message}
      </section>
    );
  }
  return (
    <section aria-label={`Trip alerts for ${lotName}`} className="p-3 rounded-xl bg-white border border-line space-y-2.5">
      <h3 className="text-[13px] font-semibold text-navy leading-snug">Trip alerts near {lotName}</h3>
      {state.status === 'loading' && (
        <p className="flex items-center gap-1.5 text-[12px] text-muted" role="status">
          <Loader2 className="w-3.5 h-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          Checking weather and construction…
        </p>
      )}
      {state.status === 'error' && (
        <div className="flex items-center justify-between gap-2 text-[12px] text-muted">
          <span>{state.message}</span>
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-line text-navy font-semibold hover:bg-paper focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/50 cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" aria-hidden="true" />
            Try again
          </button>
        </div>
      )}
      {state.status === 'ok' && (
        <>
          <SourceBlock kind="weather" source={state.alerts.weather} />
          <SourceBlock kind="construction" source={state.alerts.construction} />
          <details className="text-[11px] text-muted leading-snug">
            <summary className="cursor-pointer">About these alerts</summary>
            <ul className="mt-1 space-y-1 list-disc pl-4">
              <li>Weather tips are ParkSmart walking-comfort suggestions, not official warnings.</li>
              <li>Rain is for the hour before the time shown.</li>
              <li>Nearby construction does not mean a lot is closed or a route is blocked.</li>
              {[...state.alerts.limitations, ...state.alerts.weather.limitations, ...state.alerts.construction.limitations]
                .filter((note, i, all) => all.indexOf(note) === i)
                .map((note) => (
                  <li key={note}>{note}</li>
                ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
};
