import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const data = await api.get('/auth/me');
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);  // set loading to false after the user is loaded
    }
  }, []); // empty dependency array means loadUser will only run once when the component mounts

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = async (email, password) => {
    await api.post('/auth/login', { email, password });
    await loadUser();
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); } catch { /* ignore */ }
    setUser(null);
  };

  const hasRole = (role) => user?.roles?.includes(role);
  const isAdmin  = () => hasRole('admin');
  const isMember = () => hasRole('member');

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasRole, isAdmin, isMember, reload: loadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
