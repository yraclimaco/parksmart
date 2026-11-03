/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Valid UCSD parking permit types modeled in this prototype.
 * A: Faculty/Staff
 * B: Staff/Grad Students
 * S: Undergraduate Students
 * SR: Student Residents
 * D: Employees & upper-division commuters
 * V: Visitor
 */
export type PermitType = 'A' | 'B' | 'S' | 'SR' | 'D' | 'V';

/** Category painted on a parking stall. Uses the same letters as permits. */
export type SpaceCategory = PermitType;

/**
 * Campus destination representation for travel planning.
 */
export interface CampusDestination {
  id: string;
  name: string;
  /** Optional grouping label; not provided by the UCSD GIS source. */
  area?: string;
  /** Class-schedule and building codes, e.g. ["WLH"] or ["HSS", "LEDDN"]. */
  codes?: string[];
  /** Other names people search for, e.g. "Ledden Auditorium", "Calit2". */
  aliases?: string[];
  /** Position in the "Popular" list shown before typing (1 = first). */
  popular?: number;
  /** True for a spot the user dropped on the map rather than a campus building. */
  isPin?: boolean;
  latitude: number;
  longitude: number;
}

/**
 * Parking lot representation with sample coordinates and permit allowances.
 */
export interface ParkingLot {
  locationId: string;
  name: string;
  latitude: number;
  longitude: number;
  estimatedAvailabilityPercent: number;
  walkingMinutes: number;
  /** Stall categories found in the structure (A, B, S, SR, D, V). SAMPLE data for now. */
  spaceCategories: SpaceCategory[];
  /** Parking structure (garage) or surface lot; structures get the larger pin. */
  kind?: 'structure' | 'lot';
  /** Restriction to show on the lot card, e.g. needs a supplemental permit. */
  accessNote?: string;
  description?: string;
}

import type { LotAccess } from './utils/permitRules.ts';

/**
 * Recommendation card output after filtering and scoring.
 */
export interface ParkingRecommendation {
  /** "First choice", "Backup", then "#3", "#4", ... */
  badgeLabel: string;
  /** 1-based position in the ranking. */
  rank: number;
  lot: ParkingLot;
  score: number;
  reason: string;
  /** When the searched permit can use this lot, relative to the arrival time. */
  access: LotAccess;
  /**
   * Present only for results from the backend: its historical estimates, which replace
   * every sample number on the card. null means unknown, never zero.
   */
  estimate?: BackendEstimate;
}

/** Backend numbers for one recommendation (src/api/recommendations.ts). */
export interface BackendEstimate {
  /** 0-100, or null when the backend has no estimate. */
  availablePercent: number | null;
  walkingMinutes: number | null;
  /** The backend marked the whole response as a static example. */
  isExample: boolean;
}

/**
 * User inputs payload submitted from the preference form.
 */
export interface ParkingPlannerRequest {
  destinationId: string;
  arrivalDate: string;
  arrivalTime: string;
  permitType: PermitType;
}

/**
 * Response payload structure for recommendations.
 */
export interface ParkingPlannerResponse {
  recommendations: ParkingRecommendation[];
  query: ParkingPlannerRequest;
  generatedAt: string;
  isSampleData: true;
}

/**
 * Developer state simulation options for verifying edge cases.
 */
export type DevSimulationState = 'normal' | 'loading' | 'empty' | 'error';
