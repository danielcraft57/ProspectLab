import { useEffect, useMemo, useRef } from 'react';
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { AppTheme } from '../../ui/theme';

export type EntrepriseListFilters = {
  secteur?: string;
  statut?: string;
  opportunite?: string;
};

function chipBg(selected: boolean, t: AppTheme) {
  if (!selected) return 'transparent';
  return t.isDark ? 'rgba(79, 140, 255, 0.16)' : 'rgba(46, 107, 255, 0.10)';
}

function FilterChip({
  label,
  selected,
  onPress,
  t,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  t: AppTheme;
}) {
  const scale = useRef(new Animated.Value(1)).current;

  function pulse() {
    Animated.sequence([
      Animated.timing(scale, {
        toValue: 0.94,
        duration: 85,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.spring(scale, { toValue: 1, friction: 5, tension: 220, useNativeDriver: true }),
    ]).start();
  }

  return (
    <Pressable
      onPress={() => {
        pulse();
        onPress();
      }}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={`Filtre ${label}${selected ? ', sélectionné' : ''}`}
    >
      <Animated.View
        style={[
          styles.chip,
          {
            transform: [{ scale }],
            borderColor: selected ? t.colors.primary : t.colors.border,
            borderWidth: selected ? 2 : 1,
            backgroundColor: chipBg(selected, t),
          },
        ]}
      >
        <Text
          numberOfLines={1}
          style={{
            color: selected ? t.colors.primary : t.colors.text,
            fontWeight: selected ? '700' : '500',
            fontSize: 13,
            maxWidth: 200,
          }}
        >
          {label}
        </Text>
      </Animated.View>
    </Pressable>
  );
}

function SectionLabel({ children, t }: { children: string; t: AppTheme }) {
  return (
    <Text
      style={{
        fontSize: 11,
        fontWeight: '700',
        letterSpacing: 0.8,
        textTransform: 'uppercase',
        color: t.colors.muted,
        marginBottom: 8,
        marginTop: 4,
      }}
    >
      {children}
    </Text>
  );
}

function ChipRow({
  options,
  field,
  value,
  onToggle,
  t,
}: {
  options: string[];
  field: keyof EntrepriseListFilters;
  value: EntrepriseListFilters;
  onToggle: (field: keyof EntrepriseListFilters, option: string) => void;
  t: AppTheme;
}) {
  if (!options.length) return null;
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.chipScroll}
      keyboardShouldPersistTaps="handled"
    >
      {options.map((opt) => (
        <FilterChip
          key={`${field}-${opt}`}
          label={opt}
          selected={value[field] === opt}
          onPress={() => onToggle(field, opt)}
          t={t}
        />
      ))}
    </ScrollView>
  );
}

export type AdvancedListFiltersProps = {
  theme: AppTheme;
  expanded: boolean;
  onExpandedChange: (next: boolean) => void;
  secteurs: string[];
  opportunites: string[];
  statuts: string[];
  value: EntrepriseListFilters;
  onChange: (next: EntrepriseListFilters) => void;
  disabled?: boolean;
};

export function AdvancedListFilters({
  theme: t,
  expanded,
  onExpandedChange,
  secteurs,
  opportunites,
  statuts,
  value,
  onChange,
  disabled,
}: AdvancedListFiltersProps) {
  const progress = useRef(new Animated.Value(expanded ? 1 : 0)).current;
  const chevronSpin = useRef(new Animated.Value(expanded ? 1 : 0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.spring(progress, {
        toValue: expanded ? 1 : 0,
        friction: 8,
        tension: 64,
        useNativeDriver: false,
      }),
      Animated.timing(chevronSpin, {
        toValue: expanded ? 1 : 0,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start();
  }, [expanded, progress, chevronSpin]);

  const bodyMaxHeight = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 900],
  });

  const bodyOpacity = progress.interpolate({
    inputRange: [0, 0.12, 1],
    outputRange: [0, 0.9, 1],
  });

  const chevronRotation = chevronSpin.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });

  const activeCount = useMemo(() => {
    let n = 0;
    if (value.secteur) n++;
    if (value.statut) n++;
    if (value.opportunite) n++;
    return n;
  }, [value]);

  function toggle(field: keyof EntrepriseListFilters, option: string) {
    const cur = value[field];
    onChange({ ...value, [field]: cur === option ? undefined : option });
  }

  function reset() {
    onChange({});
  }

  return (
    <View
      style={[
        styles.wrap,
        {
          borderRadius: t.radii.card,
          borderColor: t.colors.border,
          backgroundColor: t.colors.card,
          ...(Platform.OS === 'ios'
            ? {
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 4 },
                shadowOpacity: t.isDark ? 0.35 : 0.06,
                shadowRadius: 12,
              }
            : { elevation: 3 }),
        },
      ]}
    >
      <Pressable
        onPress={() => !disabled && onExpandedChange(!expanded)}
        disabled={disabled}
        style={({ pressed }) => [
          styles.headerPress,
          { opacity: disabled ? 0.55 : pressed ? 0.88 : 1 },
        ]}
        accessibilityRole="button"
        accessibilityLabel={expanded ? 'Replier les filtres avancés' : 'Déplier les filtres avancés'}
        accessibilityState={{ expanded }}
      >
        <View style={styles.headerInner}>
          <View style={[styles.iconCircle, { backgroundColor: chipBg(true, t) }]}>
            <MaterialCommunityIcons name="tune-variant" size={20} color={t.colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: t.colors.text }]}>Filtres avancés</Text>
            <Text style={[styles.subtitle, { color: t.colors.muted }]}>
              Secteur, opportunité, statut — même logique que l’API web
            </Text>
          </View>
          {activeCount > 0 && (
            <View style={[styles.badge, { backgroundColor: t.colors.primary }]}>
              <Text style={[styles.badgeText, { color: t.colors.primaryText }]}>{activeCount}</Text>
            </View>
          )}
          <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
            <MaterialCommunityIcons name="chevron-down" size={26} color={t.colors.muted} />
          </Animated.View>
        </View>
      </Pressable>

      <Animated.View
        style={{
          maxHeight: bodyMaxHeight,
          opacity: bodyOpacity,
          overflow: 'hidden',
        }}
      >
        <View style={styles.body}>
          <SectionLabel t={t}>Secteur</SectionLabel>
          <ChipRow options={secteurs} field="secteur" value={value} onToggle={toggle} t={t} />
          <SectionLabel t={t}>Opportunité</SectionLabel>
          <ChipRow options={opportunites} field="opportunite" value={value} onToggle={toggle} t={t} />
          <SectionLabel t={t}>Statut entreprise</SectionLabel>
          <ChipRow options={statuts} field="statut" value={value} onToggle={toggle} t={t} />

          <Pressable
            onPress={reset}
            disabled={!activeCount || disabled}
            style={({ pressed }) => [
              styles.resetBtn,
              {
                borderColor: t.colors.border,
                opacity: !activeCount ? 0.45 : pressed ? 0.85 : 1,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Réinitialiser tous les filtres"
          >
            <MaterialCommunityIcons name="backup-restore" size={18} color={t.colors.danger} />
            <Text style={{ color: t.colors.danger, fontWeight: '600', marginLeft: 8 }}>Tout effacer</Text>
          </Pressable>
        </View>
      </Animated.View>
    </View>
  );
}

/** Puces horizontales sous le panneau pour retirer un critère sans rouvrir le panneau. */
export function ActiveFilterStrip({
  value,
  onChange,
  t,
}: {
  value: EntrepriseListFilters;
  onChange: (next: EntrepriseListFilters) => void;
  t: AppTheme;
}) {
  const entries: Array<{ key: keyof EntrepriseListFilters; label: string; v: string }> = [];
  if (value.secteur) entries.push({ key: 'secteur', label: 'Secteur', v: value.secteur });
  if (value.opportunite) entries.push({ key: 'opportunite', label: 'Opport.', v: value.opportunite });
  if (value.statut) entries.push({ key: 'statut', label: 'Statut', v: value.statut });

  if (!entries.length) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ gap: 8, paddingVertical: 4 }}
    >
      {entries.map((e) => (
        <Pressable
          key={e.key}
          onPress={() => onChange({ ...value, [e.key]: undefined })}
          style={({ pressed }) => [
            styles.stripChip,
            {
              borderColor: t.colors.primary,
              backgroundColor: chipBg(true, t),
              opacity: pressed ? 0.85 : 1,
            },
          ]}
        >
          <Text style={{ color: t.colors.primary, fontSize: 12, fontWeight: '600' }} numberOfLines={1}>
            {e.label}: {e.v}
          </Text>
          <MaterialCommunityIcons name="close-circle" size={16} color={t.colors.primary} style={{ marginLeft: 6 }} />
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderWidth: 1,
    overflow: 'hidden',
  },
  headerPress: {
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  headerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
  badge: {
    minWidth: 26,
    height: 26,
    borderRadius: 999,
    paddingHorizontal: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: 13,
    fontWeight: '800',
  },
  body: {
    paddingHorizontal: 14,
    paddingBottom: 16,
    paddingTop: 4,
  },
  chipScroll: {
    flexDirection: 'row',
    flexWrap: 'nowrap',
    gap: 8,
    paddingBottom: 6,
    alignItems: 'center',
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 999,
    marginRight: 4,
  },
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  stripChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1.5,
    marginRight: 4,
    maxWidth: 280,
  },
});
