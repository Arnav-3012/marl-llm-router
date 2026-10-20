import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// BASE_PATH lets the same build run at the root or under /<repo>/ on GitHub Pages.
export default defineConfig({
  base: process.env.BASE_PATH ?? "./",
  plugins: [react()],
  build: { target: "es2020", chunkSizeWarningLimit: 400 },
});
