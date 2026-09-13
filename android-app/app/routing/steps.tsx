import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PrimaryButton } from '@/components/Buttons';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { ScreenHeader } from '@/components/Header';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';
import { formatMeters } from '@/utils/format';
import { iconForAction } from '@/utils/maneuver';

export default function StepsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const { snapshot, actions } = useNavigationSession();

  const route = snapshot.route;
  const maneuvers = route?.maneuvers ?? [];
  const canStart = route && (snapshot.phase === 'routeReady' || snapshot.phase === 'navigating');

  function start() {
    actions.startNavigation();
    router.replace('/navigation');
  }

  return (
    <Screen>
      <View style={styles.header}>
        <ScreenHeader
          title="Direction Steps"
          subtitle={snapshot.destination ? `${snapshot.destination.latitude.toFixed(5)}, ${snapshot.destination.longitude.toFixed(5)}` : undefined}
          onBack={() => router.back()}
        />
      </View>

      <ScrollView contentContainerStyle={styles.list}>
        <View style={[styles.routeSummary, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
          <Icon name="destination" size={16} color={theme.colors.primary} />
          <Text style={[styles.routeSummaryText, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            Current position → Destination
          </Text>
        </View>

        {maneuvers.length === 0 ? (
          <Text style={[styles.empty, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            No route loaded yet. Pick a destination first.
          </Text>
        ) : null}

        {maneuvers.map((maneuver, index) => {
          const last = index === maneuvers.length - 1;
          return (
            <View key={`${maneuver.action}-${index}`} style={styles.stepRow}>
              <View style={styles.stepRail}>
                <View
                  style={[
                    styles.stepIconRing,
                    last
                      ? { backgroundColor: theme.colors.success }
                      : { backgroundColor: theme.colors.primaryContainer },
                  ]}
                >
                  <Icon
                    name={iconForAction(maneuver.action)}
                    size={18}
                    color={last ? theme.colors.onPrimary : theme.colors.onPrimaryContainer}
                  />
                </View>
                {!last ? <View style={[styles.rail, { backgroundColor: theme.colors.outlineVariant }]} /> : null}
              </View>
              <View style={styles.stepTextWrap}>
                <Text style={[styles.stepInstruction, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
                  {maneuver.instruction}
                </Text>
              </View>
              <Text style={[styles.stepDistance, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.semibold }]}>
                {formatMeters(maneuver.approachDistanceMeters)}
              </Text>
            </View>
          );
        })}
      </ScrollView>

      {canStart ? (
        <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
          <PrimaryButton icon="forward" onPress={start}>
            Start navigation
          </PrimaryButton>
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingTop: spacing.md,
  },
  list: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.lg,
  },
  routeSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    marginBottom: spacing.lg,
  },
  routeSummaryText: { flex: 1, fontSize: 13, lineHeight: 18 },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
  },
  stepRail: {
    alignItems: 'center',
    width: 38,
  },
  stepIconRing: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rail: {
    flex: 1,
    width: 2,
    marginVertical: spacing.xs,
  },
  stepTextWrap: {
    flex: 1,
    paddingTop: spacing.sm,
  },
  stepInstruction: { fontSize: 14, lineHeight: 19 },
  stepDistance: {
    fontSize: 13,
    lineHeight: 19,
    paddingTop: spacing.sm,
  },
  empty: {
    textAlign: 'center',
    marginTop: spacing.xl,
  },
  footer: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.sm,
  },
});