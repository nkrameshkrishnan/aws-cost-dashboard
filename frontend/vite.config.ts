import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
    // Base path for GitHub Pages project site (username.github.io/<repo>/)
    // Set to the repository name so assets are referenced under /aws-cost-dashboard/
    base: '/aws-cost-dashboard/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Optimize bundle size
    target: 'esnext',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.logs in production
        drop_debugger: true,
      },
    },
    // Chunk splitting strategy for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React libraries
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],

          // Data fetching and state management
          'query-vendor': ['@tanstack/react-query', 'axios'],

          // Chart library (heavy)
          'charts': ['recharts'],

          // UI components and styling
          'ui-vendor': ['lucide-react', 'date-fns'],

          // Dashboard page (frequently accessed)
          'dashboard': [
            './src/pages/Dashboard',
            './src/components/dashboard/KPICard',
            './src/components/dashboard/CostTrendChart',
            './src/components/dashboard/ServiceBreakdownPie',
          ],

          // Audit page (large, less frequently accessed)
          'finops': ['./src/pages/FinOpsAudit'],

          // Analytics (heavy computations)
          'analytics': ['./src/pages/Analytics'],
        },
        // Naming pattern for chunks
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
    // Increase chunk size warning limit (default is 500kb)
    chunkSizeWarningLimit: 1000,
    // Enable CSS code splitting
    cssCodeSplit: true,
    // Source maps for production debugging (optional, increases size)
    sourcemap: false,
  },
  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@tanstack/react-query',
      'axios',
      'recharts',
      'lucide-react',
      'date-fns',
    ],
  },
})
