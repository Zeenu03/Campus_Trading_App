import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import Pagination from '../components/Pagination';

const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];

function ListingCard({ listing }) {
  const statusColors = {
    Listed: 'badge-green', Sold: 'badge-gray', Withdrawn: 'badge-gray',
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
          ₹{Number(listing.asking_price).toLocaleString()}
        </span>
        {listing.is_negotiable && (
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

function tagKey(tag) {
  return `${tag.kind}:${tag.value}`;
}

export default function Listings() {
  const { isMember } = useAuth();
  const [listings, setListings] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [titleInput, setTitleInput] = useState('');
  const [titleQ, setTitleQ] = useState('');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [sort, setSort] = useState('newest');
  const [tags, setTags] = useState([]);
  const [pickCategoryId, setPickCategoryId] = useState('');
  const [pickCondition, setPickCondition] = useState('');

  const prevTitleQ = useRef(titleQ);

  useEffect(() => {
    const h = setTimeout(() => setTitleQ(titleInput.trim()), 400);
    return () => clearTimeout(h);
  }, [titleInput]);

  useEffect(() => {
    if (prevTitleQ.current !== titleQ) {
      prevTitleQ.current = titleQ;
      setPage(1);
    }
  }, [titleQ]);

  useEffect(() => {
    api.get('/categories').then(setCategories).catch(() => setCategories([]));
  }, []);

  const tagSignature = useMemo(
    () => [...tags].map(tagKey).sort().join('|'),
    [tags],
  );

  useEffect(() => {
    setLoading(true);
    const params = { page, page_size: 20, sort };
    if (titleQ) params.q = titleQ;
    const minN = parseFloat(minPrice);
    if (minPrice !== '' && !Number.isNaN(minN)) params.min_price = minN;
    const maxN = parseFloat(maxPrice);
    if (maxPrice !== '' && !Number.isNaN(maxN)) params.max_price = maxN;
    const catIds = tags.filter(t => t.kind === 'category').map(t => t.value);
    const conds = tags.filter(t => t.kind === 'condition').map(t => t.value);
    if (catIds.length) params.category_id = catIds;
    if (conds.length) params.condition = conds;

    api.get('/listings', params)
      .then(data => {
        setListings(data.data || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => setListings([]))
      .finally(() => setLoading(false));
  }, [page, titleQ, minPrice, maxPrice, sort, tagSignature]);

  const addCategoryTag = () => {
    const id = parseInt(pickCategoryId, 10);
    if (Number.isNaN(id)) return;
    const cat = categories.find(c => c.category_id === id);
    const label = cat ? cat.category_name : `Category #${id}`;
    const next = { kind: 'category', value: id, label };
    if (tags.some(t => tagKey(t) === tagKey(next))) return;
    setTags(prev => [...prev, next]);
    setPickCategoryId('');
    setPage(1);
  };

  const addConditionTag = () => {
    if (!pickCondition) return;
    const next = { kind: 'condition', value: pickCondition, label: pickCondition };
    if (tags.some(t => tagKey(t) === tagKey(next))) return;
    setTags(prev => [...prev, next]);
    setPickCondition('');
    setPage(1);
  };

  const removeTag = (key) => {
    setTags(prev => prev.filter(t => tagKey(t) !== key));
    setPage(1);
  };

  const onPriceChange = (setter) => (e) => {
    setter(e.target.value);
    setPage(1);
  };

  const onSortChange = (e) => {
    setSort(e.target.value);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Browse Listings</h1>
        {isMember() && (
          <Link to="/listings/new" className="btn-primary text-sm">+ Post Listing</Link>
        )}
      </div>

      <div className="card space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="sm:col-span-2">
            <label className="label text-xs">Search title</label>
            <input
              className="input text-sm w-full"
              placeholder="Search by title…"
              value={titleInput}
              onChange={e => setTitleInput(e.target.value)}
            />
          </div>
          <div>
            <label className="label text-xs">Min price (₹)</label>
            <input
              type="number"
              min={0}
              step="1"
              className="input text-sm w-full"
              placeholder="No minimum"
              value={minPrice}
              onChange={onPriceChange(setMinPrice)}
            />
          </div>
          <div>
            <label className="label text-xs">Max price (₹)</label>
            <input
              type="number"
              min={0}
              step="1"
              className="input text-sm w-full"
              placeholder="No maximum"
              value={maxPrice}
              onChange={onPriceChange(setMaxPrice)}
            />
          </div>
        </div>

        <div>
          <label className="label text-xs">Sort by date</label>
          <select className="input text-sm max-w-xs" value={sort} onChange={onSortChange}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>

        <div className="border-t border-gray-100 pt-4 space-y-3">
          <p className="text-xs font-medium text-gray-600">Tags — category &amp; condition (match any selected in each group)</p>
          <div className="flex flex-col sm:flex-row flex-wrap gap-3">
            <div className="flex flex-1 min-w-[200px] gap-2 items-end">
              <div className="flex-1">
                <label className="label text-xs">Add category</label>
                <select
                  className="input text-sm w-full"
                  value={pickCategoryId}
                  onChange={e => setPickCategoryId(e.target.value)}
                >
                  <option value="">Choose category…</option>
                  {categories.map(c => (
                    <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
                  ))}
                </select>
              </div>
              <button type="button" className="btn-secondary text-sm shrink-0" onClick={addCategoryTag}>
                Add
              </button>
            </div>
            <div className="flex flex-1 min-w-[200px] gap-2 items-end">
              <div className="flex-1">
                <label className="label text-xs">Add condition</label>
                <select
                  className="input text-sm w-full"
                  value={pickCondition}
                  onChange={e => setPickCondition(e.target.value)}
                >
                  <option value="">Choose condition…</option>
                  {CONDITIONS.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <button type="button" className="btn-secondary text-sm shrink-0" onClick={addConditionTag}>
                Add
              </button>
            </div>
          </div>

          {tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {tags.map(t => (
                <span
                  key={tagKey(t)}
                  className="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-900 text-xs pl-3 pr-1 py-1 border border-blue-100"
                >
                  <span className="text-blue-600/80">{t.kind === 'category' ? 'Category' : 'Condition'}:</span>
                  {t.label}
                  <button
                    type="button"
                    className="p-0.5 rounded-full hover:bg-blue-200/60 text-blue-800"
                    aria-label={`Remove ${t.label}`}
                    onClick={() => removeTag(tagKey(t))}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading listings…" />
      ) : (
        <>
          <p className="text-sm text-gray-500">{total} listing{total !== 1 ? 's' : ''} found</p>
          {listings.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <p className="text-4xl mb-3">🔍</p>
              <p>No listings found. Try different filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {listings.map(l => <ListingCard key={l.listing_id} listing={l} />)}
            </div>
          )}
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
