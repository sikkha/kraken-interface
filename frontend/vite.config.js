import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.VITE_DEV_HOST || "0.0.0.0",
    port: Number(process.env.VITE_DEV_PORT || 5173),
    proxy: {
      "/api": process.env.VITE_DEV_API_TARGET || "http://127.0.0.1:8002",
    },
  },
});
