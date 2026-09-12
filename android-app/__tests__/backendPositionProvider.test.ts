import type { GeoPosition, PositionProvider, PositionChangeListener } from '@/types/position';
import type { SensorReading } from '@/types/sensor';

const mockSensorListeners: Partial<Record<string, (reading: SensorReading) => void>> = {};
let mockUnsubscribeCount = 0;

jest.mock('@/config/env', () => ({
  isNavigationApiConfigured: jest.fn(() => true),
  env: { navigationApiUrl: 'http://nav.test:8000' },
}));

jest.mock('@/services/sensors/sensorManager', () => ({
  subscribeSensor: jest.fn(
    (kind: string, listener: (reading: SensorReading) => void) => {
      mockSensorListeners[kind] = listener;
      return Promise.resolve(() => {
        mockUnsubscribeCount += 1;
      });
    },
  ),
}));

jest.mock('@/services/api/navigationApi', () => {
  class NavigationApiError extends Error {
    status: number | null;
    constructor(message: string, status: number | null = null) {
      super(message);
      this.name = 'NavigationApiError';
      this.status = status;
    }
  }
  return {
    createNavigationSession: jest.fn(),
    updateNavigationSession: jest.fn(),
    closeNavigationSession: jest.fn().mockResolvedValue(undefined),
    NavigationApiError,
  };
});

import { BackendIdrPositionProvider } from '@/services/position/backendPositionProvider';
import { isNavigationApiConfigured } from '@/config/env';
import { subscribeSensor } from '@/services/sensors/sensorManager';
import {
  createNavigationSession,
  updateNavigationSession,
  closeNavigationSession,
  NavigationApiError,
} from '@/services/api/navigationApi';

const NOW = 1_700_000_000_000;

function sensor(kind: SensorReading['kind'], x = 1, y = 2, z = 3): SensorReading {
  return { kind, x, y, z, timestamp: NOW / 1000 };
}

function position(lat: number, lon: number, status: GeoPosition['status']): GeoPosition {
  return {
    latitude: lat,
    longitude: lon,
    altitude: null,
    accuracy: 4,
    speed: 1.5,
    heading: 90,
    timestamp: NOW - 1_000,
    source: 'gnss',
    status,
  };
}

type MutableGnss = PositionProvider & {
  setStatus(status: GeoPosition['status'], p?: GeoPosition | null): void;
};

function makeGnss(): MutableGnss {
  let status: GeoPosition['status'] = 'available';
  let current: GeoPosition | null = position(25.0, 55.0, 'available');
  const provider: MutableGnss = {
    providerId: 'gnss',
    source: 'gnss',
    getPermissionState: () => 'granted',
    getStatus: () => status,
    getCurrentPosition: () => current,
    requestPermission: async () => 'granted',
    subscribe: (_listener: PositionChangeListener) => () => {},
    start: async () => {},
    stop: () => {},
    setStatus(next: GeoPosition['status'], p: GeoPosition | null | undefined) {
      status = next;
      current = p ?? null;
    },
  };
  return provider;
}

describe('BackendIdrPositionProvider', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockUnsubscribeCount = 0;
    (isNavigationApiConfigured as jest.Mock).mockReturnValue(true);
    for (const key of Object.keys(mockSensorListeners)) delete mockSensorListeners[key];
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('stays lost and inert when the backend is not configured', async () => {
    (isNavigationApiConfigured as jest.Mock).mockReturnValue(false);
    const provider = new BackendIdrPositionProvider(makeGnss(), { now: () => NOW });
    const seen: (GeoPosition | null)[] = [];
    provider.subscribe((p) => seen.push(p));

    await provider.start();
    jest.advanceTimersByTime(5_000);

    expect(provider.getStatus()).toBe('lost');
    expect(provider.getCurrentPosition()).toBeNull();
    expect(subscribeSensor).not.toHaveBeenCalled();
    expect(seen.every((p) => p === null)).toBe(true);
  });

  it('seeds a session from a fresh GNSS fix and emits the fused estimate', async () => {
    (createNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's1',
      state: {
        timestamp: NOW / 1000,
        latitude: 25.0001,
        longitude: 55.0001,
        speedMps: 1.5,
        headingDeg: 90,
        confidence: 0.97,
        positionErrorM: 0.9,
        mode: 'GNSS_INS_FUSION',
      },
    });
    const provider = new BackendIdrPositionProvider(makeGnss(), { now: () => NOW });
    const seen: (GeoPosition | null)[] = [];
    provider.subscribe((p) => seen.push(p));

    await provider.start();
    mockSensorListeners['accelerometer']?.(sensor('accelerometer', 0.1, 0.2, 9.8));
    mockSensorListeners['gyroscope']?.(sensor('gyroscope'));
    mockSensorListeners['magnetometer']?.(sensor('magnetometer', 1, 0));

    await jest.advanceTimersByTimeAsync(1_000);

    expect(createNavigationSession).toHaveBeenCalledWith(
      expect.objectContaining({ latitude: 25.0, longitude: 55.0, accuracy: 4 }),
    );
    expect(provider.getStatus()).toBe('available');
    expect(provider.getCurrentPosition()).toMatchObject({
      latitude: 25.0001,
      longitude: 55.0001,
      accuracy: 0.9,
      source: 'hybrid',
      status: 'available',
    });
    expect(seen.at(-1)).toMatchObject({ source: 'hybrid', status: 'available' });
  });

  it('keeps emitting dead-reckoned positions during a GNSS blackout', async () => {
    const gnss = makeGnss();
    (createNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's2',
      state: {
        timestamp: NOW / 1000,
        latitude: 25.0,
        longitude: 55.0,
        speedMps: 1.5,
        headingDeg: 90,
        confidence: 0.95,
        positionErrorM: 1.0,
        mode: 'GNSS_INS_FUSION',
      },
    });
    (updateNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's2',
      state: {
        timestamp: (NOW + 2_000) / 1000,
        latitude: 25.0011,
        longitude: 55.0012,
        speedMps: 1.6,
        headingDeg: 92,
        confidence: 0.71,
        positionErrorM: 4.2,
        mode: 'DEAD_RECKONING',
      },
    });

    const provider = new BackendIdrPositionProvider(gnss, { now: () => NOW });
    const seen: (GeoPosition | null)[] = [];
    provider.subscribe((p) => seen.push(p));
    await provider.start();

    await jest.advanceTimersByTimeAsync(1_000);

    // GNSS dies; the backend keeps dead-reckoning from buffered IMU.
    gnss.setStatus('lost', null);
    mockSensorListeners['accelerometer']?.(sensor('accelerometer'));
    mockSensorListeners['gyroscope']?.(sensor('gyroscope'));
    await jest.advanceTimersByTimeAsync(1_000);

    expect(updateNavigationSession).toHaveBeenCalledWith(
      's2',
      expect.objectContaining({ gnss: null, samples: expect.any(Array) }),
    );
    expect(provider.getStatus()).toBe('degraded');
    expect(provider.getCurrentPosition()).toMatchObject({
      latitude: 25.0011,
      longitude: 55.0012,
      speed: 1.6,
      source: 'hybrid',
      status: 'degraded',
    });
  });

  it('resets the session when the backend reports 404', async () => {
    (createNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's3',
      state: {
        timestamp: NOW / 1000,
        latitude: 25.0,
        longitude: 55.0,
        speedMps: 1.5,
        headingDeg: 90,
        confidence: 0.95,
        positionErrorM: 1.0,
        mode: 'GNSS_INS_FUSION',
      },
    });
    (updateNavigationSession as jest.Mock).mockRejectedValue(
      new NavigationApiError('session not found', 404),
    );

    const provider = new BackendIdrPositionProvider(makeGnss(), { now: () => NOW });
    await provider.start();
    await jest.advanceTimersByTimeAsync(1_000);
    await jest.advanceTimersByTimeAsync(1_000);

    expect(provider.getStatus()).toBe('lost');
    expect(provider.getCurrentPosition()).toBeNull();
  });

  it('falls back to lost-but-keeps-buffering on transient backend errors', async () => {
    (createNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's4',
      state: {
        timestamp: NOW / 1000,
        latitude: 25.0,
        longitude: 55.0,
        speedMps: 1.5,
        headingDeg: 90,
        confidence: 0.95,
        positionErrorM: 1.0,
        mode: 'GNSS_INS_FUSION',
      },
    });
    (updateNavigationSession as jest.Mock).mockRejectedValue(
      new NavigationApiError('boom', 500),
    );

    const provider = new BackendIdrPositionProvider(makeGnss(), { now: () => NOW });
    await provider.start();
    mockSensorListeners['accelerometer']?.(sensor('accelerometer'));
    mockSensorListeners['gyroscope']?.(sensor('gyroscope'));
    await jest.advanceTimersByTimeAsync(1_000);
    await jest.advanceTimersByTimeAsync(1_000);

    expect(provider.getStatus()).toBe('lost');
    expect(updateNavigationSession).toHaveBeenCalled();
  });

  it('closes the session on stop()', async () => {
    (createNavigationSession as jest.Mock).mockResolvedValue({
      sessionId: 's5',
      state: {
        timestamp: NOW / 1000,
        latitude: 25.0,
        longitude: 55.0,
        speedMps: 1.5,
        headingDeg: 90,
        confidence: 0.95,
        positionErrorM: 1.0,
        mode: 'GNSS_INS_FUSION',
      },
    });
    const provider = new BackendIdrPositionProvider(makeGnss(), { now: () => NOW });
    await provider.start();
    await jest.advanceTimersByTimeAsync(1_000);

    provider.stop();

    expect(closeNavigationSession).toHaveBeenCalledWith('s5');
    expect(provider.getStatus()).toBe('lost');
    expect(provider.getCurrentPosition()).toBeNull();
    expect(mockUnsubscribeCount).toBe(3);
  });
});