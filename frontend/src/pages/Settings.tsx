import { useState, useEffect } from 'react'
import { Settings, Globe, Clock, Scan, Palette, Save, Loader2, Cpu, Database, Lock, Key } from 'lucide-react'
import { useToast } from '../components/Toast'

export default function SettingsPage() {
  const { toast } = useToast()
  const [ocrLang, setOcrLang] = useState('ch')
  const [scanTime, setScanTime] = useState('00:00')
  const [excludePatterns, setExcludePatterns] = useState('')
  const [theme, setTheme] = useState('system')
  const [ocrConcurrent, setOcrConcurrent] = useState(2)
  const [backupInterval, setBackupInterval] = useState(0)
  const [saving, setSaving] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [changingPw, setChangingPw] = useState(false)
  const [backups, setBackups] = useState<Array<{ filename: string; size_str: string; created_at: number }>>([])
  const [suggestedConcurrent, setSuggestedConcurrent] = useState(2)

  const applyTheme = (t: string) => {
    const html = document.documentElement
    if (t === 'dark') html.classList.add('dark')
    else if (t === 'light') html.classList.remove('dark')
    else {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) html.classList.add('dark')
      else html.classList.remove('dark')
    }
  }

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(d => {
        setOcrLang(d.ocr_lang || 'ch')
        setScanTime(d.scheduled_scan_time || '00:00')
        setExcludePatterns(d.exclude_patterns || '')
        const t = d.theme || 'system'
        setTheme(t)
        applyTheme(t)
        setOcrConcurrent(d.ocr_concurrent ?? 2)
        setBackupInterval(d.backup_interval_days ?? 0)
        if (d.suggested_ocr_concurrent) setSuggestedConcurrent(d.suggested_ocr_concurrent)
      })
      .catch(() => {})
    fetch('/api/index/backups')
      .then(r => r.json())
      .then(d => setBackups(d.backups || []))
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ocr_lang: ocrLang, scheduled_scan_time: scanTime,
          exclude_patterns: excludePatterns, theme,
          ocr_concurrent: ocrConcurrent, backup_interval_days: backupInterval,
        }),
      })
      if (res.ok) toast('success', '设置已保存')
      else toast('error', '保存失败')
    } catch {
      toast('error', '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (!oldPw || !newPw) return
    if (newPw.length < 4) { toast('error', '密码至少4位'); return }
    setChangingPw(true)
    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
      })
      const data = await res.json()
      if (res.ok) {
        toast('success', '密码已修改')
        setOldPw(''); setNewPw('')
      } else {
        toast('error', data.detail || '修改失败')
      }
    } catch {
      toast('error', '修改失败')
    } finally {
      setChangingPw(false)
    }
  }

  const handleBackupNow = async () => {
    try {
      await fetch('/api/index/backup', { method: 'POST' })
      toast('success', '备份已触发')
      setTimeout(async () => {
        const r = await fetch('/api/index/backups')
        const d = await r.json()
        setBackups(d.backups || [])
      }, 5000)
    } catch {
      toast('error', '备份触发失败')
    }
  }

  // Memory-based suggestion for ocr_concurrent
  const memWarning = suggestedConcurrent <= 1 ? '（可用内存较少，建议设为 1）' : ''

  // Human-readable status for backup interval
  const backupLabel = backupInterval === 0 ? '禁用' : `每 ${backupInterval} 天`

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Settings className="w-5 h-5" />设置
        </h2>
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? '保存中...' : '保存设置'}
        </button>
      </div>

      <div className="space-y-4">
        {/* OCR Language */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Globe className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">OCR 语言</h3>
          </div>
          <select value={ocrLang} onChange={e => setOcrLang(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
            <option value="ch">中文 (ch)</option>
            <option value="en">英文 (en)</option>
            <option value="japan">日文 (japan)</option>
            <option value="korean">韩文 (korean)</option>
          </select>
        </section>

        {/* OCR Concurrent */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">OCR 并发数</h3>
          </div>
          <div className="flex items-center gap-3">
            <select value={ocrConcurrent} onChange={e => setOcrConcurrent(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
              <option value={1}>1（最省内存）</option>
              <option value={2}>2（推荐）</option>
              <option value={3}>3（高内存）</option>
              <option value={4}>4（最高性能）</option>
            </select>
            <span className="text-xs text-gray-400">
              建议: {suggestedConcurrent} 并发{memWarning}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            PaddleOCR 每线程约占用 300-500MB 内存。根据系统可用内存自动建议。
          </p>
        </section>

        {/* Schedule */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">定时扫描</h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">每天</span>
            <input type="time" value={scanTime} onChange={e => setScanTime(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900" />
          </div>
        </section>

        {/* Exclude patterns */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Scan className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">排除模式</h3>
          </div>
          <textarea value={excludePatterns} onChange={e => setExcludePatterns(e.target.value)}
            placeholder="每行一个 glob 模式，如: *.tmp&#10;node_modules/**&#10;*.log"
            className="w-full h-24 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900 font-mono" />
        </section>

        {/* Theme */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Palette className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">主题</h3>
          </div>
          <div className="flex gap-3">
            {['system', 'light', 'dark'].map(t => (
              <label key={t} className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="theme" value={t} checked={theme === t}
                  onChange={e => { setTheme(e.target.value); applyTheme(e.target.value) }} className="accent-blue-600" />
                <span className="text-sm">{t === 'system' ? '跟随系统' : t === 'light' ? '浅色' : '深色'}</span>
              </label>
            ))}
          </div>
        </section>

        {/* Auto Backup */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Database className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">自动备份</h3>
          </div>
          <div className="flex items-center gap-3">
            <select value={backupInterval} onChange={e => setBackupInterval(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900">
              <option value={0}>禁用</option>
              <option value={1}>每天</option>
              <option value={3}>每 3 天</option>
              <option value={7}>每周</option>
              <option value={14}>每两周</option>
              <option value={30}>每月</option>
              <option value={90}>每季度</option>
            </select>
            <span className="text-xs text-gray-400">当前: {backupLabel}</span>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            备份包括 SQLite 数据库 + Tantivy 索引，保留最近 7 份。保存设置后生效。
          </p>
          <div className="flex items-center gap-3 mt-3">
            <button onClick={handleBackupNow}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
              立即备份
            </button>
            {backups.length > 0 && (
              <span className="text-xs text-gray-400">最近备份: {backups[0]?.filename}</span>
            )}
          </div>
        </section>

        {/* Change Password */}
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lock className="w-4 h-4 text-gray-500" />
            <h3 className="font-medium">修改密码</h3>
          </div>
          <div className="space-y-3 max-w-sm">
            <input type="password" value={oldPw} onChange={e => setOldPw(e.target.value)}
              placeholder="当前密码"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900" />
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
              placeholder="新密码（至少 4 位）"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900" />
            <button onClick={handleChangePassword} disabled={changingPw || !oldPw || !newPw}
              className="flex items-center gap-1.5 px-4 py-2 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700 disabled:opacity-50">
              {changingPw ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
              修改密码
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">密码使用 scrypt 加密存储，修改后需要重新登录。</p>
        </section>
      </div>
    </div>
  )
}