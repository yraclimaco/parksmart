/**
 * Tests for the recommendation logic: the 65/35 scoring formula and
 * permit-based filtering. These cover logic the UI relies on, not styling.
 */

import { describe, expect, it } from 'vitest';
import { SCORING_WEIGHTS } from '../constants.ts';
import { DEFAULT_DESTINATION_ID } from './destinations.ts';
import { availabilityAt } from '../utils/availabilityModel.ts';
import { ParkingPlannerRequest, PermitType } from '../types.ts';
import {
  SAMPLE_LOTS,
  calculateParkingScore,
  compareReasons,
  getSampleRecommendations,
  MAX_RECOMMENDED_WALK_MINUTES,
} from './sampleRecommendations.ts';
import { lotAccess, parseArrival } from '../utils/permitRules.ts';

/** Builds a request for the default destination (Wed Oct 21, 2026, noon by default). */
function makeRequest(
  permitType: PermitType,
  arrivalDate = '2026-10-21',
  arrivalTime = '12:00'
): ParkingPlannerRequest {
  return { destinationId: DEFAULT_DESTINATION_ID, arrivalDate, arrivalTime, permitType };
}

describe('calculateParkingScore', () => {
  const maxWalk = SCORING_WEIGHTS.MAX_WALK_BENCHMARK_MINUTES;

  it('gives 100 for full availability and a zero-minute walk', () => {
    expect(calculateParkingScore(100, 0)).toBe(100);
  });

  it('gives 0 for no availability and a walk at the benchmark limit', () => {
    expect(calculateParkingScore(0, maxWalk)).toBe(0);
  });

  it('weights availability at 65% and walking convenience at 35%', () => {
    // Full availability only, worst walk: availability weight alone
    expect(calculateParkingScore(100, maxWalk)).toBe(65);
    // No availability, best walk: walking weight alone
    expect(calculateParkingScore(0, 0)).toBe(35);
  });

  it('treats walks longer than the benchmark as zero convenience, not negative', () => {
    expect(calculateParkingScore(50, maxWalk + 15)).toBe(
      calculateParkingScore(50, maxWalk)
    );
  });

  it('scores a shorter walk higher when availability is equal', () => {
    expect(calculateParkingScore(70, 5)).toBeGreaterThan(
      calculateParkingScore(70, 12)
    );
  });
});

describe('getSampleRecommendations', () => {
  const permits: PermitType[] = ['A', 'B', 'S', 'SR', 'D', 'V'];

  it.each(permits)('only recommends lots a %s permit can use at the arrival time', (permit) => {
    const request = makeRequest(permit);
    const arrival = parseArrival(request.arrivalDate, request.arrivalTime)!;
    for (const rec of getSampleRecommendations(request).recommendations) {
      expect(['always', 'until']).toContain(lotAccess(permit, rec.lot.spaceCategories, arrival).status);
    }
  });

  it('excludes lots whose only usable stalls are evening upgrades on a weekday morning', () => {
    // South has A, B and V stalls: an S permit can use A/B only after 4 PM on weekdays
    const morning = getSampleRecommendations(makeRequest('S', '2026-10-21', '10:00'));
    expect(morning.recommendations.map((r) => r.lot.locationId)).not.toContain('south-ps');
    const saturday = getSampleRecommendations(makeRequest('V', '2026-10-24', '12:00'));
    expect(saturday.recommendations.length).toBeGreaterThan(0);
  });

  it('returns nothing for a missing date', () => {
    expect(getSampleRecommendations(makeRequest('S', '', '12:00')).recommendations).toEqual([]);
  });

  it.each(permits)('returns a full, distinct ranking for a %s permit, best first', (permit) => {
    const { recommendations } = getSampleRecommendations(makeRequest(permit));
    const ids = recommendations.map((rec) => rec.lot.locationId);
    expect(new Set(ids).size).toBe(ids.length);
    recommendations.forEach((rec, i) => {
      expect(rec.rank).toBe(i + 1);
      if (i > 0) expect(recommendations[i - 1].score).toBeGreaterThanOrEqual(rec.score);
    });
  });

  it('labels the first three First choice, Backup and #3', () => {
    const { recommendations } = getSampleRecommendations(makeRequest('S'));
    expect(recommendations.length).toBeGreaterThan(3);
    expect(recommendations.slice(0, 3).map((r) => r.badgeLabel)).toEqual(['First choice', 'Backup', '#3']);
    expect(recommendations[2].reason).toMatch(/^Compared with /);
  });

  it('ranks the first choice at or above the backup', () => {
    const { recommendations } = getSampleRecommendations(makeRequest('S'));
    expect(recommendations.length).toBeGreaterThanOrEqual(2);
    expect(recommendations[0].badgeLabel).toBe('First choice');
    expect(recommendations[1].badgeLabel).toBe('Backup');
    expect(recommendations[0].score).toBeGreaterThanOrEqual(recommendations[1].score);
  });

  it('marks every response as sample data', () => {
    expect(getSampleRecommendations(makeRequest('B')).isSampleData).toBe(true);
  });

  it('has a usable lot for every permit on a weekday at noon so no option is a dead end', () => {
    const noon = parseArrival('2026-10-21', '12:00')!;
    for (const permit of permits) {
      expect(SAMPLE_LOTS.some((lot) => lotAccess(permit, lot.spaceCategories, noon).status === 'always')).toBe(true);
    }
  });
});

describe('compareReasons', () => {
  const lot = (id: string, walk: number, open: number) => ({
    locationId: id, name: `${id} Parking Structure`, latitude: 0, longitude: 0,
    estimatedAvailabilityPercent: open, walkingMinutes: walk, spaceCategories: [],
  });

  it('compares the first choice against the backup', () => {
    const first = lot('Gilman', 5, 80);
    const backup = lot('Hopkins', 9, 60);
    const reasons = compareReasons(first, backup, [first, backup]);
    expect(reasons.first).toBe('Shorter walk and more open spaces than your backup');
    expect(reasons.backup).toBe('Next best if Gilman fills up, 4 min longer walk');
  });

  it('explains a closer but fuller backup', () => {
    const first = lot('Athena', 12, 90);
    const backup = lot('Triton', 7, 55);
    const reasons = compareReasons(first, backup, [first, backup]);
    expect(reasons.first).toBe('Most open spaces of any eligible lot (90% vs 55% at your backup)');
    expect(reasons.backup).toBe('5 min closer than Athena, but fewer open spaces');
  });

  it('handles a single eligible lot', () => {
    const only = lot('Pangea', 9, 70);
    expect(compareReasons(only, null, [only])).toEqual({
      first: 'Only structure your permit can use at this time, 9 min walk',
      backup: null,
    });
  });
});

describe('walk cutoff', () => {
  it('never recommends a lot beyond the max walk', () => {
    const recs = getSampleRecommendations(makeRequest('S')).recommendations;
    for (const rec of recs) expect(rec.lot.walkingMinutes).toBeLessThanOrEqual(MAX_RECOMMENDED_WALK_MINUTES);
  });
});

describe('recommendation availability matches the map card', () => {
  it('the percent on a recommendation equals the model applied to the original lot at the arrival time', () => {
    const request = { destinationId: DEFAULT_DESTINATION_ID, arrivalDate: '2026-10-26', arrivalTime: '14:15', permitType: 'S' as const };
    const arrival = new Date(2026, 9, 26, 14, 15);
    const { recommendations } = getSampleRecommendations(request);
    expect(recommendations.length).toBeGreaterThan(0);
    for (const rec of recommendations) {
      const base = SAMPLE_LOTS.find((l) => l.locationId === rec.lot.locationId)!;
      expect(availabilityAt(base, arrival)).toBe(rec.lot.estimatedAvailabilityPercent);
    }
  });
});
