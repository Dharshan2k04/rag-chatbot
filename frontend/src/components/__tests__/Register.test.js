import { render, screen, fireEvent } from '@testing-library/react';
import { AuthProvider } from '../../context/AuthContext';
import Register from '../Register';

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

test('renders register form with password strength meter', () => {
  render(
    <AuthProvider>
      <Register onSwitchToLogin={() => {}} />
    </AuthProvider>
  );

  expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/johndoe/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Create Account/i })).toBeInTheDocument();
});

test('shows password strength indicator on input', () => {
  render(
    <AuthProvider>
      <Register onSwitchToLogin={() => {}} />
    </AuthProvider>
  );

  const passwordInput = screen.getAllByPlaceholderText(/••••••••/i)[0];
  fireEvent.change(passwordInput, { target: { value: 'abc' } });
  expect(screen.getByText(/Weak/i)).toBeInTheDocument();

  fireEvent.change(passwordInput, { target: { value: 'StrongPass1!' } });
  expect(screen.getByText(/Strong/i)).toBeInTheDocument();
});
