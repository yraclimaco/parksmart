import { describe, expect, it } from 'vitest';
import { googleMapsDirectionsUrl } from './mapsLink.ts';

describe('googleMapsDirectionsUrl', () => {
  it('builds a driving-directions link to the coordinates', () => {
    const url = new URL(googleMapsDirectionsUrl(32.8812, -117.2374));
    expect(url.origin + url.pathname).toBe('https://www.google.com/maps/dir/');
    expect(url.searchParams.get('api')).toBe('1');
    expect(url.searchParams.get('destination')).toBe('32.8812,-117.2374');
    expect(url.searchParams.get('travelmode')).toBe('driving');
  });
});
