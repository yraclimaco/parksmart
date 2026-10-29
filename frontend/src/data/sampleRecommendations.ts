/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { SCORING_WEIGHTS } from '../constants.ts';
import { findDestination } from './destinations.ts';
import {
  ParkingLot,
  ParkingPlannerRequest,
  ParkingPlannerResponse,
  ParkingRecommendation,
} from '../types.ts';
import { ALL_PARKING } from './parkingLots.ts';
import { lotAccess, parseArrival } from '../utils/permitRules.ts';
import { availabilityAt } from '../utils/availabilityModel.ts';

/** All structures and lots (real names/coordinates, sample stats), under its original export name. */
export { ALL_PARKING as SAMPLE_LOTS };

/**
 * Calculates straight-line distance in kilometers between two geo-coordinates.
 */
function calculateDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371; // Earth radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Estimates walking time in minutes based on distance from the chosen destination.
 * Standard average campus walking speed: approx 12-14 min/km, minimum 3 min.
 */
export function estimateWalkingTime(lot: ParkingLot, destinationId: string): number {
  const dest = findDestination(destinationId);
  if (!dest) {
    return lot.walkingMinutes;
  }
  const distanceKm = calculateDistanceKm(
    lot.latitude,
    lot.longitude,
    dest.latitude,
    dest.longitude
  );
  // Estimate ~12 minutes per km on campus pedestrian walkways plus buffer
  const calculatedMinutes = Math.round(distanceKm * 13) + 2;
  return Math.max(3, calculatedMinutes);
}

/** Lots farther than this walk from the destination are not recommended (benchmark in SCORING_WEIGHTS). */
export const MAX_RECOMMENDED_WALK_MINUTES = SCORING_WEIGHTS.MAX_WALK_BENCHMARK_MINUTES;

/** Short name for reasons, e.g. "Gilman" from "Gilman Parking Structure". */
function shortName(lot: ParkingLot): string {
  return lot.name.replace(' Parking Structure', '');
}

/**
 * Explains each pick by comparing it with the other one (and with every eligible
 * lot for "closest"/"most open"), instead of restating its own numbers.
 */
export function compareReasons(
  first: ParkingLot,
  backup: ParkingLot | null,
  allEligible: ParkingLot[]
): { first: string; backup: string | null } {
  const isClosest = allEligible.every((lot) => first.walkingMinutes <= lot.walkingMinutes);
  const isMostOpen = allEligible.every(
    (lot) => first.estimatedAvailabilityPercent >= lot.estimatedAvailabilityPercent
  );

  if (!backup) {
    return {
      first: `Only structure your permit can use at this time, ${first.walkingMinutes} min walk`,
      backup: null,
    };
  }

  const walkDiff = backup.walkingMinutes - first.walkingMinutes; // > 0: first is closer
  const spaceDiff = first.estimatedAvailabilityPercent - backup.estimatedAvailabilityPercent; // > 0: first has more room

  let firstReason: string;
  if (walkDiff > 0 && spaceDiff > 0) {
    firstReason = `Shorter walk and more open spaces than your backup`;
  } else if (isClosest && walkDiff > 0) {
    firstReason = `Closest eligible parking, ${walkDiff} min shorter walk than your backup`;
  } else if (walkDiff > 0) {
    firstReason = `${walkDiff} min shorter walk than your backup, with ${first.estimatedAvailabilityPercent}% open`;
  } else if (isMostOpen && spaceDiff > 0) {
    firstReason = `Most open spaces of any eligible lot (${first.estimatedAvailabilityPercent}% vs ${backup.estimatedAvailabilityPercent}% at your backup)`;
  } else if (spaceDiff > 0) {
    firstReason = `More open spaces than your backup (${first.estimatedAvailabilityPercent}% vs ${backup.estimatedAvailabilityPercent}%)`;
  } else {
    firstReason = `Best overall balance of open spaces and walking time`;
  }

  let backupReason: string;
  if (walkDiff < 0) {
    backupReason = `${-walkDiff} min closer than ${shortName(first)}, but fewer open spaces`;
  } else if (spaceDiff < 0) {
    backupReason = `More open spaces than ${shortName(first)}, but a ${walkDiff} min longer walk`;
  } else if (walkDiff === 0) {
    backupReason = `Same walk as ${shortName(first)}, a little fuller`;
  } else {
    backupReason = `Next best if ${shortName(first)} fills up, ${walkDiff} min longer walk`;
  }

  return { first: firstReason, backup: backupReason };
}

/** Reason for picks after the backup: how they trade off against the first choice. */
export function relativeReason(lot: ParkingLot, first: ParkingLot): string {
  const walkDiff = lot.walkingMinutes - first.walkingMinutes;
  const spaceDiff = lot.estimatedAvailabilityPercent - first.estimatedAvailabilityPercent;
  const walk =
    walkDiff > 0 ? `${walkDiff} min longer walk` : walkDiff < 0 ? `${-walkDiff} min shorter walk` : 'same walk';
  const space =
    spaceDiff > 0 ? `more open spaces` : spaceDiff < 0 ? `fewer open spaces` : 'similar space';
  return `Compared with ${shortName(first)}: ${walk}, ${space}`;
}

/**
 * SCORING ALGORITHM:
 * Evaluates parking options based on 65% expected availability and 35% walking convenience.
 * Shorter walks receive higher scores on a normalized 0-100 scale.
 *
 * @param availabilityPercent - Value between 0 and 100
 * @param walkingMinutes - Walking duration in minutes
 * @returns Composite score out of 100
 */
export function calculateParkingScore(
  availabilityPercent: number,
  walkingMinutes: number
): number {
  // Normalize walking convenience: 0 min = 100, 20+ min = 0
  const normalizedWalkConvenience = Math.max(
    0,
    Math.min(
      100,
      ((SCORING_WEIGHTS.MAX_WALK_BENCHMARK_MINUTES - walkingMinutes) /
        SCORING_WEIGHTS.MAX_WALK_BENCHMARK_MINUTES) *
        100
    )
  );

  // 65% availability + 35% walking convenience
  const score =
    availabilityPercent * SCORING_WEIGHTS.AVAILABILITY_WEIGHT +
    normalizedWalkConvenience * SCORING_WEIGHTS.WALKING_WEIGHT;

  return Math.round(score * 10) / 10;
}

/**
 * Filter and rank sample parking lots for a user request.
 * A lot is eligible when the permit can use one of its stall categories at the
 * arrival time (see utils/permitRules.ts). Returns the top two by score.
 *
 * NOTE: Replace this function body with a fetch to your real API endpoint in production.
 */
export function getSampleRecommendations(
  request: ParkingPlannerRequest
): ParkingPlannerResponse {
  const response = (recommendations: ParkingRecommendation[]): ParkingPlannerResponse => ({
    recommendations,
    query: request,
    generatedAt: new Date().toISOString(),
    isSampleData: true,
  });

  const arrival = parseArrival(request.arrivalDate, request.arrivalTime);
  if (!arrival) return response([]);

  // 1. Keep lots the permit can use at the arrival time; attach walk time and access
  const scored = ALL_PARKING.flatMap((lot) => {
    const access = lotAccess(request.permitType, lot.spaceCategories, arrival);
    if (access.status !== 'always' && access.status !== 'until') return [];
    const walkingMinutes = estimateWalkingTime(lot, request.destinationId);
    if (walkingMinutes > MAX_RECOMMENDED_WALK_MINUTES) return []; // too far to be a useful pick
    // Availability expected at the arrival time (sample time-of-day model)
    const estimatedAvailabilityPercent = availabilityAt(lot, arrival);
    return [{
      lot: { ...lot, walkingMinutes, estimatedAvailabilityPercent },
      access,
      score: calculateParkingScore(estimatedAvailabilityPercent, walkingMinutes),
    }];
  });

  // 2. Highest score first
  scored.sort((a, b) => b.score - a.score);
  if (scored.length === 0) return response([]);

  // 3. First choice and backup, with reasons that compare the two
  // 3. Full ranking. First choice and backup get reasons comparing the two;
  //    the rest are explained relative to the first choice.
  const [first, backup] = scored;
  const reasons = compareReasons(first.lot, backup?.lot ?? null, scored.map((s) => s.lot));
  const recommendations: ParkingRecommendation[] = scored.map((entry, index) => ({
    rank: index + 1,
    badgeLabel: index === 0 ? 'First choice' : index === 1 ? 'Backup' : `#${index + 1}`,
    lot: entry.lot,
    score: entry.score,
    access: entry.access,
    reason: index === 0 ? reasons.first : index === 1 ? reasons.backup! : relativeReason(entry.lot, first.lot),
  }));
  return response(recommendations);
}
