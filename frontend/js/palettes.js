/**
 * @module palettes
 * Paletas de color (inspiradas en cmocean/ColorBrewer) y utilidades de escala compartidas por el mapa
 * (canvas), la leyenda (degradado CSS) y Plotly. `norm()` convierte un valor a 0…1 en escala lineal o
 * logarítmica (clorofila); `colorAt()` interpola el color RGB en esa posición.
 */
export const PALETTES = {
  thermal: ["#0b1b4d", "#2a3a99", "#5a4ea2", "#8d5a96", "#c26b72", "#e98a4b", "#f8bd3b", "#f6f45a"],
  algae: ["#2a0f5e", "#26468c", "#1f7a9a", "#21a68a", "#5cc76b", "#b3dd4d", "#f5ea3c"],
  diverging: ["#1f4e9e", "#4f8ccc", "#a8cde6", "#f3f3f1", "#f5c3a6", "#e07254", "#b0202f"],
  diverging_green: ["#8c510a", "#c99a4b", "#efdcae", "#f4f4f2", "#b6e3d9", "#47a99f", "#0b625a"],
  deep: ["#d8f1f2", "#9fd6df", "#5fb2cc", "#3486b8", "#2a5a9e", "#283a7a", "#1d2050", "#0c0d26"],
  obis: ["#fde7d4", "#f9b98f", "#f2845f", "#d9534f", "#a6295a", "#6a1b62"],
  // Radar SAR: superficie amortiguada (posibles manchas), objetos brillantes (barcos/plataformas) y viento
  slick: ["#0b1d2e", "#18394f", "#2b5d6e", "#4f8a8b", "#a7b98a", "#e8c66a", "#f08a3c", "#c9302c"],
  bright: ["#10102a", "#2c1b55", "#5b2477", "#8f2e7a", "#c4406a", "#ec6b4f", "#fca85e", "#fde99a"],
  wind: ["#253494", "#2c7fb8", "#41b6c4", "#a1dab4", "#ffffcc", "#fecc5c", "#fd8d3c", "#e31a1c"],
};

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const RGB = Object.fromEntries(Object.entries(PALETTES).map(([k, v]) => [k, v.map(hexToRgb)]));

/** Posición normalizada 0..1 de un valor según rango y escala. */
export function norm(v, [lo, hi], scale = "linear") {
  if (scale === "log") {
    const a = Math.log10(lo), b = Math.log10(hi);
    return (Math.log10(Math.max(v, lo * 1e-3)) - a) / (b - a);
  }
  return (v - lo) / (hi - lo);
}

export function colorAt(palette, t) {
  const c = RGB[palette];
  const x = Math.min(1, Math.max(0, t)) * (c.length - 1);
  const i = Math.min(c.length - 2, Math.floor(x));
  const f = x - i;
  return [0, 1, 2].map((k) => Math.round(c[i][k] + (c[i + 1][k] - c[i][k]) * f));
}

export const cssGradient = (palette) => `linear-gradient(to right, ${PALETTES[palette].join(", ")})`;

/** Escala de Plotly a partir de una paleta. */
export const plotlyScale = (palette) => PALETTES[palette].map((c, i, a) => [i / (a.length - 1), c]);

/** Marcas de la leyenda. */
export function legendTicks([lo, hi], scale) {
  if (scale === "log") {
    const out = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
      for (const m of [1, 3]) { const v = m * 10 ** e; if (v >= lo * 0.999 && v <= hi * 1.001) out.push(v); }
    }
    return out;
  }
  const n = 4;
  return Array.from({ length: n + 1 }, (_, i) => lo + ((hi - lo) * i) / n);
}
