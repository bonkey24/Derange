import React, { useState, useEffect, useCallback } from 'react';
import { useRoom } from '../context/RoomContext';
import { apiService } from '../api/client';
import Alert from '../components/Alert';

export default function ConstraintsTab() {
  const { activeRoom, students } = useRoom();

  const [forbiddenList, setForbiddenList] = useState([]);
  const [conflictList, setConflictList] = useState([]);
  const [_loading, setLoading] = useState(false);
  const [alertInfo, setAlertInfo] = useState(null);

  // Form: Forbidden seat
  const [forbiddenStudentId, setForbiddenStudentId] = useState('');
  const [forbiddenSeatIndex, setForbiddenSeatIndex] = useState(0);
  const [submittingForbidden, setSubmittingForbidden] = useState(false);

  // Form: Conflict pair
  const [studentAId, setStudentAId] = useState('');
  const [studentBId, setStudentBId] = useState('');
  const [submittingConflict, setSubmittingConflict] = useState(false);

  // Fetch constraints for active room
  const loadConstraints = useCallback(async () => {
    if (!activeRoom) return;
    setLoading(true);
    try {
      const [forbidRes, conflictRes] = await Promise.all([
        apiService.getForbiddenConstraints(),
        apiService.getConflictPairs(),
      ]);

      // Filter constraints specifically for the active room
      setForbiddenList(forbidRes.data.filter(c => Number(c.room) === Number(activeRoom.id)));
      setConflictList(conflictRes.data.filter(c => Number(c.room) === Number(activeRoom.id)));
    } catch (err) {
      console.error('Failed to load constraints:', err);
      setAlertInfo({ type: 'error', message: 'Failed to retrieve constraints from backend.' });
    } finally {
      setLoading(false);
    }
  }, [activeRoom]);

  useEffect(() => {
    loadConstraints();
  }, [loadConstraints]);

  // Handle Add Forbidden Seat
  const handleAddForbidden = async (e) => {
    e.preventDefault();
    if (!activeRoom) return;
    if (!forbiddenStudentId) {
      setAlertInfo({ type: 'error', message: 'Please select a student.' });
      return;
    }
    const idx = parseInt(forbiddenSeatIndex, 10);
    if (isNaN(idx) || idx < 0 || idx >= activeRoom.total_seats) {
      setAlertInfo({
        type: 'error',
        message: `Seat index must be between 0 and ${activeRoom.total_seats - 1} for ${activeRoom.name}.`,
      });
      return;
    }

    setSubmittingForbidden(true);
    try {
      await apiService.createForbiddenConstraint({
        room: activeRoom.id,
        student: parseInt(forbiddenStudentId, 10),
        seat_index: idx,
      });
      setAlertInfo({ type: 'success', message: 'Forbidden seat constraint added successfully.' });
      setForbiddenSeatIndex(0);
      await loadConstraints();
    } catch (err) {
      const errorMsg =
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.error ||
        'Failed to add forbidden constraint (may already exist).';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setSubmittingForbidden(false);
    }
  };

  // Handle Add Conflict Pair
  const handleAddConflict = async (e) => {
    e.preventDefault();
    if (!activeRoom) return;
    if (!studentAId || !studentBId) {
      setAlertInfo({ type: 'error', message: 'Please select both Student A and Student B.' });
      return;
    }
    if (studentAId === studentBId) {
      setAlertInfo({ type: 'error', message: 'A student cannot have a conflict constraint with themselves.' });
      return;
    }

    setSubmittingConflict(true);
    try {
      await apiService.createConflictPair({
        room: activeRoom.id,
        student_a: parseInt(studentAId, 10),
        student_b: parseInt(studentBId, 10),
      });
      setAlertInfo({ type: 'success', message: 'Adjacency conflict pair added successfully.' });
      setStudentAId('');
      setStudentBId('');
      await loadConstraints();
    } catch (err) {
      const errorMsg =
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.error ||
        'Failed to add conflict pair (may already exist).';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setSubmittingConflict(false);
    }
  };

  // Handle Delete Forbidden Constraint
  const handleDeleteForbidden = async (id) => {
    try {
      await apiService.deleteForbiddenConstraint(id);
      setForbiddenList(prev => prev.filter(item => item.id !== id));
      setAlertInfo({ type: 'info', message: 'Forbidden constraint removed.' });
    } catch {
      setAlertInfo({ type: 'error', message: 'Failed to remove constraint.' });
    }
  };

  // Handle Delete Conflict Pair
  const handleDeleteConflict = async (id) => {
    try {
      await apiService.deleteConflictPair(id);
      setConflictList(prev => prev.filter(item => item.id !== id));
      setAlertInfo({ type: 'info', message: 'Conflict pair removed.' });
    } catch {
      setAlertInfo({ type: 'error', message: 'Failed to remove conflict pair.' });
    }
  };

  if (!activeRoom) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-8 text-center">
        <h3 className="text-base font-bold text-amber-900 mb-1">No Active Room Selected</h3>
        <p className="text-sm text-amber-700">
          Please go to the <strong>Setup</strong> tab and select or create an active room first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Active Room Context Banner */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">
            Current Target Room
          </span>
          <h2 className="text-lg font-bold text-slate-900">{activeRoom.name}</h2>
          <p className="text-xs text-slate-600">
            Grid: {activeRoom.rows} rows × {activeRoom.cols} columns ({activeRoom.total_seats} total seats, indices 0 to {activeRoom.total_seats - 1})
          </p>
        </div>
        <div className="text-xs text-indigo-800 bg-white/80 px-3 py-2 rounded-lg border border-indigo-100">
          Constraints configured here feed directly into the Rook Polynomial and CSP solvers.
        </div>
      </div>

      {alertInfo && (
        <Alert
          type={alertInfo.type}
          message={alertInfo.message}
          onClose={() => setAlertInfo(null)}
        />
      )}

      {/* TWO COLUMN GRID FOR FORMS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* FORM 1: FORBIDDEN SEAT (LAYER 1) */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-amber-100 text-amber-800 text-[10px] font-bold uppercase px-2 py-0.5 rounded">
              Layer 1
            </span>
            <h3 className="text-base font-bold text-slate-900">Forbidden Seat Constraint</h3>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            Prohibit a specific student from occupying a specific desk index (e.g. accessibility requirement).
          </p>

          <form onSubmit={handleAddForbidden} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Select Student
              </label>
              <select
                value={forbiddenStudentId}
                onChange={(e) => setForbiddenStudentId(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              >
                <option value="">-- Choose Student --</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.roll_no} - {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Forbidden Seat Index (0 to {activeRoom.total_seats - 1})
              </label>
              <input
                type="number"
                min="0"
                max={activeRoom.total_seats - 1}
                value={forbiddenSeatIndex}
                onChange={(e) => setForbiddenSeatIndex(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                required
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Linear Seat #{forbiddenSeatIndex} = Row {Math.floor(forbiddenSeatIndex / activeRoom.cols) + 1}, Col {String.fromCharCode(65 + (forbiddenSeatIndex % activeRoom.cols))}
              </p>
            </div>

            <button
              type="submit"
              disabled={submittingForbidden || students.length === 0}
              className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium text-sm py-2 px-4 rounded-lg transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {submittingForbidden ? 'Adding...' : 'Add Forbidden Seat'}
            </button>
          </form>
        </div>

        {/* FORM 2: CONFLICT PAIR (LAYER 2) */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-rose-100 text-rose-800 text-[10px] font-bold uppercase px-2 py-0.5 rounded">
              Layer 2
            </span>
            <h3 className="text-base font-bold text-slate-900">Pairwise Conflict Constraint</h3>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            Forbid two students from sitting adjacent to each other in this room.
          </p>

          <form onSubmit={handleAddConflict} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Student A
              </label>
              <select
                value={studentAId}
                onChange={(e) => setStudentAId(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              >
                <option value="">-- Choose Student A --</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.roll_no} - {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Student B
              </label>
              <select
                value={studentBId}
                onChange={(e) => setStudentBId(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none"
                required
              >
                <option value="">-- Choose Student B --</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.roll_no} - {s.name}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={submittingConflict || students.length < 2}
              className="w-full bg-rose-600 hover:bg-rose-700 text-white font-medium text-sm py-2 px-4 rounded-lg transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {submittingConflict ? 'Adding...' : 'Add Conflict Pair'}
            </button>
          </form>
        </div>
      </div>

      {/* CONSTRAINTS SUMMARY LISTS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Forbidden Constraints List */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-slate-900">
              Forbidden Seats in {activeRoom.name}
            </h3>
            <span className="text-xs bg-amber-50 text-amber-800 font-semibold px-2 py-0.5 rounded border border-amber-200">
              {forbiddenList.length} defined
            </span>
          </div>

          {forbiddenList.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-400 border border-dashed rounded-lg">
              No forbidden seat constraints defined for this room.
            </div>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
              {forbiddenList.map((item) => {
                const r = Math.floor(item.seat_index / activeRoom.cols) + 1;
                const c = String.fromCharCode(65 + (item.seat_index % activeRoom.cols));
                return (
                  <div
                    key={item.id}
                    className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors text-xs"
                  >
                    <div>
                      <span className="font-mono font-bold text-indigo-700">
                        {item.student_roll_no}
                      </span>{' '}
                      is forbidden from{' '}
                      <span className="font-bold text-slate-800">
                        Seat #{item.seat_index} (R{r}C{c})
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteForbidden(item.id)}
                      className="text-slate-400 hover:text-red-600 p-1 font-bold cursor-pointer"
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Conflict Pairs List */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-slate-900">
              Adjacency Conflicts in {activeRoom.name}
            </h3>
            <span className="text-xs bg-rose-50 text-rose-800 font-semibold px-2 py-0.5 rounded border border-rose-200">
              {conflictList.length} pairs
            </span>
          </div>

          {conflictList.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-400 border border-dashed rounded-lg">
              No adjacency conflict pairs defined for this room.
            </div>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
              {conflictList.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                      {item.student_a_roll_no}
                    </span>
                    <span className="text-slate-400 font-bold">⟷</span>
                    <span className="font-mono font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                      {item.student_b_roll_no}
                    </span>
                    <span className="text-slate-500 text-[11px] ml-1">must NOT sit adjacent</span>
                  </div>
                  <button
                    onClick={() => handleDeleteConflict(item.id)}
                    className="text-slate-400 hover:text-red-600 p-1 font-bold cursor-pointer"
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
