import { describe, expect, it } from 'vitest';
import { NEARLY_FULL_MAX, PLENTY_THRESHOLD, availabilityStatus } from './availability.ts';

describe('availabilityStatus', () => {
  it('buckets percentages at the thresholds', () => {
    expect(availabilityStatus(100).level).toBe('plenty');
    expect(availabilityStatus(PLENTY_THRESHOLD).level).toBe('plenty');
    expect(availabilityStatus(PLENTY_THRESHOLD - 1).level).toBe('filling');
    expect(availabilityStatus(NEARLY_FULL_MAX + 1).level).toBe('filling');
    expect(availabilityStatus(NEARLY_FULL_MAX).level).toBe('nearlyFull');
    expect(availabilityStatus(0).level).toBe('nearlyFull');
  });

  it('matches the backend: "Often nearly full" means 10% open or less', () => {
    // src/ranking.py NEAR_FULL_FRACTION = 0.10 in the ParkSmart backend
    expect(NEARLY_FULL_MAX).toBe(10);
    expect(availabilityStatus(9).label).toBe('Usually full');
    expect(availabilityStatus(30).label).toBe('Getting tight');
  });
});
