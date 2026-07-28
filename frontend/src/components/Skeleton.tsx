export function SearchSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="p-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg animate-pulse">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded shrink-0" />
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-48" />
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-10 ml-auto" />
          </div>
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full mt-2" />
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mt-1.5" />
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mt-1.5" />
        </div>
      ))}
    </div>
  )
}

export function StatsSkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 animate-pulse">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-12 mx-auto" />
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-16 mx-auto mt-2" />
        </div>
      ))}
    </div>
  )
}