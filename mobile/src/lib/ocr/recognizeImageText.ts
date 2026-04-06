export async function recognizeImageText(_uri: string): Promise<string> {
  throw new Error("L'OCR n'est disponible que sur l'appareil (Android / iOS), pas sur le web.");
}
