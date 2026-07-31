import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// W trybie dev /api jest proxowane na backend FastAPI (port 8000).
// W produkcji frontend jest serwowany przez FastAPI z tego samego origin.
const apiTarget = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": apiTarget,
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom"],
          charts: ["recharts"],
        },
      },
    },
  },
});
