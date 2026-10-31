import { describe, expect, it } from 'vitest';
import { FILLING_THRESHOLD, PLENTY_THRESHOLD, availabilityStatus } from './availability.ts';

describe('availabilityStatus', () => {
  it('buckets percentages at the thresholds', () => {
    expect(availabilityStatus(100).level).toBe('plenty');
    expect(availabilityStatus(PLENTY_THRESHOLD).level).toBe('plenty');
    expect(availabilityStatus(PLENTY_THRESHOLD - 1).level).toBe('filling');
    expect(availabilityStatus(FILLING_THRESHOLD).level).toBe('filling');
    expect(availabilityStatus(FILLING_THRESHOLD - 1).level).toBe('nearlyFull');
    expect(availabilityStatus(0).level).toBe('nearlyFull');
  });
});
