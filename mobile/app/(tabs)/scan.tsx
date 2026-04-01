import * as ImagePicker from 'expo-image-picker';
import { useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { FontAwesome6, MaterialCommunityIcons } from '@expo/vector-icons';
import { ProspectLabApi } from '../../src/features/prospectlab/prospectLabApi';
import { useApiToken } from '../../src/features/prospectlab/useToken';
import { extractSignals } from '../../src/lib/parsing/extractSignals';
import { Card, FadeIn, H1, H2, Mono, Muted, PrimaryButton, Screen } from '../../src/ui/components';
import { useTheme } from '../../src/ui/theme';

export default function ScanScreen() {
  const t = useTheme();
  const { token } = useApiToken();
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [rawText, setRawText] = useState('');
  const [busy, setBusy] = useState(false);
  const [lookupResult, setLookupResult] = useState<any>(null);

  const signals = useMemo(() => extractSignals(rawText), [rawText]);

  async function pickImage() {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    if (!res.canceled) {
      setImageUri(res.assets[0]?.uri ?? null);
    }
  }

  async function lookup() {
    if (!token) {
      Alert.alert('Token manquant', 'Va dans Reglages pour coller ton token API.');
      return;
    }

    setBusy(true);
    setLookupResult(null);
    try {
      const website = signals.websites[0];
      const email = signals.emails[0];
      const phone = signals.phones[0];

      if (website) {
        try {
          const found = await ProspectLabApi.findEntrepriseByWebsite(token, website, { skipCache: true });
          setLookupResult({ kind: 'by-website', found });
          return;
        } catch {
          const launched = await ProspectLabApi.launchWebsiteAnalysis(token, website, false);
          setLookupResult({ kind: 'website-analysis-launched', launched });
          return;
        }
      }

      if (email) {
        const found = await ProspectLabApi.findEntrepriseByEmail(token, email, true, { skipCache: true });
        setLookupResult({ kind: 'by-email', found });
        return;
      }

      if (phone) {
        const found = await ProspectLabApi.findEntrepriseByPhone(token, phone, true, { skipCache: true });
        setLookupResult({ kind: 'by-phone', found });
        return;
      }

      Alert.alert('Rien a chercher', 'Ajoute du texte OCR, ou colle au moins un email / tel / website.');
    } catch (e: any) {
      Alert.alert('Erreur', e?.message ?? 'Erreur');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.container}>
        <H1>Scan (OCR)</H1>

        <FadeIn>
          <Card>
            <View style={styles.row}>
              <MaterialCommunityIcons name="image-outline" size={16} color="#4f8cff" />
              <H2>Image</H2>
            </View>
            <View style={{ marginTop: 10 }}>
              <PrimaryButton title="Choisir une image" onPress={pickImage} />
            </View>
            <Muted>{imageUri ? imageUri : "Aucune image. (MVP: OCR manuel via texte)"}</Muted>
          </Card>
        </FadeIn>

        <FadeIn delayMs={60}>
          <Card>
            <View style={styles.row}>
              <MaterialCommunityIcons name="text-recognition" size={16} color="#4f8cff" />
              <H2>Texte OCR (manuel pour l'instant)</H2>
            </View>
            <TextInput
              value={rawText}
              onChangeText={setRawText}
              placeholder="Colle ici le texte OCR ou le texte de la carte..."
              placeholderTextColor={t.colors.muted}
              selectionColor={t.colors.primary}
              multiline
              style={[
                styles.textarea,
                {
                  borderColor: t.colors.border,
                  color: t.colors.text,
                  backgroundColor: t.colors.bg,
                },
              ]}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={{ marginTop: 10 }}>
              <PrimaryButton title={busy ? 'Recherche...' : 'Rechercher dans ProspectLab'} onPress={lookup} disabled={busy} />
            </View>
          </Card>
        </FadeIn>

        <FadeIn delayMs={120}>
          <Card>
            <View style={styles.row}>
              <MaterialCommunityIcons name="filter-outline" size={16} color="#4f8cff" />
              <H2>Extraction</H2>
            </View>
            <View style={styles.row}>
              <FontAwesome6 name="envelope" size={12} color="#4f8cff" />
              <Muted>Emails: {signals.emails.length ? signals.emails.join(', ') : '-'}</Muted>
            </View>
            <View style={styles.row}>
              <FontAwesome6 name="phone" size={12} color="#4f8cff" />
              <Muted>Telephones: {signals.phones.length ? signals.phones.join(', ') : '-'}</Muted>
            </View>
            <View style={styles.row}>
              <FontAwesome6 name="globe" size={12} color="#4f8cff" />
              <Muted>Websites: {signals.websites.length ? signals.websites.join(', ') : '-'}</Muted>
            </View>
          </Card>
        </FadeIn>

        {!!lookupResult && (
          <FadeIn delayMs={180}>
            <Card>
              <H2>Resultat</H2>
              <Mono>{JSON.stringify(lookupResult, null, 2)}</Mono>
            </Card>
          </FadeIn>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  textarea: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 10,
    minHeight: 140,
    textAlignVertical: 'top',
    marginTop: 10,
  },
});

