import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  base: "/static/dashboard/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../robopipe_api/static/dashboard",
    emptyOutDir: true,
  },
});
