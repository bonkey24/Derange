import React, { useState } from 'react';
import { useRoom } from '../context/RoomContext';
import { apiService } from '../api/client';
import Alert from '../components/Alert';

// Chart.js imports
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

export default function RiskModelTab() {
  const { activeRoom, students } = useRoom();

  const [threshold, setThreshold] = useState(0.75);
  const [numPairs, setNumPairs] = useState(1000);
  const [useRealRoster, setUseRealRoster] = useState(true);
  const [loading, setLoading] = useState(false);
  const [sensitivityLoading, setSensitivityLoading] = useState(false);

  // Response state
  const [results, setResults] = useState(null);
  const [alertInfo, setAlertInfo] = useState(null);

  // Known Conflict Evidence state
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const [pairFeatures, setPairFeatures] = useState([]);
  const [evidenceUsedCount, setEvidenceUsedCount] = useState(0);
  const [evidenceForm, setEvidenceForm] = useState({
    studentA: '',
    studentB: '',
    pastIncidents: 1,
    academicSimilarity: 0.5,
  });

  // Chart data state for sensitivity
  const [chartData, setChartData] = useState(null);

  // Helper to resolve student roll_no to student Name
  const getStudentDisplayName = (rollNo) => {
    const s = students.find((st) => st.roll_no === rollNo);
    return s && s.name ? s.name : rollNo;
  };

  const totalPossiblePairs = students.length >= 2
    ? Math.round((students.length * (students.length - 1)) / 2)
    : 0;

  // Train and Score single run
  const handleTrainAndScore = async () => {
    if (!activeRoom) {
      setAlertInfo({ type: 'warning', message: 'Please select an active room in the Setup tab.' });
      return;
    }
    if (students.length < 2) {
      setAlertInfo({
        type: 'error',
        message: 'At least 2 students are required in the system to evaluate pairwise risk.',
      });
      return;
    }

    setLoading(true);
    setAlertInfo(null);

    try {
      const payload = {
        room_id: activeRoom.id,
        threshold: parseFloat(threshold),
        num_pairs: parseInt(numPairs, 10),
        use_real_roster: useRealRoster,
      };

      // Include pair_features only if user added evidence entries
      if (pairFeatures.length > 0) {
        payload.pair_features = pairFeatures.map((pf) => ({
          student_a: pf.studentA,
          student_b: pf.studentB,
          past_incidents_together: pf.pastIncidents,
          shared_classes_count: 5,
          academic_similarity_score: pf.academicSimilarity,
        }));
      }

      const submittedEvidenceCount = pairFeatures.length;
      const res = await apiService.trainRiskModel(payload);
      setResults(res.data);
      setEvidenceUsedCount(submittedEvidenceCount);

      // Clear evidence after successful run
      const evidenceSuffix = submittedEvidenceCount > 0
        ? ` (${submittedEvidenceCount} pair${submittedEvidenceCount > 1 ? 's' : ''} used manually-entered real evidence)`
        : '';
      setPairFeatures([]);
      setEvidenceForm({ studentA: '', studentB: '', pastIncidents: 1, academicSimilarity: 0.5 });

      setAlertInfo({
        type: 'success',
        message: `Random Forest trained on ${numPairs} pairs; evaluated ${res.data.total_students} students at threshold ${threshold}.${evidenceSuffix}`,
      });

      // Automatically run sensitivity trade-off analysis across multiple thresholds
      runSensitivityAnalysis(res.data.total_students);
    } catch (err) {
      console.error('Risk training failed:', err);
      setAlertInfo({
        type: 'error',
        message: err.response?.data?.error || 'Failed to train and evaluate ML risk model.',
      });
    } finally {
      setLoading(false);
    }
  };

  // Run sensitivity trade-off analysis for Chart.js
  const runSensitivityAnalysis = async (_totalStudents) => {
    setSensitivityLoading(true);
    const thresholdsToTest = [0.50, 0.65, 0.75, 0.85, 0.95];

    try {
      const counts = await Promise.all(
        thresholdsToTest.map(async (t) => {
          try {
            const resp = await apiService.trainRiskModel({
              room_id: activeRoom.id,
              threshold: t,
              num_pairs: 500,
              use_real_roster: useRealRoster,
            });
            return resp.data.count;
          } catch {
            return 0;
          }
        })
      );

      setChartData({
        labels: thresholdsToTest.map((t) => `θ = ${t.toFixed(2)}`),
        datasets: [
          {
            label: 'High-Risk Student Pairs Flagged',
            data: counts,
            backgroundColor: 'rgba(99, 102, 241, 0.75)',
            borderColor: 'rgb(79, 70, 229)',
            borderWidth: 1,
            borderRadius: 6,
          },
        ],
      });
    } catch (err) {
      console.error('Sensitivity test failed:', err);
    } finally {
      setSensitivityLoading(false);
    }
  };

  // Add flagged pair directly to active room's conflict constraints
  const handleAddToConflictConstraints = async (pair) => {
    if (!activeRoom) return;
    const stuA = students.find(s => s.roll_no === pair.student_a);
    const stuB = students.find(s => s.roll_no === pair.student_b);

    if (!stuA || !stuB) {
      setAlertInfo({ type: 'error', message: 'Could not resolve student IDs for constraint creation.' });
      return;
    }

    try {
      await apiService.createConflictPair({
        room: activeRoom.id,
        student_a: stuA.id,
        student_b: stuB.id,
      });
      setAlertInfo({
        type: 'success',
        message: `Added (${pair.student_a} ⟷ ${pair.student_b}) to ${activeRoom.name}'s conflict constraints!`,
      });
    } catch {
      setAlertInfo({
        type: 'warning',
        message: 'This conflict pair may already exist in the active room.',
      });
    }
  };

  // Feature Importance Chart Data
  const importanceChartData = results?.feature_importances ? {
    labels: [
      'Past incidents together',
      'Roll-number closeness',
      'Academic similarity',
      'Shared classes',
    ],
    datasets: [
      {
        label: 'Importance (%)',
        data: [
          Number(((results.feature_importances.past_incidents_together || 0) * 100).toFixed(1)),
          Number(((results.feature_importances.roll_number_proximity || 0) * 100).toFixed(1)),
          Number(((results.feature_importances.academic_similarity_score || 0) * 100).toFixed(1)),
          Number(((results.feature_importances.shared_classes_count || 0) * 100).toFixed(1)),
        ],
        backgroundColor: [
          'rgba(239, 68, 68, 0.75)',   // Red
          'rgba(16, 185, 129, 0.75)',  // Emerald
          'rgba(245, 158, 11, 0.75)',  // Amber
          'rgba(99, 102, 241, 0.75)',  // Indigo
        ],
        borderColor: [
          'rgb(239, 68, 68)',
          'rgb(16, 185, 129)',
          'rgb(245, 158, 11)',
          'rgb(99, 102, 241)',
        ],
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  } : null;

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
      {/* 1. MODEL OVERVIEW & HONESTY NOTE */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="bg-indigo-600 text-white text-[10px] font-bold uppercase px-2 py-0.5 rounded tracking-wide">
                PAIR RISK ESTIMATOR
              </span>
              <h2 className="text-base font-bold text-slate-900">
                Random Forest Pair Risk Estimator
              </h2>
            </div>
                
            <p className="text-xs text-slate-500 mt-1">
              Estimates which pairs of students are riskier to seat close together. It learns from practice data, so it gives a hint, not proof.
            </p>
          </div>
                

          <div className="text-xs bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg text-slate-600 font-medium">
            Cohort: <strong className="text-indigo-600 font-mono">{students.length}</strong> students, <strong className="text-indigo-600 font-mono">{totalPossiblePairs}</strong> possible pairs
          </div>
                
        </div>
                

        {/* Permanent Honesty Note */}
        <div className="p-3 bg-amber-50/90 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-center gap-2.5 font-medium">
          <span className="text-base leading-none">⚠️</span>
          <span>
            <strong>Demo only:</strong> trained on simulated data. Scores are a seating hint, not evidence of cheating.
          </span>
        </div>
                

        {/* 2. "HOW IT WORKS" STRIP (Three small numbered cards) */}
        <div className="space-y-2 pt-1">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
            How It Works
          </div>
                
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Card 1 */}
            <div className="p-3.5 bg-slate-50/80 border border-slate-200/80 rounded-xl space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                  1
                </span>
                <h4 className="text-xs font-bold text-slate-900">
                  Create practice examples
                </h4>
              </div>
                
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Simulated student pairs with different risk levels.
              </p>
            </div>
                

            {/* Card 2 */}
            <div className="p-3.5 bg-slate-50/80 border border-slate-200/80 rounded-xl space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                  2
                </span>
                <h4 className="text-xs font-bold text-slate-900">
                  Train a Random Forest
                </h4>
              </div>
                
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Many small decision trees that each vote on whether a pair is risky.
              </p>
            </div>
                

            {/* Card 3 */}
            <div className="p-3.5 bg-slate-50/80 border border-slate-200/80 rounded-xl space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
                  3
                </span>
                <h4 className="text-xs font-bold text-slate-900">
                  Score your room
                </h4>
              </div>
                
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Every possible pair of students gets a risk score between 0 and 1.
              </p>
            </div>
                
          </div>
                
        </div>
                

        {/* 3. "WHERE THE INPUTS COME FROM" TABLE (Always visible) */}
        <div className="pt-2">
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2.5">
            <div className="flex items-center justify-between pb-1 border-b border-slate-200/70">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wide flex items-center gap-1.5">
                <span>📋</span>
                <span>Where the inputs come from</span>
              </h4>
              <span className="text-[11px] text-slate-400">
                Data origin per feature
              </span>
            </div>
                

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200/60 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="py-1.5 px-2.5">Input Feature</th>
                    <th className="py-1.5 px-2.5 w-28">Source</th>
                    <th className="py-1.5 px-2.5">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr>
                    <td className="py-2 px-2.5 font-semibold text-slate-800">Roll-number closeness</td>
                    <td className="py-2 px-2.5">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                        ✓ Real
                      </span>
                    </td>
                    <td className="py-2 px-2.5 text-slate-600 text-[11px]">from the department rosters</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2.5 font-semibold text-slate-800">Past incidents together</td>
                    <td className="py-2 px-2.5">
                      {results?.feature_sources?.past_incidents_together === 'partial' || pairFeatures.length > 0 || evidenceUsedCount > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-100 text-violet-800 border border-violet-300">
                          ◐ Partial
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                          ~ Simulated
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-2.5 text-slate-600 text-[11px]">Real only for pairs you enter as evidence</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2.5 font-semibold text-slate-800">Academic similarity</td>
                    <td className="py-2 px-2.5">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        ~ Simulated
                      </span>
                    </td>
                    <td className="py-2 px-2.5 text-slate-600 text-[11px]">Simulated baseline values (0.0 to 1.0)</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2.5 font-semibold text-slate-800">Shared classes</td>
                    <td className="py-2 px-2.5">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        ~ Simulated
                      </span>
                    </td>
                    <td className="py-2 px-2.5 text-slate-600 text-[11px]">Simulated course overlap (0 to 5)</td>
                  </tr>
                </tbody>
              </table>
            </div>
                
          </div>
                
        </div>
                

        {/* SLIDERS & PARAMETERS */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {/* Threshold Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-semibold text-slate-700 uppercase">
                How cautious should it be?
              </label>
              <span className="font-mono font-bold text-indigo-600 text-sm">{threshold}</span>
            </div>
                
            <input
              type="range"
              min="0.50"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full accent-indigo-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-medium">
              <span>Flag more pairs</span>
              <span>Flag only the surest pairs</span>
            </div>
                
            <p className="text-[11px] text-slate-500 mt-1.5 leading-normal">
              A lower value flags more pairs; a higher value flags only the ones it is most sure about.
            </p>
          </div>
                

          {/* Training Samples */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-semibold text-slate-700 uppercase">
                Practice examples to learn from
              </label>
              <span className="font-mono font-bold text-slate-800 text-sm">{numPairs} pairs</span>
            </div>
                
            <input
              type="number"
              min="100"
              max="5000"
              step="100"
              value={numPairs}
              onChange={(e) => setNumPairs(parseInt(e.target.value, 10))}
              className="w-full text-sm border border-slate-300 rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            />
            <p className="text-[11px] text-slate-500 mt-1.5 leading-normal">
              Simulated pairs the model studies before scoring your room.
            </p>
          </div>
                
        </div>
                

        {/* Real Roster Toggle Checkbox */}
        <div className="flex items-center gap-3 p-3 bg-indigo-50/60 border border-indigo-100 rounded-lg">
          <input
            type="checkbox"
            id="useRealRosterCheckbox"
            checked={useRealRoster}
            onChange={(e) => setUseRealRoster(e.target.checked)}
            className="h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
          />
          <label htmlFor="useRealRosterCheckbox" className="text-xs text-slate-700 font-medium cursor-pointer">
            <span className="font-bold text-indigo-900">Use department rosters for roll-number proximity</span>
          </label>
        </div>
                

        {/* Known Conflict Evidence (Optional) — Collapsible */}
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setEvidenceExpanded(!evidenceExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold transition-transform duration-200 ${evidenceExpanded ? 'rotate-90' : ''}`}>▶</span>
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">Known Conflict Evidence (Optional)</span>
              {pairFeatures.length > 0 && (
                <span className="text-[10px] font-bold bg-violet-100 text-violet-700 border border-violet-200 px-1.5 py-0.5 rounded-full">
                  {pairFeatures.length} pending
                </span>
              )}
            </div>
                
            <span className="text-[10px] text-slate-400 font-medium hidden sm:block">Tell the model about pairs you already know are risky.</span>
          </button>

          {evidenceExpanded && (
            <div className="p-4 bg-white border-t border-slate-200 space-y-4">
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Tell the model about pairs you already know are risky.
                By default, past incidents and academic similarity are simulated since no real data exists.
                If you have specific real evidence for a pair (e.g. documented prior incidents), add it here
                to override the simulation for that pair only.
              </p>

              {/* Evidence Entry Form */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
                {/* Student A */}
                <div>
                  <label className="text-[10px] font-semibold text-slate-600 uppercase block mb-1">Student A</label>
                  <select
                    value={evidenceForm.studentA}
                    onChange={(e) => setEvidenceForm({ ...evidenceForm, studentA: e.target.value })}
                    className="w-full text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 outline-none focus:ring-2 focus:ring-violet-500 bg-white font-mono"
                  >
                    <option value="">Select student…</option>
                    {students
                      .filter((s) => s.roll_no !== evidenceForm.studentB)
                      .map((s) => (
                        <option key={s.id} value={s.roll_no}>
                          {s.roll_no} — {s.name}
                        </option>
                      ))}
                  </select>
                </div>
                

                {/* Student B */}
                <div>
                  <label className="text-[10px] font-semibold text-slate-600 uppercase block mb-1">Student B</label>
                  <select
                    value={evidenceForm.studentB}
                    onChange={(e) => setEvidenceForm({ ...evidenceForm, studentB: e.target.value })}
                    className="w-full text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 outline-none focus:ring-2 focus:ring-violet-500 bg-white font-mono"
                  >
                    <option value="">Select student…</option>
                    {students
                      .filter((s) => s.roll_no !== evidenceForm.studentA)
                      .map((s) => (
                        <option key={s.id} value={s.roll_no}>
                          {s.roll_no} — {s.name}
                        </option>
                      ))}
                  </select>
                </div>
                

                {/* Past Incidents Together */}
                <div>
                  <label className="text-[10px] font-semibold text-slate-600 uppercase block mb-1">
                    Past Incidents <span className="text-slate-400">(0–10)</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="1"
                    value={evidenceForm.pastIncidents}
                    onChange={(e) => setEvidenceForm({ ...evidenceForm, pastIncidents: Math.min(10, Math.max(0, parseInt(e.target.value, 10) || 0)) })}
                    className="w-full text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 outline-none focus:ring-2 focus:ring-violet-500 font-mono"
                  />
                </div>
                

                {/* Academic Similarity Score */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-[10px] font-semibold text-slate-600 uppercase">Similarity</label>
                    <span className="text-[10px] font-mono font-bold text-violet-600">{evidenceForm.academicSimilarity.toFixed(2)}</span>
                  </div>
                
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={evidenceForm.academicSimilarity}
                    onChange={(e) => setEvidenceForm({ ...evidenceForm, academicSimilarity: parseFloat(e.target.value) })}
                    className="w-full accent-violet-600 cursor-pointer"
                  />
                  <div className="flex justify-between text-[9px] text-slate-400 mt-0.5">
                    <span>0.00</span>
                    <span>1.00</span>
                  </div>
                
                </div>
                
              </div>
                

              {/* Add Evidence Button */}
              <button
                type="button"
                onClick={() => {
                  if (!evidenceForm.studentA || !evidenceForm.studentB) {
                    setAlertInfo({ type: 'warning', message: 'Select both Student A and Student B to add evidence.' });
                    return;
                  }
                  if (evidenceForm.studentA === evidenceForm.studentB) {
                    setAlertInfo({ type: 'warning', message: 'Student A and Student B must be different.' });
                    return;
                  }
                  const isDuplicate = pairFeatures.some(
                    (pf) =>
                      (pf.studentA === evidenceForm.studentA && pf.studentB === evidenceForm.studentB) ||
                      (pf.studentA === evidenceForm.studentB && pf.studentB === evidenceForm.studentA)
                  );
                  if (isDuplicate) {
                    setAlertInfo({ type: 'warning', message: 'Evidence for this pair already exists. Remove the existing entry first.' });
                    return;
                  }
                  setPairFeatures([...pairFeatures, { ...evidenceForm }]);
                  setEvidenceForm({ studentA: '', studentB: '', pastIncidents: 1, academicSimilarity: 0.5 });
                }}
                className="text-xs font-semibold text-violet-700 bg-violet-50 hover:bg-violet-100 border border-violet-200 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
              >
                + Add Evidence
              </button>

              {/* Pending Evidence Chips */}
              {pairFeatures.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {pairFeatures.map((pf, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-1.5 text-[11px] bg-violet-50 border border-violet-200 text-violet-800 px-2.5 py-1 rounded-full font-medium"
                    >
                      <span className="font-mono font-bold">{pf.studentA}</span>
                      <span className="text-violet-400">⟷</span>
                      <span className="font-mono font-bold">{pf.studentB}</span>
                      <span className="text-violet-500">:</span>
                      <span>{pf.pastIncidents} incidents, {pf.academicSimilarity.toFixed(2)} sim</span>
                      <button
                        type="button"
                        onClick={() => setPairFeatures(pairFeatures.filter((_, i) => i !== idx))}
                        className="ml-0.5 text-violet-400 hover:text-rose-500 font-bold cursor-pointer transition-colors"
                        title="Remove this evidence entry"
                      >
                        ✕
                      </button>
                    </div>
                
                  ))}
                </div>
                
              )}
            </div>
                
          )}
        </div>
                

        <button
          onClick={handleTrainAndScore}
          disabled={loading || students.length < 2}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm py-2.5 px-4 rounded-lg shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading ? 'Training & Scoring Cohort...' : 'Train & Score Active Cohort'}
        </button>
      </div>
                

      {alertInfo && (
        <Alert
          type={alertInfo.type}
          message={alertInfo.message}
          onClose={() => setAlertInfo(null)}
        />
      )}

      {/* FEATURE PROVENANCE MATRIX (Dynamic per response) */}
      {results && results.feature_sources && (
        <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs space-y-2">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-2">
              <span>Feature Provenance Matrix</span>
              {(results.pairs_with_real_evidence > 0 || evidenceUsedCount > 0) && (
                <span className="text-[10px] font-bold bg-violet-100 text-violet-700 border border-violet-200 px-2 py-0.5 rounded-full normal-case tracking-normal">
                  {results.pairs_with_real_evidence ?? evidenceUsedCount} pair{(results.pairs_with_real_evidence ?? evidenceUsedCount) !== 1 ? 's' : ''} used manually-entered real evidence
                </span>
              )}
            </h4>
            <span className="text-[11px] text-slate-500">
              Data origin per ML feature
            </span>
          </div>
                
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
            {Object.entries(results.feature_sources)
              .filter(([feat]) => !feat.startsWith('_'))
              .map(([feat, source]) => {
                const fieldCounts = results.feature_sources._field_counts?.[feat];
                return (
                  <div key={feat} className="p-2.5 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1.5">
                    <span className="text-[11px] font-mono text-slate-700 font-semibold truncate" title={feat}>
                      {feat}
                    </span>
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded w-fit ${
                      source === 'real'
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                        : source === 'partial'
                        ? 'bg-violet-100 text-violet-800 border border-violet-300'
                        : 'bg-amber-100 text-amber-800 border border-amber-300'
                    }`}>
                      {source === 'real'
                        ? '✓ Real Data'
                        : source === 'partial'
                        ? `◐ Partial${fieldCounts ? ` (${fieldCounts.real}/${fieldCounts.total} pairs)` : ''}`
                        : '~ Simulated'}
                    </span>
                  </div>
                
                );
              })}
          </div>
                
        </div>
                
      )}

      {/* 5. INFERENCE RESULTS & FEATURE IMPORTANCE */}
      {results && (
        <div className="space-y-6">
          {/* Plain-Language Caption Banner Above Results */}
          <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs font-semibold text-indigo-950 flex items-center justify-between gap-2 shadow-2xs">
            <div className="flex items-center gap-2">
              <span className="text-base leading-none">📊</span>
              <span>
                <strong>Higher score = riskier to sit close together.</strong> Pairs with risk score ≥ {results.threshold} are flagged below.
              </span>
            </div>
                
            <span className="text-[11px] font-mono bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded font-bold whitespace-nowrap">
              Threshold: {results.threshold}
            </span>
          </div>
                

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Flagged Pairs Card (Sorted Riskiest First: "Name A - Name B: 0.82") */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">High-Risk Pairs Flagged</h3>
                  <p className="text-xs text-slate-500">
                    Sorted by predicted risk score (highest risk first).
                  </p>
                </div>
                
                <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-rose-50 text-rose-700 border border-rose-200">
                  {results.count} {results.count === 1 ? 'Pair' : 'Pairs'}
                </span>
              </div>
                

              {results.high_risk_pairs.length === 0 ? (
                <div className="text-center py-10 border border-dashed rounded-lg text-slate-400 text-xs">
                  No high-risk pairs detected at threshold {results.threshold}.
                  <br />
                  Try lowering the threshold slider (e.g. to 0.50 or 0.60) to see more candidate pairs.
                </div>
                
              ) : (
                <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
                  {results.high_risk_pairs.map((pair, idx) => {
                    const nameA = getStudentDisplayName(pair.student_a);
                    const nameB = getStudentDisplayName(pair.student_b);
                    const score = pair.score !== undefined ? pair.score : results.threshold;

                    return (
                      <div
                        key={idx}
                        className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition-colors text-xs gap-2"
                      >
                        <div className="space-y-0.5">
                          <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5 flex-wrap">
                            <span>{nameA}</span>
                            <span className="text-slate-400 font-normal">-</span>
                            <span>{nameB}:</span>
                            <span className="font-mono font-extrabold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200">
                              {Number(score).toFixed(2)}
                            </span>
                          </div>
                
                          <div className="text-[10px] text-slate-400 font-mono">
                            {pair.student_a} ⟷ {pair.student_b}
                          </div>
                
                        </div>
                

                        <button
                          onClick={() => handleAddToConflictConstraints(pair)}
                          className="self-start sm:self-auto text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 bg-white border border-indigo-200 hover:border-indigo-300 px-2.5 py-1 rounded shadow-2xs cursor-pointer transition-colors whitespace-nowrap"
                          title="Enforce in backtracking CSP solver"
                        >
                          + Add to Room Constraints
                        </button>
                      </div>
                
                    );
                  })}
                </div>
                
              )}
            </div>
                

            {/* Right Column: "What mattered most" Feature Importance Bar Chart */}
            <div className="space-y-6">
              {/* Feature Importance Bar Chart */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">What mattered most</h3>
                    <p className="text-xs text-slate-500">
                      Shows how much each feature influenced the model's risk decisions.
                    </p>
                  </div>
                
                  <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold uppercase">
                    Feature Weights
                  </span>
                </div>
                

                {importanceChartData ? (
                  <div className="h-[220px]">
                    <Bar
                      data={importanceChartData}
                      options={{
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (ctx) => ` Influence: ${ctx.parsed.x.toFixed(1)}%`,
                            },
                          },
                        },
                        scales: {
                          x: {
                            beginAtZero: true,
                            ticks: {
                              callback: (v) => `${v}%`,
                              font: { size: 10 },
                            },
                            title: {
                              display: true,
                              text: 'Relative Influence (%)',
                              font: { size: 10, weight: 'bold' },
                            },
                          },
                          y: {
                            ticks: {
                              font: { size: 11, weight: '600' },
                            },
                          },
                        },
                      }}
                    />
                  </div>
                
                ) : (
                  <div className="text-center py-12 text-xs text-slate-400">
                    Feature importance plot will render after training.
                  </div>
                
                )}
                <p className="mt-2 text-xs text-slate-500">These weights show how the practice data was generated, not a real-world finding about students.</p>
              </div>

              {/* Sensitivity Trade-off Analysis */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Threshold Trade-off Analysis</h3>
                    <p className="text-xs text-slate-500">
                      How changing the cautiousness threshold impacts flagged conflict counts.
                    </p>
                  </div>
                
                  {sensitivityLoading && (
                    <span className="text-[11px] text-indigo-600 font-medium animate-pulse">
                      Evaluating...
                    </span>
                  )}
                </div>
                

                {chartData ? (
                  <div className="h-[200px]">
                    <Bar
                      data={chartData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (ctx) => ` Flagged Pairs: ${ctx.parsed.y}`,
                            },
                          },
                        },
                        scales: {
                          y: {
                            beginAtZero: true,
                            ticks: { precision: 0, font: { size: 10 } },
                            title: { display: true, text: 'Flagged Pairs Count', font: { size: 10, weight: 'bold' } },
                          },
                          x: {
                            ticks: { font: { size: 10 } },
                            title: { display: true, text: 'Cautiousness Threshold (θ)', font: { size: 10, weight: 'bold' } },
                          },
                        },
                      }}
                    />
                  </div>
                
                ) : (
                  <div className="text-center py-10 text-xs text-slate-400">
                    Sensitivity plot will render after scoring.
                  </div>
                
                )}
              </div>
                
            </div>
                
          </div>
                
        </div>
                
      )}
    </div>
                
  );
}
