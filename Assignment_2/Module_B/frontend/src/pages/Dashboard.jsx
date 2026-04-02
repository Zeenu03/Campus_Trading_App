import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

function StatCard({ label, value, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    red: 'bg-red-50 text-red-700',
  };
  return (
    <div className={`card text-center ${colors[color]}`}>
      <p className="text-3xl font-bold">{value ?? '—'}</p>
      <p className="text-sm mt-1 font-medium">{label}</p>
    </div>
  );
}

function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/admin/stats')
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Overview of Campus Trading platform</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Active Members"         value={stats?.total_active_members}    color="blue"  />
        <StatCard label="Active Listings"         value={stats?.active_listings}         color="green" />
        <StatCard label="Open Reports"            value={stats?.open_reports}            color="red"   />
        <StatCard label="Completed Transactions"  value={stats?.completed_transactions}  color="yellow"/>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <Link to="/admin/members"   className="btn-secondary w-full text-sm">Manage Members</Link>
            <Link to="/admin/reports"   className="btn-secondary w-full text-sm">Review Reports</Link>
            <Link to="/admin/audit"     className="btn-secondary w-full text-sm">View Audit Log</Link>
            <Link to="/admin/benchmark" className="btn-secondary w-full text-sm">Run Benchmark</Link>
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Navigation</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <p>Use the navigation menu to access all admin features.</p>
            <p>The audit log highlights suspicious direct DB writes (trigger path, no API session) in <span className="badge-red">red</span>.</p>
            <p>The benchmark page shows query performance before/after indexes.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function MemberDashboard() {
  const { user } = useAuth();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get('/listings', { status: 'Listed', page: 1, page_size: 6 })
      .then((l) => setListings(l?.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome, {user?.name}!</h1>
          <p className="text-gray-500 text-sm mt-1">Browse the campus marketplace</p>
        </div>
        <Link to="/listings/new" className="btn-primary text-sm">+ Post Listing</Link>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Listings</h2>
          <Link to="/listings" className="text-sm text-blue-600 hover:underline">View all →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {listings.map(listing => (
            <Link key={listing.listing_id} to={`/listings/${listing.listing_id}`} className="card hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-medium text-gray-900 line-clamp-2 text-sm">{listing.title}</h3>
                <span className="badge-blue ml-2 flex-shrink-0">
                  ₹{listing.asking_price}
                </span>
              </div>
              <p className="text-xs text-gray-500">{listing.category_name} • {listing.condition || 'N/A'}</p>
              <p className="text-xs text-gray-400 mt-1">by {listing.seller_name}</p>
            </Link>
          ))}
        </div>
        {listings.length === 0 && (
          <div className="text-center py-12 text-gray-400">No listings available yet.</div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Link to={`/portfolio/${user?.member_id}`} className="card hover:shadow-md transition-shadow text-center">
          <p className="text-2xl mb-1">👤</p>
          <p className="font-medium text-sm">My Portfolio</p>
          <p className="text-xs text-gray-500 mt-1">Listings, transactions, ratings</p>
        </Link>
        <Link to="/wishrequests" className="card hover:shadow-md transition-shadow text-center">
          <p className="text-2xl mb-1">✨</p>
          <p className="font-medium text-sm">Wish Requests</p>
          <p className="text-xs text-gray-500 mt-1">Browse & post requests</p>
        </Link>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { isAdmin } = useAuth();
  return isAdmin() ? <AdminDashboard /> : <MemberDashboard />;
}
