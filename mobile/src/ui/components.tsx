import { PropsWithChildren, useEffect, useMemo, useRef } from 'react';
import { Animated, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTheme } from './theme';

export function Screen({ children }: PropsWithChildren) {
  const t = useTheme();
  return <View style={[styles.screen, { backgroundColor: t.colors.bg }]}>{children}</View>;
}

export function Card({ children, style }: PropsWithChildren<{ style?: any }>) {
  const t = useTheme();
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: t.colors.card, borderColor: t.colors.border, borderRadius: t.radii.card },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function H1({ children }: PropsWithChildren) {
  const t = useTheme();
  return <Text style={[styles.h1, { color: t.colors.text }]}>{children}</Text>;
}

export function H2({ children }: PropsWithChildren) {
  const t = useTheme();
  return <Text style={[styles.h2, { color: t.colors.text }]}>{children}</Text>;
}

export function Muted({ children }: PropsWithChildren) {
  const t = useTheme();
  return <Text style={[styles.muted, { color: t.colors.muted }]}>{children}</Text>;
}

export function MutedText({
  children,
  style,
}: PropsWithChildren<{ style?: any }>) {
  const t = useTheme();
  return <Text style={[styles.muted, { color: t.colors.muted }, style]}>{children}</Text>;
}

export function Mono({ children }: PropsWithChildren) {
  const t = useTheme();
  return <Text style={[styles.mono, { color: t.colors.muted }]}>{children}</Text>;
}

export function PrimaryButton({
  title,
  onPress,
  disabled,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.btn,
        {
          backgroundColor: disabled ? t.colors.border : t.colors.primary,
          opacity: pressed ? 0.9 : 1,
        },
      ]}
    >
      <Text style={[styles.btnText, { color: disabled ? t.colors.muted : t.colors.primaryText }]}>{title}</Text>
    </Pressable>
  );
}

export function DangerButton({
  title,
  onPress,
}: {
  title: string;
  onPress: () => void;
}) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.btn,
        { backgroundColor: t.colors.danger, opacity: pressed ? 0.9 : 1 },
      ]}
    >
      <Text style={[styles.btnText, { color: '#fff' }]}>{title}</Text>
    </Pressable>
  );
}

export function FadeIn({ children, delayMs = 0 }: PropsWithChildren<{ delayMs?: number }>) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const t = setTimeout(() => {
      Animated.timing(anim, {
        toValue: 1,
        duration: 260,
        // Web: evite le warning "native animated module is missing"
        useNativeDriver: Platform.OS !== 'web',
      }).start();
    }, delayMs);
    return () => clearTimeout(t);
  }, [anim, delayMs]);

  const style = useMemo(() => ({ opacity: anim, transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }] }), [anim]);

  return <Animated.View style={style}>{children}</Animated.View>;
}

export function MiniBarChart({ values }: { values: number[] }) {
  const t = useTheme();
  const max = Math.max(1, ...values);
  return (
    <View style={styles.chartRow}>
      {values.map((v, i) => (
        <View key={i} style={styles.chartBarWrap}>
          <View
            style={[
              styles.chartBar,
              {
                height: Math.max(2, Math.round((v / max) * 26)),
                backgroundColor: t.colors.primary,
                opacity: 0.25 + (i / Math.max(1, values.length - 1)) * 0.55,
              },
            ]}
          />
        </View>
      ))}
    </View>
  );
}

export function FloatingAlert({
  visible,
  message,
  onClose,
  placement = 'top',
  tone = 'warning',
}: {
  visible: boolean;
  message: string;
  onClose: () => void;
  placement?: 'top' | 'bottom';
  tone?: 'warning' | 'success';
}) {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: visible ? 1 : 0,
      duration: 220,
      useNativeDriver: Platform.OS !== 'web',
    }).start();
  }, [anim, visible]);

  if (!visible) return null;
  return (
    <Animated.View
      pointerEvents="box-none"
      style={[
        placement === 'bottom'
          ? [styles.floatingWrapBottom, { bottom: insets.bottom + 62 }]
          : styles.floatingWrapTop,
        {
          opacity: anim,
          transform: [
            {
              translateY: anim.interpolate({
                inputRange: [0, 1],
                outputRange: [placement === 'bottom' ? 12 : -12, 0],
              }),
            },
          ],
        },
      ]}
    >
      <View
        style={[
          styles.floatingAlert,
          {
            backgroundColor: t.colors.card,
            borderColor: (tone === 'success' ? t.colors.success : t.colors.warning) + 'CC',
          },
        ]}
      >
        <Text style={[styles.floatingText, { color: t.colors.text }]}>{message}</Text>
        <Pressable onPress={onClose} style={styles.floatingCloseBtn}>
          <Text style={[styles.floatingCloseText, { color: t.colors.muted }]}>Fermer</Text>
        </Pressable>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  card: { borderWidth: 1, padding: 14 },
  h1: { fontSize: 26, fontWeight: '800', letterSpacing: -0.5 },
  h2: { fontSize: 16, fontWeight: '800' },
  muted: { fontSize: 13 },
  mono: { fontFamily: 'monospace', fontSize: 12 },
  btn: { paddingVertical: 12, paddingHorizontal: 14, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  btnText: { fontWeight: '800' },
  chartRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, marginTop: 10 },
  chartBarWrap: { flex: 1, height: 26, justifyContent: 'flex-end' },
  chartBar: { borderRadius: 6 },
  floatingWrapTop: {
    position: 'absolute',
    left: 12,
    right: 12,
    top: 10,
    zIndex: 30,
    elevation: 30,
  },
  floatingWrapBottom: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 62,
    zIndex: 30,
    elevation: 30,
  },
  floatingAlert: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  floatingText: { flex: 1, fontSize: 13, fontWeight: '600' },
  floatingCloseBtn: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 8,
  },
  floatingCloseText: { fontSize: 12, fontWeight: '700' },
});

