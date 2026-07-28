import { useState, useEffect } from 'react'
import { Search, FolderOpen, FileText, Settings as SettingsIcon, LogOut, Loader2 } from 'lucide-react'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './components/Auth'
import LoginPage from './pages/LoginPage'
import SearchPage from './pages/SearchPage'
import DirManager from './pages/DirManager'
import LogsPage from './pages/LogsPage'
import SettingsPage from './pages/Settings'

type Tab = 'search' | 'dirs' | 'logs' | 'settings'

const tabs: { id: Tab; label: string; icon: typeof Search }[] = [
  { id: 'search', label: '搜索', icon: Search },
  { id: 'dirs', label: '资料库', icon: FolderOpen },
  { id: 'logs', label: '日志', icon: FileText },
  { id: 'settings', label: '设置', icon: SettingsIcon },
]

function AppContent() {
  const { token, ready, logout } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('search')
  const [scanStatus, setScanStatus] = useState('')
  const [nextScan, setNextScan] = useState('')

  useEffect(() => {
    if (!token) return
    const poll = async () => {
      try {
        const res = await fetch('/api/index/status', {
          headers: { Authorization: `Bearer ${token}` },
        })
        const d = await res.json()
        if (d.scanner_status === 'scanning') {
          const fn = d.processing_file ? d.processing_file.split('/').pop() : ''
          const prog = d.processing_progress ? ' ' + d.processing_progress : ''
          setScanStatus(`扫描中 ${d.indexed}/${d.total_files}${fn ? ' ' + fn : ''}${prog}`)
        } else {
          setScanStatus('')
        }
        setNextScan(d.next_scheduled_scan || '')
      } catch {}
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [token])

  if (!ready) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>
  }

  if (!token) {
    return <LoginPage />
  }

  return (
    <div className="flex h-screen">
      <nav className="w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-200 dark:border-gray-800">
          <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
            <Search className="w-5 h-5 text-blue-600" />
            <span>FullText Search</span>
          </h1>
        </div>
        <div className="flex-1 p-2 space-y-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === id
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
              }`}>
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
        <div className="p-3 text-xs text-gray-400 border-t border-gray-200 dark:border-gray-800 space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            API connected
          </div>
          {scanStatus && (
            <div className="flex items-center gap-1.5 text-amber-600">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span className="truncate">{scanStatus}</span>
            </div>
          )}
          {nextScan && !scanStatus && (
            <div className="text-gray-500">下次扫描: {nextScan}</div>
          )}
          <button onClick={logout} className="flex items-center gap-1.5 text-gray-500 hover:text-red-500 pt-1">
            <LogOut className="w-3 h-3" />
            退出登录
          </button>
        </div>
      </nav>
      <main className="flex-1 overflow-auto">
        {activeTab === 'search' && <SearchPage />}
        {activeTab === 'dirs' && <DirManager />}
        {activeTab === 'logs' && <LogsPage />}
        {activeTab === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </AuthProvider>
  )
}