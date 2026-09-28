import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE lets the recorded-demo build live under a sub-path (GitHub Pages: /claimlens/).
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
