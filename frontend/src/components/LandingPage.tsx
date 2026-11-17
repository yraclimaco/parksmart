/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { RECOMMENDATION_SOURCE } from '../config';
import parkSmartLogoHd from '../assets/parksmart-logo-hd.png';
import { HeroDemo } from './HeroDemo';
import { PermitLot } from './PermitLot';
import { Pipeline } from './Pipeline';
import { ScoreMix } from './ScoreMix';
import { TimeLot } from './TimeLot';
import { LandingIntro } from './LandingIntro';

/** The hosted build talks to the AWS backend; other builds (previews) use labeled sample data. */
const LIVE = RECOMMENDATION_SOURCE === 'api';

interface LandingPageProps {
  isExiting: boolean;
  onPlanClick: () => void;
}

const LIMITS = [
  {
    lead: 'Past counts, not live ones.',
    text: 'There is no live feed, so a lot can be full when the estimate says it is usually open.',
  },
  {
    lead: 'Mostly the first two weeks of each quarter.',
    text: 'The detailed counts cover little else, and the model has not been checked across all ten weeks.',
  },
  {
    lead: 'Simplified permit rules.',
    text: 'Ordinary stalls only. Reserved, accessible, and A 24/7 stalls are left out, holidays count as weekdays, and only your arrival moment is checked.',
  },
  {
    lead: 'Scoring weights are starting points.',
    text: 'The default is a 65/35 mix. The other two presets still need review with experts.',
  },
  {
    lead: LIVE ? 'Historical estimates.' : 'Sample data in this preview.',
    text: LIVE
      ? 'Results come from past survey patterns through the hosted backend. Walk times are estimates for now.'
      : 'The numbers you see here are samples. The hosted app uses the real backend.',
  },
  {
    lead: 'No promises.',
    text: 'No reservations, no payments, and not an official UCSD service.',
  },
] as const;

const FAQ = [
  {
    q: 'Is this an official UCSD service?',
    a: 'No. ParkSmart is a student project and is not affiliated with UC San Diego.',
  },
  {
    q: 'Will it work with my permit?',
    a: 'You choose your permit type (A, B, S, SR, D, or V) and lots it cannot use are filtered out. Always check UCSD\'s permit pages for the final rules.',
  },
  {
    q: 'Is the data live?',
    a: 'No. Estimates come from past parking counts, not a live feed.',
  },
  {
    q: 'Will it guarantee me a space?',
    a: 'No. It shows where you are most likely to find one, based on typical patterns. Lots can still be full.',
  },
  {
    q: 'Does it cost anything?',
    a: 'There is nothing to buy and nothing to sign up for.',
  },
  {
    q: 'Does it work for visitors?',
    a: 'Not really. It is built around permit types, so visitor and daily-pay parking and costs are not covered.',
  },
] as const;

/** The intro plays once per page load, not every time someone returns from the planner. */
let introPlayedThisLoad = false;

const shouldPlayIntro = (): boolean => {
  if (introPlayedThisLoad) return false;
  introPlayedThisLoad = true;
  try {
    return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return true;
  }
};

export const LandingPage: React.FC<LandingPageProps> = ({ isExiting, onPlanClick }) => {
  const [introActive, setIntroActive] = React.useState(shouldPlayIntro);
  const heroRef = React.useRef<HTMLElement | null>(null);
  const [heroGone, setHeroGone] = React.useState(false);
  React.useEffect(() => {
    const el = heroRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([entry]) => setHeroGone(!entry.isIntersecting), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const handleSeeHowItWorks = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const target = document.getElementById('permit');
    if (!target) return;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'start' });
  };

  return (
    <div
      className={`ps-landing${isExiting ? ' ps-landing--exiting' : ''}${introActive ? ' ps-landing--intro' : ''}`}
    >
      {introActive && <LandingIntro onDone={() => setIntroActive(false)} />}

      <div className="lp-doc">
        <section ref={heroRef} className="lp-hero2 lp-dark" aria-label="ParkSmart introduction">
          <header className="lp-bar">
            <div className="lp-container lp-bar-inner">
              <span className="lp-wordmark">
                <img src={parkSmartLogoHd} alt="" className="lp-wordmark-logo" width={40} height={40} />
                ParkSmart
              </span>
              <button type="button" className="lp-btn lp-btn--yellow" onClick={onPlanClick}>
                Plan my parking
              </button>
            </div>
          </header>
          <div className="lp-container lp-hero2-grid">
            <div className="lp-hero2-copy">
              <h1 className="lp-h1">Know where to park before you get to campus.</h1>
              <p className="lp-lede">Tell it your trip. Get a first choice and a backup.</p>
              <div className="lp-top-actions">
                <button type="button" className="lp-btn lp-btn--yellow" onClick={onPlanClick}>
                  Plan my parking
                </button>
                <a href="#permit" className="lp-textlink" onClick={handleSeeHowItWorks}>
                  See how it thinks
                </a>
              </div>
              <p className="lp-fineprint">{LIVE ? 'UCSD student prototype. Uses historical survey estimates, not live data.' : 'UCSD student prototype. This preview runs on sample data.'}</p>
            </div>
            <div className="lp-hero2-demo">{!introActive && <HeroDemo />}</div>
          </div>
        </section>

        <section id="permit" className="lp-block lp-block--yellow" aria-labelledby="permit-heading">
          <div className="lp-container">
            <div className="lp-block-head">
              <h2 id="permit-heading" className="lp-big">
                Your permit decides the map.
              </h2>
              <p className="lp-sub">Pick yours. Everything you can&apos;t use fades out.</p>
            </div>
            <PermitLot />
            <p className="lp-note">Simplified example lot. Real rules live on UCSD&apos;s permit pages.</p>
          </div>
        </section>

        <section className="lp-block lp-block--blue lp-dark" aria-labelledby="time-heading">
          <div className="lp-container">
            <div className="lp-block-head">
              <h2 id="time-heading" className="lp-big">
                Drag the clock.
              </h2>
              <p className="lp-sub">Watch a busy lot fill up through the day.</p>
            </div>
            <TimeLot />
            <p className="lp-note">Example pattern, not real UCSD data.</p>
          </div>
        </section>

        <section className="lp-block lp-block--hood lp-dark" aria-labelledby="hood-heading">
          <div className="lp-container">
            <div className="lp-block-head">
              <h2 id="hood-heading" className="lp-big">
                Under the hood.
              </h2>
              <p className="lp-sub">Where a recommendation comes from, and how far along each part is.</p>
            </div>
            <Pipeline />
            <div className="lp-mix">
              <h3 className="lp-h3-light">How a pick is chosen</h3>
              <ScoreMix />
            </div>
          </div>
        </section>

        <section className="lp-block lp-block--caution" aria-labelledby="limits-heading">
          <div className="lp-stripe" aria-hidden="true" />
          <div className="lp-container lp-limits">
            <h2 id="limits-heading" className="lp-big lp-big--navy">
              A forecast, not a promise.
            </h2>
            <ul className="lp-limit-list">
              {LIMITS.map((item) => (
                <li key={item.lead}>
                  <strong>{item.lead}</strong> {item.text}
                </li>
              ))}
            </ul>
          </div>
          <div className="lp-stripe" aria-hidden="true" />
        </section>

        <section className="lp-block lp-block--paper" aria-labelledby="faq-heading">
          <div className="lp-container lp-faq">
            <h2 id="faq-heading" className="lp-big lp-big--navy">
              Quick answers.
            </h2>
            <div className="lp-faq-list">
              {FAQ.map((item) => (
                <details key={item.q} className="lp-faq-item">
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <footer className="lp-footer lp-dark">
          <div className="lp-container lp-footer-inner">
            <div>
              <p className="lp-footer-text">
                Team lead: Yra. Built by Vivaan, Hanrong, Dylan, and Daira for UCSD DS3, Fall 2026.
              </p>
              <p className="lp-footer-text lp-footer-text--note">A student project, not an official UCSD service.</p>
            </div>
            <button type="button" className="lp-btn lp-btn--yellow" onClick={onPlanClick}>
              Plan my parking
            </button>
          </div>
        </footer>
      </div>

      <div className={`lp-sticky${heroGone && !introActive ? ' lp-sticky--on' : ''}`} aria-hidden={!heroGone}>
        <button type="button" className="lp-btn lp-btn--yellow" tabIndex={heroGone ? 0 : -1} onClick={onPlanClick}>
          Plan my parking
        </button>
      </div>
    </div>
  );
};
