import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  root: ".",
  clearScreen: false,
  build: {
    outDir: "dist",
    target: "chrome120",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  worker: { format: "es" },
});
