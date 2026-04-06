import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Platform, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Config } from '../../src/core/config';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { Card, DangerButton, FadeIn, H2, Mono, MutedText, PrimaryButton, Screen } from '../../src/ui/components';
import { useTheme } from '../../src/ui/theme';

export default function SettingsScreen() {
  const t = useTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ ocrToken?: string }>();
  const { token, loading, save, clear } = useApiToken();
  const [draft, setDraft] = useState('');
  const [tokenInfo, setTokenInfo] = useState<any>(null);
  const [tokenInfoLoading, setTokenInfoLoading] = useState(false);
  const [tokenInfoError, setTokenInfoError] = useState<string | null>(null);
  const [ocrBusy, setOcrBusy] = useState(false);

  useEffect(() => {
    if (typeof params.ocrToken !== 'string' || !params.ocrToken.trim()) return;
    setDraft(params.ocrToken.trim());
    router.setParams({ ocrToken: undefined });
  }, [params.ocrToken, router]);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!token) {
        setTokenInfo(null);
        setTokenInfoError(null);
        return;
      }
      setTokenInfoLoading(true);
      setTokenInfoError(null);
      try {
        const res = await ProspectLabApi.getTokenInfo(token, { skipCache: false });
        const data = res?.data ?? res;
        if (!cancelled) setTokenInfo(data);
      } catch (e: any) {
        if (!cancelled) setTokenInfoError(e?.message ?? 'Impossible de lire les infos token');
      } finally {
        if (!cancelled) setTokenInfoLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const masked = useMemo(() => {
    if (!token) return null;
    if (token.length <= 12) return '********';
    return `${token.slice(0, 6)}...${token.slice(-4)}`;
  }, [token]);

  async function openLiveOcrScanner() {
    if (Platform.OS === 'web') {
      Alert.alert('Non disponible', "L'OCR du token n'est pas disponible sur le web.");
      return;
    }
    setOcrBusy(true);
    router.push('/token-ocr');
    setOcrBusy(false);
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.container}>
        <FadeIn>
          <Card>
            <View style={styles.rowIcon}>
              <MaterialCommunityIcons name="server" size={16} color="#4f8cff" />
              <H2>Serveur ProspectLab</H2>
            </View>
            <Mono>Base URL: {Config.prospectLabBaseUrl}</Mono>
            <Mono>Prefix: {Config.prospectLabPublicPrefix}</Mono>
          </Card>
        </FadeIn>

        <FadeIn delayMs={60}>
          <Card>
            <View style={styles.rowIcon}>
              <FontAwesome6 name="key" size={14} color="#4f8cff" />
              <H2>Token API</H2>
            </View>
            <MutedText>Etat</MutedText>
            <MutedText>{loading ? 'Chargement...' : token ? `Configure: ${masked}` : 'Aucun token'}</MutedText>

            {!!token && (
              <View style={{ marginTop: 10 }}>
                {tokenInfoLoading && <ActivityIndicator color={t.colors.primary} />}
                {!!tokenInfoError && <MutedText>{tokenInfoError}</MutedText>}
                {!tokenInfoLoading && !!tokenInfo && (
                  <>
                    <Mono>{tokenInfo.name ? `Nom: ${tokenInfo.name}` : 'Nom: —'}</Mono>
                    <Mono>
                      Acces: entreprises {tokenInfo.permissions?.entreprises ? 'oui' : 'non'}, emails {tokenInfo.permissions?.emails ? 'oui' : 'non'}, stats{' '}
                      {tokenInfo.permissions?.statistics ? 'oui' : 'non'}, campagnes {tokenInfo.permissions?.campagnes ? 'oui' : 'non'}
                    </Mono>
                    {!!tokenInfo.last_used && <Mono>Derniere utilisation: {tokenInfo.last_used}</Mono>}
                  </>
                )}
              </View>
            )}

            <MutedText style={{ marginTop: 12 }}>Photographier la clé (OCR en direct)</MutedText>
            <MutedText style={{ marginTop: 4 }}>
              Vue plein écran : cadre le texte ou le QR, puis confirme le jeton détecté en bas de l’écran.
            </MutedText>
            <View style={[styles.row, { marginTop: 8 }]}>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  title={ocrBusy ? 'Ouverture…' : 'Ouvrir la caméra'}
                  onPress={openLiveOcrScanner}
                  disabled={ocrBusy}
                />
              </View>
            </View>

            <MutedText style={{ marginTop: 12 }}>Nouveau token</MutedText>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Colle ton token ici"
              placeholderTextColor={t.colors.muted}
              selectionColor={t.colors.primary}
              autoCapitalize="none"
              autoCorrect={false}
              style={[
                styles.input,
                {
                  borderColor: t.colors.border,
                  color: t.colors.text,
                  backgroundColor: t.colors.bg,
                },
              ]}
            />
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  title="Enregistrer"
                  onPress={async () => {
                    const t = draft.trim();
                    if (!t) return;
                    await save(t);
                    setDraft('');
                    Alert.alert('OK', 'Token enregistre.');
                  }}
                />
              </View>
              <View style={{ width: 10 }} />
              <View style={{ flex: 1 }}>
                <DangerButton
                  title="Supprimer"
                  onPress={async () => {
                    await clear();
                    Alert.alert('OK', 'Token supprime.');
                  }}
                />
              </View>
            </View>
          </Card>
        </FadeIn>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 },
  row: { flexDirection: 'row', marginTop: 12, alignItems: 'center' },
  rowIcon: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
});

