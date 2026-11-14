/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { PermitType, TripPriority } from './types.ts';

/**
 * OpenFreeMap free, keyless Positron vector tile style URL.
 * Provides a clean, muted, low-saturation vector base map without API keys.
 */
export const OPENFREEMAP_POSITRON_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

/** Basemap options shown in the Map / Satellite toggle. */
export type BasemapMode = 'satellite' | 'map';
export const DEFAULT_BASEMAP: BasemapMode = 'satellite';

/**
 * USGS National Map aerial imagery: public domain, free, no API key.
 * Mostly NAIP 1-meter imagery. The service publishes cached tiles down to
 * about 1:9,028 scale (zoom 16); MapLibre upscales beyond that.
 * Service info: https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer
 */
const USGS_IMAGERY_TILE_URL =
  'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}';
const USGS_IMAGERY_MAX_ZOOM = 16;

export const SATELLITE_STYLE = {
  version: 8,
  sources: {
    'usgs-imagery': {
      type: 'raster',
      tiles: [USGS_IMAGERY_TILE_URL],
      tileSize: 256,
      maxzoom: USGS_IMAGERY_MAX_ZOOM,
      attribution: 'Imagery: USDA, USGS The National Map',
    },
  },
  layers: [{ id: 'usgs-imagery', type: 'raster', source: 'usgs-imagery' }],
} as const;

/**
 * UCSD Campus Map Center, Zoom & Framing Padding Settings
 */
/** Rough box around the UCSD main campus; dropped pins outside it are rejected. */
export const CAMPUS_BOUNDS = {
  south: 32.862,
  north: 32.906,
  west: -117.262,
  east: -117.205,
} as const;

export function isOnCampus(latitude: number, longitude: number): boolean {
  return (
    latitude >= CAMPUS_BOUNDS.south &&
    latitude <= CAMPUS_BOUNDS.north &&
    longitude >= CAMPUS_BOUNDS.west &&
    longitude <= CAMPUS_BOUNDS.east
  );
}

export const MAP_CONFIG = {
  // Center near University of California San Diego central campus (Library Walk / Price Center)
  DEFAULT_CENTER: [-117.2374, 32.8812] as [number, number],
  DEFAULT_ZOOM: 15.0,
  MIN_ZOOM: 13.5,
  MAX_ZOOM: 18.0,
  FLY_DURATION_MS: 700,
} as const;

/**
 * Map viewport framing padding:
 * Left padding equals floating panel width (380px) + 24px gap = 404px.
 * Other boundaries receive ~60px padding to keep destination pin and lots fully visible.
 */
export const MAP_PADDING = {
  left: 404,
  right: 60,
  // Clears the time scrubber floating at the top of the map
  top: 100,
  bottom: 60,
} as const;

/**
 * Animation duration & timing curves
 */
export const ANIMATION_TIMINGS = {
  // Simulated request time. 0 = instant (sample data); set > 0 to preview the loading state
  SHIMMER_DURATION_MS: 0,
  STAGGER_DELAY_SECONDS: 0.05,
} as const;


/**
 * Default ("balanced") scoring weights for recommendation engine:
 * 65% expected availability, 35% walking convenience. Other priorities use
 * PRIORITY_OPTIONS below.
 */
export const SCORING_WEIGHTS = {
  AVAILABILITY_WEIGHT: 0.65,
  WALKING_WEIGHT: 0.35,
  // Baseline max walk time for normalization in minutes
  MAX_WALK_BENCHMARK_MINUTES: 20,
} as const;


/**
 * Ranking priorities the user can pick. Weights match the backend's
 * PREFERENCE_WEIGHTS (src/ranking.py); "balanced" is the original 65/35.
 * The two non-default weightings are starting points to review with experts.
 */
export const PRIORITY_OPTIONS: Array<{
  value: TripPriority;
  label: string;
  description: string;
  availabilityWeight: number;
  walkingWeight: number;
}> = [
  {
    value: 'shorter_walk',
    label: 'Shorter walk',
    description: 'Closer parking, even if it is usually fuller',
    availabilityWeight: 0.2,
    walkingWeight: 0.8,
  },
  {
    value: 'balanced',
    label: 'Balanced',
    description: 'Weighs walking time and past availability',
    availabilityWeight: SCORING_WEIGHTS.AVAILABILITY_WEIGHT,
    walkingWeight: SCORING_WEIGHTS.WALKING_WEIGHT,
  },
  {
    value: 'more_availability',
    label: 'More space',
    description: 'More open spaces, even if it is farther',
    availabilityWeight: 0.85,
    walkingWeight: 0.15,
  },
];

export const DEFAULT_PRIORITY: TripPriority = 'balanced';

/** Walking-limit choices in minutes; null is the default 20-minute limit. */
export const WALK_LIMIT_OPTIONS: Array<{ value: number | null; label: string }> = [
  { value: 5, label: '5 min' },
  { value: 10, label: '10 min' },
  { value: 15, label: '15 min' },
  { value: null, label: '20 min' },
];

/**
 * Permit metadata with plain-language labels
 */
export const PERMIT_OPTIONS: Array<{ type: PermitType; label: string; description: string }> = [
  { type: 'A', label: 'A', description: 'Faculty & Designated Staff' },
  { type: 'B', label: 'B', description: 'Staff & Graduate Students' },
  { type: 'S', label: 'S', description: 'Undergraduate Commuter' },
  { type: 'SR', label: 'SR', description: 'Student Resident' },
  { type: 'D', label: 'D', description: 'Employees & upper-division commuters' },
  { type: 'V', label: 'V', description: 'Visitor / Daily Pay' },
];
