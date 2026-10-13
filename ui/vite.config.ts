import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The game server (server.py) must be running for `npm run dev`. Override its
// address with GAME_SERVER, e.g. GAME_SERVER=http://127.0.0.1:8877 npm run dev
const gameServer = process.env.GAME_SERVER ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'admin-route',
      configureServer(server) {
        // server.py serves the editor at /admin; mirror that in development.
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/admin' || req.url?.startsWith('/admin?')) req.url = '/admin.html'
          next()
        })
      },
    },
  ],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  build: {
    // The built game ships in ../static so players only need Python.
    outDir: path.resolve(import.meta.dirname, '../static'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: path.resolve(import.meta.dirname, 'index.html'),
        admin: path.resolve(import.meta.dirname, 'admin.html'),
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: gameServer,
        changeOrigin: true,
        configure(proxy) {
          // server.py only accepts its own origin on POST requests.
          proxy.on('proxyReq', (request) => request.setHeader('origin', gameServer))
        },
      },
    },
  },
})
