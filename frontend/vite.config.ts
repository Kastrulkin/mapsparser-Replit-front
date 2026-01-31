import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path"; // ← обязательно добавьте этот импорт!

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // ← вот это добавьте!
    },
  },
});