import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8765';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: backendUrl,
        ws: true,
      },
      '/auth': { target: backendUrl },
      '/journal': { target: backendUrl },
    },
  },
});
