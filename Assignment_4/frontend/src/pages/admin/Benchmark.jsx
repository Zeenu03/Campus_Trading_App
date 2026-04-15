import { useState } from 'react';
import { api } from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import toast from 'react-hot-toast';

export default function AdminBenchmark() {
  const [results, setResults]       = useState(null);
  const [loading, setLoading]       = useState(false);
  const [baseline, setBaseline]     = useState(null);
  const [comparison, setComparison] = useState(null);

  const runBenchmark = async (isBaseline = false) => {
    setLoading(true);
    try {
      const data = await api.get('/admin/benchmark');
      if (isBaseline) {
        setBaseline(data);
        setComparison(null);
        toast.success('Baseline recorded. Now run sql/indexes.sql, then click "Run After-Index Benchmark".');
      } else {
        setResults(data);
        if (baseline) setComparison(data);
        toast.success('Benchmark complete!');
      }
    } catch (err) {
      toast.error(err.message || 'Benchmark failed');
    } finally {
      setLoading(false);
    }
  };

  const display = results || baseline;
  const sharding = display?.sharding;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Query Benchmark</h1>
        <p className="text-sm text-gray-500 mt-1">
          Compare EXPLAIN results and query timing before and after adding indexes.
        </p>
      </div>

      <div className="card space-y-4">
        <h2 className="text-base font-semibold">How to use:</h2>
        <ol className="list-decimal list-inside space-y-1 text-sm text-gray-600">
          <li>Click <strong>"Run Before-Index Benchmark"</strong> to record baseline (no indexes).</li>
          <li>Run <code className="bg-gray-100 px-1 rounded">mysql -u &lt;team_name&gt; -p &lt;team_name&gt; &lt; sql/indexes.sql</code></li>
          <li>Click <strong>"Run After-Index Benchmark"</strong> to see improvement.</li>
        </ol>
        <div className="flex gap-3 flex-wrap">
          <button onClick={() => runBenchmark(true)} className="btn-secondary text-sm" disabled={loading}>
            📊 Run Before-Index Benchmark
          </button>
          <button onClick={() => runBenchmark(false)} className="btn-primary text-sm" disabled={loading}>
            ⚡ Run After-Index Benchmark
          </button>
        </div>
        {sharding && (
          <div className="border border-blue-100 bg-blue-50 rounded-xl p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-3 justify-between">
              <div>
                <h3 className="font-semibold text-blue-900">Sharding Overview</h3>
                <p className="text-sm text-blue-700">
                  {sharding.base_database} uses {sharding.routing_rule} across {sharding.shard_count} shards.
                </p>
              </div>
              <span className="badge-blue text-xs">3-way modulo routing</span>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {sharding.shards?.map((shard) => (
                <div key={shard.shard_id} className="bg-white border border-blue-100 rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wide text-blue-500 font-semibold">Shard {shard.shard_id + 1}</div>
                  <div className="font-mono text-sm text-gray-800 mt-1">
                    {shard.host && shard.port ? `${shard.host}:${shard.port}` : shard.database_name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{shard.database_name}</div>
                </div>
              ))}
            </div>

            <div className="grid gap-3 md:grid-cols-3 text-sm">
              <div className="bg-white border border-blue-100 rounded-lg p-3">
                <div className="font-semibold text-blue-900 mb-2">Partitioned tables</div>
                <div className="text-blue-800 leading-6">{sharding.partitioned_tables?.join(', ') || '—'}</div>
              </div>
              <div className="bg-white border border-blue-100 rounded-lg p-3">
                <div className="font-semibold text-blue-900 mb-2">Replicated tables</div>
                <div className="text-blue-800 leading-6">{sharding.replicated_tables?.join(', ') || '—'}</div>
              </div>
              <div className="bg-white border border-blue-100 rounded-lg p-3">
                <div className="font-semibold text-blue-900 mb-2">Central tables</div>
                <div className="text-blue-800 leading-6">{sharding.central_tables?.join(', ') || '—'}</div>
              </div>
            </div>
          </div>
        )}
        {display?.indexes_applied !== undefined && (
          <div className={`text-sm font-medium ${display.indexes_applied ? 'text-green-600' : 'text-yellow-600'}`}>
            {display.indexes_applied
              ? `✓ ${display.index_count} indexes are applied to this database`
              : '⚠ No custom indexes detected (baseline mode)'}
          </div>
        )}
      </div>

      {loading && <LoadingSpinner message="Running benchmark queries…" />}

      {display && !loading && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Results</h2>
          {display.results?.map((result, idx) => {
            const before = baseline?.results?.[idx];
            const after  = comparison?.results?.[idx];
            const hasComparison = before && after;

            return (
              <div key={result.query_name} className="card space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-sm">{result.query_name}</h3>
                  {hasComparison && (
                    <span className={`badge-${after.duration_ms < before.duration_ms ? 'green' : 'red'} text-xs`}>
                      {after.duration_ms < before.duration_ms ? '▼' : '▲'}{' '}
                      {Math.abs(((after.duration_ms - before.duration_ms) / before.duration_ms) * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <code className="block text-xs bg-gray-50 p-2 rounded text-gray-700 overflow-x-auto">
                  {result.query}
                </code>

                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="border border-gray-200 px-3 py-1.5 text-left font-medium">Metric</th>
                      {hasComparison ? (
                        <>
                          <th className="border border-gray-200 px-3 py-1.5 text-left text-yellow-700">Before</th>
                          <th className="border border-gray-200 px-3 py-1.5 text-left text-green-700">After</th>
                        </>
                      ) : (
                        <th className="border border-gray-200 px-3 py-1.5 text-left">Value</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="border border-gray-200 px-3 py-1.5 font-medium">Access Type</td>
                      {hasComparison ? (
                        <>
                          <td className="border border-gray-200 px-3 py-1.5 text-yellow-700 font-mono">{before.type}</td>
                          <td className="border border-gray-200 px-3 py-1.5 text-green-700 font-mono font-bold">{after.type}</td>
                        </>
                      ) : (
                        <td className="border border-gray-200 px-3 py-1.5 font-mono">{result.type}</td>
                      )}
                    </tr>
                    <tr>
                      <td className="border border-gray-200 px-3 py-1.5 font-medium">Rows Examined</td>
                      {hasComparison ? (
                        <>
                          <td className="border border-gray-200 px-3 py-1.5 text-yellow-700">{before.rows_examined?.toLocaleString()}</td>
                          <td className="border border-gray-200 px-3 py-1.5 text-green-700 font-bold">{after.rows_examined?.toLocaleString()}</td>
                        </>
                      ) : (
                        <td className="border border-gray-200 px-3 py-1.5">{result.rows_examined?.toLocaleString()}</td>
                      )}
                    </tr>
                    <tr>
                      <td className="border border-gray-200 px-3 py-1.5 font-medium">Extra</td>
                      {hasComparison ? (
                        <>
                          <td className="border border-gray-200 px-3 py-1.5 text-yellow-700 text-xs">{before.extra || '—'}</td>
                          <td className="border border-gray-200 px-3 py-1.5 text-green-700 text-xs font-medium">{after.extra || '—'}</td>
                        </>
                      ) : (
                        <td className="border border-gray-200 px-3 py-1.5 text-xs">{result.extra || '—'}</td>
                      )}
                    </tr>
                    <tr>
                      <td className="border border-gray-200 px-3 py-1.5 font-medium">Avg Time (ms)</td>
                      {hasComparison ? (
                        <>
                          <td className="border border-gray-200 px-3 py-1.5 text-yellow-700">{before.duration_ms.toFixed(3)}</td>
                          <td className="border border-gray-200 px-3 py-1.5 text-green-700 font-bold">{after.duration_ms.toFixed(3)}</td>
                        </>
                      ) : (
                        <td className="border border-gray-200 px-3 py-1.5">{result.duration_ms.toFixed(3)}</td>
                      )}
                    </tr>
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
