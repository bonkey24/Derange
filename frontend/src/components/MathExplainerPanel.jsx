import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../api/client';
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

export default function MathExplainerPanel({ roomId }) {
  const [expanded, setExpanded] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Reset data when roomId changes so a fresh fetch occurs on next expand
  useEffect(() => {
    setData(null);
    setExpanded(false);
  }, [roomId]);

  const handleToggle = useCallback(async () => {
    const willExpand = !expanded;
    setExpanded(willExpand);

    if (willExpand && !data) {
      setLoading(true);
      setError(null);
      try {
        const res = await apiService.getMathExplainer(roomId);
        setData(res.data);
      } catch (err) {
        console.error('Math explainer fetch failed:', err);
        setError('Failed to load math explainer data.');
      } finally {
        setLoading(false);
      }
    }
  }, [expanded, data, roomId]);

  // -- Chart data builders ----------------------------------------------------

  const SUB = ['₀','₁','₂','₃','₄','₅','₆','₇','₈','₉'];

  const rookChartData = data
    ? {
        labels: data.rook_polynomial_coefficients.map((_, i) =>
          i <= 9 ? `r${SUB[i]}` : `r_${i}`
        ),
        datasets: [
          {
            label: 'Coefficient',
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
        labels: data.inclusion_exclusion_terms.map((t) => `k = ${t.k}`),
        datasets: [
          {
            label: 'Contribution',
            data: data.inclusion_exclusion_terms.map((t) => t.contribution),
            backgroundColor: data.inclusion_exclusion_terms.map((t) =>
              t.contribution >= 0
                ? 'rgba(59, 130, 246, 0.65)'
                : 'rgba(239, 68, 68, 0.65)'
            ),
            borderColor: data.inclusion_exclusion_terms.map((t) =>
              t.contribution >= 0
                ? 'rgb(59, 130, 246)'
                : 'rgb(239, 68, 68)'
            ),
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      }
    : null;

  const chartOptions = (xLabel, yLabel) => ({
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      title: { display: false },
    },
    scales: {
      x: {
        title: { display: true, text: xLabel, font: { size: 11 } },
        grid: { display: false },
      },
      y: {
        title: { display: true, text: yLabel, font: { size: 11 } },
        beginAtZero: true,
        grid: { color: 'rgba(0,0,0,0.04)' },
      },
    },
  });

  // -- Render -----------------------------------------------------------------

  return (
    <div className="mt-4 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50/80 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">📊</span>
          <span className="text-sm font-bold text-slate-900">
            Math Behind This Result
          </span>
          <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded font-mono font-bold">
            Rook Poly + I‑E
          </span>
        </div>
        <span className="text-slate-400 text-xs font-bold select-none">
          {expanded ? '▲ Collapse' : '▼ Expand'}
        </span>
      </button>

      {/* Collapsible Body */}
      {expanded && (
        <div className="border-t border-slate-100 p-5 space-y-6">
          {/* Loading */}
          {loading && (
            <div className="text-center py-8 text-xs text-slate-400">
              Loading math data…
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="text-center py-8 text-xs text-red-500">
              {error}
            </div>
          )}

          {/* Data */}
          {data && !loading && (
            <>
              {/* Info bar */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100">
                <span>
                  <span className="font-bold text-indigo-700">n = {data.n}</span>{' '}
                  students
                </span>
                <span className="text-slate-300">•</span>
                <span>
                  Total valid arrangements:{' '}
                  <span className="font-bold text-slate-900">
                    {data.total_valid_arrangements.toLocaleString()}
                  </span>
                </span>
                <span className="text-slate-300">•</span>
                <span>
                  Forbidden constraints:{' '}
                  <span className="font-bold text-slate-900">
                    {data.rook_polynomial_coefficients.length > 1
                      ? data.rook_polynomial_coefficients.slice(1).reduce((a, b) => a + b, 0)
                      : 0}
                  </span>{' '}
                  cells on board
                </span>
              </div>

              {/* Rook Polynomial Chart */}
              <div>
                <h4 className="text-sm font-bold text-slate-800 mb-2">
                  Rook Polynomial Coefficients
                </h4>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <Bar
                    data={rookChartData}
                    options={chartOptions(
                      'k (number of non-attacking rooks)',
                      'rₖ (count)'
                    )}
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
                  Each bar r<sub>k</sub> shows how many ways k non-attacking
                  rooks can be placed on the forbidden board — i.e., how many
                  sets of k mutually independent forbidden (student, seat) pairs
                  exist.
                </p>
              </div>

              {/* Inclusion-Exclusion Chart */}
              <div>
                <h4 className="text-sm font-bold text-slate-800 mb-2">
                  Inclusion-Exclusion Term Breakdown
                </h4>
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <Bar
                    data={ieChartData}
                    options={chartOptions(
                      'k',
                      'Contribution  ((-1)ᵏ · rₖ · (n−k)!)'
                    )}
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
                  Each bar shows how many ways k forbidden seat-assignments can
                  occur at once — inclusion-exclusion alternately adds{' '}
                  <span className="text-blue-600 font-semibold">(blue)</span>{' '}
                  and subtracts{' '}
                  <span className="text-red-500 font-semibold">(red)</span>{' '}
                  these to avoid double-counting.
                </p>
              </div>

              {/* Derangement Info Card */}
              {data.derangement_info && (
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                  <h4 className="text-sm font-bold text-purple-900 mb-3">
                    Derangement Statistics (Retest Mode)
                  </h4>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-white rounded-lg p-3 text-center border border-purple-100">
                      <div className="text-[10px] uppercase font-bold text-purple-600 tracking-wider mb-1">
                        D(n)
                      </div>
                      <div className="text-lg font-bold text-slate-900">
                        {data.derangement_info.D_n.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 text-center border border-purple-100">
                      <div className="text-[10px] uppercase font-bold text-purple-600 tracking-wider mb-1">
                        n!
                      </div>
                      <div className="text-lg font-bold text-slate-900">
                        {data.derangement_info.n_factorial.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 text-center border border-purple-100">
                      <div className="text-[10px] uppercase font-bold text-purple-600 tracking-wider mb-1">
                        D(n) / n!
                      </div>
                      <div className="text-lg font-bold text-indigo-600">
                        {(data.derangement_info.ratio * 100).toFixed(2)}%
                      </div>
                    </div>
                  </div>
                  <p className="text-[11px] text-purple-800 mt-3 leading-relaxed">
                    Roughly{' '}
                    {(data.derangement_info.ratio * 100).toFixed(1)}% of
                    all arrangements are valid derangements — consistent with
                    the theoretical limit of ~36.8% (1/e) as n grows.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
