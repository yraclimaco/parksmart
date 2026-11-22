/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { LoadingScreen } from './components/LoadingScene.tsx';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { LandingPage } from './components/LandingPage.tsx';
import { PlannerBoundary } from './components/PlannerBoundary.tsx';

// Lazy-load the planner so MapLibre, tile workers, and map APIs do not load until opened.
const Planner = lazy(() => import('./Planner.tsx'));

const FADE_DURATION_MS = 250;

export default function App() {
  // Every visit starts on the landing page and its intro, even for people who used the planner before
  const [view, setView] = useState<'landing' | 'planner'>('landing');
  const [isExitingLanding, setIsExitingLanding] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  const handleOpenPlanner = () => {
    if (view === 'planner' || isExitingLanding) return;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      setView('planner');
      return;
    }
    setIsExitingLanding(true);
    timerRef.current = window.setTimeout(() => {
      setView('planner');
    }, FADE_DURATION_MS);
  };

  const handleBackToLanding = () => {
    setIsExitingLanding(false);
    setView('landing');
  };

  if (view === 'landing') {
    return <LandingPage isExiting={isExitingLanding} onPlanClick={handleOpenPlanner} />;
  }

  return (
    <PlannerBoundary>
      <Suspense fallback={<LoadingScreen />}>
        <div className="ps-planner-enter">
          <Planner onBack={handleBackToLanding} />
        </div>
      </Suspense>
    </PlannerBoundary>
  );
}
