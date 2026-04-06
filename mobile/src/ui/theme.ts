import { useColorScheme } from 'react-native';

export type AppTheme = {
  isDark: boolean;
  colors: {
    bg: string;
    card: string;
    text: string;
    muted: string;
    border: string;
    primary: string;
    primaryText: string;
    danger: string;
    success: string;
    warning: string;
  };
  radii: {
    card: number;
    pill: number;
  };
  spacing: {
    s: number;
    m: number;
    l: number;
  };
};

export function useTheme(): AppTheme {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  return {
    isDark,
    colors: isDark
      ? {
          bg: '#0b0f14',
          card: '#121925',
          text: '#eaf0ff',
          muted: '#a9b4c7',
          border: 'rgba(255,255,255,0.10)',
          primary: '#4f8cff',
          primaryText: '#081425',
          danger: '#ff5a6a',
          success: '#3ddc97',
          warning: '#ffcc66',
        }
      : {
          bg: '#f6f7fb',
          card: '#ffffff',
          text: '#101828',
          muted: '#475467',
          border: 'rgba(16,24,40,0.10)',
          primary: '#2e6bff',
          primaryText: '#ffffff',
          danger: '#d92d20',
          success: '#12b76a',
          warning: '#f79009',
        },
    radii: { card: 16, pill: 999 },
    spacing: { s: 10, m: 16, l: 22 },
  };
}

