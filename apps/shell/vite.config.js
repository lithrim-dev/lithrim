/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The BFF dev target (WS-5-BFF). Overridable via VITE_BFF_URL; the client uses a
// relative base so these dev-proxy routes forward /v1 + /health to the FastAPI BFF.
const BFF_TARGET = process.env.VITE_BFF_URL || "http://localhost:8787";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    proxy: {
      "/v1": { target: BFF_TARGET, changeOrigin: true },
      "/health": { target: BFF_TARGET, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
    css: true,
  },
});
