import { env, isGraphHopperConfigured } from '@/config/env';
import {
  extractGraphHopperError,
  normalizeRouteResponse,
  type GraphHopperRouteResponse,
} from '@/core/routeNormalization';
import { vehicleForMode, RoutingError, type RouteRequest, type RouteResult } from '@/types/routing';

/**
 * Routing services.
 *
 * GraphHopperRoutingService talks to graphhopper.com (or an overridden API
 * URL). The service never fabricates a route and surfaces user-safe errors.
 * DemoRoutingService exists strictly for offline UI exercise and is clearly
 * labeled.
 */

export interface RoutingService {
  readonly id: string;
  readonly isDemo: boolean;
  calculate(request: RouteRequest): Promise<RouteResult>;
}

export class GraphHopperRoutingService implements RoutingService {
  readonly id = 'graphhopper';
  readonly isDemo = false;

  constructor(
    private readonly options: {
      apiUrl?: string;
      apiKey?: string;
      timeoutMs?: number;
      fetchImpl?: typeof fetch;
    } = {},
  ) {}

  async calculate(request: RouteRequest): Promise<RouteResult> {
    const apiKey = this.options.apiKey ?? env.graphhopperApiKey;
    if (!apiKey) {
      throw new RoutingError(
        'Routing needs a GraphHopper API key. Add EXPO_PUBLIC_GRAPHHOPPER_API_KEY to your .env file.',
        'no_key',
      );
    }

    return this.execute(request, apiKey);
  }

  private async execute(request: RouteRequest, apiKey: string): Promise<RouteResult> {
    const fetchImpl = this.options.fetchImpl ?? fetch;
    const url = this.buildUrl(request, apiKey);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutMs ?? 30_000);

    try {
      const response = await fetchImpl(url, { method: 'GET', signal: controller.signal });
      let json: GraphHopperRouteResponse;
      try {
        json = (await response.json()) as GraphHopperRouteResponse;
      } catch {
        throw new RoutingError('Routing engine returned an unreadable response.', 'server');
      }
      if (!response.ok) {
        throw new RoutingError(
          extractGraphHopperError(json, `Routing request failed (HTTP ${response.status}).`),
          'server',
        );
      }
      return normalizeRouteResponse(json, request, 'graphhopper');
    } catch (error) {
      if (error instanceof RoutingError) throw error;
      if (error instanceof Error && error.name === 'AbortError') {
        throw new RoutingError('Routing timed out. Check your connection and try again.', 'network');
      }
      throw new RoutingError(
        'Could not reach the routing service. Check your connection and try again.',
        'network',
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  buildUrl(request: RouteRequest, apiKey: string): string {
    const base = (this.options.apiUrl ?? env.graphhopperApiUrl).replace(/\/$/, '');
    const vehicle = vehicleForMode(request.options.travelMode);

    const query: string[] = [];
    const push = (key: string, value: string) => query.push(`${key}=${encodeURIComponent(value)}`);
    push('key', apiKey);
    push('point', `${request.origin.latitude},${request.origin.longitude}`);
    push('point', `${request.destination.latitude},${request.destination.longitude}`);
    push('vehicle', vehicle);
    push('locale', request.options.locale ?? 'en');
    push('points_encoded', 'false');
    push('instructions', 'true');
    push('elevation', 'false');
    if (request.options.alternatives && request.options.alternatives > 0) {
      push('alternative_route.max_paths', String(request.options.alternatives));
      push('alternative_route.max_weight_factor', '1.4');
    }
    push('calc_points', 'true');

    return `${base}/route?${query.join('&')}`;
  }
}

export const routingService: GraphHopperRoutingService = new GraphHopperRoutingService();

export function createRoutingService(options?: {
  apiUrl?: string;
  apiKey?: string;
  fetchImpl?: typeof fetch;
}): GraphHopperRoutingService {
  return new GraphHopperRoutingService(options);
}

export function isRoutingConfigured(): boolean {
  return isGraphHopperConfigured();
}