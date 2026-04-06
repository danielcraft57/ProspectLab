import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, G, Line, Path } from 'react-native-svg';
import { useTheme } from './theme';

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const a = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

export type DonutSlice = { value: number; color?: string };

export function DonutChart({
  size = 120,
  thickness = 14,
  slices,
  trackOpacity = 0.12,
}: {
  size?: number;
  thickness?: number;
  slices: DonutSlice[];
  trackOpacity?: number;
}) {
  const t = useTheme();
  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;

  const { total, arcs } = useMemo(() => {
    const clean = slices
      .map((s) => ({ ...s, value: Number.isFinite(s.value) ? Math.max(0, s.value) : 0 }))
      .filter((s) => s.value > 0);
    const sum = clean.reduce((a, b) => a + b.value, 0);
    if (!sum) return { total: 0, arcs: [] as Array<{ start: number; end: number; color: string }> };
    let angle = 0;
    const computed = clean.map((s, idx) => {
      const span = (s.value / sum) * 360;
      const start = angle;
      const end = angle + span;
      angle = end;
      const fallback = idx % 2 === 0 ? t.colors.primary : t.colors.success;
      return { start, end, color: s.color ?? fallback };
    });
    return { total: sum, arcs: computed };
  }, [slices, t.colors.primary, t.colors.success]);

  return (
    <Svg width={size} height={size}>
      <G>
        <Circle
          cx={cx}
          cy={cy}
          r={r}
          stroke={t.colors.text}
          strokeOpacity={trackOpacity}
          strokeWidth={thickness}
          fill="none"
        />
        {total > 0 &&
          arcs.map((a, i) => (
            <Path
              key={i}
              d={arcPath(cx, cy, r, a.start, a.end)}
              stroke={a.color}
              strokeWidth={thickness}
              strokeLinecap="round"
              fill="none"
            />
          ))}
      </G>
    </Svg>
  );
}

export function Sparkline({
  values,
  width = 180,
  height = 46,
  strokeWidth = 3,
  showGrid = true,
}: {
  values: number[];
  width?: number;
  height?: number;
  strokeWidth?: number;
  showGrid?: boolean;
}) {
  const t = useTheme();
  const pts = useMemo(() => values.map((v) => (Number.isFinite(v) ? v : 0)), [values]);
  const max = Math.max(1, ...pts);
  const min = Math.min(0, ...pts);
  const span = Math.max(1e-6, max - min);

  const d = useMemo(() => {
    if (pts.length < 2) return '';
    return pts
      .map((v, i) => {
        const x = (i / (pts.length - 1)) * (width - 2) + 1;
        const y = (1 - (v - min) / span) * (height - 2) + 1;
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(' ');
  }, [pts, width, height, min, span]);

  if (!pts.length) return null;

  return (
    <Svg width={width} height={height}>
      {showGrid && (
        <>
          <Line x1="1" y1={height - 1} x2={width - 1} y2={height - 1} stroke={t.colors.border} strokeWidth="1" />
          <Line x1="1" y1="1" x2={width - 1} y2="1" stroke={t.colors.border} strokeWidth="1" />
        </>
      )}
      {d ? (
        <Path d={d} stroke={t.colors.primary} strokeWidth={strokeWidth} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      ) : null}
    </Svg>
  );
}

export function SegmentedBar({
  width = 220,
  height = 10,
  parts,
}: {
  width?: number;
  height?: number;
  parts: Array<{ value: number; color?: string }>;
}) {
  const t = useTheme();
  const clean = parts.map((p) => ({ ...p, value: Number.isFinite(p.value) ? Math.max(0, p.value) : 0 }));
  const total = clean.reduce((a, b) => a + b.value, 0);

  return (
    <View style={[styles.segWrap, { width, height, backgroundColor: t.colors.border, borderRadius: t.radii.pill }]}>
      {total <= 0 ? null : (
        <View style={{ flexDirection: 'row', flex: 1, height, overflow: 'hidden', borderRadius: t.radii.pill }}>
          {clean.map((p, i) => {
            const flex = clamp(p.value / total, 0, 1);
            if (flex <= 0) return null;
            const fallback = i % 2 === 0 ? t.colors.primary : t.colors.success;
            return <View key={i} style={{ flex, backgroundColor: p.color ?? fallback }} />;
          })}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  segWrap: { overflow: 'hidden' },
});

