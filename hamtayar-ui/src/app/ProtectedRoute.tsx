import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { hasDemoSession } from '../features/auth/authService';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!hasDemoSession()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}
