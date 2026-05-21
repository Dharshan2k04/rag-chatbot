import { useState, useEffect, useRef } from "react";
import { useAuth } from "./context/AuthContext";
import ModernSidebar from "./components/ModernSidebar";
import ChatMessage from "./components/ChatMessage";
import DocumentMessage from "./components/DocumentMessage";
import ModernChatInput from "./components/ModernChatInput";
import LoadingSkeleton from "./components/LoadingSkeleton";
import Login from "./components/Login";
import Register from "./components/Register";
import api from "./api";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:7860";

function ChatApp() {
  const [chatId, setChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [useStreaming, setUseStreaming] = useState(true);
  const [isIngesting, setIsIngesting] = useState(false);
  const messagesEndRef = useRef(null);
  const initChatCalled = useRef(false);
  const sidebarRefreshRef = useRef(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // ── CHAT INIT ─────────────────────────────────────────
  const startNewChat = () => {
    setChatId(null);
    setMessages([]);
    if (sidebarRefreshRef.current) {
      sidebarRefreshRef.current();
    }
  };

  const loadChat = async (id) => {
    try {
      setChatId(id);
      const res = await api.get(`/chat/${id}/messages`);
      const formattedMessages = res.data.messages.map((msg) => ({
        role: msg.role,
        message: msg.message,
      }));
      setMessages(formattedMessages);
    } catch (err) {
      console.error("Error loading chat:", err);
    }
  };

  useEffect(() => {
    if (initChatCalled.current) return;
    initChatCalled.current = true;

    const initChat = async () => {
      try {
        const res = await api.get("/chat/?limit=1&offset=0");
        if (res.data.chats && res.data.chats.length > 0) {
          const mostRecent = res.data.chats[0];
          setChatId(mostRecent.id);
          const msgRes = await api.get(`/chat/${mostRecent.id}/messages`);
          const formatted = msgRes.data.messages.map((m) => ({
            role: m.role,
            message: m.message,
          }));
          setMessages(formatted);
        }
        // No chats exist — show welcome screen, don't create a chat
      } catch (err) {
        console.error("Init error:", err);
      }
    };

    initChat();
  }, []);

  // ── DOCUMENT UPLOAD ───────────────────────────────────
  const pollIngestionStatus = async (docId) => {
    setIsIngesting(true);
    const interval = setInterval(async () => {
      try {
        const res = await api.get("/documents");
        const doc = res.data.documents.find((d) => d.id === docId);
        if (doc && doc.chunk_count > 0) {
          clearInterval(interval);
          setIsIngesting(false);
        }
      } catch (err) {
        clearInterval(interval);
        setIsIngesting(false);
      }
    }, 3000);
  };

  const handleDocumentUploaded = async (document) => {
    // Create a chat if none exists when document is uploaded
    if (!chatId) {
      try {
        const res = await api.post("/chat/new");
        setChatId(res.data.chat_id);
      } catch (err) {
        console.error("Failed to create chat on upload:", err);
      }
    }
    setMessages((prev) => [...prev, { role: "document", document }]);
    if (document.id) {
      pollIngestionStatus(document.id);
    }
  };

  // ── SEND MESSAGE ──────────────────────────────────────
  const ensureChatExists = async () => {
    if (chatId) return chatId;
    try {
      const res = await api.post("/chat/new");
      const newChatId = res.data.chat_id;
      setChatId(newChatId);
      // Refresh sidebar to show new chat
      if (sidebarRefreshRef.current) {
        sidebarRefreshRef.current();
      }
      return newChatId;
    } catch (err) {
      console.error("Failed to create chat:", err);
      return null;
    }
  };

  const sendMessageStreaming = async (input, isRegenerate = false) => {
    if (!input.trim() || loading) return;

    const activeChatId = await ensureChatExists();
    if (!activeChatId) return;

    if (!isRegenerate) {
      setMessages((prev) => [...prev, { role: "user", message: input }]);
    } else {
      setMessages((prev) => {
        const lastAssistantIdx = [...prev].map(m => m.role).lastIndexOf("assistant");
        if (lastAssistantIdx === -1) return prev;
        return prev.filter((_, idx) => idx !== lastAssistantIdx);
      });
    }

    setLoading(true);

    try {
      const aiMsgId = Date.now();
      setMessages((prev) => [
        ...prev,
        { id: aiMsgId, role: "assistant", message: "" },
      ]);

      const token = localStorage.getItem("access_token");
      const response = await fetch(
        `${API_BASE_URL}/chat/${activeChatId}/stream?query=${encodeURIComponent(input)}&regenerate=${isRegenerate}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      );

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Streaming request failed: ${errText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          setLoading(false);
          break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.done) {
                setLoading(false);
              } else if (data.token) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMsgId
                      ? { ...msg, message: msg.message + data.token }
                      : msg
                  )
                );
              }
            } catch (err) {
              console.error("Error parsing stream:", err);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", message: "Sorry, I encountered an error. Please try again." },
      ]);
    }
  };

  const sendMessageNonStreaming = async (input, isRegenerate = false) => {
    if (!input.trim() || loading) return;

    const activeChatId = await ensureChatExists();
    if (!activeChatId) return;

    if (!isRegenerate) {
      setMessages((prev) => [...prev, { role: "user", message: input }]);
    } else {
      setMessages((prev) => {
        const lastAssistantIdx = [...prev].map(m => m.role).lastIndexOf("assistant");
        if (lastAssistantIdx === -1) return prev;
        return prev.filter((_, idx) => idx !== lastAssistantIdx);
      });
    }

    setLoading(true);

    try {
      const res = await api.post(
        `/chat/${activeChatId}?query=${encodeURIComponent(input)}&regenerate=${isRegenerate}`
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", message: res.data.answer },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", message: "Sorry, I encountered an error. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = (input, isRegenerate = false) => {
    if (useStreaming) {
      return sendMessageStreaming(input, isRegenerate);
    } else {
      return sendMessageNonStreaming(input, isRegenerate);
    }
  };

  const handleRegenerate = async () => {
    if (messages.length < 2) return;
    const lastUserMsg = [...messages].reverse().find((msg) => msg.role === "user");
    if (!lastUserMsg) return;
    await sendMessage(lastUserMsg.message, true);
  };

  // ── RENDER ────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-white transition-colors">
      <ModernSidebar
        onNewChat={startNewChat}
        currentChatId={chatId}
        onSelectChat={loadChat}
        onRegisterRefresh={(fn) => { sidebarRefreshRef.current = fn; }}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b dark:border-gray-800 bg-white dark:bg-gray-900 p-4 backdrop-blur-sm bg-opacity-80">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <h1 className="text-xl font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              RAG Chatbot
            </h1>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={useStreaming}
                  onChange={(e) => setUseStreaming(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-gray-600 dark:text-gray-400">
                  ⚡ Streaming {useStreaming ? "ON" : "OFF"}
                </span>
              </label>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm text-gray-500">Online</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <AnimatePresence>
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="h-full flex items-center justify-center"
              >
                <div className="text-center space-y-4 p-8">
                  <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl mx-auto flex items-center justify-center">
                    <svg
                      className="w-8 h-8 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                  </div>
                  <h2 className="text-2xl font-semibold">Welcome to RAG Chatbot</h2>
                  <p className="text-gray-500 max-w-md">
                    Upload a document using the + button below and start asking
                    questions. I'll help you find answers based on your documents.
                  </p>
                </div>
              </motion.div>
            ) : (
              messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  {msg.role === "document" ? (
                    <DocumentMessage document={msg.document} />
                  ) : (
                    <ChatMessage
                      message={msg}
                      onRegenerate={
                        idx === messages.length - 1 && msg.role === "assistant"
                          ? handleRegenerate
                          : null
                      }
                      isLatest={idx === messages.length - 1}
                    />
                  )}
                </motion.div>
              ))
            )}
          </AnimatePresence>

          {loading && <LoadingSkeleton />}
          <div ref={messagesEndRef} />
        </div>

        <ModernChatInput
          chatId={chatId}
          onSendMessage={(input) => sendMessage(input, false)}
          onDocumentUploaded={handleDocumentUploaded}
          disabled={loading || isIngesting}
          isIngesting={isIngesting}
        />
      </div>
    </div>
  );
}

function App() {
  const { isAuthenticated, loading } = useAuth();
  const [showRegister, setShowRegister] = useState(false);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    if (showRegister) {
      return <Register onSwitchToLogin={() => setShowRegister(false)} />;
    }
    return <Login onSwitchToRegister={() => setShowRegister(true)} />;
  }

  return <ChatApp />;
}

export default App;