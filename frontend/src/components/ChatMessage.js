import { useState } from "react";
import { Copy, CheckCheck, User, Bot, RotateCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";

export default function ChatMessage({ message, onRegenerate, isLatest }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const copyToClipboard = () => {
    navigator.clipboard.writeText(message.message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group w-full ${
        isUser ? "bg-transparent" : "bg-gray-50 dark:bg-gray-800/50"
      }`}
    >
      <div className="max-w-4xl mx-auto px-4 py-6 flex gap-4">
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
            isUser
              ? "bg-gradient-to-br from-blue-500 to-purple-600"
              : "bg-gradient-to-br from-green-400 to-emerald-600"
          }`}
        >
          {isUser ? (
            <User size={18} className="text-white" />
          ) : (
            <Bot size={18} className="text-white" />
          )}
        </div>

        {/* Message Content */}
        <div className="flex-1 overflow-hidden">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      className="rounded-lg"
                      {...props}
                    >
                      {String(children).replace(/\n$/, "")}
                    </SyntaxHighlighter>
                  ) : (
                    <code
                      className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-sm"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.message}
            </ReactMarkdown>
          </div>

          {/* Action Buttons */}
          {!isUser && (
            <div className="flex gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={copyToClipboard}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                title="Copy message"
              >
                {copied ? (
                  <CheckCheck size={16} className="text-green-500" />
                ) : (
                  <Copy size={16} className="text-gray-500" />
                )}
              </button>

              {isLatest && onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  title="Regenerate response"
                >
                  <RotateCw size={16} className="text-gray-500" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}