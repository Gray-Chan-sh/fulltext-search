import { useState, useCallback } from 'react'
import { search as apiSearch, suggest as apiSuggest } from '../api/client'
import type { IndexStatus as IndexStatusType, SearchResponse } from '../api/client'

export function useSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const doSearch = useCallback(async (q: string, opts?: { page?: number }) => {
    if (!q.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiSearch(q, { page: opts?.page })
      setResults(res)
      setQuery(q)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }, [])

  const doSuggest = useCallback(async (q: string) => {
    if (!q.trim()) {
      setSuggestions([])
      return
    }
    try {
      const res = await apiSuggest(q)
      setSuggestions(res.suggestions)
    } catch {
      setSuggestions([])
    }
  }, [])

  return { query, setQuery, results, loading, error, suggestions, doSearch, doSuggest, setResults }
}

export function useIndexStatus() {
  const [status, setStatus] = useState<IndexStatusType | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const { getIndexStatus } = await import('../api/client')
      const s = await getIndexStatus()
      setStatus(s)
    } finally {
      setLoading(false)
    }
  }, [])

  return { status, loading, refresh }
}
