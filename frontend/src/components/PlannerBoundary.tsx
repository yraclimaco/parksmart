/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { ErrorState } from './ErrorState.tsx';

interface PlannerBoundaryProps {
  children: React.ReactNode;
  /** Called by the reload button; defaults to a full page reload. */
  onReload?: () => void;
}

/**
 * Catches a failed planner load. The planner is a lazy chunk, so someone who opened the
 * site before a redeploy requests a file that no longer exists; without this they would
 * see a blank screen. A full reload fetches the new build.
 */
export class PlannerBoundary extends React.Component<PlannerBoundaryProps, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="max-w-sm w-full">
          <ErrorState
            message="The planner didn't load. This can happen right after the site is updated."
            actionLabel="Reload the page"
            onRetry={this.props.onReload ?? (() => window.location.reload())}
          />
        </div>
      </div>
    );
  }
}
