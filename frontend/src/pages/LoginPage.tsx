import { useState } from 'react'
import { Search, Loader2, Lock, AlertCircle } from 'lucide-react'
import { useAuth } from '../components/Auth'

export default function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) return
    setLoading(true)
    setError('')
    try {
      const ok = await login(password)
      if (!ok) setError('密码错误')
    } catch {
      setError('登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="w-full max-w-sm mx-4">
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-sm p-8">
          <div className="flex items-center justify-center mb-6">
            <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
              <Search className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          <h1 className="text-xl font-semibold text-center mb-1">FullText Search</h1>
          <p className="text-sm text-gray-500 text-center mb-6">请输入密码登录</p>

          {error && (
            <div className="flex items-center gap-2 mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 text-sm rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="relative mb-4">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="密码"
                autoFocus
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 dark:border-gray-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900"
              />
            </div>
            <button type="submit" disabled={loading || !password.trim()}
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <p className="text-xs text-gray-400 text-center mt-6">
            默认密码: admin
          </p>
        </div>
      </div>
    </div>
  )
}
