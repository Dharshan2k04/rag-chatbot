# RAG Chatbot Frontend

React frontend for the RAG Document Intelligence Chatbot. Built with React 19, Tailwind CSS, Framer Motion, and Lucide React icons.

## Features

- **JWT Authentication**: Login/Register with password strength indicator
- **Protected Routes**: Auth context with automatic token refresh on 401
- **Real-time Streaming**: SSE EventSource for live LLM token streaming
- **PDF Upload**: Drag-and-drop upload modal with progress feedback
- **Dark Mode**: Persistent theme toggle with Tailwind `dark:` classes
- **Chat History**: Sidebar with chat list, new chat, and delete functionality
- **Responsive UI**: ChatGPT-style interface with gradient accents

## Tech Stack

- React 19 + Create React App
- Tailwind CSS 3.4
- Framer Motion
- Axios (with JWT interceptors + refresh queue)
- Lucide React (icons)
- React Markdown + Syntax Highlighter

## Environment Variables

Create a `.env` file in `frontend/`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REACT_APP_API_URL` | Yes | `https://dharshan0707-rag-chatbot-api.hf.space` | Backend API base URL |

## Local Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Create .env file
echo "REACT_APP_API_URL=http://localhost:7860" > .env

# 3. Start dev server
npm start
```

App will open at `http://localhost:3000`.

## Running Tests

```bash
npm test -- --watchAll=false
```

Tests use React Testing Library with mocked API and heavy components.

## Build for Production

```bash
npm run build
```

Creates an optimized `build/` folder for deployment.

## Deploy to Vercel

1. Push `frontend/` to GitHub
2. Import project on [vercel.com](https://vercel.com)
3. Set environment variable:
   - `REACT_APP_API_URL` = `https://<your-hf-space>.hf.space`
4. Deploy

## Project Structure

```
src/
├── api.js                    # Axios instance with JWT interceptors + refresh
├── App.js                    # Auth gating + ChatApp routing
├── index.js                  # React root with AuthProvider
├── context/
│   └── AuthContext.js        # Auth state, login/logout, token refresh
├── components/
│   ├── Login.js              # Login form
│   ├── Register.js           # Register form + password strength meter
│   ├── ModernSidebar.js      # Chat history sidebar + dark mode + logout
│   ├── ModernChatInput.js    # Message input + PDF upload modal
│   ├── ChatMessage.js        # Message bubble with markdown rendering
│   ├── DocumentMessage.js      # PDF upload success card
│   └── LoadingSkeleton.js    # Typing indicator skeleton
```

## What You Need to Do

1. **Ensure backend is running** (locally or deployed on HF Spaces)
2. **Set `REACT_APP_API_URL`** in `.env` or Vercel to point to your backend
3. **Deploy to Vercel** once the backend URL is confirmed
