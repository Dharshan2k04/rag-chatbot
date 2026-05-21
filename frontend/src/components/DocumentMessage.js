import { FileText, CheckCircle } from "lucide-react";

export default function DocumentMessage({ document }) {
  return (
    <div className="w-full bg-gray-50 dark:bg-gray-800/50">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm">
          <div className="flex items-start gap-4">
            {/* Document Icon */}
            <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
              <FileText className="text-blue-600 dark:text-blue-400" size={24} />
            </div>

            {/* Document Info */}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-semibold text-gray-900 dark:text-white">
                  {document.filename}
                </h4>
                <CheckCircle className="text-green-500" size={16} />
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {(document.size / 1024 / 1024).toFixed(2)} MB
                {document.chunks ? ` • ${document.chunks} chunks processed` : " • Processing in background..."}
              </p>
              <p className={`text-xs mt-2 ${document.chunks ? "text-green-600 dark:text-green-400" : "text-yellow-600 dark:text-yellow-400"}`}>
                {document.chunks ? "✓ Document indexed and ready for questions" : "⏳ Document uploaded, indexing in progress..."}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}