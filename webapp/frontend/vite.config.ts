import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    // /api → FastAPI. docker-compose·README는 8088 기준. 로컬 백을 18088에 띄우면 아래만 바꾸면 됩니다.
    proxy: {
      "/api": "http://127.0.0.1:8088",
    },
  },
});
