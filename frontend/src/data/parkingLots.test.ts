/**
 * Sanity checks for the real parking structure list, so a typo in a
 * coordinate or a duplicated ID is caught before it reaches the map.
 */

import { describe, expect, it } from 'vitest';
import { ALL_PARKING as PARKING_LOTS } from './parkingLots.ts';

// Rough bounding box around the UCSD La Jolla campus (incl. East Campus, SIO and the Gliderport).
const CAMPUS_BOUNDS = { minLat: 32.86, maxLat: 32.9, minLng: -117.26, maxLng: -117.21 };

describe('PARKING_LOTS', () => {
  it('has unique location IDs', () => {
    const ids = PARKING_LOTS.map((lot) => lot.locationId);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it.each(PARKING_LOTS)('places $name on the La Jolla campus', (lot) => {
    expect(lot.latitude).toBeGreaterThan(CAMPUS_BOUNDS.minLat);
    expect(lot.latitude).toBeLessThan(CAMPUS_BOUNDS.maxLat);
    expect(lot.longitude).toBeGreaterThan(CAMPUS_BOUNDS.minLng);
    expect(lot.longitude).toBeLessThan(CAMPUS_BOUNDS.maxLng);
  });

  it('keeps availability between 0 and 100 percent', () => {
    for (const lot of PARKING_LOTS) {
      expect(lot.estimatedAvailabilityPercent).toBeGreaterThanOrEqual(0);
      expect(lot.estimatedAvailabilityPercent).toBeLessThanOrEqual(100);
    }
  });
});
