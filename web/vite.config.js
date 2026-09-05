import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Relative base so a static build works from any subdirectory, including a
  // GitHub Pages project path, without a rebuild.
  base: './',
  build: { chunkSizeWarningLimit: 1200 },
})
