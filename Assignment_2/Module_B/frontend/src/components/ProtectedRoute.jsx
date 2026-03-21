import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function RoleRoute({ children, role }) {
  const { user, loading, hasRole } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-64"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!hasRole(role)) return <Navigate to="/dashboard" replace />;
  return children;
}
