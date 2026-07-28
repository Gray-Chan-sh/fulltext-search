import { useState, useEffect, type JSX as ReactJSX } from 'react'
import { FolderOpen, Plus, Trash2, RefreshCw, Loader2, ChevronRight, ChevronDown, FileText, Play, CheckSquare, Square } from 'lucide-react'
import { getDirs, addDir, deleteDir } from '../api/client'
import type { DirConfig } from '../api/client'
import { useToast } from '../components/Toast'
import ConfirmDialog from '../components/ConfirmDialog'

interface FileEntry {
  id: string
  path: string
  indexed: number
  error_msg: string | null
  mtime: number
  size: number
}

export default function DirManager() {
  const { toast } = useToast()
  const [dirs, setDirs] = useState<DirConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newPath, setNewPath] = useState('')
  const [newAlias, setNewAlias] = useState('')
  const [error, setError] = useState('')
  const [expandedDir, setExpandedDir] = useState<string | null>(null)
  const [fileMap, setFileMap] = useState<Record<string, FileEntry[]>>({})
  const [loadingFiles, setLoadingFiles] = useState<Record<string, boolean>>({})
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set())
  const [indexing, setIndexing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set())
  const [scanProgress, setScanProgress] = useState<{ status: string; processed: number; total: number; file: string; progress: string } | null>(null)
  const [duplicates, setDuplicates] = useState<Array<{ md5: string; size: number; files: string[]; count: number }>>([])
  const [recentIndexed, setRecentIndexed] = useState<Array<{ path: string; updated_at: number }>>([])
  const [failedFiles, setFailedFiles] = useState<Array<{ path: string; error_msg: string }>>([])
  const [ocrReport, setOcrReport] = useState<{ low_text_files: Array<{ path: string; char_count: number; ocr_duration_ms: number }>; stats: any } | null>(null)
  const [showDuplicates, setShowDuplicates] = useState(false)
  const [showRecent, setShowRecent] = useState(false)
  const [showOcrReport, setShowOcrReport] = useState(false)

  const loadDirs = async () => {
    setLoading(true)
    try {
      const res = await getDirs()
      setDirs(res.dirs)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

useEffect(() => { loadDirs() }, [])

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/index/status')
        const data = await res.json()
        setScanProgress({
          status: data.scanner_status,
          processed: data.indexed,
          total: data.total_files,
          file: data.processing_file || '',
          progress: data.processing_progress || '',
        })
      } catch {}
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => clearInterval(interval)
  }, [])

  // Load management data
  useEffect(() => {
    fetch('/api/files/duplicates').then(r => r.json()).then(d => setDuplicates(d.duplicates || [])).catch(() => {})
    fetch('/api/files/recent').then(r => r.json()).then(d => {
      setRecentIndexed(d.recently_indexed || [])
      setFailedFiles(d.failed || [])
    }).catch(() => {})
    fetch('/api/files/ocr-report').then(r => r.json()).then(d => setOcrReport(d)).catch(() => {})
  }, [])

  const toggleDir = async (dirId: string) => {
    if (expandedDir === dirId) {
      setExpandedDir(null)
      setSelectedFiles(new Set())
      return
    }
    setExpandedDir(dirId)
    setSelectedFiles(new Set())
    await loadFiles(dirId)
  }

  const loadFiles = async (dirId: string, filter?: string) => {
    const f = filter ?? statusFilter
    setLoadingFiles(prev => ({ ...prev, [dirId]: true }))
    try {
      const params = f === 'all' ? '' : `?status_filter=${f}`
      const res = await fetch(`/api/dirs/${dirId}/files${params}`)
      const data = await res.json()
      setFileMap(prev => ({ ...prev, [dirId]: data.files }))
    } catch {
      setError('加载文件列表失败')
    } finally {
      setLoadingFiles(prev => ({ ...prev, [dirId]: false }))
    }
  }

  const toggleFile = (fileId: string) => {
    setSelectedFiles(prev => {
      const next = new Set(prev)
      if (next.has(fileId)) next.delete(fileId)
      else next.add(fileId)
      return next
    })
  }

  const toggleAll = (dirId: string) => {
    const files = fileMap[dirId] || []
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set())
    } else {
      setSelectedFiles(new Set(files.map(f => f.id)))
    }
  }

  const indexSelected = async (dirId: string) => {
    if (selectedFiles.size === 0) return
    setIndexing(true)
    try {
      const res = await fetch(`/api/dirs/${dirId}/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_ids: Array.from(selectedFiles) }),
      })
      if (!res.ok) throw new Error('索引请求失败')
      const data = await res.json()
      const ok = data.results.filter((r: any) => r.status === 'ok').length
      toast('success', `索引完成: ${ok}/${selectedFiles.size} 个文件`)
      setSelectedFiles(new Set())
      const fres = await fetch(`/api/dirs/${dirId}/files`)
      const fdata = await fres.json()
      setFileMap(prev => ({ ...prev, [dirId]: fdata.files }))
    } catch (e) {
      toast('error', e instanceof Error ? e.message : '索引失败')
    } finally {
      setIndexing(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteDir(id)
      if (expandedDir === id) setExpandedDir(null)
      await loadDirs()
      toast('success', '目录已删除')
    } catch (e) {
      toast('error', '删除失败')
    }
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <FolderOpen className="w-5 h-5" />
          资料库管理
        </h2>
        <div className="flex gap-2">
          <button onClick={loadDirs} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            <Plus className="w-4 h-4" /> 添加目录
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 text-sm rounded-lg">{error}</div>
      )}

      {loading && !dirs.length && (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>
      )}

      {showAdd && (
        <div className="mb-4 p-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl">
          <h3 className="font-medium mb-3">添加监控目录</h3>
          <input placeholder="目录路径（Docker 内路径）" value={newPath}
            onChange={e => setNewPath(e.target.value)}
            className="w-full mb-2 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          <input placeholder="别名（可选）" value={newAlias}
            onChange={e => setNewAlias(e.target.value)}
            className="w-full mb-3 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          <div className="flex gap-2">
            <button onClick={async () => {
              if (!newPath.trim()) return
              try {
                await addDir({ path: newPath.trim(), alias: newAlias.trim() })
                setShowAdd(false); setNewPath(''); setNewAlias('')
                await loadDirs()
              } catch (e) { setError(e instanceof Error ? e.message : '添加失败') }
            }} className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">确认添加</button>
            <button onClick={() => setShowAdd(false)} className="px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700">取消</button>
          </div>
        </div>
      )}

      {/* Directory list with file tree */}
      <div className="space-y-3">
        {dirs.map(d => (
          <div key={d.id} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
            {/* Dir header — click to expand */}
            <div className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
              onClick={() => toggleDir(d.id)}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  {expandedDir === d.id
                    ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                    : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
                  }
                  <div>
                    <h3 className="font-medium">{d.alias || d.path.split('/').pop()}</h3>
                    <p className="text-xs text-gray-500 mt-0.5 font-mono truncate">{d.path}</p>
                  </div>
                </div>
                <button onClick={e => { e.stopPropagation(); setConfirmDelete(d.id) }}
                  className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 shrink-0">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-1.5 mt-2 ml-6 text-xs flex-wrap">
                {[
                  { key: 'all', label: '全部', count: d.file_count, color: 'text-gray-700' },
                  { key: 'indexed', label: '已索引', count: d.indexed_count, color: 'text-green-600' },
                  { key: 'pending', label: '待处理', count: d.file_count - d.indexed_count - d.failed_count - d.processing_count, color: 'text-amber-600' },
                  { key: 'processing', label: '正在索引', count: d.processing_count, color: 'text-blue-600' },
                  { key: 'failed', label: '失败', count: d.failed_count, color: 'text-red-600' },
                ].map(s => (
                  <button key={s.key} onClick={e => { e.stopPropagation(); setStatusFilter(s.key); if (expandedDir) loadFiles(expandedDir, s.key) }}
                    className={`px-2 py-1 rounded ${statusFilter === s.key ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
                    <span className={s.color}>{s.label}</span>
                    <span className="ml-1 text-gray-400">{s.count}</span>
                  </button>
                ))}
                <span className={`ml-1 px-1.5 py-0.5 rounded text-xs ${d.status === 'watching' ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                  {d.status === 'watching' ? '监控中' : '不可用'}
                </span>
                {scanProgress?.status === 'scanning' && (
                  <span className="flex items-center gap-1 text-amber-600 ml-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {scanProgress.processed}/{scanProgress.total}
                    {scanProgress.file && <span className="text-gray-400 truncate max-w-[100px]">{scanProgress.file.split('/').pop()}</span>}
                {scanProgress.progress && <span className="text-gray-400">{scanProgress.progress}</span>}
                  </span>
                )}
              </div>
            </div>

            {/* File tree */}
            {expandedDir === d.id && (
              <div className="border-t border-gray-100 dark:border-gray-800">
                {loadingFiles[d.id] ? (
                  <div className="flex justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-blue-500" /></div>
                ) : (
                  <>
                    {/* Toolbar — always visible when expanded */}
                    <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500">
                      <div className="flex items-center gap-1">
                        <button onClick={() => toggleAll(d.id)} className="flex items-center gap-1 hover:text-gray-700 px-1.5 py-1">
                          {(fileMap[d.id]?.length || 0) > 0 && selectedFiles.size === (fileMap[d.id]?.length || 0)
                            ? <CheckSquare className="w-3.5 h-3.5" />
                            : <Square className="w-3.5 h-3.5" />
                          }
                          全选
                        </button>
                        <span className="text-gray-300">|</span>
{['all', 'indexed', 'pending', 'processing', 'failed'].map(f => (
                            <button key={f} onClick={() => {
                              setStatusFilter(f)
                              if (expandedDir) loadFiles(expandedDir, f)
                            }}
                              className={`px-2 py-1 rounded ${statusFilter === f ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' : 'hover:text-gray-700'}`}>
                              {f === 'all' ? '全部' : f === 'indexed' ? '已索引' : f === 'pending' ? '待处理' : f === 'processing' ? '正在索引' : '失败'}
                            </button>
                          ))}
                      </div>
                      <div className="flex items-center gap-2">
                        {scanProgress?.status === 'scanning' && (
                          <span className="flex items-center gap-1.5 text-amber-600 font-medium" title={scanProgress.file ? scanProgress.file.split('/').pop() : ''}>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            {scanProgress.processed}/{scanProgress.total}
                            {scanProgress.file && <span className="text-gray-400 truncate max-w-[120px]">{scanProgress.file.split('/').pop()}</span>}
                {scanProgress.progress && <span className="text-gray-400">{scanProgress.progress}</span>}
                          </span>
                        )}
                        {selectedFiles.size > 0 && (
                          <button onClick={() => indexSelected(d.id)} disabled={indexing}
                            className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
                            <Play className="w-3 h-3" />
                            {indexing ? '索引中...' : `索引选中 (${selectedFiles.size})`}
                          </button>
                        )}
                        <span>{fileMap[d.id]?.length || 0} 个文件</span>
                      </div>
                    </div>

                    {/* File tree */}
                    <div className="divide-y divide-gray-100 dark:divide-gray-800 max-h-96 overflow-y-auto">
                      {(() => {
                        const files = fileMap[d.id] || []
                        const dirPath = d.path

                        interface TreeNode {
                          [key: string]: { subdirs: TreeNode; files: FileEntry[] }
                        }
                        const tree: TreeNode = {}
                        for (const f of files) {
                          const rel = f.path.replace(dirPath, '').replace(/^\//, '')
                          const parts = rel.split('/')
                          let node = tree
                          for (let i = 0; i < parts.length - 1; i++) {
                            if (!node[parts[i]]) node[parts[i]] = { subdirs: {}, files: [] }
                            node = node[parts[i]].subdirs
                          }
                          const fname = parts[parts.length - 1]
                          if (!node[fname]) node[fname] = { subdirs: {}, files: [] }
                          node[fname].files.push(f)
                        }

                        const toggleCollapse = (key: string) => {
                          setCollapsedDirs(prev => {
                            const next = new Set(prev)
                            if (next.has(key)) next.delete(key)
                            else next.add(key)
                            return next
                          })
                        }

                        const renderTree = (node: TreeNode, depth: number, parentKey: string): ReactJSX.Element[] => {
                          const entries = Object.entries(node)
                          entries.sort(([a], [b]) => {
                            const aIsDir = Object.keys(node[a].subdirs).length > 0 || node[a].files.length === 0
                            const bIsDir = Object.keys(node[b].subdirs).length > 0 || node[b].files.length === 0
                            if (aIsDir && !bIsDir) return -1
                            if (!aIsDir && bIsDir) return 1
                            return a.localeCompare(b, 'zh-CN')
                          })
                          return entries.flatMap(([name, val]) => {
                            const hasSubdirs = Object.keys(val.subdirs).length > 0
                            const hasFiles = val.files.length > 0
                            const isDir = hasSubdirs || !hasFiles
                            if (isDir) {
                              const key = parentKey + '/' + name
                              const isCollapsed = collapsedDirs.has(key)
                              return [
                                <div key={key}
                                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-gray-500 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/30 select-none"
                                  style={{ paddingLeft: `${12 + depth * 16}px` }}
                                  onClick={() => toggleCollapse(key)}>
                                  <span className="text-gray-400 w-3.5 shrink-0">
                                    {isCollapsed ? '▶' : '▼'}
                                  </span>
                                  📁 {name}
                                </div>,
                                ...(isCollapsed ? [] : [
                                  ...renderTree(val.subdirs, depth + 1, key),
                                  ...val.files.map(f => renderFileRow(f, depth + 1)),
                                ]),
                              ]
                            }
                            return val.files.map(f => renderFileRow(f, depth))
                          })
                        }
                        const renderFileRow = (f: FileEntry, fileDepth: number) => {
                          const statusMap: Record<number, { icon: string; label: string; color: string }> = {
                            1: { icon: '✅', label: '已索引', color: 'text-green-600' },
                            2: { icon: '❌', label: '失败', color: 'text-red-600' },
                            3: { icon: '⏳', label: '正在索引', color: 'text-blue-600' },
                          }
                          const st = statusMap[f.indexed] || { icon: '⏳', label: '待处理', color: 'text-amber-600' }
                          return (
                          <div key={f.id}
                            className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800/30"
                            style={{ paddingLeft: `${16 + fileDepth * 16}px` }}>
                            <button onClick={() => toggleFile(f.id)}
                              className="text-gray-400 hover:text-blue-600 shrink-0">
                              {selectedFiles.has(f.id)
                                ? <CheckSquare className="w-4 h-4 text-blue-600" />
                                : <Square className="w-4 h-4" />
                              }
                            </button>
                            <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                            <span className="flex-1 truncate">{f.path.split('/').pop()}</span>
                            <span className={`text-xs ${st.color} shrink-0`}>{st.icon} {st.label}</span>
                            {f.error_msg && (
                              <span className="text-xs text-red-500 truncate shrink-0 max-w-[120px]" title={f.error_msg}>
                                ⚠️ {f.error_msg}
                              </span>
                            )}
                          </div>
                          )
                        }
                        if (files.length === 0) {
                          return <div className="px-4 py-6 text-sm text-gray-400 text-center">暂无文件</div>
                        }
                        // Group by top-level subdirectories
                        const topLevel: TreeNode = {}
                        for (const f of files) {
                          const rel = f.path.replace(dirPath, '').replace(/^\//, '')
                          const parts = rel.split('/')
                          if (parts.length > 1) {
                            if (!topLevel[parts[0]]) topLevel[parts[0]] = { subdirs: {}, files: [] }
                            let node = topLevel[parts[0]].subdirs
                            for (let i = 1; i < parts.length - 1; i++) {
                              if (!node[parts[i]]) node[parts[i]] = { subdirs: {}, files: [] }
                              node = node[parts[i]].subdirs
                            }
                            const fname = parts[parts.length - 1]
                            if (!node[fname]) node[fname] = { subdirs: {}, files: [] }
                            node[fname].files.push(f)
                          } else {
                            if (!topLevel[parts[0]]) topLevel[parts[0]] = { subdirs: {}, files: [] }
                            topLevel[parts[0]].files.push(f)
                          }
                        }
                         return renderTree(topLevel, 0, '')
                      })()}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 space-y-3">
        {/* Duplicates Panel */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
          <button onClick={() => setShowDuplicates(!showDuplicates)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <span>📋 重复文件 ({duplicates.length})</span>
            <span>{showDuplicates ? '▲' : '▼'}</span>
          </button>
          {showDuplicates && (
            <div className="max-h-60 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
              {duplicates.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">暂无重复文件</div>}
              {duplicates.map((g, i) => (
                <div key={i} className="px-4 py-2.5 text-sm">
                  <div className="text-xs text-gray-400 mb-1">{(g.size / 1024).toFixed(0)}KB — {g.count} 个副本</div>
                  {g.files.map((f, j) => (
                    <div key={j} className="text-gray-700 dark:text-gray-300 truncate font-mono text-xs">{f}</div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity Panel */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
          <button onClick={() => setShowRecent(!showRecent)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <span>🕐 最近动态</span>
            <span>{showRecent ? '▲' : '▼'}</span>
          </button>
          {showRecent && (
            <div className="max-h-60 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
              {recentIndexed.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">暂无动态</div>}
              {recentIndexed.slice(0, 10).map((f, i) => (
                <div key={i} className="px-4 py-2 text-sm flex items-center gap-2">
                  <span className="text-green-500">✅</span>
                  <span className="flex-1 truncate">{f.path.split('/').pop()}</span>
                  <span className="text-xs text-gray-400">{new Date(f.updated_at * 1000).toLocaleDateString('zh-CN')}</span>
                </div>
              ))}
              {failedFiles.length > 0 && <div className="px-4 py-1.5 text-xs text-gray-400 bg-red-50 dark:bg-red-900/10">失败:</div>}
              {failedFiles.slice(0, 5).map((f, i) => (
                <div key={i} className="px-4 py-2 text-sm flex items-center gap-2">
                  <span className="text-red-500">❌</span>
                  <span className="flex-1 truncate">{f.path.split('/').pop()}</span>
                  <span className="text-xs text-red-400 truncate max-w-[150px]" title={f.error_msg}>{f.error_msg}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* OCR Report Panel */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
          <button onClick={() => setShowOcrReport(!showOcrReport)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <span>🔍 OCR 质量报告</span>
            <span>{showOcrReport ? '▲' : '▼'}</span>
          </button>
          {showOcrReport && ocrReport && (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              <div className="px-4 py-2.5 text-sm text-gray-500 flex gap-4">
                <span>已 OCR: <strong className="text-gray-900">{ocrReport.stats?.total_ocr || 0}</strong></span>
                <span>总字符: <strong className="text-gray-900">{ocrReport.stats?.total_chars || 0}</strong></span>
                <span>平均耗时: <strong className="text-gray-900">{ocrReport.stats?.avg_duration_ms ? Math.round(ocrReport.stats.avg_duration_ms) + 'ms' : '-'}</strong></span>
              </div>
              <div className="max-h-60 overflow-y-auto">
                {(!ocrReport.low_text_files || ocrReport.low_text_files.length === 0) && (
                  <div className="px-4 py-6 text-sm text-gray-400 text-center">暂无数据</div>
                )}
                {(ocrReport.low_text_files || []).slice(0, 20).map((f, i) => (
                  <div key={i} className="px-4 py-2 text-sm flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800/30">
                    <span className="text-amber-500">⚠️</span>
                    <span className="flex-1 truncate">{f.path.split('/').pop()}</span>
                    <span className="text-xs text-gray-400">{f.char_count} 字符</span>
                    <span className="text-xs text-gray-400">{f.ocr_duration_ms}ms</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete !== null}
        title="删除目录"
        message={`确定要删除这个目录的监控吗？文件追踪记录和索引将被清除。`}
        onConfirm={async () => {
          if (confirmDelete) await handleDelete(confirmDelete)
          setConfirmDelete(null)
        }}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  )
}
