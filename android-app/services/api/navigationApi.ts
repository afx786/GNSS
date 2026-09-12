import { env } from '@/config/env';

/**
 * Typed client for the fastapi navigation service (api/main.py).
 *
 * Wire shapes mirror the backend schemas 1:1 (camelCase). See docs/http_api.md
 * for the full contract. Non-finite numbers are never sent: JSON.stringify
 * cannot represent NaN/Infinity, and the backend rejects them anyway — the
 * request replacer coerces them to 0 before anything hits the wire.
 */

export type NavigationMode =
  | 'UNINITIALIZED'
  | 'DEAD_RECKONING'
  | 'GNSS_INS_FUSION'
  | 'GNSS_INS_DEGRADED'
  | 'RECOVERING';

export interface Vec3Payload {
  x: number;
  y: number;
  z: number;
}

export interface ImuSamplePayload {
  /** Epoch seconds (device clock). */
  timestamp: number;
  accelerometer: Vec3Payload;
  gyroscope: Vec3Payload;
  magnetometer?: Vec3Payload;
  headingDeg?: number;
}

export interface GnssFixPayload {
  /** Epoch seconds (device clock). */
  timestamp: number;
  latitude: number;
  longitude: number;
  /** Horizontal accuracy radius in meters. */
  accuracy: number;
  speedMps?: number | null;
  headingDeg?: number | null;
}

export interface CreateSessionPayload {
  latitude: number;
  longitude: number;
  accuracy: number;
  headingDeg?: number | null;
  timestamp?: number | null;
}

export interface UpdateSessionPayload {
  samples?: ImuSamplePayload[];
  gnss?: GnssFixPayload | null;
}

export interface NavigationStatePayload {
  /** Epoch seconds (engine clock). */
  timestamp: number;
  latitude: number | null;
  longitude: number | null;
  speedMps: number | null;
  headingDeg: number | null;
  confidence: number | null;
  positionErrorM: number | null;
  mode: NavigationMode;
}

export interface SessionCreatedPayload {
  sessionId: string;
  state: NavigationStatePayload;
}

export interface SessionStatePayload {
  sessionId: string;
  state: NavigationStatePayload;
}

export interface HealthPayload {
  status: string;
  environment: string;
  version: string;
}

/** Error thrown for any navigation-service failure (network or non-2xx). */
export class NavigationApiError extends Error {
  readonly status: number | null;
  readonly detail: unknown;

  constructor(message: string, status: number | null = null, detail: unknown = null) {
    super(message);
    this.name = 'NavigationApiError';
    this.status = status;
    this.detail = detail;
  }
}

function baseUrl(): string {
  const base = env.navigationApiUrl.trim().replace(/\/+$/, '');
  if (!base) {
    throw new NavigationApiError('Navigation API is not configured');
  }
  return base;
}

function finite(value: unknown): unknown {
  if (typeof value === 'number' && !Number.isFinite(value)) return 0;
  return value;
}

async function request<Result>(
  method: 'GET' | 'POST' | 'DELETE',
  path: string,
  body?: object,
): Promise<Result> {
  const url = `${baseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body, (_, value) => finite(value)),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new NavigationApiError(`Cannot reach navigation service: ${message}`, null);
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = (await response.json())?.detail ?? null;
    } catch {
      // non-JSON error body — keep the generic message.
    }
    const message =
      typeof detail === 'string'
        ? detail
        : `Navigation service ${method} ${path} failed with ${response.status}`;
    throw new NavigationApiError(message, response.status, detail);
  }

  return (await response.json()) as Result;
}

/** Create a navigation session from the first known GNSS fix. */
export async function createNavigationSession(
  input: CreateSessionPayload,
): Promise<SessionCreatedPayload> {
  return request<SessionCreatedPayload>('POST', '/navigation/sessions', input);
}

/** Fetch a session's latest fused state (GNSS-INS / dead-reckoning). */
export async function getNavigationSession(
  sessionId: string,
): Promise<SessionStatePayload> {
  return request<SessionStatePayload>('GET', `/navigation/sessions/${sessionId}`);
}

/** Stream buffered IMU samples and the latest GNSS fix to the engine. */
export async function updateNavigationSession(
  sessionId: string,
  input: UpdateSessionPayload,
): Promise<SessionStatePayload> {
  return request<SessionStatePayload>('POST', `/navigation/sessions/${sessionId}/update`, input);
}

/** Close a session and release engine resources. */
export async function closeNavigationSession(sessionId: string): Promise<void> {
  await request<null>('DELETE', `/navigation/sessions/${sessionId}`);
}

/** Service health/liveness probe. */
export async function getNavigationHealth(): Promise<HealthPayload> {
  return request<HealthPayload>('GET', '/health');
}