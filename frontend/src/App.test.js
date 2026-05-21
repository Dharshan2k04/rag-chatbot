import { render, screen, waitFor } from '@testing-library/react';

jest.mock('./api', () => ({
  __esModule: true,
  default: {
    interceptors: {
      request: { use: jest.fn(), eject: jest.fn() },
      response: { use: jest.fn(), eject: jest.fn() },
    },
    get: jest.fn(() => Promise.reject({ response: { status: 401 } })),
    post: jest.fn(() => Promise.reject({ response: { status: 401 } })),
  },
}));

jest.mock('./components/ChatMessage', () => () => null);
jest.mock('./components/DocumentMessage', () => () => null);
jest.mock('./components/ModernChatInput', () => () => null);
jest.mock('./components/LoadingSkeleton', () => () => null);
jest.mock('./components/ModernSidebar', () => () => null);

import { AuthProvider } from './context/AuthContext';
import App from './App';

test('renders login when not authenticated', async () => {
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
  await waitFor(() => {
    expect(screen.getByText(/Welcome Back/i)).toBeInTheDocument();
  });
});
