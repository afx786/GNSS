import { actionForSign, parsePoints, normalizePathToRoute, normalizeRouteResponse, extractGraphHopperError, toBounds, travelModeFromVehicle } from '@/core/routeNormalization';
import type { RouteRequest } from '@/types/routing';

const REQUEST: RouteRequest = {
  origin: { latitude: 25.0, longitude: 55.0 },
  destination: { latitude: 25.1, longitude: 55.1 },
  options: { travelMode: 'car' },
};

describe('actionForSign', () => {
  it('maps common signs', () => {
    expect(actionForSign(0)).toBe('straight');
    expect(actionForSign(2)).toBe('turn-right');
    expect(actionForSign(-2)).toBe('turn-left');
    expect(actionForSign(3)).toBe('turn-sharp-right');
    expect(actionForSign(4)).toBe('uturn');
  });

  it('falls back to straight for unknown signs', () => {
    expect(actionForSign(99)).toBe('straight');
  });
});

describe('parsePoints', () => {
  it('parses [lng, lat] tuples', () => {
    const pts = parsePoints([[55.0, 25.0], [55.1, 25.1]]);
    expect(pts).toEqual([
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.1, longitude: 55.1 },
    ]);
  });

it('returns [] for empty input', () => {
    expect(parsePoints([])).toEqual([]);
  });

  it('parses GeoJSON LineString geometry', () => {
    const pts = parsePoints({
      type: 'LineString',
      coordinates: [[55.0, 25.0], [55.1, 25.1]],
    });
    expect(pts).toEqual([
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.1, longitude: 55.1 },
    ]);
  });

  it('returns [] for non-array, non-LineString input', () => {
    expect(parsePoints(null as never)).toEqual([]);
  });
});

describe('toBounds', () => {
  it('builds southwest/northeast from bbox', () => {
    const bounds = toBounds([55.0, 25.0, 55.1, 25.1]);
    expect(bounds).toEqual({
      southwest: { latitude: 25.0, longitude: 55.0 },
      northeast: { latitude: 25.1, longitude: 55.1 },
    });
  });

  it('returns null for short bbox', () => {
    expect(toBounds([1, 2])).toBeNull();
    expect(toBounds(undefined)).toBeNull();
  });
});

describe('normalizePathToRoute', () => {
  it('builds a route with maneuvers from instructions', () => {
    const path = {
      distance: 1200,
      time: 300000,
      points_encoded: false,
      points: [[55.0, 25.0], [55.1, 25.1]] as [number, number][],
      instructions: [
        { text: 'Head east', distance: 600, time: 150000, sign: 0, interval: [0, 1] },
        { text: 'Continue', distance: 600, time: 150000, sign: 0, interval: [1, 2] },
      ],
    };
    const route = normalizePathToRoute({ path, request: REQUEST });
    expect(route.distanceMeters).toBe(1200);
    expect(route.durationSeconds).toBe(300);
    expect(route.maneuvers.length).toBe(2);
    expect(route.maneuvers[0].action).toBe('depart');
    expect(route.maneuvers[1].action).toBe('arrive');
  });

  it('inserts depart/arrive maneuvers when no instructions', () => {
    const path = {
      distance: 800,
      time: 120000,
      points_encoded: false,
      points: [[55.0, 25.0], [55.05, 25.05], [55.1, 25.1]] as [number, number][],
      instructions: [] as never[],
    };
    const route = normalizePathToRoute({ path, request: REQUEST });
    expect(route.maneuvers[0].action).toBe('depart');
    expect(route.maneuvers[route.maneuvers.length - 1].action).toBe('arrive');
  });
});

describe('normalizeRouteResponse', () => {
  it('normalizes multiple paths', () => {
    const json = {
      paths: [
        { distance: 100, time: 10000, points_encoded: false, points: [[55.0, 25.0], [55.05, 25.05]] as [number, number][] },
        { distance: 200, time: 20000, points_encoded: false, points: [[55.0, 25.0], [55.06, 25.06]] as [number, number][] },
      ],
    };
    const result = normalizeRouteResponse(json, REQUEST);
    expect(result.routes.length).toBe(2);
    expect(result.provider).toBe('graphhopper');
  });

  it('handles empty paths', () => {
    const result = normalizeRouteResponse({ paths: [] }, REQUEST);
    expect(result.routes).toEqual([]);
  });
});

describe('extractGraphHopperError', () => {
  it('extracts message from error body', () => {
    expect(extractGraphHopperError({ message: 'Rate limit' }, 'fallback')).toBe('Rate limit');
  });

  it('falls back when no message', () => {
    expect(extractGraphHopperError({ code: 429 }, 'fallback')).toBe('fallback');
    expect(extractGraphHopperError(null, 'fallback')).toBe('fallback');
  });
});

describe('travelModeFromVehicle', () => {
  it('maps vehicles to travel modes', () => {
    expect(travelModeFromVehicle('foot')).toBe('foot');
    expect(travelModeFromVehicle('bike')).toBe('bike');
    expect(travelModeFromVehicle('car')).toBe('car');
    expect(travelModeFromVehicle('mtb')).toBe('car');
  });
});

