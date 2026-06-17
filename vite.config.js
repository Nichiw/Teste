import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// A URL do gateway é injetada pelo deploy.sh após o minikube subir.
// Se estiver rodando sem kubernetes, use http://localhost:8080
const GATEWAY_URL = process.env.GATEWAY_URL || "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/auth":       { target: GATEWAY_URL, changeOrigin: true },
      "/recovery":   { target: GATEWAY_URL, changeOrigin: true },
      "/doctors":    { target: GATEWAY_URL, changeOrigin: true },
      "/scheduling": { target: GATEWAY_URL, changeOrigin: true },
    },
  },
});
