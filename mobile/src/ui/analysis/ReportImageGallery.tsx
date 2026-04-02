import { useCallback, useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import ImageView from 'react-native-image-viewing';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '../theme';

const GAP = 10;
const COLS = 2;

type Props = {
  uris: string[];
  containerWidth: number;
};

/**
 * Grille 2 colonnes + viewer plein ecran (pinch/zoom + deplacement natifs Android/iOS).
 */
export function ReportImageGallery({ uris, containerWidth }: Props) {
  const t = useTheme();
  const [viewerVisible, setViewerVisible] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const cellW = Math.max(1, Math.floor((containerWidth - GAP) / COLS));
  const images = useMemo(() => uris.map((uri) => ({ uri })), [uris]);

  const openAt = useCallback((idx: number) => {
    // Certains navigateurs/générateurs d’état de `react-native-image-viewing` lisent l’index au moment où
    // `visible` passe à `true`. On force donc une séquence "visible false -> set index -> visible true".
    setViewerVisible(false);
    setTimeout(() => {
      setViewerIndex(idx);
      setViewerVisible(true);
    }, 0);
  }, []);

  const close = useCallback(() => {
    setViewerVisible(false);
  }, []);

  if (!uris.length) return null;

  return (
    <View style={[styles.grid, { width: containerWidth }]}>
      {uris.map((uri, idx) => (
        <Pressable
          key={`${uri}-${idx}`}
          onPress={() => openAt(idx)}
          style={({ pressed }) => [
            styles.cell,
            {
              width: cellW,
              height: Math.round(cellW * 0.72),
              marginRight: idx % COLS === 0 ? GAP : 0,
              marginBottom: GAP,
              borderColor: t.colors.border,
              opacity: pressed ? 0.9 : 1,
            },
          ]}
          accessibilityRole="button"
          accessibilityLabel="Agrandir la capture"
        >
          <Image source={{ uri }} style={styles.thumb} resizeMode="cover" />
          <View style={[styles.zoomHint, { backgroundColor: `${t.colors.bg}cc` }]}>
            <MaterialCommunityIcons name="magnify-plus-outline" size={16} color={t.colors.primary} />
          </View>
        </Pressable>
      ))}

      <ImageView
        // force un remount à l'ouverture pour garantir l’index correct
        key={viewerVisible ? `view-${viewerIndex}` : 'view-off'}
        images={images}
        imageIndex={viewerIndex}
        visible={viewerVisible}
        onRequestClose={close}
        swipeToCloseEnabled
        doubleTapToZoomEnabled
        backgroundColor="#000"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: {
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
  },
  thumb: { width: '100%', height: '100%' },
  zoomHint: {
    position: 'absolute',
    right: 6,
    bottom: 6,
    borderRadius: 8,
    padding: 4,
  },
});
