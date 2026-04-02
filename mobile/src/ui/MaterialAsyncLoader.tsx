import { useEffect, useRef, type ComponentProps } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { MutedText } from './components';
import { useTheme } from './theme';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

/**
 * Chargement sans spinner circulaire : icône Material en rebond vertical + pulsation d’opacité.
 */
export function MaterialAsyncLoader({
  visible,
  message,
  compact,
  icon = 'cloud-sync-outline',
  size,
}: {
  visible: boolean;
  message?: string;
  compact?: boolean;
  icon?: IconName;
  size?: number;
}) {
  const t = useTheme();
  const bounce = useRef(new Animated.Value(0)).current;
  const iconSize = size ?? (compact ? 28 : 44);

  useEffect(() => {
    if (!visible) {
      bounce.setValue(0);
      return;
    }
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(bounce, {
          toValue: 1,
          duration: 520,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(bounce, {
          toValue: 0,
          duration: 520,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [visible, bounce]);

  const translateY = bounce.interpolate({
    inputRange: [0, 1],
    outputRange: [0, compact ? -6 : -10],
  });
  const opacity = bounce.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0.5, 1, 0.5],
  });

  if (!visible) return null;

  return (
    <View
      style={[styles.center, compact && styles.compact]}
      accessibilityRole="progressbar"
      accessibilityLabel={message ?? 'Chargement en cours'}
    >
      <Animated.View style={{ transform: [{ translateY }], opacity }}>
        <MaterialCommunityIcons name={icon} size={iconSize} color={t.colors.primary} />
      </Animated.View>
      {!!message && <MutedText style={[styles.msg, compact && styles.msgCompact]}>{message}</MutedText>}
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 18,
    gap: 10,
  },
  compact: {
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    justifyContent: 'flex-start',
  },
  msg: {
    marginTop: 2,
    textAlign: 'center',
    fontSize: 13,
  },
  msgCompact: {
    marginTop: 0,
    flex: 1,
    textAlign: 'left',
  },
});
