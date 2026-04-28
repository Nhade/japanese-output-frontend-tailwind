/**
 * Build an API URL from a path.
 *
 * Handles three deployment shapes uniformly:
 *   - VITE_API_BASE_URL unset → ''           → '/api/foo' (dev proxy)
 *   - VITE_API_BASE_URL = ''  → ''           → '/api/foo' (dev proxy)
 *   - VITE_API_BASE_URL = 'https://api.example.com' → absolute URL
 *
 * The previous pattern `${import.meta.env.VITE_API_BASE_URL}/api/foo`
 * would render as 'undefined/api/foo' on a fresh checkout with no
 * .env.development, breaking auth on first run.
 */
const RAW = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const API_ORIGIN = RAW.replace(/\/+$/, '')

export function apiUrl(path: string): string {
  if (!path.startsWith('/')) path = '/' + path
  return `${API_ORIGIN}${path}`
}
