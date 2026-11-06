import { describe, expect, it } from 'vitest';
import { NO_DESTINATION, NO_LOT_POINT, NO_START, formatDistance, formatDuration, planRoutes, tripKey } from './routePlan.ts';

const LOT = { latitude: 32.8776, longitude: -117.2337 };
const DEST = { latitude: 32.8811, longitude: -117.2376 };
const START = { latitude: 32.7157, longitude: -117.1611 };

describe('planRoutes', () => {
  it('drives from the start to the lot and walks from the lot to the destination', () => {
    const plan = planRoutes(LOT, DEST, START);
    expect(plan.driving).toEqual({ mode: 'driving', trip: { mode: 'driving', origin: START, destination: LOT } });
    expect(plan.walking).toEqual({ mode: 'walking', trip: { mode: 'walking', origin: LOT, destination: DEST } });
  });

  it('still walks when there is no starting point', () => {
    const plan = planRoutes(LOT, DEST, null);
    expect(plan.driving).toEqual({ mode: 'driving', skipped: NO_START });
    expect('trip' in plan.walking).toBe(true);
  });

  it('explains a lot without a verified pin instead of routing to nowhere', () => {
    const plan = planRoutes({ latitude: NaN, longitude: NaN }, DEST, START);
    expect(plan.driving).toEqual({ mode: 'driving', skipped: NO_LOT_POINT });
    expect(plan.walking).toEqual({ mode: 'walking', skipped: NO_LOT_POINT });
  });

  it('explains a missing destination', () => {
    expect(planRoutes(LOT, null, START).walking).toEqual({ mode: 'walking', skipped: NO_DESTINATION });
  });

  it('copies only coordinates, never extra lot fields', () => {
    const plan = planRoutes({ ...LOT, name: 'Gilman' } as never, DEST, null);
    if (!('trip' in plan.walking)) throw new Error('expected a trip');
    expect(plan.walking.trip.origin).toEqual(LOT);
  });
});

describe('tripKey', () => {
  it('ignores sub-metre differences but not the mode', () => {
    const trip = { mode: 'walking' as const, origin: LOT, destination: DEST };
    expect(tripKey(trip)).toBe(tripKey({ ...trip, origin: { ...LOT, latitude: LOT.latitude + 1e-7 } }));
    expect(tripKey(trip)).not.toBe(tripKey({ ...trip, mode: 'driving' }));
  });
});

describe('formatting', () => {
  it('formats durations', () => {
    expect(formatDuration(0.4)).toBe('1 min');
    expect(formatDuration(9.2)).toBe('10 min');
    expect(formatDuration(60)).toBe('1 hr');
    expect(formatDuration(65)).toBe('1 hr 5 min');
  });

  it('formats distances', () => {
    expect(formatDistance(0.05)).toBe('260 ft');
    expect(formatDistance(0.5)).toBe('0.5 mi');
    expect(formatDistance(15.3)).toBe('15 mi');
  });
});
