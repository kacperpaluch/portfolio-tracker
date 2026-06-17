import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// W trybie dev /api jest proxowane na backend FastAPI (port 8000).
// W produkcji frontend jest serwowany przez FastAPI z tego samego origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
