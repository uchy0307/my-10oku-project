import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Tasks",
        short_name: "Tasks",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        orientation: "portrait",
        start_url: "./",
        scope: "./",
        icons: [{ src: "favicon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }]
      },
      workbox: {
        runtimeCaching: [
          { urlPattern: /^https:\/\/note\.com\/api\/.*/, handler: "NetworkFirst", options: { cacheName: "note-api", networkTimeoutSeconds: 8 } },
          { urlPattern: /^https:\/\/www\.youtube\.com\/feeds\/.*/, handler: "NetworkFirst", options: { cacheName: "yt-rss", networkTimeoutSeconds: 8 } }
        ]
      }
    })
  ],
  build: { target: "es2020", sourcemap: false }
});
