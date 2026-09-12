import {
  createNavigationSession,
  updateNavigationSession,
  closeNavigationSession,
  NavigationApiError,
  type SessionStatePayload,
} from '@/services/api/navigationApi';
import { env } from '@/config/env';

jest.mock('@/config/env', () => ({
  env: { navigationApiUrl: 'http://nav.test:8000/' },
}));

const originalFetch = globalThis.fetch;

function jsonResponse(body: unknown, status = 200): Partial<Response> {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

const state = {
  timestamp: 1700000000,
  latitude: 25.0667,
  longitude: 55.3,
  speedMps: 1.2,
  headingDeg: 90,
  confidence: 0.9,
  positionErrorM: 3.4,
  mode: 'GNSS_INS_FUSION',
};

describe('navigationApi', () => {
  beforeEach(() => {
    env.navigationApiUrl = 'http://nav.test:8000/';
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('creates a session and strips the trailing slash from the base URL', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      jsonResponse({ sessionId: 's1', state }),
    ) as unknown as typeof fetch;

    const result = await createNavigationSession({ latitude: 25, longitude: 55, accuracy: 5 });

    expect(result.sessionId).toBe('s1');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://nav.test:8000/navigation/sessions',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = JSON.parse(
      (globalThis.fetch as jest.Mock).mock.calls[0][1].body,
    ) as Record<string, number>;
    expect(body).toMatchObject({ latitude: 25, longitude: 55, accuracy: 5 });
  });

  it('updates with samples and optionally a GNSS fix', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      jsonResponse({ sessionId: 's2', state }) as Response,
    ) as unknown as typeof fetch;

    await updateNavigationSession('s2', {
      samples: [
        {
          timestamp: 100,
          accelerometer: { x: 0.1, y: 0.2, z: 9.8 },
          gyroscope: { x: 0, y: 0, z: 0 },
          headingDeg: 45,
        },
      ],
      gnss: { timestamp: 100, latitude: 25.1, longitude: 55.1, accuracy: 4 },
    });

    const [url, init] = (globalThis.fetch as jest.Mock).mock.calls[0] as [
      string,
      { body: string },
    ];
    expect(url).toBe('http://nav.test:8000/navigation/sessions/s2/update');
    const body = JSON.parse(init.body) as { samples: unknown[]; gnss: unknown };
    expect(body.samples).toHaveLength(1);
    expect(body.samples[0]).toMatchObject({ headingDeg: 45 });
    expect(body.gnss).toMatchObject({ longitude: 55.1 });
  });

  it('coerces non-finite numbers before anything hits the wire', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      jsonResponse({ sessionId: 's3', state }) as Response,
    ) as unknown as typeof fetch;

    await createNavigationSession({
      latitude: NaN,
      longitude: Infinity,
      accuracy: -Infinity,
    });

    const body = JSON.parse(
      (globalThis.fetch as jest.Mock).mock.calls[0][1].body,
    ) as Record<string, number>;
    expect(body.latitude).toBe(0);
    expect(body.longitude).toBe(0);
    expect(body.accuracy).toBe(0);
  });

  it('surfaces the API detail for non-2xx responses', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      jsonResponse({ detail: 'session not found' }, 404) as Response,
    ) as unknown as typeof fetch;

    await expect(updateNavigationSession('nope', { samples: [] })).rejects.toThrow(
      NavigationApiError,
    );
    await expect(updateNavigationSession('nope', { samples: [] })).rejects.toThrow(
      'session not found',
    );
  });

  it('wraps network failures with a null status code', async () => {
    globalThis.fetch = jest
      .fn()
      .mockRejectedValue(new TypeError('Network request failed')) as unknown as typeof fetch;

    const error = await closeNavigationSession('s4').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NavigationApiError);
    expect((error as NavigationApiError).status).toBeNull();
    expect((error as NavigationApiError).message).toContain('Cannot reach navigation service');
  });

  it('throws a configuration error when no URL is set', async () => {
    env.navigationApiUrl = '';
    const error = await createNavigationSession({
      latitude: 25,
      longitude: 55,
      accuracy: 5,
    }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NavigationApiError);
    expect((error as NavigationApiError).message).toBe('Navigation API is not configured');
  });

  it('latest state typed as SessionStatePayload round-trips', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue(
      jsonResponse({ sessionId: 's5', state }) as Response,
    ) as unknown as typeof fetch;
    const result = await updateNavigationSession('s5', { samples: [], gnss: null });
    expect((result as SessionStatePayload).state.mode).toBe('GNSS_INS_FUSION');
  });
});