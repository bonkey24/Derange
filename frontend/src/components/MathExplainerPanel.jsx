import React, { useState, useEffect } from 'react';
import { apiService } from '../api/client';
import TinyProofPanel from './TinyProofPanel';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

/**
 * Robustly format large numbers with thousands separators using BigInt
 * to prevent any loss of precision for high-dimensional factorials.
 */
export function formatLargeNumber(val) {
  if (val === null || val === undefined || val === '') return '0';
  try {
    const str = String(val).trim();
    const isNegative = str.startsWith('-');
    const cleanStr = isNegative ? str.slice(1) : str;

    if (cleanStr.includes('.')) {
      const [intPart, decPart] = cleanStr.split('.');
      const formattedInt = BigInt(intPart).toLocaleString();
      return `${isNegative ? '-' : ''}${formattedInt}.${decPart}`;
    }

    const big = BigInt(cleanStr);
    return `${isNegative ? '-' : ''}${big.toLocaleString()}`;
  } catch {
    return String(val);
  }
}

/**
 * Compact visual representation of the classroom grid.
 * Reuses the styling semantics of SeatingGrid (seat indices, front of room, desk foot bar).
 * Responsive for small rooms (3x4) and large rooms (6x9).
 */
function MiniSeatGrid({ rows, cols, forbiddenSeats = [], mode = 'neutral' }) {
  const numRows = Number(rows) || 3;
  const numCols = Number(cols) || 4;
  const forbiddenSet = new Set(forbiddenSeats);
  const isLargeGrid = numCols > 6 || numRows > 5;

  return (
    <div className="p-3 bg-slate-50/90 rounded-xl border border-slate-200 w-full max-w-[340px] shadow-2xs overflow-hidden">
      {/* Front of room marker */}
      <div className="mb-2 py-0.5 px-2 bg-slate-200/80 border border-slate-300 text-slate-600 text-center rounded text-[9px] font-bold uppercase tracking-wider select-none">
        ▲ Front of Room ▲
      </div>

      <div className="overflow-x-auto pb-1 max-w-full">
        <div
          className="grid gap-1 mx-auto justify-center"
          style={{
            gridTemplateColumns: `repeat(${numCols}, minmax(${isLargeGrid ? '26px' : '32px'}, 1fr))`,
            minWidth: isLargeGrid ? `${numCols * 28}px` : undefined,
          }}
        >
          {Array.from({ length: numRows }).map((_, r) => (
            <React.Fragment key={`row-${r}`}>
              {Array.from({ length: numCols }).map((_, c) => {
                const seatIndex = r * numCols + c;
                const isForbidden = forbiddenSet.has(seatIndex);

                let cellStyle = 'bg-white border-slate-200 text-slate-500';
                let badge = `#${seatIndex}`;

                if (mode === 'norules') {
                  cellStyle = 'bg-indigo-50/80 border-indigo-200 text-indigo-700';
                  badge = '✓';
                } else if (mode === 'forbidden') {
                  if (isForbidden) {
                    cellStyle = 'bg-rose-100 border-rose-300 text-rose-700 font-bold ring-1 ring-rose-400/40';
                    badge = '🚫';
                  } else {
                    cellStyle = 'bg-white border-slate-200 text-slate-400';
                    badge = `#${seatIndex}`;
                  }
                } else if (mode === 'valid') {
                  if (isForbidden) {
                    cellStyle = 'bg-slate-100 border-dashed border-slate-300 text-slate-400 line-through opacity-60';
                    badge = '✕';
                  } else {
                    cellStyle = 'bg-emerald-50 border-emerald-300 text-emerald-800 font-semibold';
                    badge = '✓';
                  }
                } else if (mode === 'derangement') {
                  cellStyle = 'bg-purple-50 border-purple-200 text-purple-700 font-medium';
                  badge = '≠';
                }

                return (
                  <div
                    key={`cell-${seatIndex}`}
                    className={`flex flex-col items-center justify-between p-0.5 rounded border text-center transition-all ${
                      isLargeGrid ? 'min-h-[30px]' : 'min-h-[36px]'
                    } ${cellStyle}`}
                    title={`Desk #${seatIndex}${isForbidden ? ' (Forbidden desk)' : ''}`}
                  >
                    <span className="text-[7px] sm:text-[8px] font-mono opacity-60 leading-none">
                      #{seatIndex}
                    </span>
                    <span className="text-[9px] sm:text-[10px] font-bold leading-none">
                      {badge}
                    </span>
                    <div
                      className={`h-0.5 w-full rounded-full mt-0.5 ${
                        isForbidden && mode === 'forbidden' ? 'bg-rose-500' : 'bg-slate-200'
                      }`}
                    />
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MathExplainerPanel({ roomId, activeRoom = null }) {
  const [expanded, setExpanded] = useState(true);
  const [showCharts, setShowCharts] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Auto-fetch data on roomId change or initial load
  useEffect(() => {
    if (!roomId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    apiService
      .getMathExplainer(roomId)
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        console.error('Math explainer fetch failed:', err);
        setError('Failed to load mathematical breakdown.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [roomId]);

  if (!roomId) return null;

  const roomRows = data?.rows || activeRoom?.rows || 3;
  const roomCols = data?.cols || activeRoom?.cols || 4;
  const forbiddenSeats = data?.forbidden_seats || [];

  // Filter inclusion-exclusion terms with k >= 1 and r_k > 0 for term cards
  const badSeatingTerms = (data?.inclusion_exclusion_terms || []).filter(
    (t) => t.k > 0 && t.r_k > 0
  );

  // Construct written-out sum expression for the Valid Seatings card
  const buildSumExpression = () => {
    if (!data) return '';
    const nFactStr = formatLargeNumber(data.n_factorial_str || data.n_factorial);
    if (badSeatingTerms.length === 0) {
      return `${nFactStr} = ${formatLargeNumber(data.total_valid_arrangements_str || data.total_valid_arrangements)}`;
    }
    let expr = nFactStr;
    badSeatingTerms.forEach((t) => {
      const raw = t.contribution_str || String(t.contribution || '0');
      const absVal = raw.startsWith('-') ? raw.slice(1) : raw;
      const contribAbs = formatLargeNumber(absVal);
      if (t.sign < 0) {
        expr += ` − ${contribAbs}`;
      } else {
        expr += ` + ${contribAbs}`;
      }
    });
    expr += ` = ${formatLargeNumber(data.total_valid_arrangements_str || data.total_valid_arrangements)}`;
    return expr;
  };

  // Chart configs (plain-English labels, behind toggle)
  const rookChartData = data
    ? {
        labels: data.rook_polynomial_coefficients.map(
          (_, i) => `${i} forbidden seat${i === 1 ? '' : 's'} picked`
        ),
        datasets: [
          {
            label: 'number of ways',
            data: data.rook_polynomial_coefficients,
            backgroundColor: 'rgba(99, 102, 241, 0.65)',
            borderColor: 'rgb(99, 102, 241)',
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      }
    : null;

  const ieChartData = data
    ? {
        labels: data.inclusion_exclusion_terms.map(
          (t) => `${t.k} rule${t.k === 1 ? '' : 's'} broken`
        ),
        datasets: [
          {
            label: 'number of ways',
            data: data.inclusion_exclusion_terms.map((t) => t.contribution),
            backgroundColor: data.inclusion_exclusion_terms.map((t) =>
              t.contribution >= 0
                ? 'rgba(59, 130, 246, 0.65)'
                : 'rgba(239, 68, 68, 0.65)'
            ),
            borderColor: data.inclusion_exclusion_terms.map((t) =>
              t.contribution >= 0 ? 'rgb(59, 130, 246)' : 'rgb(239, 68, 68)'
            ),
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      }
    : null;

  const chartOptions = (xLabel, yLabel) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: { display: false },
    },
    scales: {
      x: {
        title: { display: true, text: xLabel, font: { size: 11, weight: 'bold' } },
        grid: { display: false },
      },
      y: {
        title: { display: true, text: yLabel, font: { size: 11, weight: 'bold' } },
        beginAtZero: true,
        grid: { color: 'rgba(0,0,0,0.04)' },
      },
    },
  });

  return (
    <div className="mt-4 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Outer Collapsible Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50/80 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-xl">🧮</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">
                How the Math Works
              </span>
              <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded-full font-semibold">
                Step-by-Step Story
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Follow how unrestricted seating, forbidden cells, and derangements combine in plain English.
            </p>
          </div>
        </div>
        <span className="text-slate-400 text-xs font-bold select-none px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 transition-colors">
          {expanded ? '▲ Hide Story' : '▼ Read Story'}
        </span>
      </button>

      {/* Panel Body */}
      {expanded && (
        <div className="border-t border-slate-100 p-4 sm:p-5 space-y-6">
          {loading && (
            <div className="text-center py-8 text-xs text-slate-400">
              Loading mathematical analysis...
            </div>
          )}

          {error && (
            <div className="text-center py-8 text-xs text-red-500 font-medium">
              {error}
            </div>
          )}

          {data && !loading && (
            <>
              {/* Summary Stats Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div className="flex flex-wrap items-center gap-2 sm:gap-4">
                  <span>
                    Enrolled Students: <strong className="text-indigo-600 font-mono">{data.n}</strong>
                  </span>
                  <span className="text-slate-300">•</span>
                  <span>
                    Room Grid: <strong className="text-slate-800 font-mono">{roomRows}×{roomCols}</strong> ({roomRows * roomCols} desks)
                  </span>
                  <span className="text-slate-300">•</span>
                  <span>
                    Forbidden Desks: <strong className="text-rose-600 font-mono">{forbiddenSeats.length}</strong>
                  </span>
                </div>
                <div className="text-slate-500 text-[11px]">
                  All counts computed live from your active room constraints
                </div>
              </div>

              {/* SECTION 1: STEP-BY-STEP STORY CARDS */}
              {data.n === 0 ? (
                /* Friendly empty state when room has 0 students */
                <div className="bg-slate-50 border-2 border-dashed border-slate-200 rounded-xl p-8 text-center space-y-2">
                  <div className="text-3xl">👥</div>
                  <h4 className="text-sm font-bold text-slate-800">Add students to see the math</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                    This room currently has 0 enrolled students. Add students from department rosters in the Setup tab to see the step-by-step seating calculation.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* CARD 1: No Rules */}
                  <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                          1
                        </span>
                        <h4 className="text-sm font-bold text-slate-900">
                          No rules (All possible arrangements)
                        </h4>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                        {data.n}! arrangements
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                      <div className="md:col-span-2 space-y-2">
                        <p className="text-sm text-slate-700 leading-relaxed font-medium break-words">
                          <strong className="text-indigo-600 font-mono font-bold">{data.n}</strong> students can sit in{' '}
                          <strong className="text-slate-900 font-mono font-bold">{data.n}!</strong> ways ={' '}
                          <span className="font-mono font-extrabold text-indigo-700 text-sm sm:text-base bg-indigo-50/80 px-2 py-0.5 rounded border border-indigo-200 inline-block break-all">
                            {formatLargeNumber(data.n_factorial_str || data.n_factorial)}
                          </span>
                          .
                        </p>
                        <p className="text-xs text-slate-500 leading-relaxed">
                          If there were zero restrictions, every student could sit at any available desk. This total serves as our starting baseline before filtering out invalid desks.
                        </p>
                      </div>
                      <div className="flex justify-center md:justify-end max-w-full overflow-hidden">
                        <MiniSeatGrid
                          rows={roomRows}
                          cols={roomCols}
                          forbiddenSeats={forbiddenSeats}
                          mode="norules"
                        />
                      </div>
                    </div>

                    {/* In plain words box */}
                    <div className="bg-amber-50/80 border border-amber-200/70 rounded-lg p-2.5 text-xs text-amber-900 flex items-start gap-2">
                      <span className="text-base leading-none">💡</span>
                      <div>
                        <span className="font-bold uppercase tracking-wider text-[10px] text-amber-800 block mb-0.5">
                          In plain words
                        </span>
                        <span>
                          Start with every possible seating arrangement, assuming no student has any desk restrictions.
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* CARDS 2..m: Remove the bad seatings */}
                  {badSeatingTerms.length === 0 ? (
                    /* Friendly note when room has 0 forbidden cells */
                    <div className="bg-emerald-50/80 border border-emerald-200 rounded-xl p-3.5 text-xs text-emerald-800 flex items-center gap-2.5">
                      <span className="text-base">✓</span>
                      <span className="font-medium">
                        No forbidden seats, so every seating is valid.
                      </span>
                    </div>
                  ) : (
                    badSeatingTerms.map((term, idx) => {
                      const stepNumber = 2 + idx;
                      const isOdd = term.k % 2 === 1;
                      const signChar = term.sign < 0 ? '−' : '+';
                      const rawContrib = term.contribution_str || String(term.contribution || '0');
                      const absContribStr = rawContrib.startsWith('-') ? rawContrib.slice(1) : rawContrib;
                      const absContribution = formatLargeNumber(absContribStr);
                      const factorialTermFormatted = formatLargeNumber(
                        term.factorial_term_str || term.factorial_term
                      );
                      const rKFormatted = formatLargeNumber(term.r_k);

                      return (
                        <div
                          key={`term-${term.k}`}
                          className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-3"
                        >
                          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                            <div className="flex items-center gap-2">
                              <span className="w-6 h-6 rounded-full bg-rose-100 text-rose-700 font-bold text-xs flex items-center justify-center">
                                {stepNumber}
                              </span>
                              <h4 className="text-sm font-bold text-slate-900">
                                Remove the bad seatings ({term.k} rule{term.k > 1 ? 's' : ''} broken)
                              </h4>
                            </div>
                            <span
                              className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${
                                isOdd
                                  ? 'bg-rose-50 text-rose-700 border-rose-200'
                                  : 'bg-blue-50 text-blue-700 border-blue-200'
                              }`}
                            >
                              k = {term.k} ({signChar}{absContribution})
                            </span>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                            <div className="md:col-span-2 space-y-2">
                              {/* Math Display */}
                              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 font-mono text-xs sm:text-sm text-slate-900 break-words">
                                <span className={isOdd ? 'text-rose-600 font-bold' : 'text-blue-600 font-bold'}>
                                  {signChar}
                                </span>{' '}
                                <span className="font-bold">{rKFormatted}</span> × ({data.n}−{term.k})! ={' '}
                                <span className="text-slate-600">
                                  {rKFormatted} × {factorialTermFormatted}
                                </span>{' '}
                                ={' '}
                                <span
                                  className={`font-extrabold ${
                                    isOdd ? 'text-rose-600' : 'text-blue-600'
                                  }`}
                                >
                                  {signChar}
                                  {absContribution}
                                </span>
                              </div>

                              {/* Rule explanation sentence */}
                              <p className="text-xs text-slate-600 leading-relaxed font-medium">
                                {isOdd
                                  ? `Odd k subtracts the seatings that break ${term.k} rule${term.k > 1 ? 's' : ''} at once.`
                                  : `Even k adds back what was subtracted twice when accounting for ${term.k} rules.`}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                r<sub>{term.k}</sub> = {rKFormatted} counts independent placements of forbidden seats, and ({data.n}−{term.k})! = {factorialTermFormatted} counts ways to place the remaining students.
                              </p>
                            </div>

                            <div className="flex justify-center md:justify-end max-w-full overflow-hidden">
                              <MiniSeatGrid
                                rows={roomRows}
                                cols={roomCols}
                                forbiddenSeats={forbiddenSeats}
                                mode="forbidden"
                              />
                            </div>
                          </div>

                          {/* In plain words box */}
                          <div className="bg-amber-50/80 border border-amber-200/70 rounded-lg p-2.5 text-xs text-amber-900 flex items-start gap-2">
                            <span className="text-base leading-none">💡</span>
                            <div>
                              <span className="font-bold uppercase tracking-wider text-[10px] text-amber-800 block mb-0.5">
                                In plain words
                              </span>
                              <span>
                                {term.k === 1 ? (
                                  <>
                                    <strong>rook polynomial</strong> = &ldquo;ways to pick forbidden seats that do not share a row or a column&rdquo;
                                  </>
                                ) : (
                                  <>
                                    <strong>inclusion-exclusion</strong> = &ldquo;add everything, subtract the overlaps, add back what you subtracted twice&rdquo;
                                  </>
                                )}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}

                  {/* FINAL CARD: Valid Seatings */}
                  <div className="bg-white rounded-xl border-2 border-emerald-300/80 p-4 sm:p-5 shadow-xs space-y-3 bg-gradient-to-br from-white to-emerald-50/20">
                    <div className="flex items-center justify-between pb-2 border-b border-emerald-100">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-800 font-bold text-xs flex items-center justify-center">
                          ✓
                        </span>
                        <h4 className="text-sm font-bold text-emerald-950">
                          Valid seatings (Running total)
                        </h4>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-emerald-700 bg-emerald-100 px-2.5 py-0.5 rounded-full">
                        Final Total
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                      <div className="md:col-span-2 space-y-3">
                        <div className="p-3 bg-emerald-50/80 border border-emerald-200 rounded-lg">
                          <div className="text-[11px] text-emerald-700 uppercase font-bold tracking-wider mb-1">
                            Sum written out
                          </div>
                          <div className="font-mono text-xs sm:text-sm font-semibold text-slate-800 break-all leading-relaxed">
                            {buildSumExpression()}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs text-slate-500 font-medium">Total valid seating arrangements:</div>
                          <div className="text-xl sm:text-2xl font-mono font-black text-emerald-700 break-all">
                            {formatLargeNumber(data.total_valid_arrangements_str || data.total_valid_arrangements)}
                          </div>
                        </div>
                        <p className="text-xs text-slate-600">
                          These are the exact legal seating arrangements that satisfy every forbidden desk rule on the board.
                        </p>
                      </div>

                      <div className="flex justify-center md:justify-end max-w-full overflow-hidden">
                        <MiniSeatGrid
                          rows={roomRows}
                          cols={roomCols}
                          forbiddenSeats={forbiddenSeats}
                          mode="valid"
                        />
                      </div>
                    </div>

                    {/* In plain words box */}
                    <div className="bg-amber-50/80 border border-amber-200/70 rounded-lg p-2.5 text-xs text-amber-900 flex items-start gap-2">
                      <span className="text-base leading-none">💡</span>
                      <div>
                        <span className="font-bold uppercase tracking-wider text-[10px] text-amber-800 block mb-0.5">
                          In plain words
                        </span>
                        <span>
                          <strong>inclusion-exclusion</strong> = &ldquo;add everything, subtract the overlaps, add back what you subtracted twice&rdquo;
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* LAST CARD: Retest (derangement) */}
                  {data.derangement_info && (
                    <div className="bg-white rounded-xl border border-purple-200 p-4 sm:p-5 shadow-xs space-y-3 bg-gradient-to-br from-white to-purple-50/20">
                      <div className="flex items-center justify-between pb-2 border-b border-purple-100">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-purple-100 text-purple-700 font-bold text-xs flex items-center justify-center">
                            !
                          </span>
                          <h4 className="text-sm font-bold text-purple-950">
                            Retest (derangement)
                          </h4>
                        </div>
                        <span className="text-[11px] font-mono font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">
                          !{data.n} Zero Fixed Points
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                        <div className="md:col-span-2 space-y-3">
                          <p className="text-sm text-slate-800 leading-relaxed break-words">
                            If nobody may keep their old seat, only{' '}
                            <strong className="font-mono text-purple-700 font-bold break-all">
                              D({data.n}) = {formatLargeNumber(data.derangement_info.D_n_str || data.derangement_info.D_n)}
                            </strong>{' '}
                            of the{' '}
                            <strong className="font-mono text-slate-800 font-bold break-all">
                              {formatLargeNumber(data.derangement_info.n_factorial_str || data.derangement_info.n_factorial)}
                            </strong>{' '}
                            seatings work, which is{' '}
                            <span className="inline-block bg-purple-100 text-purple-800 font-mono font-bold px-1.5 py-0.5 rounded">
                              {data.derangement_info.percentage ?? ((data.derangement_info.ratio || 0) * 100).toFixed(2)}%
                            </span>
                            , about 1/e (36.8%), for any room size.
                          </p>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-center text-xs">
                            <div className="p-2 bg-purple-50/70 border border-purple-100 rounded-lg overflow-hidden">
                              <div className="text-[10px] text-purple-600 font-bold uppercase">D({data.n})</div>
                              <div className="font-mono font-bold text-slate-900 truncate" title={formatLargeNumber(data.derangement_info.D_n_str || data.derangement_info.D_n)}>
                                {formatLargeNumber(data.derangement_info.D_n_str || data.derangement_info.D_n)}
                              </div>
                            </div>
                            <div className="p-2 bg-purple-50/70 border border-purple-100 rounded-lg overflow-hidden">
                              <div className="text-[10px] text-purple-600 font-bold uppercase">{data.n}!</div>
                              <div className="font-mono font-bold text-slate-900 truncate" title={formatLargeNumber(data.derangement_info.n_factorial_str || data.derangement_info.n_factorial)}>
                                {formatLargeNumber(data.derangement_info.n_factorial_str || data.derangement_info.n_factorial)}
                              </div>
                            </div>
                            <div className="p-2 bg-purple-50/70 border border-purple-100 rounded-lg overflow-hidden">
                              <div className="text-[10px] text-purple-600 font-bold uppercase">Ratio</div>
                              <div className="font-mono font-bold text-purple-700">
                                {data.derangement_info.percentage ?? ((data.derangement_info.ratio || 0) * 100).toFixed(2)}%
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="flex justify-center md:justify-end max-w-full overflow-hidden">
                          <MiniSeatGrid
                            rows={roomRows}
                            cols={roomCols}
                            forbiddenSeats={forbiddenSeats}
                            mode="derangement"
                          />
                        </div>
                      </div>

                      {/* In plain words box */}
                      <div className="bg-amber-50/80 border border-amber-200/70 rounded-lg p-2.5 text-xs text-amber-900 flex items-start gap-2">
                        <span className="text-base leading-none">💡</span>
                        <div>
                          <span className="font-bold uppercase tracking-wider text-[10px] text-amber-800 block mb-0.5">
                            In plain words
                          </span>
                          <span>
                            <strong>derangement</strong> = &ldquo;everyone ends up in a different seat from before&rdquo;
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* SECTION: TINY-ROOM PROOF */}
              <TinyProofPanel roomId={roomId} activeRoom={activeRoom} />

              {/* SECTION 2: CHARTS BEHIND TOGGLE */}
              {data.n > 0 && (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCharts(!showCharts)}
                    className="w-full flex items-center justify-between p-3.5 bg-slate-50 hover:bg-slate-100 transition-colors rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span>📊</span>
                      <span>{showCharts ? 'Hide charts (details)' : 'Show charts (details)'}</span>
                    </div>
                    <span className="text-slate-400 font-mono text-[11px]">
                      {showCharts ? '▲ Collapse Graphs' : '▼ Expand Graphs'}
                    </span>
                  </button>

                  {showCharts && (
                    <div className="mt-4 space-y-6 p-4 sm:p-5 bg-slate-50/60 rounded-xl border border-slate-200">
                      {/* Rook Polynomial Chart */}
                      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-slate-900">
                            Rook Polynomial Coefficients
                          </h4>
                          <span className="text-[11px] text-slate-500 font-mono">
                            Independent forbidden placements
                          </span>
                        </div>
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 h-64">
                          <Bar
                            data={rookChartData}
                            options={chartOptions(
                              'number of forbidden seats picked together',
                              'number of ways'
                            )}
                          />
                        </div>
                        <p className="text-xs text-slate-600 leading-relaxed">
                          This chart shows how many ways we can choose forbidden seats without picking any two in the same row or column. When seats do not share a row or column, different students can be blocked at the same time.
                        </p>
                      </div>

                      {/* Inclusion-Exclusion Chart */}
                      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-slate-900">
                            Inclusion-Exclusion Term Breakdown
                          </h4>
                          <span className="text-[11px] text-slate-500 font-mono">
                            Alternating sign contributions
                          </span>
                        </div>
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 h-64">
                          <Bar
                            data={ieChartData}
                            options={chartOptions(
                              'number of forbidden seats picked together',
                              'number of ways'
                            )}
                          />
                        </div>
                        <p className="text-xs text-slate-600 leading-relaxed">
                          This chart shows the adjustment made at each step. We add all possibilities in blue, then subtract the forbidden overlaps in red. If we subtracted too much, we add it back in the next step.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
