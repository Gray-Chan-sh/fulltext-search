export interface Hit {
  id: string
  filename: string
  path: string
  dir_id: string
  dir_name: string
  snippet: string
  modified: string
  size: number
  extension: string
  score: number
}

export interface SearchFacets {
  types: Record<string, number>
  dirs: Record<string, { name: string; count: number }>
}

export interface SearchResponse {
  total: number
  page: number
  size: number
  took_ms: number
  hits: Hit[]
  facets: SearchFacets
}

export interface SuggestResponse {
  suggestions: string[]
  took_ms: number
}

export interface DirConfig {
  id: string
  path: string
  alias: string
  ocr_lang: string
  exclude_patterns: string
  include_exts: string
  file_count: number
  indexed_count: number
  failed_count: number
  processing_count: number
  status: string
}

export interface IndexStatus {
  total_files: number
  indexed: number
  pending: number
  failed: number
  scanner_status: string
  progress_percent: number
  last_full_scan: string
  next_scheduled_scan: string
}

const BASE = '/api'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function authFetch(url: string, opts: RequestInit = {}): Promise<Response> {
  const headers = { ...opts.headers, ...authHeaders() } as Record<string, string>
  return fetch(url, { ...opts, headers })
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) url.searchParams.set(k, v)
    }
  }
  const res = await authFetch(url.toString())
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
  return res.json()
}

export async function search(
  q: string,
  opts?: { dir_ids?: string; types?: string; page?: number; size?: number; sort?: string; order?: string },
): Promise<SearchResponse> {
  return get<SearchResponse>('/search', {
    q,
    dir_ids: opts?.dir_ids ?? '',
    types: opts?.types ?? '',
    page: String(opts?.page ?? 1),
    size: String(opts?.size ?? 20),
    sort: opts?.sort ?? 'score',
    order: opts?.order ?? 'desc',
  })
}

export async function suggest(q: string): Promise<SuggestResponse> {
  return get<SuggestResponse>('/suggest', { q })
}

export async function getDirs(): Promise<{ dirs: DirConfig[] }> {
  return get<{ dirs: DirConfig[] }>('/dirs')
}

export async function addDir(data: {
  path: string
  alias?: string
  ocr_lang?: string
  exclude_patterns?: string
  include_exts?: string
}): Promise<{ id: string }> {
  const res = await authFetch(`${BASE}/dirs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteDir(id: string): Promise<void> {
  await fetch(`${BASE}/dirs/${id}`, { method: 'DELETE' })
}

export async function getIndexStatus(): Promise<IndexStatus> {
  return get<IndexStatus>('/index/status')
}

export async function triggerScan(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/index/trigger`, { method: 'POST' })
  return res.json()
}

export async function getPreview(id: string): Promise<{ id: string; content: string; char_count: number; ocr_used: boolean; pages: number }> {
  return get<{ id: string; content: string; char_count: number; ocr_used: boolean; pages: number }>(`/file/${id}/preview`)
}

export async function getDownloadUrl(id: string): Promise<string> {
  return `${BASE}/file/${id}/download`
}

export async function getContent(id: string): Promise<{ id: string; content: string; char_count: number; ocr_used: boolean }> {
  return get<{ id: string; content: string; char_count: number; ocr_used: boolean }>(`/file/${id}/content`)
}

export async function getHistory(): Promise<{ history: Array<{ id: string; query: string; result_count: number; pinned: boolean; created_at: string }> }> {
  return get('/history')
}

export async function pinResult(historyId: string): Promise<void> {
  await fetch(`${BASE}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history_id: historyId }),
  })
}

export async function deleteHistory(id: string): Promise<void> {
  await fetch(`${BASE}/history/${id}`, { method: 'DELETE' })
}
