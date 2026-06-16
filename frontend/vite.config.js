import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Built assets are served by Flask from /static/wireframe-app/, and the
// Flask route /wireframe-app renders the built index.html shell.
export default defineConfig({
  plugins: [react()],
  base: '/static/wireframe-app/',
  build: {
    outDir: '../static/wireframe-app',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
