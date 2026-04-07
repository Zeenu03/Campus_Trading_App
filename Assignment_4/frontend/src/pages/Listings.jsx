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

      <div className="rounded-xl border border-gray-200/90 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-4 py-2.5 bg-gradient-to-r from-slate-50 to-gray-50 border-b border-gray-100">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Filters</span>
          <span className="text-[11px] text-gray-400 hidden sm:inline">
            Category &amp; condition tags use OR within each group
          </span>
        </div>

        <div className="p-4">
          {/* Below xl: 12-col grid = 2 rows; xl+: display:contents lifts cells into one flex row */}
          <div className="flex flex-col gap-3 xl:flex-row xl:flex-nowrap xl:items-end xl:gap-3">
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 lg:items-end xl:contents">
              <div className="sm:col-span-2 lg:col-span-5 xl:min-w-0 xl:flex-1 xl:max-w-none">
                <label className="label text-xs text-gray-600">Title</label>
                <input
                  className="input text-sm w-full"
                  placeholder="Search by title…"
                  value={titleInput}
                  onChange={e => setTitleInput(e.target.value)}
                />
              </div>
              <div className="lg:col-span-2 xl:w-[6.25rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Min ₹</label>
                <input
                  type="number"
                  min={0}
                  step="1"
                  className="input text-sm w-full tabular-nums"
                  placeholder="—"
                  value={minPrice}
                  onChange={onPriceChange(setMinPrice)}
                />
              </div>
              <div className="lg:col-span-2 xl:w-[6.25rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Max ₹</label>
                <input
                  type="number"
                  min={0}
                  step="1"
                  className="input text-sm w-full tabular-nums"
                  placeholder="—"
                  value={maxPrice}
                  onChange={onPriceChange(setMaxPrice)}
                />
              </div>
              <div className="sm:col-span-2 lg:col-span-3 xl:w-[10.5rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Sort</label>
                <select className="input text-sm w-full" value={sort} onChange={onSortChange}>
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                </select>
              </div>

              <div className="sm:col-span-2 lg:col-span-6 flex gap-2 items-end min-w-0 xl:flex-1 xl:min-w-[12rem]">
                <div className="flex-1 min-w-0">
                  <label className="label text-xs text-gray-600">Category tag</label>
                  <select
                    className="input text-sm w-full"
                    value={pickCategoryId}
                    onChange={e => setPickCategoryId(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {categories.map(c => (
                      <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="btn-secondary text-sm px-3.5 shrink-0" onClick={addCategoryTag}>
                  Add
                </button>
              </div>
              <div className="sm:col-span-2 lg:col-span-6 flex gap-2 items-end min-w-0 xl:flex-1 xl:min-w-[12rem]">
                <div className="flex-1 min-w-0">
                  <label className="label text-xs text-gray-600">Condition tag</label>
                  <select
                    className="input text-sm w-full"
                    value={pickCondition}
                    onChange={e => setPickCondition(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {CONDITIONS.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="btn-secondary text-sm px-3.5 shrink-0" onClick={addConditionTag}>
                  Add
                </button>
              </div>
            </div>
          </div>

          {tags.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-[11px] font-medium text-gray-500 mb-2">Active tags</p>
              <div className="flex flex-wrap gap-2">
                {tags.map(t => (
                  <span
                    key={tagKey(t)}
                    className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-800 text-xs pl-3 pr-1 py-1 border border-slate-200/80"
                  >
                    <span className="text-slate-500">{t.kind === 'category' ? 'Category' : 'Condition'}</span>
                    <span className="font-medium text-slate-900">{t.label}</span>
                    <button
                      type="button"
                      className="ml-0.5 flex h-6 w-6 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200/80 hover:text-slate-800"
                      aria-label={`Remove ${t.label}`}
                      onClick={() => removeTag(tagKey(t))}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
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
