import { Bot } from "lucide-react";

export default function LoadingSkeleton() {
  return (
    <div className="w-full bg-gray-50 dark:bg-gray-800/50">
      <div className="max-w-4xl mx-auto px-4 py-6 flex gap-4">
        {/* Avatar */}
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center">
          <Bot size={18} className="text-white" />
        </div>

        {/* Content */}
        <div className="flex-1 space-y-3">
          {/* Animated dots */}
          <div className="flex gap-1 items-center">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
          </div>

          {/* Skeleton lines */}
          <div className="space-y-2">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 animate-pulse"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 animate-pulse"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 animate-pulse"></div>
          </div>
        </div>
      </div>
    </div>
  );
}