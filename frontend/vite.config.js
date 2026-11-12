import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    watch: { usePolling: true },
    proxy: {
      // All /api/* calls go to the FastAPI backend.
      // Running locally with `npm run dev`, that is localhost. Inside Docker
      // Compose it is the `backend` service hostname, which compose supplies
      // via BACKEND_URL.
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
