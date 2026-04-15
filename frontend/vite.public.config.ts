import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  base: "/public-audit/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: "public-dist",
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "public-audit/index.html"),
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            return "vendor";
          }

          return undefined;
        },
      },
    },
  },
});
