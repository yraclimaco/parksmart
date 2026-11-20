/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { ArrowLeft, ChevronDown, ChevronUp, Menu, RotateCcw } from 'lucide-react';
import 'maplibre-gl/dist/maplibre-gl.css';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import { MapContainer } from './components/MapContainer.tsx';
import { LoadingScreen } from './components/LoadingScene.tsx';
import { PreferenceForm } from './components/PreferenceForm.tsx';
import { ResultsList } from './components/ResultsList.tsx';
import { LotDetailCard } from './components/LotDetailCard.tsx';
import { SCRUB_MAX, SCRUB_MIN, TimeScrubber } from './components/TimeScrubber.tsx';
import ucsdLogo from './assets/ucsd-logo.png';
import parkSmartLogo from './assets/parksmart-logo.png';
import { SchedulePanel, type ClassTrip } from './components/SchedulePanel.tsx';
import { recordRecentDestination } from './utils/recentDestinations.ts';
import {
  DEFAULT_PREFERENCES,
  clearPreferences,
  isCustomized,
  loadPreferences,
  savePreferences,
  type SavedPreferences,
} from './utils/savedPreferences.ts';
import { ANIMATION_TIMINGS, DEFAULT_PRIORITY, PRIORITY_OPTIONS, isOnCampus } from './constants.ts';
import { findDestination, makePinDestinationId } from './data/destinations.ts';
import { alertArrivalTime, getArrivalError } from './utils/arrival.ts';
import {
  blankRequest,
  formatLocalDate,
  formatLocalTime,
  isResultStale,
  sameRequest,
  shouldAutoRefresh,
} from './utils/plannerState.ts';
import { parseArrival } from './utils/permitRules.ts';
import { SAMPLE_LOTS, getSampleRecommendations } from './data/sampleRecommendations.ts';
import { RECOMMENDATION_SOURCE } from './config.ts';
import { fetchRecommendations, toRankedOptions, type RankedOption } from './api/recommendations.ts';
import { TripDetails } from './components/TripDetails.tsx';
import { OSM_FIX_THE_MAP_URL } from './api/routes.ts';
import { useTripAlerts } from './hooks/useTripAlerts.ts';
import { useRoutes } from './hooks/useRoutes.ts';
import type { ResultInfo } from './components/ResultsList.tsx';
import {
  ParkingPlannerRequest,
  ParkingRecommendation,
} from './types.ts';

/** Quiet time after the last change before results refresh by themselves (about one request a second at most). */
const AUTO_REFRESH_DELAY_MS = 1000;

/** Width the open planner panel covers on the left (380px panel + 24px gap). */
const PANEL_OFFSET_PX = 404;

/** How many earlier searches "Recent" keeps for this visit. */
const MAX_HISTORY = 5;

/** Today's date as YYYY-MM-DD, local time. */
function getTodayDateString(): string {
  return formatLocalDate(new Date());
}

/** The current local time as HH:MM (24-hour). */
function getCurrentTimeString(): string {
  return formatLocalTime(new Date());
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

/** The setting that is remembered between visits: the permit. */
function preferencesOf(request: Pick<ParkingPlannerRequest, 'permitType'>): SavedPreferences {
  return { permitType: request.permitType };
}

/**
 * Main application component.
 * Owns state for formInputs, recommendations, selectedLocationId, and simulated UI states.
 */
interface PlannerProps {
  /** Returns to the landing page. */
  onBack: () => void;
}

// True after the first time the planner has been shown in this page load
let plannerShownOnce = false;

export default function Planner({ onBack }: PlannerProps) {
  // 1. Form inputs. No destination until the user picks one (no Geisel default);
  // date and time start at right now.
  // "Your usual" only exists after a real search (saved in this browser only); it is
  // offered as a card, never prefilled into the form.

  // The permit comes back from the last visit (this browser only); everything else starts blank
  // and per trip. Priority and walking limit are fixed defaults with no controls.
  const [formInputs, setFormInputs] = useState<ParkingPlannerRequest>(() => ({
    ...blankRequest(),
    ...(loadPreferences() ?? DEFAULT_PREFERENCES),
  }));

  // Earlier searches this visit, most recent first (the current one is not included).
  // Picking one swaps it with the current search, so X then Y, then "Recent", returns to X.
  const [searchHistory, setSearchHistory] = useState<ParkingPlannerRequest[]>([]);

  // 2. Recommendations State
  const [recommendations, setRecommendations] = useState<ParkingRecommendation[]>([]);

  // 3. Selection State (synchronizes selected card with map marker)
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);

  // Full-window loading screen: stays until the map has drawn, and at least a moment on the
  // first visit so it never flashes when tiles are cached
  const [mapReady, setMapReady] = useState(false);
  const [minShown, setMinShown] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setMinShown(true), plannerShownOnce ? 500 : 1500);
    plannerShownOnce = true;
    return () => window.clearTimeout(id);
  }, []);
  const handleMapReady = useCallback(() => setMapReady(true), []);

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

  // Bring the answer into view after each search: the form above it is tall on every screen size
  useEffect(() => {
    if (searchedRequest === null || isLoading) return;
    // Scroll only the sheet's own list (scrollIntoView can also shift the page behind it)
    const results = document.getElementById('planner-results');
    const box = document.getElementById('planner-scroll');
    if (results && box) {
      box.scrollTo({
        top: box.scrollTop + results.getBoundingClientRect().top - box.getBoundingClientRect().top - 8,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      });
    }
  }, [searchedRequest, isLoading]);

  // Compute recommendations from current formInputs
  const runPlanner = useCallback(
    (customInputs?: ParkingPlannerRequest) => {
      const inputs = customInputs || formInputs;
      if (getArrivalError(inputs)) return; // the form shows the message; nothing to search
      const destination = findDestination(inputs.destinationId);
      if (!destination) return; // no destination picked yet
      if (!destination.isPin) recordRecentDestination(destination.id); // one-tap repeat trips
      setIsLoading(true);
      setErrorMessage(null);
      setIsDetailOpen(false); // a new search shows results in the panel, not the pin card

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

  // Picking a destination in the form searches right away (one request per pick), so a repeat
  // trip is two taps. Changes to the permit or time refresh on their own after a pause (below).
  const handleDestinationOrFormChange = (changes: Partial<ParkingPlannerRequest>) => {
    handleFormChange(changes);
    if (changes.destinationId) runPlanner({ ...formInputs, ...changes });
  };

  // Park for a class from the imported schedule: set the arrival just before it starts and,
  // when its building is known, search right away (a destination pick searches on its own)
  const handlePlanClass = (trip: ClassTrip) => {
    const { destinationId, arrivalDate, arrivalTime } = trip;
    if (destinationId) handleDestinationOrFormChange({ destinationId, arrivalDate, arrivalTime });
    else handleFormChange({ arrivalDate, arrivalTime });
  };

  // Back to the first-visit permit (S); the effect below forgets the saved one
  const handleResetPreferences = () => {
    setFormInputs((prev) => ({ ...prev, ...DEFAULT_PREFERENCES }));
  };

  // Clear all: back to an empty planner, like a fresh visit. The trip form (destination, arrival,
  // permit) and everything shown from the search (results, selection, routes' start, errors) reset.
  // The imported schedule, starred and recent places and "Recent" searches this visit stay.
  const handleClearAll = () => {
    requestRef.current?.abort(); // a search still in flight must not fill the cleared panel
    setFormInputs(blankRequest());
    setRecommendations([]);
    setResultInfo(null);
    setRankedOptions({});
    setErrorMessage(null);
    setIsLoading(false);
    searchedRequestRef.current = null;
    setSearchedRequest(null);
    setSelectedLocationId(null);
    setIsDetailOpen(false);
    setStartPoint(null);
    setLocateError(null);
    setPinNotice(null);
  };

  // Remember the permit after every change. Saving from state (not from the event) means
  // quick successive changes never overwrite each other. The default permit stores nothing.
  const { permitType } = formInputs;
  useEffect(() => {
    const prefs = preferencesOf({ permitType });
    if (isCustomized(prefs)) savePreferences(prefs);
    else clearPreferences();
  }, [permitType]);

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
  const isStale = isResultStale(searchedRequest, formInputs);

  // Inline validation for the arrival date/time (empty or already passed)
  const arrivalError = getArrivalError(formInputs);

  // After a first search, changing the permit or arrival time refreshes the results on its own once
  // the changes settle, so there is no Update tap. One request per settled change keeps the
  // rate-limited hosted API safe; a new destination searches at once instead (see shouldAutoRefresh).
  const autoRefresh = shouldAutoRefresh(searchedRequest, formInputs, arrivalError);
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setTimeout(() => runPlanner(formInputs), AUTO_REFRESH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [autoRefresh, formInputs, runPlanner]);

  // First choice / backup IDs for labeling pins (hidden while results are stale)
  const rankedLotIds = useMemo(() => {
    if (isStale) return { first: null, backup: null, third: null };
    return {
      first: recommendations[0]?.lot.locationId ?? null,
      backup: recommendations[1]?.lot.locationId ?? null,
      third: recommendations[2]?.lot.locationId ?? null,
    };
  }, [recommendations, isStale]);

  // Opening directions for a spot chooses it, so the highlighted card, the map pin and the
  // route always point at the same lot. Unlike a card click it never toggles the selection off.
  const handleChooseLot = useCallback((locationId: string) => {
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

  // If this browser has already allowed location for the site, use it as the driving start as
  // soon as there are results, so directions need no tap. Never prompts: when permission is
  // not granted yet, the "Use my location" button stays the way to ask.
  const autoLocateTried = useRef(false);
  const hasResults = recommendations.length > 0;
  useEffect(() => {
    if (!hasResults || startPoint || autoLocateTried.current) return;
    autoLocateTried.current = true;
    if (!('permissions' in navigator) || !('geolocation' in navigator)) return;
    navigator.permissions
      .query({ name: 'geolocation' })
      .then((status) => {
        if (status.state === 'granted') handleUseMyLocation();
      })
      .catch(() => {
        // Permissions API unavailable: leave the button as the way to share location
      });
  }, [hasResults, startPoint, handleUseMyLocation]);

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

  const routeAttribution =
    [routeLegs.driving, routeLegs.walking].find(
      (leg): leg is Extract<typeof routeLegs.driving, { status: 'ok' }> => leg.status === 'ok'
    )?.route.attribution ?? null;

  // Weather and construction notices for the same selected result. Separate from the
  // search: if they fail, the parking results above are unaffected.
  const [alertsRetry, setAlertsRetry] = useState(0);
  // The arrival sent for weather is worked out once per search. "Now" moves every minute, so
  // recomputing it on each render would change the request every minute and refetch for nothing.
  const alertArrival = useMemo(
    () => (searchedRequest ? alertArrivalTime(searchedRequest.arrivalDate, searchedRequest.arrivalTime) : null),
    [searchedRequest]
  );
  const tripAlerts = useTripAlerts(
    routedRecommendation !== null && searchedRequest !== null,
    routedRecommendation && searchedRequest
      ? {
          arrivalTime: alertArrival ?? '',
          parkingLocationId: routedRecommendation.lot.locationId,
          destination: routedDestination
            ? { name: routedDestination.name, latitude: routedDestination.latitude, longitude: routedDestination.longitude }
            : null,
        }
      : null,
    alertsRetry
  );

  return (
    // reducedMotion="user" turns off Motion animations for people who ask their OS for less motion
    <MotionConfig reducedMotion="user">
    <div className="relative w-full h-screen h-[100dvh] overflow-hidden overscroll-none bg-slate-100 font-sans text-navy select-none">
      <LoadingScreen visible={!(mapReady && minShown)} label="Loading the map" />

      {/* Full-Screen MapLibre GL Map */}
      <MapContainer
        onReady={handleMapReady}
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
        className={`max-sm:hidden absolute left-4 ${isPanelOpen ? 'top-[22px]' : 'top-4'} z-30 w-9 h-9 before:content-[''] before:absolute before:-inset-1 rounded-[10px] flex items-center justify-center text-navy transition-colors duration-200 hover:bg-paper active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer ${
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
        className={`sm:hidden absolute left-1/2 -translate-x-1/2 z-30 h-8 px-4 before:content-[''] before:absolute before:-inset-y-2 before:inset-x-0 rounded-full bg-white border border-line text-navy flex items-center justify-center gap-1 text-[12px] font-semibold shadow-[0_2px_10px_rgba(24,43,73,0.18)] transition-[top,bottom] duration-300 ease-out motion-reduce:transition-none active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer ${
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
        // `inert` alone hides a closed panel from assistive tech and takes focus out of it. Adding
        // aria-hidden as well made the browser warn when something inside still had focus.
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
            {/* Second row: Clear all sits under the hamburger button (the panel's left padding is
                pulled back on desktop so it lines up with it), then the tagline and Home */}
            <div className="mt-2 flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleClearAll}
                aria-label="Clear all: reset the destination, time, permit and results"
                className="shrink-0 -ml-[44px] max-sm:ml-0 inline-flex relative before:content-[''] before:absolute before:-inset-2 items-center gap-1 h-7 pl-2 pr-2.5 rounded-full border border-line bg-white text-[12px] font-semibold text-navy transition-colors duration-200 hover:bg-paper active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Clear all</span>
              </button>
              <p className="flex-1 min-w-0 text-[13px] text-muted leading-snug">
                Find where to park before you arrive.
              </p>
              <button
                type="button"
                onClick={onBack}
                aria-label="Back to the ParkSmart home page"
                className="shrink-0 inline-flex relative before:content-[''] before:absolute before:-inset-2 items-center gap-1 h-7 pl-1.5 pr-2.5 rounded-full border border-line bg-white text-[12px] font-semibold text-navy transition-colors duration-200 hover:bg-paper active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Home</span>
              </button>
            </div>
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
                hasSavedSettings={isCustomized(preferencesOf(formInputs))}
                onResetSettings={handleResetPreferences}
                onChange={handleDestinationOrFormChange}
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

            {/* Class schedule: import once, then park for any class in one tap */}
            <SchedulePanel date={formInputs.arrivalDate} onPlanClass={handlePlanClass} />

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
                onChooseLot={handleChooseLot}
                selectedLocationId={selectedLocationId}
                onSelectLot={handleSelectLot}
                onRetry={handleRetry}
                onResetFilters={handleResetFilters}
                errorMessage={errorMessage}
                resultInfo={resultInfo}
                renderDetails={(rec) =>
                  routedRecommendation && routedDestination && rec.lot.locationId === routedRecommendation.lot.locationId ? (
                    <TripDetails
                      tone={rec.badgeLabel === 'First choice' ? 'dark' : 'light'}
                      destinationName={routedDestination.name}
                      legs={routeLegs}
                      fallbackWalkMinutes={rec.estimate?.walkingMinutes ?? rec.lot.walkingMinutes ?? null}
                      startLabel={startPoint ? 'your location' : null}
                      isLocating={isLocating}
                      locateError={locateError}
                      onUseMyLocation={handleUseMyLocation}
                      onClearStart={() => {
                        setStartPoint(null);
                        setLocateError(null);
                      }}
                      onRetryRoutes={() => setRouteRetry((n) => n + 1)}
                      alerts={tripAlerts}
                      onRetryAlerts={() => setAlertsRetry((n) => n + 1)}
                    />
                  ) : null
                }
                extraNotes={
                  routedRecommendation ? (
                    <p>
                      Drive and walk times are typical, without live traffic. Routes use the parking location’s map point,
                      which may not be its entrance.
                      {routeAttribution && (
                        <>
                          {' '}
                          {routeAttribution} ·{' '}
                          <a href={OSM_FIX_THE_MAP_URL} target="_blank" rel="noopener noreferrer" className="underline hover:text-navy">
                            Fix the map
                          </a>
                        </>
                      )}
                    </p>
                  ) : null
                }
              />
            </section>
          </div>

          {/* Panel Footer Note */}
          <footer className="px-5 py-2.5 bg-paper border-t border-line text-xs text-muted leading-snug shrink-0">
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
                onChoose={() => handleChooseLot(selectedLot.locationId)}
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
