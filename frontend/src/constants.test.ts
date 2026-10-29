import { describe, expect, it } from 'vitest';
import { isOnCampus } from './constants.ts';

describe('isOnCampus', () => {
  it('accepts central campus and rejects far-away points', () => {
    expect(isOnCampus(32.8812, -117.2374)).toBe(true);
    expect(isOnCampus(32.7157, -117.1611)).toBe(false); // downtown San Diego
  });
});
