import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

type RgbColor = {
  red: number;
  green: number;
  blue: number;
};

const stylesheet = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

const readLightToken = (name: string) => {
  const lightTheme = stylesheet.match(/:root\s*\{([\s\S]*?)\n\s*\}/)?.[1] || '';
  const token = lightTheme.match(new RegExp(`--${name}:\\s*([^;]+);`))?.[1]?.trim();
  if (!token) throw new Error(`Missing light theme token: ${name}`);
  const [hue, saturation, lightness] = token.split(/\s+/).map((value) => Number.parseFloat(value));
  if (![hue, saturation, lightness].every(Number.isFinite)) {
    throw new Error(`Invalid HSL token: ${name}`);
  }
  return { hue, saturation, lightness };
};

const hslToRgb = (hue: number, saturation: number, lightness: number): RgbColor => {
  const normalizedSaturation = saturation / 100;
  const normalizedLightness = lightness / 100;
  const chroma = (1 - Math.abs(2 * normalizedLightness - 1)) * normalizedSaturation;
  const hueSection = ((hue % 360) + 360) % 360 / 60;
  const intermediate = chroma * (1 - Math.abs((hueSection % 2) - 1));
  let red = 0;
  let green = 0;
  let blue = 0;

  if (hueSection < 1) [red, green] = [chroma, intermediate];
  else if (hueSection < 2) [red, green] = [intermediate, chroma];
  else if (hueSection < 3) [green, blue] = [chroma, intermediate];
  else if (hueSection < 4) [green, blue] = [intermediate, chroma];
  else if (hueSection < 5) [red, blue] = [intermediate, chroma];
  else [red, blue] = [chroma, intermediate];

  const offset = normalizedLightness - chroma / 2;
  return {
    red: red + offset,
    green: green + offset,
    blue: blue + offset,
  };
};

const relativeLuminance = (color: RgbColor) => {
  const linearize = (channel: number) => (
    channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4
  );
  return (
    0.2126 * linearize(color.red)
    + 0.7152 * linearize(color.green)
    + 0.0722 * linearize(color.blue)
  );
};

const contrastRatio = (foregroundToken: string, backgroundToken: string) => {
  const foreground = readLightToken(foregroundToken);
  const background = readLightToken(backgroundToken);
  const foregroundLuminance = relativeLuminance(hslToRgb(foreground.hue, foreground.saturation, foreground.lightness));
  const backgroundLuminance = relativeLuminance(hslToRgb(background.hue, background.saturation, background.lightness));
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
    / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
};

describe('dashboard accessibility tokens', () => {
  it.each([
    ['primary-foreground', 'primary'],
    ['accent-foreground', 'accent'],
    ['muted-foreground', 'muted'],
    ['success-foreground', 'success'],
  ])('%s on %s meets WCAG AA for normal text', (foreground, background) => {
    expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
  });
});
