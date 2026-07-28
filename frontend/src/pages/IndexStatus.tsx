import { useState, useEffect } from 'react'
import { BarChart3, RefreshCw, Play, Loader2, Search, Filter } from 'lucide-react'
import { getIndexStatus, triggerScan } from '../api/client'
import type { IndexStatus as IndexStatusType } from '../api/client'
import { useToast } from '../components/Toast'
import { StatsSkeleton } from '../components/Skeleton'

interface LogEntry {
  id: number
  level: string
  message: string
  file_path: string | null
  duration_ms: number | null
  created_at: number
}

export default function IndexStatus() {
  const { toast } = useToast()
  const [status, setStatus] = useState<IndexStatusType | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState('')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [logLoading, setLogLoading] = useState(false)
  const [logLevel, setLogLevel] = useState('')
  const [logQuery, setLogQuery] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const s = await getIndexStatus()
      setStatus(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const loadLogs = async () => {
    setLogLoading(true)
    try {
      const params = new URLSearchParams()
      if (logLevel) params.set('level', logLevel)
      if (logQuery) params.set('q', logQuery)
      params.set('limit', '200')
      const res = await fetch(`/api/logs?${params}`)
      const data = await res.json()
      setLogs(data.logs)
    } catch {
      // ignore
    } finally {
      setLogLoading(false)
    }
  }

  useEffect(() => {
    load()
    loadLogs()
    const interval = setInterval(() => { load(); loadLogs() }, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => { loadLogs() }, [logLevel, logQuery])

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      const res = await triggerScan()
      if (res.status === 'busy') {
        toast('warning', '扫描已在运行中')
      } else {
        toast('success', '全量扫描已触发')
        setTimeout(() => { load(); loadLogs() }, 2000)
      }
    } catch {
      toast('error', '触发扫描失败')
    } finally {
      setTriggering(false)
    }
  }

  const progress = status ? Math.round(status.progress_percent) : 0
  const levelColors: Record<string, string> = {
    INFO: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20',
    WARNING: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20',
    ERROR: 'text-red-600 bg-red-50 dark:bg-red-900/20',
  }
  const formatTime = (ts: number) => new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2"><BarChart3 className="w-5 h-5" />索引状态</h2>
        <div className="flex gap-2">
          <button onClick={() => { load(); loadLogs() }} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={handleTrigger} disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Play className="w-4 h-4" />{triggering ? '触发中...' : '重新索引'}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 text-sm rounded-lg">{error}</div>}

      {loading && !status && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-2" />
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full w-full mb-3" />
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-48" />
          </div>
          <StatsSkeleton />
        </div>
      )}

      {status && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">索引进度</span>
              <span className="text-sm text-gray-500">{progress}%</span>
            </div>
            <div className="w-full h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
            <div className="flex items-center justify-between mt-3 text-sm text-gray-500">
              <div className="flex items-center gap-2">
                <span>{status.scanner_status === 'scanning' ? '扫描中...' : '空闲'}</span>
                {status.scanner_status === 'scanning' && status.processing_file && (
                  <span className="flex items-center gap-1 text-amber-600">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {status.processing_file.split('/').pop()}
                  </span>
                )}
              </div>
              <span>下次定时扫描: {status.next_scheduled_scan}</span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            {[
              { label: '文件总数', value: status.total_files, color: 'text-gray-900' },
              { label: '已索引', value: status.indexed, color: 'text-green-600' },
              { label: '待处理', value: status.pending, color: 'text-amber-600' },
              { label: '失败', value: status.failed, color: 'text-red-600' },
            ].map(s => (
              <div key={s.label} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 text-center">
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-gray-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>

          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium flex items-center gap-2"><Filter className="w-4 h-4" />扫描日志</h3>
                <span className="text-xs text-gray-400">{logLoading ? '加载中...' : `${logs.length} 条`}</span>
              </div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input type="text" value={logQuery} onChange={e => setLogQuery(e.target.value)}
                    placeholder="搜索日志..."
                    className="w-full pl-9 pr-3 py-1.5 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900" />
                </div>
                <select value={logLevel} onChange={e => setLogLevel(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
                  <option value="">全部</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                </select>
              </div>
            </div>
            <div className="max-h-80 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
              {logLoading && logs.length === 0 && <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-blue-500" /></div>}
              {!logLoading && logs.length === 0 && <div className="py-8 text-sm text-gray-400 text-center">暂无日志</div>}
              {logs.map(log => (
                <div key={log.id} className="px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800/30">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs text-gray-400 font-mono">{formatTime(log.created_at)}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${levelColors[log.level] || 'text-gray-600 bg-gray-100'}`}>{log.level}</span>
                    <span className="flex-1 text-gray-700 dark:text-gray-300">{log.message}</span>
                    {log.duration_ms != null && <span className="text-xs text-gray-400">{log.duration_ms}ms</span>}
                  </div>
                  {log.file_path && <div className="text-xs text-gray-400 font-mono truncate pl-2">{log.file_path}</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}