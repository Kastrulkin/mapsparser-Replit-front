import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path"; // ← обязательно добавьте этот импорт!

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 8080, // или 3000, если нужно
    allowedHosts: [
      "localhost",
      "127.0.0.1",
      "6463ac8a-2c20-46f2-bae0-11bc92991339-00-1uzunkaw6b2ub.riker.replit.dev",
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // ← вот это добавьте!
    },
  },
});