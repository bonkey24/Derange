import React, { useState, useEffect, useCallback } from 'react';
import { useRoom } from '../context/RoomContext';
import { apiService } from '../api/client';
import SeatingGrid from '../components/SeatingGrid';
import MathExplainerPanel from '../components/MathExplainerPanel';
import Alert from '../components/Alert';

export default function GenerateTab() {
  const { activeRoom, students } = useRoom();

  const [currentResult, setCurrentResult] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  const [selectedPreviousId, setSelectedPreviousId] = useState('');
  const [includeDiagonal, setIncludeDiagonal] = useState(true);

  const [loadingNormal, setLoadingNormal] = useState(false);
  const [loadingRetest, setLoadingRetest] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [alertInfo, setAlertInfo] = useState(null);

  // Load past seating history for the active room
  const loadHistory = useCallback(async () => {
    if (!activeRoom) return;
    setLoadingHistory(true);
    try {
      const res = await apiService.getSeatingResults(activeRoom.id);
      setHistoryList(res.data);
      if (res.data.length > 0) {
        // Default selected previous result for retest to the most recent normal result
        const latestNormal = res.data.find(r => r.type === 'normal') || res.data[0];
        setSelectedPreviousId(String(latestNormal.id));
        // If currentResult is not set, display the latest one
        setCurrentResult(prev => prev || res.data[0]);
      } else {
        setSelectedPreviousId('');
        setCurrentResult(null);
      }
    } catch (err) {
      console.error('Failed to load seating history:', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [activeRoom]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Generate Normal Seating
  const handleGenerateNormal = async () => {
    if (!activeRoom) return;
    setLoadingNormal(true);
    setAlertInfo(null);

    try {
      const res = await apiService.generateSeating({
        room_id: activeRoom.id,
        include_diagonal: includeDiagonal,
      });
      setCurrentResult(res.data);
      setAlertInfo({
        type: 'success',
        message: `Successfully computed optimal seating chart for ${activeRoom.name} using CSP Backtracking!`,
      });
      await loadHistory();
    } catch (err) {
      console.error('Generation failed:', err);
      let msg = 'Failed to generate seating chart.';
      if (err.response?.status === 409) {
        msg = 'No valid seating arrangement found under the current constraints! The conflict or forbidden constraints may be too tight for this room size.';
      } else if (err.response?.data?.error) {
        msg = err.response.data.error;
      }
      setAlertInfo({ type: 'error', message: msg });
    } finally {
      setLoadingNormal(false);
    }
  };

  // Generate Retest Seating
  const handleGenerateRetest = async () => {
    if (!activeRoom) return;
    if (!selectedPreviousId) {
      setAlertInfo({
        type: 'error',
        message: 'Please select a previous seating result to compute a derangement retest against.',
      });
      return;
    }

    setLoadingRetest(true);
    setAlertInfo(null);

    try {
      const res = await apiService.generateRetest({
        room_id: activeRoom.id,
        previous_result_id: parseInt(selectedPreviousId, 10),
        include_diagonal: includeDiagonal,
      });
      setCurrentResult(res.data);
      setAlertInfo({
        type: 'success',
        message: 'Derangement retest seating generated successfully! All students have been moved to new seats.',
      });
      await loadHistory();
    } catch (err) {
      console.error('Retest generation failed:', err);
      let msg = 'Failed to generate retest seating.';
      if (err.response?.status === 409) {
        msg = 'No valid retest arrangement found! Combining the derangement constraint (!n) with adjacency conflicts resulted in 0 feasible permutations.';
      } else if (err.response?.data?.error) {
        msg = err.response.data.error;
      }
      setAlertInfo({ type: 'error', message: msg });
    } finally {
      setLoadingRetest(false);
    }
  };

  if (!activeRoom) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-8 text-center">
        <h3 className="text-base font-bold text-amber-900 mb-1">No Active Room Selected</h3>
        <p className="text-sm text-amber-700">
          Please select or create an active room in the <strong>Setup</strong> tab first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Control Panel Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Seating Engine Controls: {activeRoom.name}
            </h2>
            <p className="text-xs text-slate-500">
              Run backtracking solver with forward checking & MRV heuristics or generate constrained derangements.
            </p>
          </div>

          <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
            <input
              type="checkbox"
              checked={includeDiagonal}
              onChange={(e) => setIncludeDiagonal(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span>Include Diagonal Adjacency (8-neighborhood)</span>
          </label>
        </div>

        {/* Action Buttons Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Action 1: Normal Seating */}
          <div className="p-4 rounded-xl border border-indigo-100 bg-indigo-50/40 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-900 uppercase tracking-wider">
                  Initial Exam Run
                </span>
                <span className="text-[10px] bg-indigo-200 text-indigo-900 px-2 py-0.5 rounded font-mono font-bold">
                  Layer 1 + Layer 2
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1">
                Places all eligible students avoiding forbidden individual desks and adjacency conflicts.
              </p>
            </div>
            <button
              onClick={handleGenerateNormal}
              disabled={loadingNormal || loadingRetest}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm py-2.5 px-4 rounded-lg shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loadingNormal ? 'Executing CSP Solver...' : 'Generate Seating Chart'}
            </button>
          </div>

          {/* Action 2: Retest Derangement */}
          <div className="p-4 rounded-xl border border-purple-100 bg-purple-50/40 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-purple-900 uppercase tracking-wider">
                  Retest Re-seating
                </span>
                <span className="text-[10px] bg-purple-200 text-purple-900 px-2 py-0.5 rounded font-mono font-bold">
                  Derangement (!n)
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1">
                Enforces zero fixed points: strictly forbids students from their previous exam desk.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-[11px] font-semibold text-slate-600 uppercase">
                  Base Exam:
                </label>
                <select
                  value={selectedPreviousId}
                  onChange={(e) => setSelectedPreviousId(e.target.value)}
                  className="w-full text-xs border border-purple-200 bg-white rounded px-2.5 py-1.5 focus:ring-2 focus:ring-purple-500 outline-none"
                  disabled={historyList.length === 0}
                >
                  {historyList.length === 0 ? (
                    <option value="">No past results available</option>
                  ) : (
                    historyList.map(item => (
                      <option key={item.id} value={item.id}>
                        #{item.id} ({item.type}) - {new Date(item.generated_at).toLocaleTimeString()}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <button
                onClick={handleGenerateRetest}
                disabled={loadingNormal || loadingRetest || !selectedPreviousId}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold text-sm py-2 px-4 rounded-lg shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loadingRetest ? 'Solving Derangement...' : 'Generate Retest Seating'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Alert / Notification */}
      {alertInfo && (
        <Alert
          type={alertInfo.type}
          message={alertInfo.message}
          onClose={() => setAlertInfo(null)}
        />
      )}

      {/* MAIN CONTENT AREA: CURRENT SEATING GRID + HISTORY SIDEBAR */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Visual Seating Grid (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          {currentResult ? (
            <div>
              {/* Active Result Banner */}
              <div className="mb-3 flex flex-wrap items-center justify-between p-3 bg-white rounded-lg border border-slate-200 text-xs gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-700">Displaying Result #{currentResult.id}</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                      currentResult.type === 'retest'
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                    }`}
                  >
                    {currentResult.type === 'retest' ? 'Retest (Derangement !n)' : 'Normal Exam'}
                  </span>
                </div>
                <div className="text-slate-400 text-[11px]">
                  Generated: {new Date(currentResult.generated_at).toLocaleString()}
                </div>
              </div>

              {currentResult.type === 'retest' && (
                <div className="mb-3 p-3 bg-purple-50 border border-purple-200 text-purple-900 rounded-lg text-xs font-medium flex items-center gap-2">
                  <span>ℹ</span>
                  <span>
                    <strong>Derangement Condition Verified:</strong> Each student has been assigned to a desk strictly different from their initial seating position.
                  </span>
                </div>
              )}

              <SeatingGrid
                rows={activeRoom.rows}
                cols={activeRoom.cols}
                assignment={currentResult.assignment || {}}
                students={students}
                title={`Seating Chart: ${activeRoom.name}`}
              />
              <MathExplainerPanel roomId={activeRoom.id} />
            </div>
          ) : (
            <div className="bg-white rounded-xl border-2 border-dashed border-slate-200 p-12 text-center text-slate-400">
              <div className="text-4xl mb-3">📋</div>
              <h3 className="text-sm font-bold text-slate-700 mb-1">No Seating Chart Generated Yet</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Click <strong>"Generate Seating Chart"</strong> above to compute assignments using the combinatorial backtracking solver.
              </p>
            </div>
          )}
        </div>

        {/* History Sidebar (1 col) */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">Run History</h3>
            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
              {historyList.length}
            </span>
          </div>

          {loadingHistory ? (
            <div className="text-center py-6 text-xs text-slate-400">Loading history...</div>
          ) : historyList.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-400">No past runs recorded.</div>
          ) : (
            <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
              {historyList.map((item) => {
                const isSelected = currentResult && currentResult.id === item.id;
                const assignedCount = Object.keys(item.assignment || {}).length;
                return (
                  <div
                    key={item.id}
                    onClick={() => setCurrentResult(item)}
                    className={`p-3 rounded-lg border transition-all cursor-pointer text-xs ${
                      isSelected
                        ? 'border-indigo-600 bg-indigo-50/60 ring-1 ring-indigo-500/20'
                        : 'border-slate-100 hover:border-slate-200 bg-slate-50/50 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-800 font-mono">#{item.id}</span>
                      <span
                        className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                          item.type === 'retest'
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-indigo-100 text-indigo-800'
                        }`}
                      >
                        {item.type}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500">
                      {new Date(item.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {assignedCount} seated
                    </div>

                    {isSelected && (
                      <div className="mt-1 text-[10px] text-indigo-600 font-semibold text-right">
                        Viewing
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
