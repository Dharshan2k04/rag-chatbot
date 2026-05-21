import { render, screen } from '@testing-library/react';
import Login from '../Login';
import { AuthProvider } from '../../context/AuthContext';

jest.mock('../../api', () => ({
  __esModule: true,
  default: {
    interceptors: {
      request: { use: jest.fn(), eject: jest.fn() },
      response: { use: jest.fn(), eject: jest.fn() },
    },
    get: jest.fn(),
    post: jest.fn(),
  },
}));

test('renders login form with email and password inputs', () => {
  render(
    <AuthProvider>
      <Login onSwitchToRegister={() => {}} />
    </AuthProvider>
  );

  expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
});
