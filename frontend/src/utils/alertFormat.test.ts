import { describe, expect, it } from 'vitest';
import type { AlertSource } from '../api/tripAlerts.ts';
import {
  celsiusToFahrenheit,
  describeForecast,
  emptySourceMessage,
  formatAlertTime,
  kmhToMph,
  matchLabel,
} from './alertFormat.ts';

const forecast = {
  forecast_time: '2026-11-18T10:00:00-08:00',
  temperature_c: 20,
  apparent_temperature_c: 18,
  precipitation_probability_percent: 30,
  precipitation_mm: 2.54,
  wind_speed_kmh: 16.09,
};

const source = (status: AlertSource['status']): AlertSource => ({
  status,
  source_name: 'x',
  source_url: 'https://example.org',
  last_checked_at: null,
  alerts: [],
  forecast: null,
  limitations: [],
});

describe('unit conversion', () => {
  it('converts Celsius and km/h', () => {
    expect(celsiusToFahrenheit(20)).toBe(68);
    expect(Math.round(kmhToMph(16.09))).toBe(10);
  });
});

describe('describeForecast', () => {
  it('writes temperature, wind and rain, and labels rain as the hour before', () => {
    expect(describeForecast(forecast)).toBe('68°F (feels like 64°F) · wind 10 mph · 30% chance of rain, 0.10 in in the hour before');
  });

  it('leaves unknown values out instead of showing zero', () => {
    const text = describeForecast({
      ...forecast,
      apparent_temperature_c: null,
      precipitation_probability_percent: null,
      precipitation_mm: null,
      wind_speed_kmh: null,
    });
    expect(text).toBe('68°F');
  });

  it('skips a zero rain amount but keeps the chance', () => {
    expect(describeForecast({ ...forecast, precipitation_mm: 0 })).toContain('30% chance of rain in the hour before');
  });
});

describe('emptySourceMessage', () => {
  it('only says nothing matched for a fresh no_relevant check, and never claims there is none', () => {
    const message = emptySourceMessage('construction', source('no_relevant'));
    expect(message).toMatch(/doesn't prove there is none/);
    expect(message).toMatch(/within about 650 ft \(200 m\)/);
  });

  it('does not read as an all-clear when a source is unavailable or stale', () => {
    for (const kind of ['weather', 'construction'] as const) {
      expect(emptySourceMessage(kind, source('unavailable'))).toMatch(/isn't available|aren't available/);
      expect(emptySourceMessage(kind, source('stale'))).toMatch(/last saved/);
    }
  });

  it('explains an out-of-range forecast', () => {
    expect(emptySourceMessage('weather', source('out_of_range'))).toMatch(/two weeks/);
  });
});

describe('formatAlertTime', () => {
  it('formats in UCSD time and rejects bad input', () => {
    expect(formatAlertTime('2026-11-18T18:00:00Z')).toMatch(/Nov 18, 10:00 AM/);
    expect(formatAlertTime(null)).toBeNull();
    expect(formatAlertTime('not a date')).toBeNull();
  });
});

describe('matchLabel', () => {
  it('tells on-site notices from nearby ones, and gives unknown bases no label', () => {
    expect(matchLabel('intersects_geometry')).toBe('At this location');
    expect(matchLabel('within_200m')).toBe('Within about 650 ft (200 m)');
    expect(matchLabel('something_new')).toBeNull();
    expect(matchLabel(null)).toBeNull();
  });
});
