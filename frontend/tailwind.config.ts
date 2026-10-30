import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: { colors: { act: "#1d4ed8", drop: "#dc2626", ok: "#16a34a" } } },
  plugins: [],
};
export default config;
