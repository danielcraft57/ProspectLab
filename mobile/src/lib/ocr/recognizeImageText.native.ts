import * as FileSystem from 'expo-file-system/legacy';
import { Platform } from 'react-native';
import TextRecognition from '@react-native-ml-kit/text-recognition';

export async function recognizeImageText(uri: string): Promise<string> {
  let inputUri = uri;
  if (Platform.OS === 'android' && uri.startsWith('content://')) {
    const base = FileSystem.cacheDirectory;
    if (!base) throw new Error('Cache indisponible');
    const dest = `${base}pl-ocr-${Date.now()}.jpg`;
    await FileSystem.copyAsync({ from: uri, to: dest });
    inputUri = dest;
  }
  const result = await TextRecognition.recognize(inputUri);
  return (result.text ?? '').trim();
}
