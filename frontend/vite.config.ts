import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path"; // ← обязательно добавьте этот импорт!

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3001,
    allowedHosts: [
      "localhost",
      "127.0.0.1",
      "6463ac8a-2c20-46f2-bae0-11bc92991339-00-1uzunkaw6b2ub.riker.replit.dev",
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // ← вот это добавьте!
    },
  },
});