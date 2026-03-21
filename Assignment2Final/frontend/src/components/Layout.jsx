import { Link, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import NotificationBell from './NotificationBell';

export default function Layout({ children = <Outlet /> }) {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
    toast.success('Logged out');
  };

  const isActive = (path) =>
    location.pathname.startsWith(path)
      ? 'text-blue-600 font-semibold'
      : 'text-gray-600 hover:text-gray-900';

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-8">
              <Link to="/dashboard" className="flex items-center gap-2">
                <span className="text-2xl">🎓</span>
                <span className="font-bold text-blue-700 text-lg hidden sm:block">Campus Trading</span>
              </Link>
              {user && (
                <div className="hidden md:flex items-center gap-6 text-sm">
                  <Link to="/listings" className={isActive('/listings')}>Listings</Link>
                  <Link to="/wishrequests" className={isActive('/wishrequests')}>Wish Requests</Link>
                  <Link to="/dashboard" className={isActive('/dashboard')}>Dashboard</Link>
                  {isAdmin() && (
                    <>
                      <Link to="/admin/members" className={isActive('/admin')}>Admin</Link>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-4">
              {user ? (
                <>
                  {isAdmin() && (
                    <span className="badge-red text-xs">Admin</span>
                  )}
                  <NotificationBell />
                  <Link
                    to={`/portfolio/${user.member_id || 'me'}`}
                    className="text-sm text-gray-600 hover:text-gray-900 hidden sm:block"
                  >
                    {user.name || user.email}
                  </Link>
                  <button onClick={handleLogout} className="btn-secondary btn-sm text-sm">
                    Logout
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" className="btn-secondary btn-sm text-sm">Login</Link>
                  <Link to="/register" className="btn-primary btn-sm text-sm">Sign up</Link>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile nav */}
      {user && (
        <div className="md:hidden bg-white border-b border-gray-100 px-4 py-2 flex gap-6 text-sm overflow-x-auto">
          <Link to="/listings" className={isActive('/listings')}>Listings</Link>
          <Link to="/wishrequests" className={isActive('/wishrequests')}>Wish Requests</Link>
          <Link to="/dashboard" className={isActive('/dashboard')}>Dashboard</Link>
          {user.member_id && (
            <Link to={`/portfolio/${user.member_id}`} className={isActive('/portfolio')}>Portfolio</Link>
          )}
          {isAdmin() && <Link to="/admin/members" className={isActive('/admin')}>Admin</Link>}
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        Campus Trading App — IIT Gandhinagar
      </footer>
    </div>
  );
}
