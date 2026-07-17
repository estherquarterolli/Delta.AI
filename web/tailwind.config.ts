import type { Config } from "tailwindcss";

const config: Config = {
  // "media": segue o tema do sistema automaticamente, sem exigir um
  // seletor de tema manual (fora de escopo desta entrega) — modo escuro
  // nativo desde o início, não afterthought (ver CLAUDE.md).
  darkMode: "media",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Paleta neutra + acento único — evita "tela vermelha" em desvios
        // pequenos (ex.: pesar 200g a mais). Feedback emocional cuidadoso
        // (ver CLAUDE.md), não cores de alarme pra estados normais do produto.
        acento: {
          50: "#f0fdf6",
          100: "#dcfce9",
          500: "#16a34a",
          600: "#15803d",
          700: "#166534",
        },
      },
    },
  },
  plugins: [],
};

export default config;
