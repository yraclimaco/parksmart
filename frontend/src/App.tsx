/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { ChevronDown, ChevronUp, Menu } from 'lucide-react';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import { MapContainer } from './components/MapContainer.tsx';
import { PreferenceForm } from './components/PreferenceForm.tsx';
import { ResultsList } from './components/ResultsList.tsx';
import { LotDetailCard } from './components/LotDetailCard.tsx';
import { SCRUB_MAX, SCRUB_MIN, TimeScrubber } from './components/TimeScrubber.tsx';
import ucsdLogo from './assets/ucsd-logo.png';
import parkSmartLogo from './assets/parksmart-logo.png';
import { ANIMATION_TIMINGS, DEFAULT_PRIORITY, PRIORITY_OPTIONS, isOnCampus } from './constants.ts';
import { findDestination, makePinDestinationId } from './data/destinations.ts';
import { getArrivalError } from './utils/arrival.ts';
import { parseArrival } from './utils/permitRules.ts';
import { SAMPLE_LOTS, getSampleRecommendations } from './data/sampleRecommendations.ts';
import { RECOMMENDATION_SOURCE } from './config.ts';
import { fetchRecommendations, toRankedOptions, type RankedOption } from './api/recommendations.ts';
import { DirectionsPanel } from './components/DirectionsPanel.tsx';
import { useRoutes } from './hooks/useRoutes.ts';
import type { ResultInfo } from './components/ResultsList.tsx';
import {
  ParkingPlannerRequest,
  ParkingRecommendation,
} from './types.ts';

/** How many earlier searches "Recent" keeps for this visit. */
const MAX_HISTORY = 5;

/** Same destination, date, time, permit, priority and walking limit. */
function sameRequest(a: ParkingPlannerRequest, b: ParkingPlannerRequest): boolean {
  return (
    a.destinationId === b.destinationId &&
    a.arrivalDate === b.arrivalDate &&
    a.arrivalTime === b.arrivalTime &&
    a.permitType === b.permitType &&
    (a.priority ?? DEFAULT_PRIORITY) === (b.priority ?? DEFAULT_PRIORITY) &&
    (a.maxWalkMinutes ?? null) === (b.maxWalkMinutes ?? null)
  );
}

/** Width the open planner panel covers on the left (380px panel + 24px gap). */
const PANEL_OFFSET_PX = 404;

/**
 * Returns today's date formatted as YYYY-MM-DD in local time.
 */
function toDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getTodayDateString(): string {
  return toDateString(new Date());
}

/**
 * Returns the current local time formatted as HH:MM (24-hour, as <input type="time"> expects).
 */
function getCurrentTimeString(): string {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

/** True on phone-width screens, where the planner becomes a bottom sheet instead of a left panel. */
function useIsMobile(): boolean {
  const query = '(max-width: 639px)';
  const [isMobile, setIsMobile] = useState<boolean>(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setIsMobile(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return isMobile;
}

/** True when searches go to the backend; sample-only map features are then hidden. */
const USE_API = RECOMMENDATION_SOURCE === 'api';


/** "HH:MM" to minutes after midnight, clamped to the scrubber's range. */
function minutesOf(time: string): number {
  const [h, m] = time.split(':').map(Number);
  const minutes = Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : 9 * 60;
  return Math.min(SCRUB_MAX, Math.max(SCRUB_MIN, minutes));
}

/** Minutes after midnight to "HH:MM". */
function timeOf(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

/**
 * Main application component.
 * Owns state for formInputs, recommendations, selectedLocationId, and simulated UI states.
 */
export default function App() {
  // 1. Form inputs. No destination until the user picks one (no Geisel default);
  // date and time start at right now.
  // "Your usual" only exists after a real search (saved in this browser only); it is
  // offered as a card, never prefilled into the form.

  const [formInputs, setFormInputs] = useState<ParkingPlannerRequest>(() => ({
    destinationId: '',
    arrivalDate: getTodayDateString(),
    arrivalTime: getCurrentTimeString(),
    permitType: 'S',
    priority: DEFAULT_PRIORITY,
    maxWalkMinutes: null,
  }));

  // Earlier searches this visit, most recent first (the current one is not included).
  // Picking one swaps it with the current search, so X then Y, then "Recent", returns to X.
  const [searchHistory, setSearchHistory] = useState<ParkingPlannerRequest[]>([]);

  // 2. Recommendations State
  const [recommendations, setRecommendations] = useState<ParkingRecommendation[]>([]);

  // 3. Selection State (synchronizes selected card with map marker)
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);

  // 4. Loading & Animation State
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Backend results: where they came from, its status message and limitations, or
  // the error to show. Sample searches set source 'sample' and nothing else.
  const [resultInfo, setResultInfo] = useState<ResultInfo | null>(null);
  // Backend ranking for every ranked location, so any ranked pin's card can show
  // its estimate, walk and why it fits the chosen priority. Empty for sample data.
  const [rankedOptions, setRankedOptions] = useState<Record<string, RankedOption>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  // The exact request the current results were computed for. null until the first
  // search, which is how the panel knows to show its "enter your trip" prompt.
  const [searchedRequest, setSearchedRequest] = useState<ParkingPlannerRequest | null>(null);
  const searchedRequestRef = useRef<ParkingPlannerRequest | null>(null);

  // Lot the user confirmed with "Select this spot"
  const [confirmedLotId, setConfirmedLotId] = useState<string | null>(null);

  // Starting point for driving directions (browser location). Only sent to the
  // ParkSmart backend to compute a route; never saved.
  const [startPoint, setStartPoint] = useState<{ latitude: number; longitude: number } | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);
  const [routeRetry, setRouteRetry] = useState(0);

  // Lot detail card (opened by clicking a pin on the map)
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  // Time scrubber: previewed time of day (minutes after midnight) and play state.
  // Follows the arrival time until the user scrubs.
  const [previewMinutes, setPreviewMinutes] = useState<number>(() => minutesOf(formInputs.arrivalTime));
  const [isTimelinePlaying, setIsTimelinePlaying] = useState<boolean>(false);
  // The Time tool is a toggle in the map's controls; closing it snaps the map and every
  // number back to the arrival time, so nothing keeps showing a time you can no longer see.
  const [isTimeOpen, setIsTimeOpen] = useState<boolean>(false);
  useEffect(() => {
    setPreviewMinutes(minutesOf(formInputs.arrivalTime));
  }, [formInputs.arrivalTime]);
  const handleTimeToggle = useCallback(() => {
    setIsTimeOpen((open) => {
      if (open) setIsTimelinePlaying(false);
      return !open;
    });
  }, []);
  useEffect(() => {
    if (!isTimeOpen) setPreviewMinutes(minutesOf(formInputs.arrivalTime));
  }, [isTimeOpen, formInputs.arrivalTime]);
  const previewTime = useMemo(() => {
    const day = parseArrival(formInputs.arrivalDate, '00:00') ?? new Date();
    day.setHours(Math.floor(previewMinutes / 60), previewMinutes % 60, 0, 0);
    return day;
  }, [formInputs.arrivalDate, previewMinutes]);

  // Side panel open/closed (hamburger toggle)
  const [isPanelOpen, setIsPanelOpen] = useState<boolean>(true);
  const isMobile = useIsMobile();

  // 5. Dev State Simulator

  // Phone: the lot card needs the space, so tuck the planner away while they are open
  useEffect(() => {
    if (isMobile && isDetailOpen) setIsPanelOpen(false);
  }, [isMobile, isDetailOpen]);

  // Phone: the sheet is short, so bring the results into view after each search
  useEffect(() => {
    if (!isMobile || searchedRequest === null || isLoading) return;
    // Scroll only the sheet's own list (scrollIntoView can also shift the page behind it)
    const results = document.getElementById('planner-results');
    const box = document.getElementById('planner-scroll');
    if (results && box) {
      box.scrollTo({
        top: box.scrollTop + results.getBoundingClientRect().top - box.getBoundingClientRect().top - 8,
        behavior: 'smooth',
      });
    }
  }, [isMobile, searchedRequest, isLoading]);

  // Compute recommendations from current formInputs
  const runPlanner = useCallback(
    (customInputs?: ParkingPlannerRequest) => {
      const inputs = customInputs || formInputs;
      if (getArrivalError(inputs)) return; // the form shows the message; nothing to search
      if (!findDestination(inputs.destinationId)) return; // no destination picked yet
      setIsLoading(true);
      setErrorMessage(null);
      setIsDetailOpen(false); // a new search shows results in the panel, not the pin card
      setConfirmedLotId(null);

      const finish = (
        results: ParkingRecommendation[],
        info: ResultInfo,
        options: Record<string, RankedOption> = {}
      ) => {
        setRecommendations(results);
        setResultInfo(info);
        setRankedOptions(options);
        // Move the search being replaced into history (unless it is the same trip)
        const previous = searchedRequestRef.current;
        if (previous && !sameRequest(previous, inputs)) {
          setSearchHistory((history) =>
            [previous, ...history.filter((r) => !sameRequest(r, previous) && !sameRequest(r, inputs))].slice(0, MAX_HISTORY)
          );
        }
        searchedRequestRef.current = inputs;
        setSearchedRequest(inputs);
        setIsLoading(false);

        // Pre-select the First Choice recommendation lot by default
        setSelectedLocationId(results[0]?.lot.locationId ?? null);
      };

      if (USE_API) {
        // Only the latest search may update the panel
        requestRef.current?.abort();
        const controller = new AbortController();
        requestRef.current = controller;
        fetchRecommendations(inputs, { signal: controller.signal })
          .then((outcome) => {
            if (controller.signal.aborted) return;
            if (outcome.kind === 'error') {
              setRecommendations([]);
              setResultInfo(null);
              setRankedOptions({});
              setErrorMessage(outcome.message);
              setIsLoading(false);
              return;
            }
            const { response } = outcome;
            finish(
              outcome.recommendations,
              {
                source: 'api',
                status: response.status,
                explanation: response.explanation,
                limitations: response.limitations,
                isExample: response.is_example,
              },
              toRankedOptions(response)
            );
          })
          .catch(() => {
            // Aborted by a newer search; that search owns the loading state.
          });
        return () => controller.abort();
      }

      const sample = () => finish(getSampleRecommendations(inputs).recommendations, { source: 'sample' });
      // Sample data answers instantly; a real API call would keep the loading state up
      if (ANIMATION_TIMINGS.SHIMMER_DURATION_MS === 0) {
        sample();
        return;
      }
      const timer = setTimeout(sample, ANIMATION_TIMINGS.SHIMMER_DURATION_MS);
      return () => clearTimeout(timer);
    },
    [formInputs]
  );

  // Handle preference form changes
  const handleFormChange = (changes: Partial<ParkingPlannerRequest>) => {
    if (changes.destinationId !== undefined) setPinNotice(null);
    setFormInputs((prev) => ({
      ...prev,
      ...changes,
    }));
  };

  // Handle Form Submission
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runPlanner();
  };

  // Handle lot selection (from card click or marker click)
  const handleSelectLot = useCallback((locationId: string) => {
    setSelectedLocationId((prev) => (prev === locationId ? null : locationId));
  }, []);

  // Handle clearing selection on map background click
  // Pin clicks on the map also open the lot detail card (panel card clicks do not,
  // since those cards already show the same details)
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedLocationId;
  const handleSelectLotFromMap = useCallback((locationId: string) => {
    const next = selectedIdRef.current === locationId ? null : locationId;
    setSelectedLocationId(next);
    setIsDetailOpen(next !== null);
  }, []);

  // Whenever nothing is selected (from any source), the card is closed too
  useEffect(() => {
    if (!selectedLocationId) setIsDetailOpen(false);
  }, [selectedLocationId]);

  const handleClearSelection = useCallback(() => {
    setIsDetailOpen(false);
    setSelectedLocationId(null);
  }, []);

  // Lot whose detail card is open (any selected pin or card)
  const selectedLot = useMemo(
    () => SAMPLE_LOTS.find((lot) => lot.locationId === selectedLocationId) ?? null,
    [selectedLocationId]
  );

  // Esc closes the lot card
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsDetailOpen(false);
        setSelectedLocationId(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Handle retry from error state
  const handleRetry = () => {
    runPlanner();
  };

  // Handle resetting filters from empty state
  const handleResetFilters = () => {
    const updated: ParkingPlannerRequest = { ...formInputs, permitType: 'S' };
    setFormInputs(updated);
    runPlanner(updated);
  };

  // Selected campus destination (or dropped pin); null until the user picks one
  const currentDestination = useMemo(
    () => findDestination(formInputs.destinationId) ?? null,
    [formInputs.destinationId]
  );

  // A parking lot picked in the search box: select its pin and open its card.
  // It does not become the destination.
  const handleSelectParking = useCallback((locationId: string) => {
    setSelectedLocationId(locationId);
    setIsDetailOpen(true);
  }, []);

  // "Drop pin" on the map: use the clicked spot as the destination
  const [pinNotice, setPinNotice] = useState<string | null>(null);
  const handleDropPin = useCallback((latitude: number, longitude: number): boolean => {
    if (!isOnCampus(latitude, longitude)) {
      setPinNotice('That spot is off campus. Drop the pin on the UCSD campus, or pick a building.');
      return false;
    }
    setPinNotice(null);
    setFormInputs((prev) => ({ ...prev, destinationId: makePinDestinationId(latitude, longitude) }));
    return true;
  }, []);

  // Turning Drop pin off removes the dropped pin
  const handleClearPin = useCallback(() => {
    setPinNotice(null);
    setFormInputs((prev) => (findDestination(prev.destinationId)?.isPin ? { ...prev, destinationId: '' } : prev));
  }, []);

  // Re-run an earlier search from "Recent"
  const handleRestoreSearch = (request: ParkingPlannerRequest) => {
    setFormInputs(request);
    runPlanner(request);
  };

  // Results go stale when any trip detail changes after the search that produced them
  const isStale =
    searchedRequest !== null &&
    (searchedRequest.destinationId !== formInputs.destinationId ||
      searchedRequest.permitType !== formInputs.permitType ||
      searchedRequest.arrivalDate !== formInputs.arrivalDate ||
      searchedRequest.arrivalTime !== formInputs.arrivalTime ||
      (searchedRequest.priority ?? DEFAULT_PRIORITY) !== (formInputs.priority ?? DEFAULT_PRIORITY) ||
      (searchedRequest.maxWalkMinutes ?? null) !== (formInputs.maxWalkMinutes ?? null));

  // Inline validation for the arrival date/time (empty or already passed)
  const arrivalError = getArrivalError(formInputs);

  // First choice / backup IDs for labeling pins (hidden while results are stale)
  const rankedLotIds = useMemo(() => {
    if (isStale) return { first: null, backup: null, third: null };
    return {
      first: recommendations[0]?.lot.locationId ?? null,
      backup: recommendations[1]?.lot.locationId ?? null,
      third: recommendations[2]?.lot.locationId ?? null,
    };
  }, [recommendations, isStale]);

  // Confirming a spot also selects it, so the highlighted card, the map pin and
  // the route always point at the same lot. Undoing keeps the selection.
  const handleConfirmLot = useCallback((locationId: string) => {
    setConfirmedLotId((prev) => (prev === locationId ? null : locationId));
    setSelectedLocationId(locationId);
  }, []);

  const handleUseMyLocation = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setLocateError('This browser cannot share your location.');
      return;
    }
    setIsLocating(true);
    setLocateError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setIsLocating(false);
        setStartPoint({ latitude: position.coords.latitude, longitude: position.coords.longitude });
      },
      (error) => {
        setIsLocating(false);
        setLocateError(
          error.code === error.PERMISSION_DENIED
            ? 'Location permission is off. Allow it in your browser to see driving directions.'
            : "Couldn't find your location. Try again."
        );
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 5 * 60_000 }
    );
  }, []);

  // Rendering state for the results list
  const activeIsLoading = isLoading;
  const activeIsError = errorMessage !== null;
  const activeRecommendations = recommendations;

  // Routes follow the selected result (first choice after a search, or whichever card
  // or pin the user picks). Only real backend results have routes; stale results and
  // sample data do not.
  const routedRecommendation =
    USE_API && !isStale
      ? activeRecommendations.find((rec) => rec.lot.locationId === selectedLocationId) ?? null
      : null;
  const routedDestination = searchedRequest ? findDestination(searchedRequest.destinationId) ?? null : null;
  const routeLegs = useRoutes(
    routedRecommendation !== null,
    routedRecommendation ? routedRecommendation.lot : null,
    routedDestination,
    startPoint,
    routeRetry
  );

  return (
    // reducedMotion="user" turns off Motion animations for people who ask their OS for less motion
    <MotionConfig reducedMotion="user">
    <div className="relative w-full h-screen h-[100dvh] overflow-hidden overscroll-none bg-slate-100 font-sans text-navy select-none">
      {/* Full-Screen MapLibre GL Map */}
      <MapContainer
        lots={SAMPLE_LOTS}
        selectedLocationId={selectedLocationId}
        selectedDestination={currentDestination}
        onSelectLot={handleSelectLotFromMap}
        onClearSelection={handleClearSelection}
        onDropPin={handleDropPin}
        hasDroppedPin={currentDestination?.isPin === true}
        onClearPin={handleClearPin}
        isTimeOpen={isTimeOpen}
        onTimeToggle={handleTimeToggle}
        timePanel={
          <TimeScrubber
            day={previewTime}
            minutes={previewMinutes}
            onMinutesChange={setPreviewMinutes}
            isPlaying={isTimelinePlaying}
            onPlayingChange={setIsTimelinePlaying}
            differsFromArrival={previewMinutes !== minutesOf(formInputs.arrivalTime)}
            onUseTime={() => handleFormChange({ arrivalTime: timeOf(previewMinutes) })}
          />
        }
        isPanelOpen={isPanelOpen}
        isDetailOpen={isDetailOpen}
        rankedLotIds={rankedLotIds}
        availabilityTime={previewTime}
        showSampleAvailability={!USE_API}
        routeLines={{
          driving: routeLegs.driving.status === 'ok' ? routeLegs.driving.route.geometry : null,
          walking: routeLegs.walking.status === 'ok' ? routeLegs.walking.route.geometry : null,
        }}
        startPoint={routedRecommendation ? startPoint : null}
      />

      {/* Desktop: hamburger toggle in the top-left whether the panel is open or closed */}
      <button
        type="button"
        onClick={() => setIsPanelOpen((open) => !open)}
        aria-label={isPanelOpen ? 'Hide planner panel' : 'Show planner panel'}
        aria-expanded={isPanelOpen}
        aria-controls="planner-panel"
        className={`max-sm:hidden absolute left-4 ${isPanelOpen ? 'top-[22px]' : 'top-4'} z-30 w-9 h-9 rounded-[10px] flex items-center justify-center text-navy transition-colors duration-200 hover:bg-paper active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/50 cursor-pointer ${
          isPanelOpen
            ? ''
            : 'bg-white border border-line shadow-[0_1px_2px_rgba(24,43,73,0.08),0_4px_12px_rgba(24,43,73,0.1)]'
        }`}
      >
        <Menu className="w-5 h-5" aria-hidden="true" />
      </button>

      {/* Phones: an arrow tab on the sheet's top edge slides the planner down and back up */}
      <button
        type="button"
        onClick={() => setIsPanelOpen((open) => !open)}
        aria-label={isPanelOpen ? 'Hide planner panel' : 'Show planner panel'}
        aria-expanded={isPanelOpen}
        aria-controls="planner-panel"
        className={`sm:hidden absolute left-1/2 -translate-x-1/2 z-30 h-8 px-4 rounded-full bg-white border border-line text-navy flex items-center justify-center gap-1 text-[12px] font-semibold shadow-[0_2px_10px_rgba(24,43,73,0.18)] transition-[top,bottom] duration-300 ease-out motion-reduce:transition-none active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/50 cursor-pointer ${
          isPanelOpen ? 'top-[calc(50%-16px)]' : 'top-[calc(100%-80px)]'
        }`}
      >
        {isPanelOpen ? (
          <ChevronDown className="w-5 h-5" aria-hidden="true" />
        ) : (
          <>
            <ChevronUp className="w-5 h-5" aria-hidden="true" />
            <span>Planner</span>
          </>
        )}
      </button>

      {/* Planner: a solid sheet on the left edge (a bottom sheet on phones), slides out when hidden */}
      <aside
        id="planner-panel"
        aria-label="Parking planner controls and recommendations"
        aria-hidden={!isPanelOpen}
        inert={!isPanelOpen}
        className={`absolute top-0 left-0 bottom-0 w-[388px] max-w-full max-sm:top-1/2 max-sm:bottom-9 max-sm:left-3 max-sm:right-3 max-sm:w-auto max-sm:max-w-none z-20 flex flex-col transition-transform duration-300 ease-out motion-reduce:transition-none ${
          isPanelOpen
            ? 'translate-x-0 pointer-events-auto'
            : '-translate-x-full max-sm:translate-x-0 max-sm:translate-y-[calc(100%+3rem)] pointer-events-none'
        }`}
      >
        <div className="flex-1 flex flex-col bg-white border-r border-line max-sm:border max-sm:rounded-2xl shadow-[4px_0_24px_rgba(24,43,73,0.12)] max-sm:shadow-[0_4px_24px_rgba(24,43,73,0.2)] overflow-hidden">
          {/* Panel header. Left padding leaves room for the hamburger button that sits on top. */}
          <header className="pl-[60px] max-sm:pl-4 pr-4 pt-[22px] pb-3.5 border-b-2 border-gold shrink-0">
            {/* One 36px row, centered on the hamburger button that sits on top of its left end */}
            <div className="flex items-center justify-between gap-3 h-9">
              <div className="flex items-center gap-2 min-w-0">
                <img src={parkSmartLogo} alt="" aria-hidden="true" className="w-9 h-9 block shrink-0" />
                <h1 className="font-serif text-[26px] font-semibold text-navy tracking-[-0.01em] leading-none">
                  ParkSmart
                </h1>
              </div>

              {/* UC San Diego wordmark (transparent PNG, sits directly on the panel) */}
              <img src={ucsdLogo} alt="UC San Diego" className="h-[20px] w-auto block shrink-0" />
            </div>
            <p className="mt-2 text-[13px] text-muted leading-snug">
              Find where to park before you arrive.
            </p>
          </header>

          {/* Internally Scrollable Body */}
          <div
            id="planner-scroll"
            className="flex-1 overflow-y-auto overflow-x-hidden px-5 py-4 space-y-4 overscroll-contain touch-pan-y focus:outline-none"
          >
            {/* Preference Form Section */}
            <section aria-labelledby="planner-preferences-title">
              <h2 id="planner-preferences-title" className="sr-only">
                Trip Preferences
              </h2>
              <PreferenceForm
                formData={formInputs}
                onChange={handleFormChange}
                onSubmit={handleFormSubmit}
                isLoading={activeIsLoading}
                arrivalError={arrivalError}
                onSetArrivalNow={() =>
                  handleFormChange({ arrivalDate: getTodayDateString(), arrivalTime: getCurrentTimeString() })
                }
                submitLabel={isStale ? 'Update results' : 'Find parking'}
                onSelectParking={handleSelectParking}
              />
              {pinNotice && (
                <p role="status" className="mt-3 px-3 py-2 rounded-lg bg-[#D98A00]/12 border border-[#D98A00]/30 text-[12px] font-medium text-[#835300]">
                  {pinNotice}
                </p>
              )}
            </section>

            {/* Subtle Divider */}
            <div className="flex items-center gap-3 py-0.5 text-[13px] font-semibold text-navy">
              <span>Results</span>
              <div className="flex-1 border-t border-line" />
            </div>

            {/* Results Section */}
            <section id="planner-results" aria-labelledby="planner-results-title">
              <h2 id="planner-results-title" className="sr-only">
                Recommended Parking
              </h2>
              <ResultsList
                isLoading={activeIsLoading}
                isError={activeIsError}
                recommendations={activeRecommendations}
                searchedRequest={searchedRequest}
                searchHistory={searchHistory}
                onRestoreSearch={handleRestoreSearch}
                showIntroPrompt={searchedRequest === null}
                isStale={isStale}
                availabilityTime={previewTime}
                confirmedLotId={confirmedLotId}
                onConfirmLot={handleConfirmLot}
                selectedLocationId={selectedLocationId}
                onSelectLot={handleSelectLot}
                onRetry={handleRetry}
                onResetFilters={handleResetFilters}
                errorMessage={errorMessage}
                resultInfo={resultInfo}
                directions={
                  routedRecommendation && routedDestination ? (
                    <DirectionsPanel
                      lotName={routedRecommendation.lot.name}
                      destinationName={routedDestination.name}
                      legs={routeLegs}
                      startLabel={startPoint ? 'your location' : null}
                      isLocating={isLocating}
                      locateError={locateError}
                      onUseMyLocation={handleUseMyLocation}
                      onClearStart={() => {
                        setStartPoint(null);
                        setLocateError(null);
                      }}
                      onRetry={() => setRouteRetry((n) => n + 1)}
                    />
                  ) : null
                }
              />
            </section>
          </div>

          {/* Panel Footer Note */}
          <footer className="px-5 py-2.5 bg-paper border-t border-line text-[11px] text-muted leading-snug shrink-0">
            <span>
              {USE_API
                ? 'Historical estimates from past surveys, not live availability.'
                : 'Sample data. Estimates only.'}{' '}
              Unofficial student project, not affiliated with UC San Diego.
            </span>
          </footer>
        </div>
      </aside>

      {/* Dev Simulator Toggle (Tucked into bottom right corner) */}
      {/* Lot detail card: centered in the visible map area (beside the panel when it is open) */}
      <div
        className="absolute bottom-6 max-sm:bottom-10 z-20 -translate-x-1/2 transition-[left] duration-300 ease-out pointer-events-none"
        style={{ left: isPanelOpen && !isMobile ? `calc(${PANEL_OFFSET_PX}px + (100% - ${PANEL_OFFSET_PX}px) / 2)` : '50%' }}
      >
        <AnimatePresence mode="wait">
          {isDetailOpen && selectedLot && (
            // Only transforms here. Fading a *parent* of a backdrop-filter element makes
            // Chrome skip the blur until the fade ends (the frost "pops in"), so the
            // opacity fade lives on the glass card itself (see LotDetailCard).
            <motion.div
              key={selectedLot.locationId}
              className="pointer-events-auto"
              initial={{ y: 20, scale: 0.97 }}
              animate={{ y: 0, scale: 1 }}
              exit={{ y: 12, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 600, damping: 38 }}
            >
              <LotDetailCard
                lot={selectedLot}
                userPermit={formInputs.permitType}
                arrival={parseArrival(formInputs.arrivalDate, formInputs.arrivalTime)}
                availabilityTime={previewTime}
                destination={currentDestination}
                rankLabel={
                  isStale
                    ? null
                    : rankedOptions[selectedLot.locationId]?.badgeLabel ??
                      activeRecommendations.find((r) => r.lot.locationId === selectedLot.locationId)?.badgeLabel ??
                      null
                }
                isConfirmed={confirmedLotId === selectedLot.locationId}
                onConfirm={() => handleConfirmLot(selectedLot.locationId)}
                backendMode={USE_API}
                backendEstimate={
                  isStale
                    ? null
                    : rankedOptions[selectedLot.locationId]?.estimate ??
                      activeRecommendations.find((r) => r.lot.locationId === selectedLot.locationId)?.estimate ??
                      null
                }
                priorityLabel={
                  PRIORITY_OPTIONS.find((o) => o.value === (searchedRequest?.priority ?? DEFAULT_PRIORITY))?.label ??
                  null
                }
                onPlanFor={(date) =>
                  handleFormChange({
                    arrivalDate: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
                    arrivalTime: `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`,
                  })
                }
                onClose={handleClearSelection}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

    </div>
    </MotionConfig>
  );
}
