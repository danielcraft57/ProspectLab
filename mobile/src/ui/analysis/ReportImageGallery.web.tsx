import { useCallback, useMemo, useState } from 'react';
import { Dimensions, Image, Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from '../theme';

const GAP = 10;
const COLS = 2;

type Props = {
  uris: string[];
  containerWidth: number;
};

function safeUri(uri: unknown): string | null {
  if (typeof uri !== 'string') return null;
  const s = uri.trim();
  return s ? s : null;
}

/**
 * Version Web: évite `react-native-image-viewing` (qui casse le bundling Web sur certaines versions).
 * On garde la grille 2 colonnes + un viewer modal (sans pinch/zoom natif sur web).
 */
export function ReportImageGallery({ uris, containerWidth }: Props) {
  const t = useTheme();
  const [viewerVisible, setViewerVisible] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const cellW = Math.max(1, Math.floor((containerWidth - GAP) / COLS));
  const images = useMemo(() => uris.map((u) => safeUri(u)).filter((u): u is string => !!u), [uris]);
  const currentUri = images[viewerIndex] ?? null;

  const openAt = useCallback((idx: number) => {
    setViewerIndex(idx);
    setViewerVisible(true);
  }, []);

  const close = useCallback(() => setViewerVisible(false), []);

  if (!images.length) return null;

  const { width: winW, height: winH } = Dimensions.get('window');
  const modalMaxH = Math.max(120, Math.floor(winH * 0.86));

  return (
    <View style={[styles.grid, { width: containerWidth }]}>
      {images.map((uri, idx) => (
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

      <Modal
        visible={viewerVisible}
        transparent={false}
        animationType="fade"
        onRequestClose={close}
      >
        <View style={[styles.modalRoot, { backgroundColor: t.colors.bg }]}>
          <Pressable
            onPress={close}
            style={({ pressed }) => [
              styles.modalClose,
              { opacity: pressed ? 0.8 : 1, borderColor: t.colors.border },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Fermer l'image"
          >
            <MaterialCommunityIcons name="close" size={20} color={t.colors.muted} />
          </Pressable>

          <ScrollView contentContainerStyle={styles.modalScroll} maximumZoomScale={1}>
            {currentUri ? (
              <Image
                source={{ uri: currentUri }}
                resizeMode="contain"
                style={{ width: winW, maxHeight: modalMaxH }}
              />
            ) : null}
          </ScrollView>
        </View>
      </Modal>
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
  modalRoot: { flex: 1 },
  modalClose: {
    position: 'absolute',
    top: 14,
    right: 14,
    zIndex: 5,
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1,
    backgroundColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalScroll: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 48, paddingBottom: 20 },
});

