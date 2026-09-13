import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Chip } from '@/components/Chip';
import { GlassSheet } from '@/components/GlassSheet';
import { Icon } from '@/components/Icon';
import { NavMap } from '@/components/maps/NavMap';
import { Waypoint } from '@/components/MapAnnotations';
import { ModeTabs } from '@/components/ModeTabs';
import { Screen } from '@/components/Screen';
import { ScreenHeader } from '@/components/Header';
import { isGraphHopperConfigured } from '@/config/env';
import { fonts, radius, spacing } from '@/constants/theme';
import { estimateArrivalMillis, formatRemainingDuration } from '@/core/eta';
import { TRAVEL_MODE_OPTIONS } from '@/types/routing';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';
import type { TravelMode } from '@/types/routing';
import { formatClock, formatMeters } from '@/utils/format';

export default function RoutePreviewScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const { lat, lng, name, address, mode } = useLocalSearchParams() as Record<string, string | undefined>;
  const { snapshot, actions, settings } = useNavigationSession();
  const [selectedMode, setSelectedMode] = useState<TravelMode>((mode as TravelMode) ?? 'car');

  const destination =
    lat && lng && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng))
      ? { latitude: Number(lat), longitude: Number(lng) }
      : null;

  useEffect(() => {
    if (destination) {
      actions.requestRoute(destination, selectedMode).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [destination?.latitude, destination?.longitude, selectedMode]);

  const route = snapshot.route;
  const eta = route ? estimateArrivalMillis(route.durationSeconds) : null;
  const durationLabel = route ? formatRemainingDuration(route.durationSeconds) : '--';
  const distanceLabel = route ? formatMeters(route.distanceMeters) : '--';
  const calculating = snapshot.phase === 'calculating' || snapshot.phase === 'searching';
  const errorMessage = snapshot.phase === 'error' ? snapshot.error : null;

  const startNavigation = useCallback(() => {
    actions.startNavigation();
    router.replace('/navigation');
  }, [actions, router]);

  return (
    <Screen topInset={false} bottomInset={false}>
      <NavMap
        styleId={settings.map.styleId}
        coords={route?.geometry ?? null}
        origin={null}
        destination={destination}
        userPosition={snapshot.position}
        followUser={false}
      />

      <View style={styles.headerOverlay}>
        <ScreenHeader
          onBack={() => router.back()}
          title="Route Details"
          right={<Icon name="tune" size={20} />}
        />
      </View>

      {destination ? (
        <View style={styles.destMarker} pointerEvents="none">
          <Waypoint label="Dest" />
        </View>
      ) : null}

      <View style={[styles.bottomWrap, { bottom: insets.bottom + spacing.md }]}>
        <GlassSheet>
          <Text numberOfLines={1} style={[styles.destinationName, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            {name || 'Selected destination'}
          </Text>
          <Text numberOfLines={1} style={[styles.destinationAddress, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            {address || (destination ? `${destination.latitude.toFixed(5)}, ${destination.longitude.toFixed(5)}` : '')}
          </Text>

          {calculating ? (
            <View style={styles.statusRow}>
              <Icon name="pulse" size={18} color={theme.colors.secondary} />
              <Text style={[styles.statusText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                {snapshot.phase === 'searching' ? 'Waiting for your GPS position…' : 'Calculating best route…'}
              </Text>
            </View>
          ) : null}

          {errorMessage ? (
            <View style={[styles.errorBox, { backgroundColor: theme.colors.errorContainer }]}>
              <Icon name="alert" size={18} color={theme.colors.onErrorContainer} />
              <View style={styles.errorText}>
                <Text style={[styles.errorMessage, { color: theme.colors.onErrorContainer, fontFamily: fonts.medium }]}>
                  {errorMessage}
                </Text>
                {!isGraphHopperConfigured() ? (
                  <Text style={[styles.errorHint, { color: theme.colors.onErrorContainer, fontFamily: fonts.regular }]}>
                    Add EXPO_PUBLIC_GRAPHHOPPER_API_KEY to `.env`, or head to Profile → Demo mode.
                  </Text>
                ) : null}
              </View>
            </View>
          ) : null}

          {route ? (
            <>
              <View style={styles.summaryRow}>
                <View>
                  <Text style={[styles.eta, { color: theme.colors.primary, fontFamily: fonts.extrabold }]}>
                    {formatClock(new Date(eta ?? 0))}
                  </Text>
                  <Text style={[styles.summaryMeta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                    {`${durationLabel} \u00b7 ${distanceLabel}`}
                  </Text>
                </View>
                <View style={[styles.fastestPill, { backgroundColor: theme.colors.secondaryContainer }]}>
                  <Text style={[styles.fastestText, { color: theme.colors.onSecondaryContainer, fontFamily: fonts.semibold }]}>
                    {snapshot.phase === 'rerouting' ? 'Rerouting' : 'Estimated'}
                  </Text>
                </View>
              </View>

              <View style={styles.modesRow}>
                <ModeTabs
                  options={TRAVEL_MODE_OPTIONS}
                  value={selectedMode}
                  onChange={(id) => setSelectedMode(id as TravelMode)}
                />
              </View>

              <View style={styles.chipsRow}>
                <Chip icon="route" label={`${route.maneuvers.length - 1} navigations`} />
                <Chip icon="compass" label="From current GPS position" />
              </View>
            </>
          ) : null}

          <View style={styles.actions}>
            {errorMessage ? (
              <SecondaryButton icon="refresh" onPress={() => actions.retryRoute().catch(() => {})} disabled={!destination}>
                Retry
              </SecondaryButton>
            ) : null}
            <PrimaryButton icon="forward" disabled={!route} loading={calculating} onPress={startNavigation}>
              Start
            </PrimaryButton>
          </View>
        </GlassSheet>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  destMarker: {
    position: 'absolute',
    right: 40,
    top: 140,
  },
  bottomWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
  },
  destinationName: { fontSize: 17, lineHeight: 22 },
  destinationAddress: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  statusText: { fontSize: 13, lineHeight: 18 },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  errorText: { flex: 1 },
  errorMessage: { fontSize: 13, lineHeight: 18 },
  errorHint: { fontSize: 11, lineHeight: 16, marginTop: 2 },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  eta: { fontSize: 28, lineHeight: 32 },
  summaryMeta: { fontSize: 14, lineHeight: 19, marginTop: 2 },
  fastestPill: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  fastestText: { fontSize: 13, lineHeight: 18 },
  modesRow: { marginLeft: -spacing.gutter - spacing.lg, marginRight: -spacing.gutter - spacing.lg },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.lg,
  },
});