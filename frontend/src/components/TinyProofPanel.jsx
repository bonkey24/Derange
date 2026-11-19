import React, { useState, useEffect } from 'react';
import { apiService } from '../api/client';

export default function TinyProofPanel({ roomId, activeRoom = null }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('seating'); // 'seating' or 'retest'
  const [retestN, setRetestN] = useState(3); // 3 or 4 for derangement example

  useEffect(() => {
    if (!roomId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    apiService
      .getTinyProof(roomId)
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        console.error('Failed to load tiny-room proof:', err);
        setError('Failed to load tiny-room proof data.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [roomId]);

  if (!roomId) return null;

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-xs text-slate-400">
        Loading tiny-room proof...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-xl border border-red-200 p-4 text-xs text-red-600">
        {error}
      </div>
    );
  }

  if (!data) return null;

  // Select the active proof object based on mode and chosen n
  let activeProof = null;
  if (mode === 'seating') {
    activeProof = data.seating;
  } else {
    if (data.is_mini_example) {
      activeProof = retestN === 4 ? data.retest_n4 : data.retest_n3;
    } else {
      activeProof = data.retest;
    }
  }

  if (!activeProof) return null;

  const isN3Derangement = mode === 'retest' && activeProof.n === 3;

  return (
    <div className="mt-8 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-slate-100 bg-slate-50/50">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🔬</span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">
                  See it on a tiny room
                </h3>
                <span className="text-[10px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">
                  Exhaustive Brute-Force Proof
                </span>
                {data.is_mini_example && (
                  <span className="text-[10px] bg-amber-100 text-amber-800 font-semibold px-2 py-0.5 rounded-full">
                    Mini Example
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                To prove that the formula gives the exact right answer, we list and check every single arrangement one by one on a small room.
              </p>
            </div>
          </div>

          {/* Mode Toggle Buttons */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setMode('seating')}
              className={`px-3 py-1.5 rounded-md transition-all cursor-pointer ${
                mode === 'seating'
                  ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Seating rules
            </button>
            <button
              type="button"
              onClick={() => setMode('retest')}
              className={`px-3 py-1.5 rounded-md transition-all cursor-pointer ${
                mode === 'retest'
                  ? 'bg-white text-purple-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Retest (nobody keeps their seat)
            </button>
          </div>
        </div>

        {/* Mini Example banner if active room > 5 */}
        {data.is_mini_example && (
          <div className="mt-3 p-3 bg-amber-50/90 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
            <span className="text-base leading-none">💡</span>
            <div>
              <span className="font-bold">Mini Example:</span>{' '}
              {data.reason || 'Your room is larger than 5 students, so here is the same idea on a small room.'}{' '}
              (Listing every arrangement for large rooms would produce millions of rows).
            </div>
          </div>
        )}

        {/* Retest N selector if mini example */}
        {mode === 'retest' && data.is_mini_example && (
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-600">Choose room size:</span>
            <button
              type="button"
              onClick={() => setRetestN(3)}
              className={`px-2.5 py-1 rounded border text-xs font-mono font-bold transition-all cursor-pointer ${
                retestN === 3
                  ? 'bg-purple-100 text-purple-800 border-purple-300'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              n = 3 (D3 = 2)
            </button>
            <button
              type="button"
              onClick={() => setRetestN(4)}
              className={`px-2.5 py-1 rounded border text-xs font-mono font-bold transition-all cursor-pointer ${
                retestN === 4
                  ? 'bg-purple-100 text-purple-800 border-purple-300'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              n = 4 (D4 = 9)
            </button>
          </div>
        )}
      </div>

      {/* Body: Summary & Table */}
      <div className="p-5 space-y-4">
        {/* Summary Card Above Table */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">
              Exhaustive Count Summary
            </div>
            <div className="text-sm font-bold text-slate-900 flex flex-wrap items-center gap-2">
              <span className="font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                {activeProof.all} arrangements
              </span>
              <span className="text-slate-300">•</span>
              <span className="font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                {activeProof.valid} valid
              </span>
              <span className="text-slate-300">•</span>
              <span className="font-mono text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                {activeProof.invalid} invalid
              </span>
            </div>

            {/* Formula line below summary */}
            <div className="mt-2 text-xs text-slate-700 flex flex-wrap items-center gap-2">
              <span className="font-medium">Formula:</span>
              <code className="bg-white border border-slate-200 px-2 py-0.5 rounded font-mono text-xs text-slate-800">
                {activeProof.formula_str}
              </code>
              <span className="text-slate-500 font-medium">
                (matches the list)
              </span>
            </div>
          </div>

          {/* Green Matches Badge */}
          <div>
            {activeProof.matches ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-100 border border-emerald-300 text-emerald-900 font-bold text-xs shadow-2xs">
                <span>✓</span>
                <span>Matches</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-100 border border-rose-300 text-rose-900 font-bold text-xs">
                <span>✕</span>
                <span>Mismatch</span>
              </span>
            )}
          </div>
        </div>

        {/* Highlight callout for n=3 Retest Derangements */}
        {isN3Derangement && (
          <div className="p-3 bg-purple-50/90 border border-purple-200 rounded-lg text-xs text-purple-900 flex items-start gap-2">
            <span className="text-base leading-none">⭐</span>
            <div>
              <span className="font-bold">Highlighting n = 3 Retest Derangements (D3 = 2):</span>{' '}
              Out of all 6 possible seating arrangements, exactly <strong>2</strong> shift every single student into a different seat (
              <span className="font-mono font-semibold">S1→2, S2→3, S3→1</span> and{' '}
              <span className="font-mono font-semibold">S1→3, S2→1, S3→2</span>). In the other 4 arrangements, at least one student keeps their old seat.
            </div>
          </div>
        )}

        {/* Scrollable Arrangements Table */}
        <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
          <div className="max-h-[380px] overflow-y-auto overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-slate-100/80 sticky top-0 border-b border-slate-200 z-10 text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3 w-12 text-center">#</th>
                  <th className="py-2.5 px-4">Seat Assignment</th>
                  <th className="py-2.5 px-4 w-32">Result</th>
                  <th className="py-2.5 px-4">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {activeProof.arrangements.map((item) => {
                  const isValid = item.is_valid;
                  const isHighlightedDerangement = isN3Derangement && isValid;

                  return (
                    <tr
                      key={item.id}
                      className={`transition-colors ${
                        isHighlightedDerangement
                          ? 'bg-purple-50/70 border-l-4 border-l-purple-600 font-medium'
                          : isValid
                          ? 'hover:bg-emerald-50/30'
                          : 'hover:bg-rose-50/20'
                      }`}
                    >
                      {/* # Column */}
                      <td className="py-2 px-3 text-center font-mono text-slate-500 font-bold text-[11px]">
                        {item.id}
                      </td>

                      {/* Seat Assignment Column */}
                      <td className="py-2 px-4">
                        <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                          {item.assignment_items ? (
                            item.assignment_items.map((pair) => (
                              <span
                                key={pair.student}
                                className={`px-1.5 py-0.5 rounded border text-[11px] font-semibold ${
                                  isHighlightedDerangement
                                    ? 'bg-purple-100 text-purple-900 border-purple-200'
                                    : isValid
                                    ? 'bg-slate-50 text-slate-800 border-slate-200'
                                    : item.fixed_points?.includes(pair.student) ||
                                      item.violating_students?.includes(pair.student)
                                    ? 'bg-rose-100 text-rose-900 border-rose-300 font-bold'
                                    : 'bg-slate-50 text-slate-600 border-slate-200'
                                }`}
                              >
                                {pair.student}→{pair.seat}
                              </span>
                            ))
                          ) : (
                            <span>{item.assignment}</span>
                          )}
                        </div>
                      </td>

                      {/* Result Badge */}
                      <td className="py-2 px-4 whitespace-nowrap">
                        {isValid ? (
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              isHighlightedDerangement
                                ? 'bg-purple-100 text-purple-800 border border-purple-300'
                                : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            }`}
                          >
                            <span>✓</span>
                            <span>{isHighlightedDerangement ? 'Derangement' : 'Valid'}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                            <span>✕</span>
                            <span>Invalid</span>
                          </span>
                        )}
                      </td>

                      {/* Reason Column */}
                      <td className="py-2 px-4 text-xs">
                        {isValid ? (
                          <span className={isHighlightedDerangement ? 'text-purple-700 font-semibold' : 'text-emerald-700 font-medium'}>
                            {item.reason}
                          </span>
                        ) : (
                          <span className="text-rose-600 font-medium">
                            {item.reason}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
