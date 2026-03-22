import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import Pagination from '../components/Pagination';

const CONDITIONS = ['New', 'Like New', 'Good', 'Fair', 'Poor'];

function WishRequestCard({ wishRequest }) {
  const statusColors = {
    Active: 'badge-green',
    Fulfilled: 'badge-gray',
    Expired: 'badge-gray',
    Cancelled: 'badge-gray',
  };

  const wishRequestId = wishRequest.wish_request_id ?? wishRequest.wishRequestID;
  if (!wishRequestId) return null;

  return (
    <Link
      to={`/wishrequests/${wishRequestId}`}
      className="card hover:shadow-lg transition-shadow flex flex-col gap-3"
    >
      <div className="flex justify-between items-start gap-2">
        <h3 className="font-semibold text-gray-900 line-clamp-2 flex-1 text-sm">{wishRequest.item_description}</h3>
        <span className={statusColors[wishRequest.status] || 'badge-gray'}>{wishRequest.status}</span>
      </div>

      <div className="text-xs text-gray-500 space-y-1">
        <p>{wishRequest.category_name}</p>
        {wishRequest.preferred_condition && <p>Condition: {wishRequest.preferred_condition}</p>}
        <p className="text-gray-400">by {wishRequest.requester_name}</p>
      </div>

      <div className="flex items-center justify-between mt-auto">
        <span className="text-base font-semibold text-blue-700">
          ₹{Number(wishRequest.min_budget || 0).toLocaleString()} - ₹{Number(wishRequest.max_budget || 0).toLocaleString()}
        </span>
      </div>
    </Link>
  );
}

function tagKey(tag) {
  return `${tag.kind}:${tag.value}`;
}

export default function WishRequests() {
  const { isMember } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [titleInput, setTitleInput] = useState('');
  const [titleQ, setTitleQ] = useState('');
  const [minBudget, setMinBudget] = useState('');
  const [maxBudget, setMaxBudget] = useState('');
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

  const tagSignature = useMemo(() => [...tags].map(tagKey).sort().join('|'), [tags]);

  useEffect(() => {
    setLoading(true);
    const params = { page, page_size: 20, sort };
    if (titleQ) params.q = titleQ;
    const minN = parseFloat(minBudget);
    if (minBudget !== '' && !Number.isNaN(minN)) params.min_budget = minN;
    const maxN = parseFloat(maxBudget);
    if (maxBudget !== '' && !Number.isNaN(maxN)) params.max_budget = maxN;

    const catIds = tags.filter((t) => t.kind === 'category').map((t) => t.value);
    const conds = tags.filter((t) => t.kind === 'condition').map((t) => t.value);
    if (catIds.length) params.category_id = catIds;
    if (conds.length) params.condition = conds;

    api.get('/wishrequests', params)
      .then((data) => {
        const rows = (data.data || []).map((row) => ({
          ...row,
          wish_request_id: row.wish_request_id ?? row.WishRequestID ?? null,
          item_description: row.item_description ?? row.ItemDescription ?? '',
          requester_name: row.requester_name ?? row.RequesterName ?? '',
          category_name: row.category_name ?? row.CategoryName ?? '',
        }));
        setItems(rows);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [page, titleQ, minBudget, maxBudget, sort, tagSignature]);

  const addCategoryTag = () => {
    const id = parseInt(pickCategoryId, 10);
    if (Number.isNaN(id)) return;
    const cat = categories.find((c) => c.category_id === id);
    const label = cat ? cat.category_name : `Category #${id}`;
    const next = { kind: 'category', value: id, label };
    if (tags.some((t) => tagKey(t) === tagKey(next))) return;
    setTags((prev) => [...prev, next]);
    setPickCategoryId('');
    setPage(1);
  };

  const addConditionTag = () => {
    if (!pickCondition) return;
    const next = { kind: 'condition', value: pickCondition, label: pickCondition };
    if (tags.some((t) => tagKey(t) === tagKey(next))) return;
    setTags((prev) => [...prev, next]);
    setPickCondition('');
    setPage(1);
  };

  const removeTag = (key) => {
    setTags((prev) => prev.filter((t) => tagKey(t) !== key));
    setPage(1);
  };

  const onBudgetChange = (setter) => (e) => {
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
        <h1 className="text-2xl font-bold text-gray-900">Browse Wish Requests</h1>
        {isMember() && (
          <Link to="/wishrequests/new" className="btn-primary text-sm">+ Post Wish Request</Link>
        )}
      </div>

      <div className="rounded-xl border border-gray-200/90 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-4 py-2.5 bg-gradient-to-r from-slate-50 to-gray-50 border-b border-gray-100">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Filters</span>
          <span className="text-[11px] text-gray-400 hidden sm:inline">Category &amp; condition tags use OR within each group</span>
        </div>

        <div className="p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:flex-nowrap xl:items-end xl:gap-3">
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 lg:items-end xl:contents">
              <div className="sm:col-span-2 lg:col-span-5 xl:min-w-0 xl:flex-1 xl:max-w-none">
                <label className="label text-xs text-gray-600">Item Description</label>
                <input
                  className="input text-sm w-full"
                  placeholder="Search by request…"
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                />
              </div>

              <div className="lg:col-span-2 xl:w-[6.25rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Min ₹</label>
                <input type="number" min={0} step="1" className="input text-sm w-full tabular-nums" placeholder="—" value={minBudget} onChange={onBudgetChange(setMinBudget)} />
              </div>
              <div className="lg:col-span-2 xl:w-[6.25rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Max ₹</label>
                <input type="number" min={0} step="1" className="input text-sm w-full tabular-nums" placeholder="—" value={maxBudget} onChange={onBudgetChange(setMaxBudget)} />
              </div>

              <div className="sm:col-span-2 lg:col-span-3 xl:w-[10.5rem] xl:shrink-0">
                <label className="label text-xs text-gray-600">Sort</label>
                <select className="input text-sm w-full" value={sort} onChange={onSortChange}>
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                  <option value="budget_asc">Budget low to high</option>
                  <option value="budget_desc">Budget high to low</option>
                </select>
              </div>

              <div className="sm:col-span-2 lg:col-span-6 flex gap-2 items-end min-w-0 xl:flex-1 xl:min-w-[12rem]">
                <div className="flex-1 min-w-0">
                  <label className="label text-xs text-gray-600">Category tag</label>
                  <select className="input text-sm w-full" value={pickCategoryId} onChange={(e) => setPickCategoryId(e.target.value)}>
                    <option value="">Select…</option>
                    {categories.map((c) => (
                      <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="btn-secondary text-sm px-3.5 shrink-0" onClick={addCategoryTag}>Add</button>
              </div>

              <div className="sm:col-span-2 lg:col-span-6 flex gap-2 items-end min-w-0 xl:flex-1 xl:min-w-[12rem]">
                <div className="flex-1 min-w-0">
                  <label className="label text-xs text-gray-600">Condition tag</label>
                  <select className="input text-sm w-full" value={pickCondition} onChange={(e) => setPickCondition(e.target.value)}>
                    <option value="">Select…</option>
                    {CONDITIONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="btn-secondary text-sm px-3.5 shrink-0" onClick={addConditionTag}>Add</button>
              </div>
            </div>
          </div>

          {tags.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-[11px] font-medium text-gray-500 mb-2">Active tags</p>
              <div className="flex flex-wrap gap-2">
                {tags.map((t) => (
                  <span key={tagKey(t)} className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-800 text-xs pl-3 pr-1 py-1 border border-slate-200/80">
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
        <LoadingSpinner message="Loading wish requests…" />
      ) : (
        <>
          <p className="text-sm text-gray-500">{total} wish request{total !== 1 ? 's' : ''} found</p>
          {items.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <p className="text-4xl mb-3">✨</p>
              <p>No wish requests found. Try different filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {items.map((w) => <WishRequestCard key={w.wish_request_id} wishRequest={w} />)}
            </div>
          )}
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
