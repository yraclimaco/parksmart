/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ParkingLot } from '../types.ts';

/**
 * Surface lots (52) from the team's cleaned QPASS inventory (issue #3,
 * results/issue3/facility_cleaned_inventory.json): every P-numbered facility with
 * records since 2024 that UCSD's campus GIS can place on the map.
 *
 * REAL (verified 2026-10-21):
 *   - Lot IDs: QPASS facility labels (P-numbers).
 *   - Coordinates: area-weighted center of each lot's outline in UCSD GIS
 *     BaseData/Campus_Map_Vector/MapServer layer 21 (ParkingLotID field).
 *   - Gliderport = P386: verified alias in config/facility_aliases.json. It is not in
 *     UCSD's GIS (city-owned land); its pin uses the published, approximate airfield
 *     coordinates (https://airport-data.com/airport/CA84).
 *   - accessNote text: lot restrictions from Domain Research v1.2, section 4.
 *
 * SAMPLE (not real yet): estimatedAvailabilityPercent and spaceCategories (generated
 * deterministically per lot). Restricted lots (SIO P001 to P017, Preuss P706, Medical
 * Center P759, International Center P416) get no categories, so they show on the map but are never recommended.
 *
 * Not placed (no GIS outline found): P021, P206, P359, P383, P395, P506, P604, P751,
 * P752, P760. Names for other P-numbers are not verified yet, so they show as "Lot Pxxx".
 */
export const SURFACE_LOTS: ParkingLot[] = [
  { locationId: "p001", name: "Lot P001", kind: 'lot', latitude: 32.8649, longitude: -117.25554, estimatedAvailabilityPercent: 64, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p002", name: "Lot P002", kind: 'lot', latitude: 32.8637, longitude: -117.25404, estimatedAvailabilityPercent: 82, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p003", name: "Lot P003", kind: 'lot', latitude: 32.86393, longitude: -117.25384, estimatedAvailabilityPercent: 39, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p006", name: "Lot P006", kind: 'lot', latitude: 32.86602, longitude: -117.25248, estimatedAvailabilityPercent: 57, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p007", name: "Lot P007", kind: 'lot', latitude: 32.86704, longitude: -117.2537, estimatedAvailabilityPercent: 76, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p008", name: "Lot P008", kind: 'lot', latitude: 32.86682, longitude: -117.2529, estimatedAvailabilityPercent: 82, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p010", name: "Lot P010", kind: 'lot', latitude: 32.86886, longitude: -117.25336, estimatedAvailabilityPercent: 69, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p011", name: "Lot P011", kind: 'lot', latitude: 32.86923, longitude: -117.25151, estimatedAvailabilityPercent: 50, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p012", name: "Lot P012", kind: 'lot', latitude: 32.87005, longitude: -117.25263, estimatedAvailabilityPercent: 57, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p013", name: "Lot P013", kind: 'lot', latitude: 32.87007, longitude: -117.25161, estimatedAvailabilityPercent: 89, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p014", name: "Lot P014", kind: 'lot', latitude: 32.86963, longitude: -117.2511, estimatedAvailabilityPercent: 36, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p016", name: "Lot P016", kind: 'lot', latitude: 32.8674, longitude: -117.2516, estimatedAvailabilityPercent: 50, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p017", name: "Lot P017", kind: 'lot', latitude: 32.86553, longitude: -117.24899, estimatedAvailabilityPercent: 39, walkingMinutes: 10, spaceCategories: [], accessNote: "Scripps (SIO) lot: needs a supplemental SIO permit 7 AM to 11 PM daily" },
  { locationId: "p031", name: "Lot P031", kind: 'lot', latitude: 32.87087, longitude: -117.25252, estimatedAvailabilityPercent: 76, walkingMinutes: 10, spaceCategories: ['S', 'D'] },
  { locationId: "p032", name: "Lot P032", kind: 'lot', latitude: 32.87104, longitude: -117.25053, estimatedAvailabilityPercent: 72, walkingMinutes: 10, spaceCategories: ['D', 'S', 'SR'] },
  { locationId: "p106", name: "Lot P106", kind: 'lot', latitude: 32.87305, longitude: -117.23851, estimatedAvailabilityPercent: 79, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p113", name: "Lot P113", kind: 'lot', latitude: 32.87658, longitude: -117.24004, estimatedAvailabilityPercent: 67, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p201", name: "Lot P201", kind: 'lot', latitude: 32.87788, longitude: -117.24192, estimatedAvailabilityPercent: 78, walkingMinutes: 10, spaceCategories: ['S', 'D'] },
  { locationId: "p302", name: "Lot P302", kind: 'lot', latitude: 32.88128, longitude: -117.24165, estimatedAvailabilityPercent: 71, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p303", name: "Lot P303", kind: 'lot', latitude: 32.88162, longitude: -117.24278, estimatedAvailabilityPercent: 36, walkingMinutes: 10, spaceCategories: ['D', 'S', 'SR'] },
  { locationId: "p304", name: "Lot P304", kind: 'lot', latitude: 32.88259, longitude: -117.24274, estimatedAvailabilityPercent: 60, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p351", name: "Lot P351", kind: 'lot', latitude: 32.88734, longitude: -117.24198, estimatedAvailabilityPercent: 92, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p357", name: "Lot P357", kind: 'lot', latitude: 32.88761, longitude: -117.2409, estimatedAvailabilityPercent: 89, walkingMinutes: 10, spaceCategories: ['S', 'B', 'V'] },
  { locationId: "p384", name: "Lot P384", kind: 'lot', latitude: 32.88851, longitude: -117.24494, estimatedAvailabilityPercent: 44, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p385", name: "Lot P385", kind: 'lot', latitude: 32.88842, longitude: -117.24395, estimatedAvailabilityPercent: 84, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p386", name: "Gliderport (P386)", kind: 'lot', latitude: 32.889722, longitude: -117.246944, estimatedAvailabilityPercent: 68, walkingMinutes: 10, spaceCategories: ['S', 'D'], accessNote: "Gliderport: daylight only (6 AM to 6 PM Nov to Mar, 6 AM to 8 PM Apr to Oct)" },
  { locationId: "p401", name: "Lot P401", kind: 'lot', latitude: 32.87941, longitude: -117.22917, estimatedAvailabilityPercent: 41, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p402", name: "Lot P402", kind: 'lot', latitude: 32.87844, longitude: -117.23034, estimatedAvailabilityPercent: 43, walkingMinutes: 10, spaceCategories: ['B', 'A'] },
  { locationId: "p406", name: "Lot P406", kind: 'lot', latitude: 32.87734, longitude: -117.2303, estimatedAvailabilityPercent: 41, walkingMinutes: 10, spaceCategories: ['S', 'D'] },
  { locationId: "p414", name: "Lot P414", kind: 'lot', latitude: 32.8782, longitude: -117.23992, estimatedAvailabilityPercent: 55, walkingMinutes: 10, spaceCategories: ['S', 'D'] },
  { locationId: "p416", name: "Lot P416", kind: 'lot', latitude: 32.87778, longitude: -117.23813, estimatedAvailabilityPercent: 87, walkingMinutes: 10, spaceCategories: [], accessNote: "International Center: affiliate access only 7 AM to 5 PM weekdays" },
  { locationId: "p503", name: "Lot P503", kind: 'lot', latitude: 32.88219, longitude: -117.23547, estimatedAvailabilityPercent: 79, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p504", name: "Lot P504", kind: 'lot', latitude: 32.882, longitude: -117.23221, estimatedAvailabilityPercent: 75, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p507", name: "Lot P507", kind: 'lot', latitude: 32.88365, longitude: -117.22914, estimatedAvailabilityPercent: 39, walkingMinutes: 10, spaceCategories: ['D', 'S', 'SR'] },
  { locationId: "p508", name: "Lot P508", kind: 'lot', latitude: 32.88054, longitude: -117.23423, estimatedAvailabilityPercent: 48, walkingMinutes: 10, spaceCategories: ['B', 'A'] },
  { locationId: "p510", name: "Lot P510", kind: 'lot', latitude: 32.88156, longitude: -117.23011, estimatedAvailabilityPercent: 56, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p602", name: "Lot P602", kind: 'lot', latitude: 32.87668, longitude: -117.23458, estimatedAvailabilityPercent: 54, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p603", name: "Lot P603", kind: 'lot', latitude: 32.87401, longitude: -117.23467, estimatedAvailabilityPercent: 61, walkingMinutes: 10, spaceCategories: ['B', 'A'] },
  { locationId: "p610", name: "Lot P610", kind: 'lot', latitude: 32.87495, longitude: -117.2378, estimatedAvailabilityPercent: 73, walkingMinutes: 10, spaceCategories: ['B', 'A'] },
  { locationId: "p671", name: "Lot P671", kind: 'lot', latitude: 32.8738, longitude: -117.23331, estimatedAvailabilityPercent: 65, walkingMinutes: 10, spaceCategories: ['S', 'B', 'V'] },
  { locationId: "p701", name: "Lot P701", kind: 'lot', latitude: 32.88104, longitude: -117.22739, estimatedAvailabilityPercent: 46, walkingMinutes: 10, spaceCategories: ['D', 'S', 'SR'] },
  { locationId: "p702", name: "Lot P702", kind: 'lot', latitude: 32.88166, longitude: -117.2243, estimatedAvailabilityPercent: 43, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p703", name: "Lot P703", kind: 'lot', latitude: 32.87984, longitude: -117.22071, estimatedAvailabilityPercent: 37, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p704", name: "Lot P704", kind: 'lot', latitude: 32.87952, longitude: -117.2191, estimatedAvailabilityPercent: 53, walkingMinutes: 10, spaceCategories: ['A', 'B', 'V'] },
  { locationId: "p705", name: "Lot P705", kind: 'lot', latitude: 32.88094, longitude: -117.2195, estimatedAvailabilityPercent: 87, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p706", name: "Lot P706", kind: 'lot', latitude: 32.88269, longitude: -117.22216, estimatedAvailabilityPercent: 42, walkingMinutes: 10, spaceCategories: [], accessNote: "Preuss School lot: needs supplemental authorization 24/7" },
  { locationId: "p707", name: "Lot P707", kind: 'lot', latitude: 32.88118, longitude: -117.22271, estimatedAvailabilityPercent: 49, walkingMinutes: 10, spaceCategories: ['B', 'A'] },
  { locationId: "p753", name: "Lot P753", kind: 'lot', latitude: 32.87695, longitude: -117.22645, estimatedAvailabilityPercent: 40, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
  { locationId: "p759", name: "Lot P759", kind: 'lot', latitude: 32.87705, longitude: -117.22759, estimatedAvailabilityPercent: 46, walkingMinutes: 10, spaceCategories: [], accessNote: "La Jolla Medical Center lot: needs supplemental authorization 24/7" },
  { locationId: "p782", name: "Lot P782", kind: 'lot', latitude: 32.87596, longitude: -117.21883, estimatedAvailabilityPercent: 82, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p784", name: "Lot P784", kind: 'lot', latitude: 32.87809, longitude: -117.22182, estimatedAvailabilityPercent: 54, walkingMinutes: 10, spaceCategories: ['S', 'B', 'A'] },
  { locationId: "p785", name: "Lot P785", kind: 'lot', latitude: 32.87812, longitude: -117.22079, estimatedAvailabilityPercent: 81, walkingMinutes: 10, spaceCategories: ['B', 'S', 'D'] },
];
