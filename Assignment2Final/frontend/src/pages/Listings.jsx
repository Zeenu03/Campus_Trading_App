import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import Pagination from '../components/Pagination';

const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];
const STATUSES   = ['Listed', 'Sold', 'Expired', 'Withdrawn'];

function ListingCard({ listing }) {
  const statusColors = {
    Listed: 'badge-green', Sold: 'badge-gray', Expired: 'badge-gray', Withdrawn: 'badge-gray',
  };
  return (
    <Link to={`/listings/${listing.listing_id}`}
      className="card hover:shadow-lg transition-shadow flex flex-col gap-3">
      <div className="flex justify-between items-start gap-2">
        <h3 className="font-semibold text-gray-900 line-clamp-2 flex-1 text-sm">{listing.title}</h3>
        <span className={statusColors[listing.status] || 'badge-gray'}>{listing.status}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xl font-bold text-blue-700">
          {listing.is_donation ? 'FREE' : `₹${Number(listing.asking_price).toLocaleString()}`}
        </span>
        {listing.is_negotiable && !listing.is_donation && (
          <span className="text-xs text-gray-400">Negotiable</span>
        )}
      </div>
      <div className="text-xs text-gray-500 space-y-1">
        <p>{listing.category_name}</p>
        {listing.condition && <p>Condition: {listing.condition}</p>}
        <p className="text-gray-400">by {listing.seller_name}</p>
      </div>
    </Link>
  );
}

export default function Listings() {
  const { isMember } = useAuth();
  const [listings, setListings] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: 'Listed', condition: '', sort: 'newest' });
  const [search, setSearch] = useState('');
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState('');

  useEffect(() => {
    api.get('/wishrequests').catch(() => {}); // warm up
    api.get('/listings', { page: 1, page_size: 1, status: 'Listed' })
      .then(() => {})
      .catch(() => {});
    // Load categories from listings metadata
    fetch('http://localhost:8080/api/v1/listings?page=1&page_size=1&status=Listed', { credentials: 'include' })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { page, page_size: 20, ...filters };
    if (category) params.category = category;
    api.get('/listings', params)
      .then(data => {
        setListings(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => setListings([]))
      .finally(() => setLoading(false));
  }, [page, filters, category]);

  const handleFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const filtered = search
    ? listings.filter(l => l.title.toLowerCase().includes(search.toLowerCase()))
    : listings;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Browse Listings</h1>
        {isMember() && (
          <Link to="/listings/new" className="btn-primary text-sm">+ Post Listing</Link>
        )}
      </div>

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="label text-xs">Search</label>
            <input
              className="input text-sm"
              placeholder="Search listings…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <div>
            <label className="label text-xs">Status</label>
            <select className="input text-sm" value={filters.status}
              onChange={e => handleFilter('status', e.target.value)}>
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="label text-xs">Condition</label>
            <select className="input text-sm" value={filters.condition}
              onChange={e => handleFilter('condition', e.target.value)}>
              <option value="">Any</option>
              {CONDITIONS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="label text-xs">Sort</label>
            <select className="input text-sm" value={filters.sort}
              onChange={e => handleFilter('sort', e.target.value)}>
              <option value="newest">Newest</option>
              <option value="price_asc">Price: Low → High</option>
              <option value="price_desc">Price: High → Low</option>
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading listings…" />
      ) : (
        <>
          <p className="text-sm text-gray-500">{total} listing{total !== 1 ? 's' : ''} found</p>
          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <p className="text-4xl mb-3">🔍</p>
              <p>No listings found. Try different filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map(l => <ListingCard key={l.listing_id} listing={l} />)}
            </div>
          )}
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
