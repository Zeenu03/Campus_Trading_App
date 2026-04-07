export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null;

  const pages = [];
  const start = Math.max(1, page - 2);
  const end   = Math.min(totalPages, page + 2);
  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <div className="flex items-center justify-center gap-1 mt-6">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="btn btn-secondary btn-sm"
      >
        ‹ Prev
      </button>

      {start > 1 && (
        <>
          <button onClick={() => onPageChange(1)} className="btn btn-secondary btn-sm">1</button>
          {start > 2 && <span className="px-2 text-gray-400">…</span>}
        </>
      )}

      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onPageChange(p)}
          className={`btn btn-sm ${p === page ? 'btn-primary' : 'btn-secondary'}`}
        >
          {p}
        </button>
      ))}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span className="px-2 text-gray-400">…</span>}
          <button onClick={() => onPageChange(totalPages)} className="btn btn-secondary btn-sm">{totalPages}</button>
        </>
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="btn btn-secondary btn-sm"
      >
        Next ›
      </button>
    </div>
  );
}
