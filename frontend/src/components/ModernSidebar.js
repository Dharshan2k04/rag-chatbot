import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  MessageSquarePlus,
  Moon,
  Sun,
  History,
  ChevronRight,
  MessageSquare,
  Trash2,
  LogOut,
  User,
} from "lucide-react";
import api from "../api";

export default function ModernSidebar({ onNewChat, currentChatId, onSelectChat }) {
  const { user, logout } = useAuth();
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem("dark_mode");
    if (saved !== null) return saved === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  const [collapsed, setCollapsed] = useState(false);
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e) => setDarkMode(e.matches);
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    loadChats();
  }, []);

  

  const loadChats = async () => {
    try {
      setLoading(true);
      const response = await api.get("/chat/?limit=20&offset=0");
      setChats(response.data.chats);
    } catch (err) {
      console.error("Error loading chats:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChat = async (chatId, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this chat?")) return;

    try {
      await api.delete(`/chat/${chatId}`);
      loadChats(true);  // reset to page 1 after delete
      if (chatId === currentChatId) {
        onNewChat();
      }
    } catch (err) {
      console.error("Error deleting chat:", err);
    }
  };

  const toggleDarkMode = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem("dark_mode", String(next));
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      className={`${
        collapsed ? "w-16" : "w-64"
      } bg-gray-900 dark:bg-black text-white flex flex-col transition-all duration-300 relative border-r border-gray-800`}
    >
      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-6 bg-gray-800 hover:bg-gray-700 rounded-full p-1 transition-colors z-10"
      >
        <ChevronRight
          size={16}
          className={`transition-transform ${collapsed ? "" : "rotate-180"}`}
        />
      </button>

      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <button
          onClick={onNewChat}
          className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-all hover:shadow-lg group"
        >
          <MessageSquarePlus size={20} className="flex-shrink-0" />
          {!collapsed && <span className="font-medium">New Chat</span>}
        </button>
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto p-3">
        {!collapsed && (
          <div className="mb-4">
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-gray-400 font-medium">
              <History size={14} />
              <span>Chat History</span>
            </div>
            
            {loading ? (
              <div className="space-y-2 mt-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-12 bg-gray-800 rounded-lg animate-pulse"
                  />
                ))}
              </div>
            ) : chats.length === 0 ? (
              <p className="text-sm text-gray-500 px-3 py-2">
                No previous chats
              </p>
            ) : (
              <div className="space-y-1 mt-2">
                {chats.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => onSelectChat(chat.id)}
                    className={`group px-3 py-3 rounded-lg cursor-pointer transition-all flex items-start gap-2 ${
                      chat.id === currentChatId
                        ? "bg-gray-800"
                        : "hover:bg-gray-800/50"
                    }`}
                  >
                    <MessageSquare size={16} className="flex-shrink-0 mt-0.5 text-gray-400" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-300 truncate">
                        {chat.title}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {formatDate(chat.updated_at)}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteChat(chat.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-700 rounded transition-all"
                    >
                      <Trash2 size={14} className="text-red-400" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-800 space-y-2">
        <button
          onClick={toggleDarkMode}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-gray-800 transition-colors group"
        >
          {darkMode ? (
            <Sun size={18} className="flex-shrink-0" />
          ) : (
            <Moon size={18} className="flex-shrink-0" />
          )}
          {!collapsed && (
            <span className="text-sm">
              {darkMode ? "Light" : "Dark"} Mode
            </span>
          )}
        </button>

        {!collapsed && user && (
          <div className="px-3 py-2">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <User size={12} className="text-white" />
              </div>
              <span className="text-xs text-gray-300 truncate">{user.email || user.username}</span>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg hover:bg-red-900/30 text-red-400 transition-colors text-xs"
            >
              <LogOut size={14} />
              <span>Logout</span>
            </button>
          </div>
        )}

        {collapsed && (
          <button onClick={logout} className="flex items-center justify-center w-full p-2 rounded-lg hover:bg-red-900/30 text-red-400 transition-colors">
            <LogOut size={18} />
          </button>
        )}
      </div>
    </div>
  );
}