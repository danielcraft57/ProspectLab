import { useCallback, useMemo, useState, type ReactNode } from 'react';
import {
  Dimensions,
  LayoutAnimation,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';
import { FontAwesome6 } from '@expo/vector-icons';
import { DonutChart, SegmentedBar } from '../charts';
import { Mono, MutedText } from '../components';
import type { AppTheme } from '../theme';
import { useTheme } from '../theme';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function tryParseJson(v: unknown): unknown {
  if (typeof v !== 'string') return v;
  const s = v.trim();
  if (!s) return v;
  if (!(s.startsWith('{') || s.startsWith('['))) return v;
  try {
    return JSON.parse(s);
  } catch {
    return v;
  }
}

export type AnalysisKind = 'seo' | 'technical' | 'pentest' | 'osint';

function num01to100(v: unknown): number | null {
  if (typeof v !== 'number' || !Number.isFinite(v)) {
    if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) return num01to100(Number(v));
    return null;
  }
  if (v >= 0 && v <= 1) return Math.round(v * 100);
  if (v > 1 && v <= 100) return Math.round(v);
  return Math.round(Math.min(100, Math.max(0, v)));
}

function scoreToColor(t: AppTheme, pct: number) {
  if (pct >= 75) return t.colors.success;
  if (pct >= 50) return t.colors.warning;
  return t.colors.danger;
}

function ScoreBar({ label, valuePct, t }: { label: string; valuePct: number | null; t: AppTheme }) {
  const pct = valuePct == null ? null : Math.min(100, Math.max(0, valuePct));
  const color = pct == null ? t.colors.muted : scoreToColor(t, pct);
  return (
    <View style={{ marginBottom: 10 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
        <Text style={{ color: t.colors.muted, fontSize: 12, fontWeight: '600' }}>{label}</Text>
        <Text style={{ color: t.colors.text, fontSize: 12, fontWeight: '800' }}>{pct == null ? '—' : `${pct}`}</Text>
      </View>
      <View style={[styles.track, { backgroundColor: t.colors.border }]}>
        {pct != null ? (
          <View style={[styles.trackFill, { width: `${pct}%`, backgroundColor: color }]} />
        ) : null}
      </View>
    </View>
  );
}

function SectionTitle({ children, t }: { children: ReactNode; t: AppTheme }) {
  return <Text style={[styles.sectionTitle, { color: t.colors.text }]}>{children}</Text>;
}

function Chip({ text, tone, t }: { text: string; tone: 'ok' | 'warn' | 'bad' | 'neutral'; t: AppTheme }) {
  const bg =
    tone === 'ok'
      ? `${t.colors.success}22`
      : tone === 'warn'
        ? `${t.colors.warning}22`
        : tone === 'bad'
          ? `${t.colors.danger}22`
          : t.colors.border;
  const fg =
    tone === 'ok'
      ? t.colors.success
      : tone === 'warn'
        ? t.colors.warning
        : tone === 'bad'
          ? t.colors.danger
          : t.colors.muted;
  return (
    <View style={[styles.chip, { backgroundColor: bg, borderColor: t.colors.border }]}>
      <Text style={{ color: fg, fontSize: 11, fontWeight: '700' }} numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

function KeyValueRow({ k, v, t }: { k: string; v: string; t: AppTheme }) {
  return (
    <View style={styles.kvRow}>
      <Text style={{ color: t.colors.muted, fontSize: 12, flex: 1 }} numberOfLines={3}>
        {k}
      </Text>
      <Text style={{ color: t.colors.text, fontSize: 12, flex: 1.2, fontWeight: '600' }} selectable>
        {v}
      </Text>
    </View>
  );
}

function flattenForKv(obj: Record<string, unknown>, max = 24): Array<{ k: string; v: string }> {
  const out: Array<{ k: string; v: string }> = [];
  const keys = Object.keys(obj).filter((x) => !x.startsWith('_'));
  for (const key of keys) {
    if (out.length >= max) break;
    const val = obj[key];
    if (val == null) continue;
    if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
      out.push({ k: key, v: String(val) });
    }
  }
  return out;
}

function RiskMeter({ score, t }: { score: number; t: AppTheme }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = score >= 70 ? t.colors.danger : score >= 40 ? t.colors.warning : t.colors.success;
  return (
    <View style={{ alignItems: 'center', marginVertical: 8 }}>
      <DonutChart
        size={112}
        thickness={12}
        slices={[
          { value: pct, color },
          { value: Math.max(0, 100 - pct), color: t.colors.border },
        ]}
      />
      <Text style={{ marginTop: 8, color: t.colors.text, fontWeight: '900', fontSize: 18 }}>Risque {score}/100</Text>
      <SegmentedBar
        width={260}
        height={8}
        parts={[
          { value: Math.max(0, 100 - pct), color: t.colors.success },
          { value: pct, color },
        ]}
      />
      <MutedText style={{ marginTop: 6, fontSize: 11 }}>Barre : faible → élevé</MutedText>
    </View>
  );
}

function parseJsonFields(row: Record<string, unknown>, keys: string[]) {
  const o = { ...row };
  for (const k of keys) {
    if (typeof o[k] === 'string') {
      const p = tryParseJson(o[k]);
      if (p !== o[k]) o[k] = p as unknown;
    }
  }
  return o;
}

function SeoBody({ row, parsed, t }: { row: Record<string, unknown>; parsed: unknown; t: AppTheme }) {
  const merged = useMemo(() => parseJsonFields(row, ['lighthouse_json', 'issues_json', 'meta_tags_json', 'structure_json']), [row]);

  const lighthouseRaw = useMemo(() => {
    const lj = merged.lighthouse_json;
    if (lj && typeof lj === 'object') return lj as Record<string, unknown>;
    if (parsed && typeof parsed === 'object') {
      const p = parsed as Record<string, unknown>;
      if (p.categories || p.audits) return p;
      if (p.raw_data && typeof p.raw_data === 'object') return p.raw_data as Record<string, unknown>;
    }
    return null;
  }, [merged.lighthouse_json, parsed]);

  const lhCompact = useMemo(() => {
    if (parsed && typeof parsed === 'object') {
      const p = parsed as Record<string, unknown>;
      if (p.audits && (p.score != null || p.performance_score != null)) return p;
    }
    return null;
  }, [parsed]);

  const categories = lighthouseRaw?.categories as Record<string, { score?: number }> | undefined;
  const catLabels: Record<string, string> = {
    performance: 'Performance',
    accessibility: 'Accessibilité',
    'best-practices': 'Bonnes pratiques',
    seo: 'SEO (Lighthouse)',
    pwa: 'PWA',
  };

  const issues = useMemo(() => {
    const ij = merged.issues_json;
    if (Array.isArray(ij)) return ij as unknown[];
    if (parsed && Array.isArray(parsed)) return parsed as unknown[];
    return [];
  }, [merged.issues_json, parsed]);

  const meta = merged.meta_tags_json as Record<string, unknown> | undefined;
  const scoreDb = typeof merged.score === 'number' ? merged.score : Number(merged.score);

  return (
    <View>
      {(Number.isFinite(scoreDb) || lhCompact?.score != null) && (
        <View style={{ marginBottom: 12 }}>
          <SectionTitle t={t}>Score global</SectionTitle>
          <ScoreBar
            label="Score SEO (base)"
            valuePct={Number.isFinite(scoreDb) ? Math.min(100, Math.max(0, scoreDb)) : null}
            t={t}
          />
          {lhCompact?.score != null && (
            <ScoreBar label="SEO Lighthouse (extrait)" valuePct={num01to100(lhCompact.score)} t={t} />
          )}
          {lhCompact?.performance_score != null && (
            <ScoreBar label="Performance Lighthouse" valuePct={num01to100(lhCompact.performance_score)} t={t} />
          )}
        </View>
      )}

      {categories && Object.keys(categories).length > 0 && (
        <View style={{ marginBottom: 12 }}>
          <SectionTitle t={t}>Catégories Lighthouse</SectionTitle>
          {Object.entries(categories).map(([key, cat]) => (
            <ScoreBar key={key} label={catLabels[key] ?? key} valuePct={num01to100(cat?.score)} t={t} />
          ))}
        </View>
      )}

      {meta && Object.keys(meta).length > 0 && (
        <View style={{ marginBottom: 12 }}>
          <SectionTitle t={t}>Méta-tags</SectionTitle>
          {flattenForKv(meta as Record<string, unknown>, 16).map(({ k, v }) => (
            <KeyValueRow key={k} k={k} v={v} t={t} />
          ))}
        </View>
      )}

      {issues.length > 0 && (
        <View style={{ marginBottom: 8 }}>
          <SectionTitle t={t}>{`Points d’attention (${issues.length})`}</SectionTitle>
          {issues.slice(0, 12).map((it, i) => {
            const o = it && typeof it === 'object' ? (it as Record<string, unknown>) : {};
            const msg = String(o.message ?? o.title ?? JSON.stringify(it)).slice(0, 220);
            const impact = String(o.impact ?? o.type ?? '');
            const tone =
              /high|critical|error/i.test(impact) || /critical/i.test(String(o.type))
                ? 'bad'
                : /medium|warning/i.test(impact)
                  ? 'warn'
                  : 'neutral';
            return (
              <View key={i} style={[styles.issueRow, { borderColor: t.colors.border }]}>
                {!!impact && <Chip text={impact} tone={tone} t={t} />}
                <MutedText style={{ marginTop: 4, fontSize: 12 }}>{msg}</MutedText>
              </View>
            );
          })}
          {issues.length > 12 && <MutedText style={{ marginTop: 4 }}>+ {issues.length - 12} autres…</MutedText>}
        </View>
      )}
    </View>
  );
}

function TechnicalBody({ row, t }: { row: Record<string, unknown>; t: AppTheme }) {
  const merged = useMemo(
    () =>
      parseJsonFields(row, [
        'seo_meta',
        'performance_metrics',
        'nmap_scan',
        'technical_details',
        'pages_summary',
      ]),
    [row],
  );

  const perf = merged.performance_metrics as Record<string, unknown> | undefined;
  const pages = merged.pages as unknown[] | undefined;
  const headers = merged.security_headers as Record<string, unknown> | undefined;

  return (
    <View>
      {!!merged.url && <KeyValueRow k="URL" v={String(merged.url)} t={t} />}
      {!!merged.date_analyse && <KeyValueRow k="Date" v={String(merged.date_analyse)} t={t} />}

      {perf && Object.keys(perf).length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>Performances / métriques</SectionTitle>
          {Object.entries(perf).map(([k, v]) => {
            const pct = num01to100(v as number);
            if (pct != null) return <ScoreBar key={k} label={k} valuePct={pct} t={t} />;
            if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
              return <KeyValueRow key={k} k={k} v={String(v)} t={t} />;
            }
            if (v && typeof v === 'object') {
              return <KeyValueRow key={k} k={k} v={JSON.stringify(v).slice(0, 400)} t={t} />;
            }
            return null;
          })}
        </View>
      )}

      {headers && typeof headers === 'object' && !Array.isArray(headers) && Object.keys(headers).length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>En-têtes sécurité</SectionTitle>
          {Object.entries(headers).map(([name, data]) => (
            <KeyValueRow
              key={name}
              k={name}
              v={data && typeof data === 'object' ? JSON.stringify(data) : String(data ?? '—')}
              t={t}
            />
          ))}
        </View>
      )}

      {Array.isArray(pages) && pages.length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>{`Pages (${pages.length})`}</SectionTitle>
          <Text style={{ fontSize: 12, color: t.colors.muted }} numberOfLines={3}>
            Aperçu des chemins :{' '}
            {pages
              .slice(0, 4)
              .map((p) => (p && typeof p === 'object' ? String((p as any).url ?? (p as any).path ?? '') : ''))
              .filter(Boolean)
              .join(' · ')}
          </Text>
        </View>
      )}

      {Array.isArray(merged.cms_plugins) && merged.cms_plugins.length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>Plugins / CMS</SectionTitle>
          <MutedText style={{ fontSize: 12 }}>{merged.cms_plugins.length} entrées</MutedText>
        </View>
      )}
    </View>
  );
}

function severityTone(s: string): 'ok' | 'warn' | 'bad' | 'neutral' {
  const x = s.toLowerCase();
  if (/critical|high|élevé|severe/i.test(x)) return 'bad';
  if (/medium|warn|moyen/i.test(x)) return 'warn';
  if (/low|info|faible/i.test(x)) return 'neutral';
  return 'neutral';
}

function PentestBody({ row, t }: { row: Record<string, unknown>; t: AppTheme }) {
  const merged = useMemo(
    () =>
      parseJsonFields(row, [
        'vulnerabilities',
        'sql_injection',
        'xss_vulnerabilities',
        'csrf_vulnerabilities',
        'authentication_issues',
        'authorization_issues',
        'sensitive_data_exposure',
        'security_headers_analysis',
        'ssl_tls_analysis',
        'waf_detection',
        'cms_vulnerabilities',
        'api_security',
        'network_scan',
        'pentest_details',
      ]),
    [row],
  );

  const risk = typeof merged.risk_score === 'number' ? merged.risk_score : Number(merged.risk_score);
  const vulns = merged.vulnerabilities as unknown[] | undefined;

  return (
    <View>
      {Number.isFinite(risk) && <RiskMeter score={Math.min(100, Math.max(0, risk))} t={t} />}

      {!!merged.url && <KeyValueRow k="Cible" v={String(merged.url)} t={t} />}
      {!!merged.date_analyse && <KeyValueRow k="Date" v={String(merged.date_analyse)} t={t} />}

      {Array.isArray(vulns) && vulns.length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>{`Vulnérabilités (${vulns.length})`}</SectionTitle>
          {vulns.slice(0, 15).map((it, i) => {
            const o = it && typeof it === 'object' ? (it as Record<string, unknown>) : {};
            const name = String(o.name ?? o.title ?? `Item ${i + 1}`);
            const sev = String(o.severity ?? o.level ?? '');
            const desc = String(o.description ?? o.message ?? '').slice(0, 280);
            return (
              <View key={i} style={[styles.issueRow, { borderColor: t.colors.border }]}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Text style={{ color: t.colors.text, fontWeight: '800', flex: 1 }} numberOfLines={2}>
                    {name}
                  </Text>
                  {!!sev && <Chip text={sev} tone={severityTone(sev)} t={t} />}
                </View>
                {!!desc && (
                  <Text style={{ marginTop: 6, fontSize: 12, color: t.colors.muted }} numberOfLines={6}>
                    {desc}
                  </Text>
                )}
              </View>
            );
          })}
        </View>
      )}

      {Array.isArray(merged.open_ports) && merged.open_ports.length > 0 && (
        <View style={{ marginTop: 12 }}>
          <SectionTitle t={t}>Ports ouverts</SectionTitle>
          {(merged.open_ports as Record<string, unknown>[])
            .slice(0, 12)
            .map((p, i) => (
              <KeyValueRow key={i} k={String(p.port ?? i)} v={String(p.service ?? '—')} t={t} />
            ))}
        </View>
      )}
    </View>
  );
}

const OSINT_SECTIONS: Array<{ key: string; title: string }> = [
  { key: 'subdomains', title: 'Sous-domaines' },
  { key: 'dns_records', title: 'DNS' },
  { key: 'emails_found', title: 'Emails' },
  { key: 'social_media', title: 'Réseaux sociaux' },
  { key: 'technologies_detected', title: 'Technologies' },
  { key: 'open_ports', title: 'Ports' },
  { key: 'services', title: 'Services' },
  { key: 'ssl_details', title: 'SSL / TLS' },
  { key: 'certificates', title: 'Certificats' },
  { key: 'whois_info', title: 'WHOIS' },
  { key: 'whois_data', title: 'WHOIS (brut)' },
  { key: 'waf_detections', title: 'WAF' },
  { key: 'directories', title: 'Répertoires' },
];

function OsintBody({ row, t }: { row: Record<string, unknown>; t: AppTheme }) {
  const merged = useMemo(
    () => parseJsonFields(row, ['whois_data', 'ssl_info', 'ip_info', 'shodan_data', 'censys_data', 'osint_details']),
    [row],
  );

  return (
    <View>
      {!!merged.url && <KeyValueRow k="Cible" v={String(merged.url)} t={t} />}
      {!!merged.date_analyse && <KeyValueRow k="Date" v={String(merged.date_analyse)} t={t} />}

      {OSINT_SECTIONS.map(({ key, title }) => {
        const data =
          key === 'emails_found'
            ? (merged as Record<string, unknown>).emails_found ?? (merged as Record<string, unknown>).emails
            : (merged as Record<string, unknown>)[key];
        if (data == null) return null;
        const n = Array.isArray(data) ? data.length : typeof data === 'object' ? Object.keys(data).length : 1;
        if (!n) return null;
        return (
          <View key={key} style={{ marginTop: 12 }}>
            <SectionTitle t={t}>
              {`${title}${Array.isArray(data) ? ` (${data.length})` : ''}`}
            </SectionTitle>
            {Array.isArray(data) ? (
              data.slice(0, 8).map((it, i) => (
                <Text
                  key={i}
                  style={{ fontSize: 12, marginBottom: 4, color: t.colors.muted }}
                  numberOfLines={4}
                >
                  {typeof it === 'object' ? JSON.stringify(it) : String(it)}
                </Text>
              ))
            ) : typeof data === 'object' ? (
              flattenForKv(data as Record<string, unknown>, 14).map(({ k, v }) => <KeyValueRow key={k} k={k} v={v} t={t} />)
            ) : (
              <MutedText style={{ fontSize: 12 }}>{String(data)}</MutedText>
            )}
            {Array.isArray(data) && data.length > 8 && <MutedText>+ {data.length - 8} autres…</MutedText>}
          </View>
        );
      })}
    </View>
  );
}

function JsonFallback({ data, t }: { data: unknown; t: AppTheme }) {
  const [open, setOpen] = useState(false);
  const text = useMemo(() => {
    try {
      return typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  }, [data]);

  return (
    <View style={{ marginTop: 8 }}>
      <Pressable
        onPress={() => {
          LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
          setOpen((o) => !o);
        }}
        style={({ pressed }) => [styles.jsonBtn, { borderColor: t.colors.border, opacity: pressed ? 0.85 : 1 }]}
      >
        <FontAwesome6 name="code" size={12} color={t.colors.primary} />
        <Text style={{ color: t.colors.primary, fontWeight: '700', fontSize: 12 }}>
          {open ? 'Masquer' : 'Voir'} les données brutes (JSON)
        </Text>
      </Pressable>
      {open && (
        <View style={{ marginTop: 8 }}>
          <Mono>{text.length > 12000 ? `${text.slice(0, 12000)}\n…` : text}</Mono>
        </View>
      )}
    </View>
  );
}

function unwrapEnvelope(envelope: unknown, parsed: unknown): { status?: string; row: Record<string, unknown> | null } {
  if (envelope && typeof envelope === 'object' && envelope !== null && 'latest' in envelope) {
    const e = envelope as Record<string, unknown>;
    const latest = e.latest;
    const status = typeof e.status === 'string' ? e.status : undefined;
    if (latest && typeof latest === 'object') {
      return { status, row: latest as Record<string, unknown> };
    }
    return { status, row: null };
  }
  if (envelope && typeof envelope === 'object' && envelope !== null) {
    return { row: envelope as Record<string, unknown> };
  }
  if (parsed && typeof parsed === 'object') {
    return { row: parsed as Record<string, unknown> };
  }
  return { row: null };
}

function AnalysisContent({ kind, envelope, parsed }: { kind: AnalysisKind; envelope: unknown; parsed: unknown }) {
  const t = useTheme();
  const { status, row } = unwrapEnvelope(envelope, parsed);

  const mergedRow = useMemo(() => {
    if (row && Object.keys(row).length) return row;
    if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
    return row;
  }, [row, parsed]);

  const empty = !mergedRow || Object.keys(mergedRow).length === 0;

  if (empty && status === 'never') {
    return <MutedText style={{ fontSize: 13 }}>Aucune analyse enregistrée pour cette catégorie.</MutedText>;
  }

  if (empty) {
    return <MutedText style={{ fontSize: 13 }}>Pas de détail structuré.</MutedText>;
  }

  return (
    <View>
      {!!status && status !== 'done' && (
        <View style={{ marginBottom: 8 }}>
          <Chip text={`Statut: ${status}`} tone={status === 'never' ? 'neutral' : 'warn'} t={t} />
        </View>
      )}
      {kind === 'seo' && <SeoBody row={mergedRow!} parsed={parsed} t={t} />}
      {kind === 'technical' && <TechnicalBody row={mergedRow!} t={t} />}
      {kind === 'pentest' && <PentestBody row={mergedRow!} t={t} />}
      {kind === 'osint' && <OsintBody row={mergedRow!} t={t} />}
      <JsonFallback
        data={parsed && typeof parsed === 'object' ? { envelope: row, parsed } : mergedRow}
        t={t}
      />
    </View>
  );
}

const ANALYSIS_BODY_MAX_H = Math.min(380, Math.round(Dimensions.get('window').height * 0.42));

export function WebsiteAnalysisSection({
  kind,
  title,
  icon,
  expanded,
  onToggle,
  subtitle,
  envelope,
  parsed,
}: {
  kind: AnalysisKind;
  title: string;
  icon: string;
  expanded: boolean;
  onToggle: () => void;
  /** Ligne de contexte (scores fiche, date analyse, opportunité…) — pas de préfixe « Statut ». */
  subtitle?: string;
  envelope: unknown;
  parsed: unknown;
}) {
  const t = useTheme();
  const onPress = useCallback(() => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    onToggle();
  }, [onToggle]);

  return (
    <View style={[styles.card, { borderColor: t.colors.border, backgroundColor: t.colors.card }]}>
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [styles.header, { opacity: pressed ? 0.92 : 1 }]}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
      >
        <View style={[styles.iconWrap, { backgroundColor: `${t.colors.primary}18` }]}>
          <FontAwesome6 name={icon} size={14} color={t.colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ color: t.colors.text, fontWeight: '800', fontSize: 15 }}>{title}</Text>
          <Text style={{ marginTop: 2, fontSize: 12, color: t.colors.muted }} numberOfLines={3}>
            {subtitle?.trim() ? subtitle : '—'}
          </Text>
        </View>
        <FontAwesome6 name={expanded ? 'chevron-up' : 'chevron-down'} size={12} color={t.colors.muted} />
      </Pressable>
      {expanded && (
        <ScrollView
          style={{ maxHeight: ANALYSIS_BODY_MAX_H }}
          nestedScrollEnabled
          showsVerticalScrollIndicator
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.body}>
            <AnalysisContent kind={kind} envelope={envelope} parsed={parsed} />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderRadius: 14,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 12,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: {
    paddingHorizontal: 12,
    paddingBottom: 12,
  },
  track: {
    height: 8,
    borderRadius: 999,
    overflow: 'hidden',
  },
  trackFill: {
    height: 8,
    borderRadius: 999,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  kvRow: {
    flexDirection: 'row',
    gap: 8,
    paddingVertical: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(128,128,128,0.2)',
  },
  issueRow: {
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 8,
  },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  jsonBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
});
