/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { ChevronDown, MapPin } from 'lucide-react';
import { ParkingPlannerRequest, ParkingRecommendation } from '../types.ts';
import { getDestination } from '../data/destinations.ts';
import { holidayNotice, parseArrival } from '../utils/permitRules.ts';
import { RecommendationCard } from './RecommendationCard.tsx';
import { SkeletonCard } from './SkeletonCard.tsx';
import { EmptyState } from './EmptyState.tsx';
import { ErrorState } from './ErrorState.tsx';
import { RecentSearches } from './RecentSearches.tsx';
import type { ApiStatus } from '../api/recommendations.ts';

/** Where the shown results came from, plus the backend's own messages. */
export type ResultInfo =
  | { source: 'sample' }
  | { source: 'api'; status: ApiStatus; explanation: string; limitations: string[]; isExample: boolean };

/** Headline for backend results that contain no parking choice. */
const EMPTY_TITLES: Record<Exclude<ApiStatus, 'ready'>, string> = {
  no_suitable_location: 'No suitable parking found',
  predictions_unavailable: 'No availability estimate for this trip',
  not_implemented: 'Recommendations are not available yet',
};

/** Results shown before "Show more", and how many each click reveals. */
const INITIAL_VISIBLE = 3;
const LOAD_MORE_STEP = 5;

interface ResultsListProps {
  isLoading: boolean;
  isError: boolean;
  recommendations: ParkingRecommendation[];
  /** The request these results were computed for (null before the first search). */
  searchedRequest: ParkingPlannerRequest | null;
  /** Earlier searches this visit (most recent first), for the "Recent" menu. */
  searchHistory: ParkingPlannerRequest[];
  onRestoreSearch: (request: ParkingPlannerRequest) => void;
  /** Show the "enter your trip details" prompt instead of results. */
  showIntroPrompt: boolean;
  /** "Your usual" card, shown in place of the generic prompt when a trip is saved. */
  usualTripCard?: React.ReactNode;
  /** True when trip details changed since the search; results are greyed out. */
  isStale: boolean;
  /** Time every availability number describes (follows the arrival time unless the Time tool is used). */
  availabilityTime: Date;
  confirmedLotId: string | null;
  onConfirmLot: (locationId: string) => void;
  selectedLocationId: string | null;
  onSelectLot: (locationId: string) => void;
  onRetry: () => void;
  onResetFilters: () => void;
  /** Backend failure to explain in the error state (API mode). */
  errorMessage?: string | null;
  /** Source and backend messages for the current results; null for the dev simulator. */
  resultInfo?: ResultInfo | null;
}

/**
 * Animated results container orchestrating loading skeletons,
 * empty/error messages, and staggered recommendation cards.
 */
export const ResultsList: React.FC<ResultsListProps> = ({
  isLoading,
  isError,
  recommendations,
  searchedRequest,
  searchHistory,
  onRestoreSearch,
  showIntroPrompt,
  usualTripCard,
  isStale,
  availabilityTime,
  confirmedLotId,
  onConfirmLot,
  selectedLocationId,
  onSelectLot,
  onRetry,
  onResetFilters,
  errorMessage = null,
  resultInfo = null,
}) => {
  const api = resultInfo?.source === 'api' ? resultInfo : null;
  // Show the top 3, then reveal 5 more per "Show more" click; reset on every new search
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE);
  const previousVisibleRef = useRef(INITIAL_VISIBLE);
  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE);
    previousVisibleRef.current = INITIAL_VISIBLE;
  }, [recommendations]);

  if (showIntroPrompt && !isLoading && usualTripCard) {
    return <div className="pt-2">{usualTripCard}</div>;
  }

  if (showIntroPrompt && !isLoading) {
    return (
      <div className="pt-2">
        <div className="p-5 text-center rounded-2xl bg-white border border-line space-y-2">
          <div className="w-10 h-10 mx-auto rounded-full bg-paper flex items-center justify-center text-muted">
            <MapPin className="w-5 h-5" aria-hidden="true" />
          </div>
          <p className="text-sm font-semibold text-navy">Enter your trip details to see options</p>
          <p className="text-xs text-muted leading-relaxed">
            Pick where you're going (or use Drop pin on the map), when you'll arrive and your
            permit, then press Find parking. Search a lot by name or tap any P to check it.
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between text-xs text-muted font-medium px-1">
          <span>Finding best matches...</span>
          <span className="text-[11px] animate-pulse">Calculating walking routes</span>
        </div>
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="pt-2">
        <ErrorState onRetry={onRetry} message={errorMessage ?? undefined} />
      </div>
    );
  }

  if (recommendations.length === 0 && api && api.status !== 'ready') {
    return (
      <div className="pt-2 space-y-3">
        {api.isExample && <ExampleBadge />}
        <div role="status" className="p-5 text-center bg-white rounded-2xl border border-line space-y-2">
          <h4 className="text-sm font-bold text-navy">{EMPTY_TITLES[api.status]}</h4>
          <p className="text-xs text-muted max-w-xs mx-auto leading-relaxed">{api.explanation}</p>
          <p className="text-xs text-muted max-w-xs mx-auto leading-relaxed">
            Try a different time, destination or permit.
          </p>
        </div>
        <Limitations notes={api.limitations} />
      </div>
    );
  }

  if (recommendations.length === 0) {
    return (
      <div className="pt-2">
        <EmptyState onResetFilters={onResetFilters} permitType={searchedRequest?.permitType} />
      </div>
    );
  }

  // Cards describe the search that produced them, not whatever the form says now
  const arrival = searchedRequest ? parseArrival(searchedRequest.arrivalDate, searchedRequest.arrivalTime) : null;
  const destinationName = searchedRequest ? getDestination(searchedRequest.destinationId).name : '';

  return (
    <div className="space-y-3 pt-2">
      {api?.isExample && <ExampleBadge />}
      <div className="flex items-center justify-between text-xs text-ink font-medium px-1">
        <span>Recommended for your arrival</span>
        <RecentSearches history={searchHistory} onRestore={onRestoreSearch} />
      </div>

      {/* University holiday: fee waived, category rules unconfirmed */}
      {arrival && holidayNotice(arrival) && (
        <div role="note" className="px-3 py-2 rounded-xl bg-[#D98A00]/15 text-[12px] font-medium text-[#835300]">
          {holidayNotice(arrival)}
        </div>
      )}

      {/* Results no longer match the form: say so and grey them out */}
      {isStale && (
        <div role="status" className="px-3 py-2 rounded-xl bg-[#D98A00]/15 text-[12px] font-medium text-[#835300]">
          Trip details changed. Press Update results to refresh these options.
        </div>
      )}

      <div
        className={`space-y-3 transition-[opacity,filter] duration-200 ${isStale ? 'opacity-50 grayscale' : ''}`}
        aria-disabled={isStale}
      >
        {recommendations.slice(0, visibleCount).map((rec, index) => {
          // Newly revealed cards stagger from their own start, not from the top of the list
          const staggerIndex = index >= previousVisibleRef.current ? index - previousVisibleRef.current : index;
          return (
            <motion.div
              key={rec.lot.locationId}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.25,
                delay: staggerIndex * 0.06,
                ease: [0.16, 1, 0.3, 1],
              }}
            >
              <RecommendationCard
                recommendation={rec}
                userPermit={searchedRequest!.permitType}
                arrival={arrival}
                availabilityTime={availabilityTime}
                destinationName={destinationName}
                isStale={isStale}
                isConfirmed={confirmedLotId === rec.lot.locationId}
                onConfirm={() => onConfirmLot(rec.lot.locationId)}
                isSelected={selectedLocationId === rec.lot.locationId}
                onSelect={() => onSelectLot(rec.lot.locationId)}
              />
            </motion.div>
          );
        })}
      </div>

      {api ? (
        <Limitations notes={api.limitations} />
      ) : (
        <p className="px-1 text-[11px] text-muted leading-snug">
          Open-space numbers are a time-of-day estimate from sample data, not live counts. Walk times are
          straight-line estimates. Always check posted signs and UCSD Transportation before you park.
        </p>
      )}

      {visibleCount < recommendations.length && (
        <button
          type="button"
          disabled={isStale}
          onClick={() => {
            previousVisibleRef.current = visibleCount;
            setVisibleCount((n) => Math.min(recommendations.length, n + LOAD_MORE_STEP));
          }}
          className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-white border border-line hover:bg-white text-[13px] font-semibold text-navy transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronDown className="w-4 h-4" aria-hidden="true" />
          Show {Math.min(LOAD_MORE_STEP, recommendations.length - visibleCount)} more
          <span className="font-normal text-muted">
            ({recommendations.length - visibleCount} left)
          </span>
        </button>
      )}
    </div>
  );
};

/** Shown when the backend says the response is a static example, not a real estimate. */
const ExampleBadge: React.FC = () => (
  <div role="note" className="px-3 py-2 rounded-xl bg-[#D98A00]/15 text-[12px] font-semibold text-[#835300]">
    Example response from the backend, not a real estimate.
  </div>
);

/** The backend's limitations for these results, in its own words. */
const Limitations: React.FC<{ notes: string[] }> = ({ notes }) =>
  notes.length === 0 ? null : (
    <ul className="px-1 space-y-1 text-[11px] text-muted leading-snug list-disc list-inside">
      {notes.map((note) => (
        <li key={note}>{note}</li>
      ))}
    </ul>
  );
