import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Pressable, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

type Props = {
  /** Torche LED arrière activée */
  enabled: boolean;
  onToggle: () => void;
};

/**
 * Bouton torche en bas à droite dans la zone caméra (au-dessus du panneau / onglets, safe area bas).
 */
export function ScanTorchFab({ enabled, onToggle }: Props) {
  const insets = useSafeAreaInsets();

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: enabled }}
      accessibilityLabel={enabled ? 'Éteindre la torche' : 'Allumer la torche'}
      onPress={onToggle}
      style={({ pressed }) => [
        styles.fab,
        {
          bottom: Math.max(insets.bottom, 10) + 8,
          right: 14,
        },
        enabled ? styles.fabActive : styles.fabIdle,
        pressed && styles.fabPressed,
      ]}
    >
      <MaterialCommunityIcons
        name={enabled ? 'flashlight' : 'flashlight-off'}
        size={22}
        color={enabled ? '#ffb84d' : 'rgba(255,255,255,0.9)'}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    zIndex: 20,
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  fabIdle: {
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderColor: 'rgba(255,255,255,0.35)',
  },
  fabActive: {
    backgroundColor: 'rgba(255,140,0,0.35)',
    borderColor: 'rgba(255,184,77,0.85)',
  },
  fabPressed: { opacity: 0.85 },
});
