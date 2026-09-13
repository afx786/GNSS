import type {
  Coordinate,
  ManeuverAction,
  Route,
  RouteRequest,
  RouteResult,
  TravelMode,
} from '@/types/routing';

/**
 * Normalization of raw GraphHopper API responses into the app's Route model.
 * Pure; unit-tested with fixture JSON.
 */

export interface GraphHopperInstruction {
  text: string;
  distance: number;
  time: number;
  sign: number;
  interval: number[];
  exit_number?: number;
}

export interface GraphHopperPath {
  distance: number;
  time: number;
  points_encoded: boolean;
  /** Raw geometry as returned by the engine (array of [lng, lat] tuples or a GeoJSON LineString). */
  points: Coordinate[] | [number, number][] | [number, number, number][] | GraphHopperLineString;
  instructions?: GraphHopperInstruction[];
  bbox?: number[];
}

export interface GraphHopperLineString {
  type: 'LineString';
  coordinates: [number, number][] | [number, number, number][];
}

/** Accepted raw point list shapes. */
export type RawPoints = Coordinate[] | [number, number][] | [number, number, number][] | GraphHopperLineString;

export interface GraphHopperRouteResponse {
  paths?: GraphHopperPath[];
  message?: string;
  hints?: unknown[];
}

/**
 * Map GraphHopper instruction `sign` (see GH docs) to a maneuver action.
 * Unmapped signs fall back to `straight` — the instruction text still comes
 * from the engine so guidance remains readable.
 */
export function actionForSign(sign: number): ManeuverAction {
  switch (sign) {
    case -3:
      return 'turn-sharp-left';
    case -2:
      return 'turn-left';
    case -1:
      return 'turn-slight-left';
    case 0:
      return 'straight';
    case 1:
      return 'turn-slight-right';
    case 2:
      return 'turn-right';
    case 3:
      return 'turn-sharp-right';
    case 4:
      return 'uturn';
    case 6:
      return 'roundabout-right';
    case 7:
      return 'keep-right';
    default:
      return 'straight';
  }
}

/** Insert departure/arrival maneuvers when the engine returned none. */
function noInstructionManeuvers(points: Coordinate[], distanceMeters: number, durationSeconds: number): Route['maneuvers'] {
  if (points.length === 0) return [];
  return [
    {
      action: 'depart',
      instruction: 'Leave',
      approachDistanceMeters: 0,
      approachDurationSeconds: 0,
      coordinates: points.slice(0, 2),
    },
    {
      action: 'arrive',
      instruction: 'Arrive at destination',
      approachDistanceMeters: distanceMeters,
      approachDurationSeconds: durationSeconds,
      coordinates: points.slice(-2),
    },
  ];
}

export function parsePoints(raw: RawPoints): Coordinate[] {
  const list = Array.isArray(raw) ? raw : raw?.type === 'LineString' ? raw.coordinates : [];
  if (list.length === 0) return [];
  return list
    .map((entry) => {
      if (Array.isArray(entry)) {
        const [lng, lat] = entry;
        if (typeof lng !== 'number' || typeof lat !== 'number') return null;
        return { latitude: lat, longitude: lng };
      }
      if (typeof entry.latitude !== 'number' || typeof entry.longitude !== 'number') return null;
      return entry;
    })
    .filter((c): c is Coordinate => c !== null);
}

export function toBounds(bbox: number[] | undefined | null): Route['bounds'] {
  if (!bbox || bbox.length < 4) return null;
  return {
    southwest: { latitude: bbox[1], longitude: bbox[0] },
    northeast: { latitude: bbox[3], longitude: bbox[2] },
  };
}

function buildManeuvers(path: GraphHopperPath, points: Coordinate[]): Route['maneuvers'] {
  const instructions = path.instructions;
  if (!instructions || instructions.length === 0) {
    return noInstructionManeuvers(points, path.distance, path.time / 1000);
  }

  const totalDurationSeconds = path.time / 1000;

  const maneuvers: Route['maneuvers'] = instructions.map((inst, index) => {
    const [startIdx, endIdx] = inst.interval;
    const slice = points.slice(
      Math.max(0, Math.min(startIdx, points.length - 1)),
      Math.max(startIdx + 1, Math.min(endIdx + 1, points.length)),
    );
    const isLast = index === instructions.length - 1;
    const action: ManeuverAction = isLast ? 'arrive' : index === 0 ? 'depart' : actionForSign(inst.sign);
    return {
      action,
      instruction: inst.text || (action === 'arrive' ? 'Arrive at destination' : action),
      approachDistanceMeters: inst.distance || 0,
      approachDurationSeconds: Math.round((inst.time || 0) / 1000),
      coordinates: slice.length > 0 ? slice : points.slice(-1),
      exitNumber: inst.exit_number,
    };
  }) as Route['maneuvers'];

  if (maneuvers.length === 0) {
    return noInstructionManeuvers(points, path.distance, totalDurationSeconds);
  }
  return maneuvers;
}

export interface NormalizedRouteInput {
  path: GraphHopperPath;
  request: RouteRequest;
}

export function normalizePathToRoute(input: NormalizedRouteInput): Route {
  const { path, request } = input;
  const geometry = parsePoints(path.points);
  return {
    geometry,
    distanceMeters: Math.round(path.distance),
    durationSeconds: Math.round(path.time / 1000),
    maneuvers: buildManeuvers(path, geometry),
    bounds: toBounds(path.bbox),
  };
}

export function normalizeRouteResponse(
  json: GraphHopperRouteResponse,
  request: RouteRequest,
  provider = 'graphhopper',
): RouteResult {
  const paths = json.paths ?? [];
  const routes = paths.map((path) => normalizePathToRoute({ path, request }));
  return {
    routes,
    request,
    provider,
  };
}

/** Best-effort extraction of a human-readable error from a GH error body. */
export function extractGraphHopperError(json: unknown, fallback: string): string {
  if (json && typeof json === 'object') {
    const message = (json as { message?: unknown }).message;
    if (typeof message === 'string' && message.length > 0) return message;
  }
  return fallback;
}

export function travelModeFromVehicle(vehicle: string): TravelMode {
  switch (vehicle) {
    case 'foot':
      return 'foot';
    case 'bike':
      return 'bike';
    default:
      return 'car';
  }
}