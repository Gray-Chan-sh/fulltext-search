import { useState, useEffect } from 'react'
import { FileText, Search, Filter, Download, Loader2, RefreshCw } from 'lucide-react'
import { getIndexStatus } from '../api/client'

interface LogEntry {
  id: number
  level: string
  source: string
  message: string
  file_path: string | null
  duration_ms: number | null
  created_at: number
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [level, setLevel] = useState('')
  const [source, setSource] = useState('')
  const [query, setQuery] = useState('')
  const [scanSummary, setScanSummary] = useState({ total: 0, indexed: 0, pending: 0, failed: 0 })
  const [processingFile, setProcessingFile] = useState('')
  const [processingProgress, setProcessingProgress] = useState('')

  const loadLogs = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (level) params.set('level', level)
      if (source) params.set('source', source)
      if (query) params.set('q', query)
      params.set('limit', '500')
      const res = await fetch(`/api/logs?${params}`)
      const data = await res.json()
      setLogs(data.logs)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const loadSummary = async () => {
    try {
      const res = await fetch('/api/index/status')
      const d = await res.json()
      setScanSummary({ total: d.total_files, indexed: d.indexed, pending: d.pending, failed: d.failed })
      setProcessingFile(d.processing_file || '')
      setProcessingProgress(d.processing_progress || '')
    } catch {}
  }

  useEffect(() => {
    loadLogs()
    loadSummary()
    const interval = setInterval(() => { loadLogs(); loadSummary() }, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => { loadLogs() }, [level, source, query])

  const handleExport = () => {
    const params = new URLSearchParams()
    if (level) params.set('level', level)
    if (source) params.set('source', source)
    if (query) params.set('q', query)
    window.open(`/api/logs/export?${params}`, '_blank')
  }

  const levelColors: Record<string, string> = {
    INFO: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20',
    WARNING: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20',
    ERROR: 'text-red-600 bg-red-50 dark:bg-red-900/20',
  }

  const sourceColors: Record<string, string> = {
    server: 'bg-gray-100 text-gray-600 dark:bg-gray-800',
    indexer: 'bg-blue-50 text-blue-600 dark:bg-blue-900/20',
    ocr: 'bg-purple-50 text-purple-600 dark:bg-purple-900/20',
    extractor: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-900/20',
    watcher: 'bg-green-50 text-green-600 dark:bg-green-900/20',
  }

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Mini summary */}
      <div className="flex items-center gap-4 mb-6 text-sm">
        <span className="text-gray-500">文件总数 <strong className="text-gray-900">{scanSummary.total}</strong></span>
        <span className="text-green-600">已索引 <strong>{scanSummary.indexed}</strong></span>
        <span className="text-amber-600">待处理 <strong>{scanSummary.pending}</strong></span>
        <span className="text-red-600">失败 <strong>{scanSummary.failed}</strong></span>
        <span className="text-gray-300">|</span>
        <span className="text-gray-400">{logs.length} 条日志</span>
        {processingFile && (
          <span className="flex items-center gap-1 text-amber-600">
            <Loader2 className="w-3 h-3 animate-spin" />
            {processingFile.split('/').pop()}
            {processingProgress && <span className="text-gray-400">{processingProgress}</span>}
          </span>
        )}
        <button onClick={() => { loadLogs(); loadSummary() }} className="p-1 text-gray-400 hover:text-gray-600">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="搜索日志内容或文件名..."
            className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900" />
        </div>
        <select value={level} onChange={e => setLevel(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
          <option value="">全部级别</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
        <select value={source} onChange={e => setSource(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
          <option value="">全部来源</option>
          <option value="server">服务器</option>
          <option value="indexer">索引器</option>
          <option value="ocr">OCR</option>
          <option value="extractor">提取器</option>
          <option value="watcher">文件监控</option>
        </select>
        <button onClick={handleExport}
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
          <Download className="w-4 h-4" />
          导出 CSV
        </button>
      </div>

      {/* Log list */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        <div className="max-h-[calc(100vh-280px)] overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
          {loading && logs.length === 0 && (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>
          )}
          {!loading && logs.length === 0 && (
            <div className="py-12 text-sm text-gray-400 text-center">暂无日志</div>
          )}
          {logs.map(log => (
            <div key={log.id} className="px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800/30">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs text-gray-400 font-mono w-28 shrink-0">{formatTime(log.created_at)}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${levelColors[log.level] || 'text-gray-600 bg-gray-100'}`}>
                  {log.level}
                </span>
                {log.source && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${sourceColors[log.source] || 'bg-gray-100 text-gray-600'}`}>
                    {log.source}
                  </span>
                )}
                <span className="flex-1 text-gray-700 dark:text-gray-300">{log.message}</span>
                {log.duration_ms != null && (
                  <span className="text-xs text-gray-400 shrink-0">{log.duration_ms}ms</span>
                )}
              </div>
              {log.file_path && (
                <div className="text-xs text-gray-400 font-mono truncate pl-2">{log.file_path}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}