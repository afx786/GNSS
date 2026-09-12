/**
 * Central, type-safe access to environment configuration.
 *
 * All values are read from EXPO_PUBLIC_* variables (inlined by Expo at build
 * time) and never baked into source. See `.env.example` for the full list.
 *
 * Public (safe to ship in the client binary) vs secret keys are documented in
 * `.env.example`. No server-side secret is ever expected here — if a future
 * service needs one, it must be proxied by a backend, not shipped in the app.
 */

export type RuntimeEnv = 'development' | 'production';

const GRAPHHOPPER_ROUTE_ENDPOINT = 'route';
const GRAPHHOPPER_GEOCODE_ENDPOINT = 'geocode';

export interface EnvConfig {
  /** Overridable base URL for the GraphHopper API. */
  graphhopperApiUrl: string;
  /** Optional public GraphHopper API key (read-only, rate-limited). */
  graphhopperApiKey: string;
  graphhopperRouteEndpoint: string;
  graphhopperGeocodeEndpoint: string;
  /** Default vector style id when the user has not chosen one yet. */
  defaultMapStyleId: string;
  runtimeEnv: RuntimeEnv;
  /** Base URL of the navigation backend (FastAPI). Empty = feature off. */
  navigationApiUrl: string;
}

export const env: EnvConfig = {
  graphhopperApiUrl:
    process.env.EXPO_PUBLIC_GRAPHHOPPER_API_URL ?? 'https://graphhopper.com/api/1',
  graphhopperApiKey: process.env.EXPO_PUBLIC_GRAPHHOPPER_API_KEY ?? '',
  graphhopperRouteEndpoint: GRAPHHOPPER_ROUTE_ENDPOINT,
  graphhopperGeocodeEndpoint: GRAPHHOPPER_GEOCODE_ENDPOINT,
  defaultMapStyleId: process.env.EXPO_PUBLIC_DEFAULT_MAP_STYLE ?? 'liberty',
  runtimeEnv:
    process.env.EXPO_PUBLIC_APP_ENV === 'production' ? 'production' : 'development',
  navigationApiUrl: process.env.EXPO_PUBLIC_NAVIGATION_API_URL ?? '',
};

/**
 * True when a GraphHopper key is configured. The app can still run (with
 * degraded search/routing) when this is false — every failure surfaces an
 * explanatory message instead of fabricated data.
 */
export function isGraphHopperConfigured(): boolean {
  return env.graphhopperApiKey.length > 0;
}

/**
 * True when the navigation backend is configured. The position pipeline falls
 * back to pure GNSS when this is false — no fake IDR fix is ever emitted.
 */
export function isNavigationApiConfigured(): boolean {
  return env.navigationApiUrl.trim().length > 0;
}