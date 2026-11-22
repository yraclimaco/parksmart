import { describe, expect, it } from 'vitest';
import type { AlertSource } from '../api/tripAlerts.ts';
import {
  celsiusToFahrenheit,
  describeForecast,
  emptySourceMessage,
  formatAlertTime,
  kmhToMph,
  matchLabel,
  weatherSummary,
  constructionSummary,
  INCOMPLETE_LABEL,
  isCompleteAlerts,
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

describe('collapsed alert summaries', () => {
  const tip = { alert_id: 'a', message: 'Bring an umbrella', match_basis: null } as unknown as AlertSource['alerts'][number];

  it('weather: temperature and rain chance, leaving out what is unknown', () => {
    expect(weatherSummary({ ...source('available'), forecast })).toBe('68°F, 30% rain');
    expect(
      weatherSummary({
        ...source('available'),
        forecast: { ...forecast, temperature_c: null, precipitation_probability_percent: null },
      })
    ).toBe('No forecast details');
  });

  it('weather: counts tips, and says when data is older or missing', () => {
    expect(weatherSummary({ ...source('available'), forecast, alerts: [tip, tip] })).toBe('68°F, 30% rain, 2 tips');
    expect(weatherSummary({ ...source('stale'), forecast })).toBe('68°F, 30% rain (older data)');
    expect(weatherSummary(source('unavailable'))).toBe('Weather unavailable');
    expect(weatherSummary(source('out_of_range'))).toBe('No forecast yet');
  });

  it('construction: counts notices and never reads as an all-clear when unavailable', () => {
    expect(constructionSummary({ ...source('available'), alerts: [tip] })).toBe('1 notice nearby');
    expect(constructionSummary({ ...source('available'), alerts: [tip, tip] })).toBe('2 notices nearby');
    expect(constructionSummary(source('no_relevant'))).toBe('None found nearby');
    expect(constructionSummary(source('unavailable'))).toBe('Construction unavailable');
    expect(constructionSummary({ ...source('stale'), alerts: [] })).toBe('None found nearby (older data)');
  });
});

describe('partial checks are labeled incomplete', () => {
  const tip = { alert_id: 'a', message: 'Bring an umbrella', match_basis: null } as unknown as AlertSource['alerts'][number];

  it('collapsed weather summary says the check was incomplete', () => {
    expect(weatherSummary({ ...source('partial'), forecast })).toBe(`68°F, 30% rain (${INCOMPLETE_LABEL})`);
    expect(weatherSummary(source('partial'))).toBe(`No forecast details (${INCOMPLETE_LABEL})`);
  });

  it('collapsed construction summary never reads as "None found" without the label', () => {
    expect(constructionSummary(source('partial'))).toBe(`None found nearby (${INCOMPLETE_LABEL})`);
    expect(constructionSummary({ ...source('partial'), alerts: [tip] })).toBe(`1 notice nearby (${INCOMPLETE_LABEL})`);
  });

  it('expanded details explain that nothing listed is not an all-clear', () => {
    for (const kind of ['weather', 'construction'] as const) {
      expect(emptySourceMessage(kind, source('partial'))).toMatch(/incomplete/);
      expect(emptySourceMessage(kind, source('partial'))).toMatch(/doesn't mean there is nothing/);
    }
  });

  it('does not label complete checks', () => {
    expect(weatherSummary({ ...source('available'), forecast })).not.toMatch(/incomplete/);
    expect(constructionSummary(source('no_relevant'))).not.toMatch(/incomplete/);
  });
});

describe('isCompleteAlerts (what is kept for the visit)', () => {
  const both = (w: AlertSource['status'], c: AlertSource['status']) => ({ weather: source(w), construction: source(c) });

  it('keeps full, fresh answers', () => {
    expect(isCompleteAlerts(both('available', 'no_relevant'))).toBe(true);
    expect(isCompleteAlerts(both('available', 'available'))).toBe(true);
    expect(isCompleteAlerts(both('out_of_range', 'no_relevant'))).toBe(true);
  });

  it('does not keep a partial, older or unavailable source, so "check again" really asks again', () => {
    expect(isCompleteAlerts(both('available', 'partial'))).toBe(false);
    expect(isCompleteAlerts(both('stale', 'available'))).toBe(false);
    expect(isCompleteAlerts(both('available', 'unavailable'))).toBe(false);
  });
});
