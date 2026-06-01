import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The BFF dev target (WS-5-BFF). Overridable via VITE_BFF_URL; the client uses a
// relative base so these dev-proxy routes forward /v1 + /health to the FastAPI BFF.
const BFF_TARGET = process.env.VITE_BFF_URL || "http://localhost:8787";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/v1": { target: BFF_TARGET, changeOrigin: true },
      "/health": { target: BFF_TARGET, changeOrigin: true },
    },
  },
});
