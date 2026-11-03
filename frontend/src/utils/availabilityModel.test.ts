import { describe, expect, it } from 'vitest';
import { availabilityAt, tightFrom } from './availabilityModel.ts';
import { ParkingLot } from '../types.ts';

const lot = (base: number): ParkingLot => ({
  locationId: 'x', name: 'X', latitude: 0, longitude: 0,
  estimatedAvailabilityPercent: base, walkingMinutes: 5, spaceCategories: ['S'],
});
// Oct 21, 2026 is a Wednesday; Oct 24 a Saturday.
const wed = (h: number, m = 0) => new Date(2026, 9, 21, h, m);

describe('availabilityAt', () => {
  it('stays between 0 and 100', () => {
    for (let h = 0; h < 24; h++) {
      const v = availabilityAt(lot(20), wed(h));
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });
  it('is fuller at the weekday late-morning peak than early morning or evening', () => {
    expect(availabilityAt(lot(60), wed(10, 30))).toBeLessThan(availabilityAt(lot(60), wed(6)));
    expect(availabilityAt(lot(60), wed(10, 30))).toBeLessThan(availabilityAt(lot(60), wed(19)));
  });
  it('is emptier on weekends', () => {
    expect(availabilityAt(lot(60), new Date(2026, 9, 24, 10, 30))).toBeGreaterThan(availabilityAt(lot(60), wed(10, 30)));
  });
  it('makes busier lots (lower base) fuller at peak', () => {
    expect(availabilityAt(lot(45), wed(10, 30))).toBeLessThan(availabilityAt(lot(85), wed(10, 30)));
  });
});

describe('tightFrom', () => {
  it('finds a morning time for a busy lot and none on a quiet weekend', () => {
    const t = tightFrom(lot(50), wed(12));
    expect(t).not.toBeNull();
    expect(t!.getHours()).toBeLessThan(11);
    expect(tightFrom(lot(95), new Date(2026, 9, 24, 12))).toBeNull();
  });
});
