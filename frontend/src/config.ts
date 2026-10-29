/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/** FastAPI backend started with `python -m uvicorn src.api.main:app --reload`. */
export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * Backend base URL without a trailing slash. Set VITE_API_BASE_URL in
 * frontend/.env.local to point at another backend; blank values use the default.
 */
export function resolveApiBaseUrl(configured: string | undefined): string {
  const value = configured?.trim();
  return (value || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

export const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

/** Where recommendations come from: built-in sample data, or the FastAPI backend. */
export type RecommendationSource = 'sample' | 'api';

/**
 * VITE_RECOMMENDATION_SOURCE=api sends searches to POST /recommendations. Anything
 * else (including unset, as in AI Studio previews) keeps the labeled sample data.
 */
export function resolveRecommendationSource(configured: string | undefined): RecommendationSource {
  return configured?.trim().toLowerCase() === 'api' ? 'api' : 'sample';
}

export const RECOMMENDATION_SOURCE = resolveRecommendationSource(
  import.meta.env.VITE_RECOMMENDATION_SOURCE
);
