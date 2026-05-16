import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    // /api 호출은 FastAPI(18088)로 프록시 — CORS 우회. Windows에서 8088이
    // 자주 reserved/blocked 되므로 18088 사용.
    proxy: {
      "/api": "http://127.0.0.1:18088",
    },
  },
});
