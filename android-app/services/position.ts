import { GnssPositionProvider } from '@/services/position/gnssPositionProvider';
import { HybridPositionProvider } from '@/services/position/hybridPositionProvider';
import { BackendIdrPositionProvider } from '@/services/position/backendPositionProvider';
import { DemoPositionProvider } from '@/services/position/demoPositionProvider';
import type { PositionProvider, PositioningStatus } from '@/types/position';
import type { Coordinate } from '@/types/routing';

/**
 * Positioning entry point.
 *
 * The default provider graph is GNSS + backend-powered IDR wrapped in the
 * hybrid seam: the backend runs the GNSS-INS fusion / dead-reckoning engine
 * (services/position/backendPositionProvider.ts) and the hybrid supervisor
 * picks the most authoritative source per fix. When the backend is not
 * configured or unreachable, the backend provider stays "lost" and the graph
 * degrades to plain GNSS.
 *
 * Status copy is deliberately truthful: when there is no fix it says exactly
 * that. There is no fabricated "intelligent positioning" fallback.
 */

const FRIENDLY_STATUS: Record<PositioningStatus, string> = {
  available: 'Location is accurate',
  degraded: 'GPS signal is weak — accuracy reduced',
  lost: 'GPS signal lost — waiting for a stronger signal',
  recovering: 'Recovering GPS signal',
};

export function friendlyPositionText(status: PositioningStatus): string {
  return FRIENDLY_STATUS[status];
}

// Backwards-compatible alias kept for existing UI call sites.
export const friendlyStatus = friendlyPositionText;

/** The default provider graph: GNSS (truth) + backend IDR (outage fallback). */
export function createDefaultPositionProvider(): PositionProvider {
  const gnss = new GnssPositionProvider();
  const backendIdr = new BackendIdrPositionProvider(gnss);
  return new HybridPositionProvider([gnss, backendIdr]);
}

/**
 * Demo provider for exercising the navigation UI without GPS. Explicitly a
 * simulation — creating one signals the developer's intent in the UI legend.
 */
export function createDemoPositionProvider(path: Coordinate[]): DemoPositionProvider {
  return new DemoPositionProvider(path);
}