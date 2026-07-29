import { Globe } from 'lucide-react'

interface Props {
  onSelect: (lang: 'zh' | 'en') => void
}

export default function LanguageSelect({ onSelect }: Props) {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-gray-900 via-gray-950 to-black">
      <div className="w-full max-w-lg mx-4">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 mb-6">
            <Globe className="w-8 h-8 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">FullText Search</h1>
          <p className="text-gray-400">选择语言 / Choose Language</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => onSelect('zh')}
            className="group relative flex flex-col items-center gap-4 p-8 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 hover:border-blue-500/50 transition-all duration-200"
          >
            <span className="text-5xl">🇨🇳</span>
            <div className="text-center">
              <div className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">中文</div>
              <div className="text-sm text-gray-500 mt-1">简体中文</div>
            </div>
          </button>

          <button
            onClick={() => onSelect('en')}
            className="group relative flex flex-col items-center gap-4 p-8 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 hover:border-blue-500/50 transition-all duration-200"
          >
            <span className="text-5xl">🇬🇧</span>
            <div className="text-center">
              <div className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">English</div>
              <div className="text-sm text-gray-500 mt-1">International</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  )
}