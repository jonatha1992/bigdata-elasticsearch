import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Every /api request is proxied to the FastAPI service and the prefix is
// stripped, so the browser only ever talks to one origin. That sidesteps CORS
// entirely in development and mirrors how a reverse proxy would serve both in
// production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
