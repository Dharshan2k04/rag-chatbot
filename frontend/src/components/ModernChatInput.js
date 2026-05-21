import { useState, useRef } from "react";
import { Send, Plus, X, FileText, Upload as UploadIcon } from "lucide-react";
import api from "../api";

export default function ModernChatInput({ chatId, onSendMessage, disabled, onDocumentUploaded, isIngesting }) {  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type === "application/pdf") {
      setSelectedFile(file);
    } else {
      alert("Please select a PDF file");
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      setUploading(true);
      const response = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      // Notify parent component about successful upload
      if (onDocumentUploaded) {
        onDocumentUploaded({
          id: response.data.document_id,
          filename: selectedFile.name,
          chunks: response.data.chunks,
          size: selectedFile.size,
        });
      }
      
      setSelectedFile(null);
      setShowUploadModal(false);
    } catch (err) {
      alert("❌ Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleSend = () => {
    if (!input.trim() || !chatId || disabled) return;
    onSendMessage(input);
    setInput("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold">Upload Document</h3>
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setSelectedFile(null);
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Drag & Drop Area */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center cursor-pointer hover:border-blue-500 transition-colors"
            >
              <UploadIcon className="mx-auto mb-3 text-gray-400" size={40} />
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Click to upload or drag and drop
              </p>
              <p className="text-xs text-gray-500 mt-1">PDF files only</p>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* Selected File Preview */}
            {selectedFile && (
              <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex items-center gap-3">
                <FileText className="text-blue-600" size={24} />
                <div className="flex-1">
                  <p className="font-medium text-sm">{selectedFile.name}</p>
                  <p className="text-xs text-gray-500">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="p-1 hover:bg-white dark:hover:bg-gray-700 rounded"
                >
                  <X size={16} />
                </button>
              </div>
            )}

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="w-full mt-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
            >
              {uploading ? "Uploading..." : "Upload Document"}
            </button>
          </div>
        </div>
      )}

      {/* Chat Input */}
      <div className="border-t dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end gap-3 bg-gray-100 dark:bg-gray-800 rounded-2xl p-3 focus-within:ring-2 focus-within:ring-blue-500 transition-all">
            {/* Plus Button */}
            <button
              onClick={() => setShowUploadModal(true)}
              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors flex-shrink-0"
              title="Upload document"
            >
              <Plus size={20} className="text-gray-600 dark:text-gray-400" />
            </button>

            {/* Text Input */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isIngesting ? "⏳ Indexing document, please wait..." : "Message RAG Chatbot..."}
              rows={1}
              className="flex-1 bg-transparent outline-none resize-none max-h-32 text-gray-900 dark:text-white placeholder-gray-500"
              style={{
                minHeight: "24px",
                height: "auto",
              }}
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = e.target.scrollHeight + "px";
              }}
            />

            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || !chatId || disabled}
              className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all flex-shrink-0"
            >
              <Send size={20} />
            </button>
          </div>
          <p className="text-xs text-center text-gray-500 mt-2">
            Press Enter to send, Shift + Enter for new line
          </p>
        </div>
      </div>
    </>
  );
}