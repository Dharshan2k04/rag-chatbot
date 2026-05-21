export default function ChatWindow({ messages }) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`flex ${
            msg.role === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <div
            className={`px-4 py-2 rounded-2xl max-w-lg ${
              msg.role === "user"
                ? "bg-blue-600 text-white"
                : "bg-white border"
            }`}
          >
            {msg.message}
          </div>
        </div>
      ))}
    </div>
  );
}
