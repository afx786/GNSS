import { isNavigationApiConfigured } from '@/config/env';
import {
  closeNavigationSession,
  createNavigationSession,
  updateNavigationSession,
  NavigationApiError,
  type CreateSessionPayload,
  type GnssFixPayload,
  type ImuSamplePayload,
  type NavigationStatePayload,
  type UpdateSessionPayload,
} from '@/services/api/navigationApi';
import { subscribeSensor } from '@/services/sensors/sensorManager';
import type { SensorReading } from '@/types/sensor';
import type {
  GeoPosition,
  PermissionState,
  PositionChangeListener,
  PositionProvider,
  PositioningStatus,
} from '@/types/position';

/**
 * Backend-powered inertial-dead-reckoning provider.
 *
 * Buffers accelerometer/gyroscope readings (plus magnetometer heading) and
 * streams them to the fastapi navigation service together with the latest
 * GNSS fix. The engine's GNSS-INS fusion runs server-side and the returned
 * dead-reckoning / fused estimate is emitted as a `hybrid` fix — so during a
 * GNSS blackout the map keeps moving on IMU alone.
 *
 * Honest failure: if the backend is unreachable, not configured, or the
 * session dies, this provider reports `lost` and the hybrid supervisor falls
 * back to plain GNSS. A session only ever starts from a real GNSS fix (the
 * engine needs an origin), so this provider never fabricates coordinates.
 */

const IMU_INTERVAL_MS = 100;
const MAGNETOMETER_INTERVAL_MS = 200;
const FLUSH_INTERVAL_MS = 1_000;
const MAX_BUFFERED_SAMPLES = 120;
const MAX_GNSS_AGE_MS = 10_000;

function normalizeHeading(radians: number): number {
  return ((radians * 180) / Math.PI + 360) % 360;
}

function mapStatus(mode: string): PositioningStatus {
  switch (mode) {
    case 'GNSS_INS_FUSION':
      return 'available';
    case 'GNSS_INS_DEGRADED':
    case 'DEAD_RECKONING':
      return 'degraded';
    case 'RECOVERING':
      return 'recovering';
    default:
      return 'lost';
  }
}

export class BackendIdrPositionProvider implements PositionProvider {
  readonly providerId = 'backend-idr';
  readonly source = 'hybrid' as const;

  private readonly gnss: PositionProvider;
  private readonly flushIntervalMs: number;
  private readonly now: () => number;

  private readonly listeners = new Set<PositionChangeListener>();
  private unsubscribes: (() => void)[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private started = false;

  private sessionId: string | undefined;
  private current: GeoPosition | null = null;
  private status: PositioningStatus = 'lost';

  private batch: ImuSamplePayload[] = [];
  private accel: { x: number; y: number; z: number } | null = null;
  private gyro: { x: number; y: number; z: number } | null = null;
  private headingDeg: number | undefined;

  constructor(
    gnss: PositionProvider,
    options?: { flushIntervalMs?: number; now?: () => number },
  ) {
    this.gnss = gnss;
    this.flushIntervalMs = options?.flushIntervalMs ?? FLUSH_INTERVAL_MS;
    this.now = options?.now ?? Date.now;
  }

  getPermissionState(): PermissionState {
    // No platform permission of its own — reuses the GNSS grant.
    return 'unavailable';
  }

  getStatus(): PositioningStatus {
    return this.status;
  }

  getCurrentPosition(): GeoPosition | null {
    return this.current;
  }

  subscribe(listener: PositionChangeListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  requestPermission(): Promise<PermissionState> {
    return Promise.resolve('unavailable');
  }

  async start(): Promise<void> {
    if (this.started) return;
    if (!isNavigationApiConfigured()) return; // feature off → stays honest 'lost'

    this.started = true;
    const unsubscribes: (() => void)[] = [];
    for (const [kind, intervalMs] of [
      ['accelerometer', IMU_INTERVAL_MS],
      ['gyroscope', IMU_INTERVAL_MS],
      ['magnetometer', MAGNETOMETER_INTERVAL_MS],
    ] as const) {
      try {
        unsubscribes.push(await subscribeSensor(kind, this.onSensor, intervalMs));
      } catch {
        // Sensor stream unavailable — IMU stays empty, modem no dead-reckoning.
      }
    }
    this.unsubscribes = unsubscribes;
    this.timer = setInterval(() => void this.flush(), this.flushIntervalMs);
  }

  stop(): void {
    if (!this.started) return;
    this.started = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    for (const unsubscribe of this.unsubscribes) unsubscribe();
    this.unsubscribes = [];

    if (this.sessionId) {
      const sessionId = this.sessionId;
      this.sessionId = undefined;
      closeNavigationSession(sessionId).catch(() => {});
    }
    this.reset();
  }

  private onSensor = (reading: SensorReading): void => {
    if (reading.kind === 'magnetometer') {
      this.headingDeg = normalizeHeading(Math.atan2(-reading.y, reading.x));
      return;
    }
    if (reading.kind === 'accelerometer') {
      this.accel = { x: reading.x, y: reading.y, z: reading.z };
    } else {
      this.gyro = { x: reading.x, y: reading.y, z: reading.z };
    }
    if (!this.accel || !this.gyro) return;

    this.batch.push({
      timestamp: this.now() / 1000,
      accelerometer: this.accel,
      gyroscope: this.gyro,
      ...(this.headingDeg === undefined ? {} : { headingDeg: this.headingDeg }),
    });
    if (this.batch.length > MAX_BUFFERED_SAMPLES) {
      this.batch = this.batch.slice(-MAX_BUFFERED_SAMPLES);
    }
  };

  private readGnssFix(): GnssFixPayload | null {
    const fix = this.gnss.getCurrentPosition();
    if (!fix) return null;
    if (fix.status === 'lost') return null; // never re-send a stale fix
    if (this.now() - fix.timestamp > MAX_GNSS_AGE_MS) return null;
    return {
      timestamp: fix.timestamp / 1000,
      latitude: fix.latitude,
      longitude: fix.longitude,
      accuracy: fix.accuracy ?? 10,
      speedMps: fix.speed,
      headingDeg: fix.heading,
    };
  }

  private async flush(): Promise<void> {
    const gnss = this.readGnssFix();
    if (!this.sessionId) {
      await this.trySeed(gnss);
      return;
    }

    try {
      const result = await updateNavigationSession(this.sessionId, {
        samples: this.batch,
        gnss,
      });
      this.batch = [];
      this.applyState(result.state);
    } catch (error) {
      if (error instanceof NavigationApiError && error.status === 404) {
        this.sessionId = undefined;
        this.reset();
        return;
      }
      // Backend hiccup — keep the buffered samples and stay honest.
      this.setResult(null, 'lost');
    }
  }

  private async trySeed(gnss: GnssFixPayload | null): Promise<void> {
    if (!gnss) return; // engine needs a real origin — nothing to seed yet
    const payload: CreateSessionPayload = {
      latitude: gnss.latitude,
      longitude: gnss.longitude,
      accuracy: gnss.accuracy,
      headingDeg: gnss.headingDeg ?? null,
      timestamp: gnss.timestamp,
    };
    try {
      const result = await createNavigationSession(payload);
      this.sessionId = result.sessionId;
      this.applyState(result.state);
    } catch {
      this.setResult(null, 'lost');
    }
  }

  private applyState(state: NavigationStatePayload | undefined): void {
    if (
      !state ||
      state.latitude === null ||
      state.longitude === null ||
      state.mode === 'UNINITIALIZED'
    ) {
      this.reset();
      return;
    }
    const status = mapStatus(state.mode);
    this.setResult(
      {
        latitude: state.latitude,
        longitude: state.longitude,
        altitude: null,
        accuracy: state.positionErrorM ?? null,
        speed: state.speedMps,
        heading: state.headingDeg,
        timestamp: Math.round(state.timestamp * 1000),
        source: 'hybrid',
        status,
      },
      status,
    );
  }

  private setResult(position: GeoPosition | null, status: PositioningStatus): void {
    this.current = position;
    this.status = status;
    this.emit();
  }

  private reset(): void {
    this.batch = [];
    this.setResult(null, 'lost');
  }

  private emit(): void {
    const position = this.current;
    for (const listener of this.listeners) {
      listener(position);
    }
  }
}