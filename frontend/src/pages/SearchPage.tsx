import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Search, X, ArrowUpDown, ChevronDown, FileText, Loader2, Download, CheckSquare, Square, HelpCircle, Layers, List, FileDown } from 'lucide-react'
import { search as apiSearch, suggest as apiSuggest } from '../api/client'
import type { SearchResponse, Hit } from '../api/client'
import { SearchSkeleton } from '../components/Skeleton'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [selectedHit, setSelectedHit] = useState<Hit | null>(null)
  const [preview, setPreview] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [sort, setSort] = useState('score')
  const [sortOrder, setSortOrder] = useState('desc')
  const [showSort, setShowSort] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'file'>('list')
  const [showHelp, setShowHelp] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Pre-compute file-grouped items for file view
  const fileGrouped = useMemo(() => {
    if (!results || viewMode !== 'file') return []
    const grouped = new Map<string, { hit: Hit; count: number; snippets: string[] }>()
    for (const hit of results.hits) {
      const key = hit.path
      if (grouped.has(key)) {
        const g = grouped.get(key)!
        g.count++
        if (hit.snippet) g.snippets.push(hit.snippet)
      } else {
        grouped.set(key, { hit, count: 1, snippets: hit.snippet ? [hit.snippet] : [] })
      }
    }
    return Array.from(grouped.values())
  }, [results, viewMode])

  useEffect(() => { inputRef.current?.focus() }, [])

  const doSearch = useCallback(async (q: string, page = 1) => {
    if (!q.trim()) return
    setLoading(true)
    setError(null)
    setSelectedIds(new Set())
    try {
      const res = await apiSearch(q, { page, sort, order: sortOrder })
      setResults(res)
      setSuggestions([])
    } catch (e) {
      setError(e instanceof Error ? e.message : '搜索失败')
    } finally {
      setLoading(false)
    }
  }, [sort, sortOrder])

  const handleInput = useCallback((value: string) => {
    setQuery(value)
    clearTimeout(debounceRef.current)
    if (value.trim().length >= 1) {
      debounceRef.current = setTimeout(async () => {
        try {
          const res = await apiSuggest(value)
          setSuggestions(res.suggestions)
        } catch { setSuggestions([]) }
      }, 200)
    } else {
      setSuggestions([])
    }
  }, [])

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (!results) return
    if (selectedIds.size === results.hits.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(results.hits.map(h => h.id)))
    }
  }

  const handleDownloadSelected = async () => {
    if (selectedIds.size === 0) return
    setDownloading(true)
    try {
      const res = await fetch('/api/file/batch-download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': localStorage.getItem('auth_token') ? `Bearer ${localStorage.getItem('auth_token')}` : '' },
        body: JSON.stringify({ file_ids: Array.from(selectedIds) }),
      })
      if (!res.ok) throw new Error('Download failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'search-results.zip'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : '下载失败')
    } finally {
      setDownloading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setSuggestions([])
      doSearch(query)
    }
    if (e.key === 'Escape') {
      setSelectedHit(null)
      setPreview('')
    }
    if (e.key === 'ArrowDown' && results?.hits.length) {
      const idx = results.hits.findIndex(h => h.id === selectedHit?.id)
      const next = results.hits[Math.min(idx + 1, results.hits.length - 1)]
      if (next) showPreview(next)
    }
    if (e.key === 'ArrowUp' && results?.hits.length) {
      const idx = results.hits.findIndex(h => h.id === selectedHit?.id)
      const prev = results.hits[Math.max(idx - 1, 0)]
      if (prev) showPreview(prev)
    }
  }

  const showPreview = async (hit: Hit) => {
    setSelectedHit(hit)
    setPreview('加载中...')
    try {
      const { getPreview } = await import('../api/client')
      const p = await getPreview(hit.id)
      setPreview(p.content || '(无内容)')
    } catch {
      setPreview('加载失败')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="p-6 pb-4">
        <div className="relative max-w-2xl">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索文件内容... 支持 AND / OR / &quot;精确短语&quot; / -排除"
            className="w-full pl-12 pr-12 py-3.5 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-lg transition-all"
          />
          {query && (
            <button onClick={() => { setQuery(''); setResults(null); setSuggestions([]); setSelectedIds(new Set()) }}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          )}
          {suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10">
              {suggestions.map((s, i) => (
                <button key={i} onClick={() => { setQuery(s); setSuggestions([]); doSearch(s) }}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800">
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-auto px-6">
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm mb-4">{error}</div>
          )}
          {loading && (
            <div className="py-4"><SearchSkeleton count={5} /></div>
          )}
          {results && !loading && (
            <div className="contents">
              {/* Toolbar */}
              <div className="flex items-center justify-between mb-4 text-sm text-gray-500">
                <div className="flex items-center gap-3">
                  <button onClick={toggleSelectAll} className="flex items-center gap-1.5 hover:text-gray-700 dark:hover:text-gray-300">
                    {results.hits.length > 0 && selectedIds.size === results.hits.length
                      ? <CheckSquare className="w-4 h-4" />
                      : <Square className="w-4 h-4" />
                    }
                    全选
                  </button>
                  <span>找到 {results.total} 个结果 (用时 {results.took_ms}ms)</span>
                  {selectedIds.size > 0 && (
                    <span className="text-blue-600 font-medium">{selectedIds.size} 项已选</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {selectedIds.size > 0 && (
                    <button onClick={handleDownloadSelected} disabled={downloading}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
                      <Download className="w-3.5 h-3.5" />
                      {downloading ? '打包中...' : `下载选中 (${selectedIds.size})`}
                    </button>
                  )}
                  <button onClick={() => window.open(`/api/search/export?q=${encodeURIComponent(query)}`, '_blank')}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
                    <FileDown className="w-3.5 h-3.5" />
                    导出 CSV
                  </button>
                  <div className="flex items-center border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    <button onClick={() => setViewMode('list')}
                      className={`p-1.5 ${viewMode === 'list' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                      title="逐条视图">
                      <List className="w-4 h-4" />
                    </button>
                    <button onClick={() => setViewMode('file')}
                      className={`p-1.5 ${viewMode === 'file' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                      title="按文件视图">
                      <Layers className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="relative">
                    <button onClick={() => setShowSort(!showSort)}
                      className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
                      <ArrowUpDown className="w-3 h-3" />
                      {sort === 'score' ? '相关度' : sort === 'date' ? '修改日期' : sort === 'size' ? '文件大小' : sort === 'name' ? '文件名' : '类型'}
                      <ChevronDown className="w-3 h-3" />
                    </button>
                    {showSort && (
                      <div className="relative">
                        <div className="fixed inset-0 z-10" onClick={() => setShowSort(false)} />
                        <div className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-20 py-1 w-36">
                          {[
                            { value: 'score', label: '相关度' },
                            { value: 'date', label: '修改日期' },
                            { value: 'size', label: '文件大小' },
                            { value: 'name', label: '文件名' },
                            { value: 'type', label: '文件类型' },
                          ].map(opt => (
                            <button key={opt.value}
                              onClick={() => {
                                const newOrder = opt.value === sort && sortOrder === 'desc' ? 'asc' : 'desc'
                                setSort(opt.value)
                                setSortOrder(newOrder)
                                setShowSort(false)
                                if (query) doSearch(query)
                              }}
                              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                sort === opt.value ? 'text-blue-600 font-medium' : 'text-gray-700 dark:text-gray-300'
                              }`}>
                              {opt.label}
                              {sort === opt.value && (
                                <span className="ml-1 text-xs">{sortOrder === 'desc' ? '↓' : '↑'}</span>
                              )}
                            </button>
                          ))}
                        </div>
                      </div>)}
                    </div>
                    <button onClick={() => setShowHelp(true)}
                    className="p-1.5 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                    title="搜索语法帮助">
                    <HelpCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Result list */}
              <div className="space-y-3">
                {viewMode === 'file' && fileGrouped.map(item => 
                      <div key={item.hit.id}
                        className={`p-4 bg-white dark:bg-gray-900 border rounded-lg cursor-pointer transition-all hover:shadow-md ${
                          selectedHit?.id === item.hit.id ? 'border-blue-400 dark:border-blue-500 shadow-sm' : 'border-gray-200 dark:border-gray-800'
                        }`}
                        onClick={() => showPreview(item.hit)}>
                        <div className="flex items-start gap-3">
                          <button onClick={e => { e.stopPropagation(); toggleSelect(item.hit.id) }}
                            className="mt-1 text-gray-400 hover:text-blue-600 shrink-0">
                            {selectedIds.has(item.hit.id) ? <CheckSquare className="w-4 h-4 text-blue-600" /> : <Square className="w-4 h-4" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                              <span className="font-medium text-blue-700 dark:text-blue-400 truncate">{item.hit.filename}</span>
                              <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-500">{item.hit.extension}</span>
                              <span className="text-xs text-gray-400 ml-auto">{item.hit.modified?.split('T')[0]}</span>
                            </div>
                            <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                              <span className="truncate">{item.hit.path}</span>
                              <span>{item.item.hit.size > 0 ? (item.item.hit.size / 1024).toFixed(0) + 'KB' : ''}</span>
                              <span className="text-blue-600">{item.count} 处匹配</span>
                            </div>
                            {item.snippets.slice(0, 2).map((s, i) => (
                              <p key={i} className="text-sm mt-1 text-gray-700 dark:text-gray-300 line-clamp-1"
                                dangerouslySetInnerHTML={{ __html: s }} />
                            ))}
                            {item.snippets.length > 2 && (
                              <p className="text-xs text-gray-400 mt-1">还有 {item.snippets.length - 2} 处匹配... 点击查看更多</p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                {viewMode !== 'file' && results.hits.map(hit => (
                  <div
                    key={hit.id}
                    className={`p-4 bg-white dark:bg-gray-900 border rounded-lg transition-all hover:shadow-md ${
                      selectedHit?.id === hit.id
                        ? 'border-blue-400 dark:border-blue-500 shadow-sm'
                        : 'border-gray-200 dark:border-gray-800'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <button onClick={e => { e.stopPropagation(); toggleSelect(hit.id) }}
                        className="mt-1 text-gray-400 hover:text-blue-600 shrink-0">
                        {selectedIds.has(hit.id)
                          ? <CheckSquare className="w-4 h-4 text-blue-600" />
                          : <Square className="w-4 h-4" />
                        }
                      </button>
                      <div onClick={() => showPreview(hit)} className="min-w-0 flex-1 cursor-pointer">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                          <span className="font-medium text-blue-700 dark:text-blue-400 truncate">{hit.filename}</span>
                          <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-500">{hit.extension}</span>
                          <span className="text-xs text-gray-400 ml-auto">{hit.modified?.split('T')[0]}</span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">{hit.path}</p>
                        <p className="text-sm mt-1.5 text-gray-700 dark:text-gray-300 line-clamp-2"
                          dangerouslySetInnerHTML={{ __html: hit.snippet }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {results.total > results.size && (
                <div className="flex items-center justify-center gap-2 py-6">
                  {Array.from({ length: Math.ceil(results.total / results.size) }, (_, i) => (
                    <button
                      key={i}
                      onClick={() => doSearch(query, i + 1)}
                      className={`px-3 py-1.5 text-sm rounded-lg ${
                        results.page === i + 1
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
                      }`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
{!results && !loading && !error && (
            <div className="flex flex-col items-center justify-center py-32 text-gray-400">
              <Search className="w-16 h-16 mb-4 opacity-30" />
              <p className="text-lg">输入关键词开始搜索</p>
              <p className="text-sm mt-1">支持 AND / OR / &quot;精确短语&quot; / -排除 语法</p>
            </div>
          )}
          {results && results.total === 0 && !loading && (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <FileText className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-base">没有找到匹配的文件</p>
              <p className="text-sm mt-1">试试其他关键词，或检查排除模式设置</p>
            </div>
          )}
        </div>

        {/* Preview panel */}
        {selectedHit && (
          <div className="w-96 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-auto p-4 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-sm truncate">{selectedHit.filename}</h3>
              <button onClick={() => { setSelectedHit(null); setPreview('') }}
                className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3 break-all">{selectedHit.path}</p>
            <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
              {preview === '加载中...' ? (
                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              ) : (
                <>{preview || '(无文字内容)'}</>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Help modal */}
      {showHelp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowHelp(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-800 p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium">搜索语法</h3>
              <button onClick={() => setShowHelp(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3 text-sm text-gray-600 dark:text-gray-400">
              <div><code className="text-blue-600 font-mono">关键词1 关键词2</code> — 默认 AND 匹配，同时包含两个词</div>
              <div><code className="text-blue-600 font-mono">"精确短语"</code> — 精确匹配完整短语</div>
              <div><code className="text-blue-600 font-mono">A AND B</code> — 同时包含 A 和 B</div>
              <div><code className="text-blue-600 font-mono">A OR B</code> — 包含 A 或 B</div>
              <div><code className="text-blue-600 font-mono">A -B</code> — 包含 A 但不包含 B</div>
              <div><code className="text-blue-600 font-mono">A ~</code> — 模糊搜索（拼写容错）</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
