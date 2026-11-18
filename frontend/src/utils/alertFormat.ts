/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { AlertSource, WeatherForecast } from '../api/tripAlerts.ts';

const UCSD_TIME_ZONE = 'America/Los_Angeles';
const MM_PER_INCH = 25.4;
const MPH_PER_KMH = 0.621371;

/**
 * How close a construction notice must be to the parking lot or destination to be listed.
 * Mirrors the backend's 200 m advisory buffer (docs/construction_source.md); it is a
 * matching choice, not a measured impact radius.
 */
export const NEARBY_DISTANCE_TEXT = 'about 650 ft (200 m)';

export const celsiusToFahrenheit = (c: number): number => (c * 9) / 5 + 32;
export const kmhToMph = (kmh: number): number => kmh * MPH_PER_KMH;

/** "Nov 18, 10:00 AM" in UCSD time, or null if the timestamp is not a real date. */
export function formatAlertTime(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString('en-US', {
    timeZone: UCSD_TIME_ZONE,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * One line for the hourly forecast. Unknown values are left out, never shown as zero.
 * Rain describes the hour BEFORE the forecast time (the backend's exact-hour rule).
 */
export function describeForecast(forecast: WeatherForecast): string {
  const parts: string[] = [];
  if (forecast.temperature_c !== null) {
    let temp = `${Math.round(celsiusToFahrenheit(forecast.temperature_c))}°F`;
    if (forecast.apparent_temperature_c !== null) {
      temp += ` (feels like ${Math.round(celsiusToFahrenheit(forecast.apparent_temperature_c))}°F)`;
    }
    parts.push(temp);
  }
  if (forecast.wind_speed_kmh !== null) {
    parts.push(`wind ${Math.round(kmhToMph(forecast.wind_speed_kmh))} mph`);
  }
  const rain: string[] = [];
  if (forecast.precipitation_probability_percent !== null) {
    rain.push(`${Math.round(forecast.precipitation_probability_percent)}% chance of rain`);
  }
  if (forecast.precipitation_mm !== null && forecast.precipitation_mm > 0) {
    rain.push(`${(forecast.precipitation_mm / MM_PER_INCH).toFixed(2)} in`);
  }
  if (rain.length > 0) parts.push(`${rain.join(', ')} in the hour before`);
  return parts.join(' · ');
}

/**
 * What to say when a source has nothing to list. Never an all-clear unless the backend
 * checked fresh data and found nothing; unavailable and stale data say so instead.
 */
export function emptySourceMessage(kind: 'weather' | 'construction', source: AlertSource): string {
  switch (source.status) {
    case 'no_relevant':
      return `No published construction notices matched within ${NEARBY_DISTANCE_TEXT} of the parking location or your destination. That doesn't prove there is none.`;
    case 'out_of_range':
      return 'No forecast for this date yet. Forecasts only reach about two weeks ahead.';
    case 'missing_location':
      return `We couldn't check ${kind} for this location.`;
    case 'unavailable':
      return kind === 'weather' ? "Weather isn't available right now." : "Construction notices aren't available right now.";
    case 'stale':
      return kind === 'weather' ? 'No weather suggestions in the last saved forecast.' : 'No matching notices in the last saved list.';
    default:
      return kind === 'weather' ? 'No weather suggestions for this arrival.' : 'No construction notices matched.';
  }
}

/**
 * Short tag for how a construction notice matched: inside the mapped work area, or only
 * nearby. Null for anything else (weather, or a basis the backend adds later), so an
 * unknown value never gets a made-up label.
 */
export function matchLabel(basis: string | null): string | null {
  if (basis === 'intersects_geometry') return 'At this location';
  if (basis === 'within_200m') return `Within ${NEARBY_DISTANCE_TEXT}`;
  return null;
}
