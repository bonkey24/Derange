import React, { useState } from 'react';
import { useRoom } from '../context/RoomContext';
import { apiService } from '../api/client';
import Alert from '../components/Alert';

export default function SetupTab() {
  const { rooms, activeRoom, setActiveRoom, students, fetchRooms, fetchStudents } = useRoom();

  // Room Form State
  const [roomName, setRoomName] = useState('');
  const [roomRows, setRoomRows] = useState(3);
  const [roomCols, setRoomCols] = useState(4);
  const [roomSubmitting, setRoomSubmitting] = useState(false);

  // Student Form State
  const [studentName, setStudentName] = useState('');
  const [studentRollNo, setStudentRollNo] = useState('');
  const [studentSubmitting, setStudentSubmitting] = useState(false);

  // Feedback State
  const [alertInfo, setAlertInfo] = useState(null);

  // Inline Edit State
  const [editingStudentId, setEditingStudentId] = useState(null);
  const [editingName, setEditingName] = useState('');

  const handleCreateRoom = async (e) => {
    e.preventDefault();
    if (!roomName.trim()) {
      setAlertInfo({ type: 'error', message: 'Room name is required.' });
      return;
    }
    if (Number(roomRows) <= 0 || Number(roomCols) <= 0) {
      setAlertInfo({ type: 'error', message: 'Rows and Columns must be positive integers.' });
      return;
    }

    setRoomSubmitting(true);
    try {
      const res = await apiService.createRoom({
        name: roomName.trim(),
        rows: parseInt(roomRows, 10),
        cols: parseInt(roomCols, 10),
      });
      setAlertInfo({ type: 'success', message: `Room "${res.data.name}" created successfully!` });
      setRoomName('');
      setRoomRows(3);
      setRoomCols(4);
      await fetchRooms();
      // Auto-set as active if no active room
      if (!activeRoom) {
        setActiveRoom(res.data);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.name?.[0] || err.response?.data?.error || 'Failed to create room.';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setRoomSubmitting(false);
    }
  };

  const handleCreateStudent = async (e) => {
    e.preventDefault();
    if (!studentName.trim() || !studentRollNo.trim()) {
      setAlertInfo({ type: 'error', message: 'Both student name and roll number are required.' });
      return;
    }

    setStudentSubmitting(true);
    try {
      const res = await apiService.createStudent({
        name: studentName.trim(),
        roll_no: studentRollNo.trim().toUpperCase(),
      });
      setAlertInfo({ type: 'success', message: `Student ${res.data.roll_no} (${res.data.name}) added!` });
      setStudentName('');
      setStudentRollNo('');
      await fetchStudents();
    } catch (err) {
      const errorMsg = err.response?.data?.roll_no?.[0] || err.response?.data?.error || 'Failed to add student (Roll number may already exist).';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setStudentSubmitting(false);
    }
  };

  // --- DELETE / EDIT HANDLERS ---

  const handleDeleteStudent = async (student) => {
    if (!window.confirm(`Delete student ${student.roll_no}? This cannot be undone.`)) return;
    try {
      await apiService.deleteStudent(student.id);
      setAlertInfo({ type: 'info', message: `Student ${student.roll_no} deleted.` });
      await fetchStudents();
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.data?.error ||
        (typeof err.response?.data === 'string' ? err.response.data : null) ||
        'Failed to delete student. They may be referenced by existing constraints or results.';
      setAlertInfo({ type: 'error', message: errorMsg });
    }
  };

  const handleStartEdit = (student) => {
    setEditingStudentId(student.id);
    setEditingName(student.name);
  };

  const handleCancelEdit = () => {
    setEditingStudentId(null);
    setEditingName('');
  };

  const handleSaveEdit = async (student) => {
    const trimmed = editingName.trim();
    if (!trimmed) {
      setAlertInfo({ type: 'error', message: 'Student name cannot be empty.' });
      return;
    }
    if (trimmed === student.name) {
      handleCancelEdit();
      return;
    }
    try {
      await apiService.updateStudent(student.id, { name: trimmed });
      setAlertInfo({ type: 'success', message: `Student ${student.roll_no} renamed to "${trimmed}".` });
      handleCancelEdit();
      await fetchStudents();
    } catch (err) {
      const errorMsg =
        err.response?.data?.name?.[0] ||
        err.response?.data?.error ||
        'Failed to update student name.';
      setAlertInfo({ type: 'error', message: errorMsg });
    }
  };

  const handleDeleteRoom = async (room) => {
    if (!window.confirm(`Delete room ${room.name}? This will also remove its associated constraints and seating results. This cannot be undone.`)) return;
    try {
      await apiService.deleteRoom(room.id);
      // If the deleted room was active, clear the active selection
      if (activeRoom && activeRoom.id === room.id) {
        setActiveRoom(null);
      }
      setAlertInfo({ type: 'info', message: `Room "${room.name}" deleted.` });
      await fetchRooms();
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.data?.error ||
        (typeof err.response?.data === 'string' ? err.response.data : null) ||
        'Failed to delete room.';
      setAlertInfo({ type: 'error', message: errorMsg });
    }
  };

  return (
    <div className="space-y-8">
      {alertInfo && (
        <Alert
          type={alertInfo.type}
          message={alertInfo.message}
          onClose={() => setAlertInfo(null)}
        />
      )}

      {/* SECTION 1: ROOM MANAGEMENT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Create Room Form */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-base font-bold text-slate-900 mb-1">Create Exam Room</h2>
          <p className="text-xs text-slate-500 mb-4">
            Define classroom grid dimensions (rows × cols).
          </p>

          <form onSubmit={handleCreateRoom} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Room Name
              </label>
              <input
                type="text"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                placeholder="e.g. Hall 204 or Physics Lab"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Rows
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={roomRows}
                  onChange={(e) => setRoomRows(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Columns
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={roomCols}
                  onChange={(e) => setRoomCols(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  required
                />
              </div>
            </div>

            <div className="text-xs font-medium text-slate-500 bg-slate-50 p-2.5 rounded border border-slate-100">
              Total Desks: <span className="font-bold text-indigo-600">{roomRows * roomCols}</span> seats
            </div>

            <button
              type="submit"
              disabled={roomSubmitting}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm py-2 px-4 rounded-lg transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {roomSubmitting ? 'Saving Room...' : 'Create Room'}
            </button>
          </form>
        </div>

        {/* Existing Rooms List */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Registered Rooms</h2>
              <p className="text-xs text-slate-500">
                Select a room below to set it as the active room for constraints and solver runs.
              </p>
            </div>
            <span className="text-xs font-semibold bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full">
              {rooms.length} {rooms.length === 1 ? 'Room' : 'Rooms'}
            </span>
          </div>

          {rooms.length === 0 ? (
            <div className="text-center py-10 border-2 border-dashed border-slate-200 rounded-lg text-slate-400 text-sm">
              No rooms defined yet. Use the form on the left to create your first classroom.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[380px] overflow-y-auto pr-1">
              {rooms.map((room) => {
                const isActive = activeRoom && activeRoom.id === room.id;
                return (
                  <div
                    key={room.id}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between relative group ${
                      isActive
                        ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div onClick={() => setActiveRoom(room)}>
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-bold text-slate-900 text-sm">{room.name}</h3>
                        {isActive && (
                          <span className="text-[10px] uppercase font-bold tracking-wider bg-indigo-600 text-white px-2 py-0.5 rounded">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">
                        {room.rows} rows × {room.cols} cols
                      </div>
                    </div>

                    <div className="mt-4 pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700" onClick={() => setActiveRoom(room)}>
                        Capacity: {room.total_seats} seats
                      </span>
                      <div className="flex items-center gap-2">
                        <span
                          className="text-indigo-600 font-semibold hover:underline"
                          onClick={() => setActiveRoom(room)}
                        >
                          {isActive ? 'Currently Active' : 'Click to Activate'}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteRoom(room);
                          }}
                          className="text-slate-400 hover:text-red-600 p-1 font-bold cursor-pointer transition-colors"
                          title={`Delete room ${room.name}`}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* SECTION 2: STUDENT ROSTER */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Add Student Form */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-base font-bold text-slate-900 mb-1">Add Student</h2>
          <p className="text-xs text-slate-500 mb-4">
            Register students by Name and unique Roll Number.
          </p>

          <form onSubmit={handleCreateStudent} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Student Full Name
              </label>
              <input
                type="text"
                value={studentName}
                onChange={(e) => setStudentName(e.target.value)}
                placeholder="e.g. Alice Chen"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Roll Number / ID
              </label>
              <input
                type="text"
                value={studentRollNo}
                onChange={(e) => setStudentRollNo(e.target.value)}
                placeholder="e.g. S1, S2, 21BCS001"
                className="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none font-mono"
                required
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Serves as the invariant ID across combinatorial engines.
              </p>
            </div>

            <button
              type="submit"
              disabled={studentSubmitting}
              className="w-full bg-slate-900 hover:bg-black text-white font-medium text-sm py-2 px-4 rounded-lg transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {studentSubmitting ? 'Adding...' : 'Add Student'}
            </button>
          </form>
        </div>

        {/* Student List Table */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Enrolled Students</h2>
              <p className="text-xs text-slate-500">
                All students available to be placed by the backtracking solver.
              </p>
            </div>
            <span className="text-xs font-semibold bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full">
              {students.length} {students.length === 1 ? 'Student' : 'Students'}
            </span>
          </div>

          {students.length === 0 ? (
            <div className="text-center py-10 border-2 border-dashed border-slate-200 rounded-lg text-slate-400 text-sm">
              No students enrolled yet. Add students using the form on the left.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[380px] border border-slate-100 rounded-lg">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider sticky top-0 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">#</th>
                    <th className="px-4 py-3">Roll Number</th>
                    <th className="px-4 py-3">Student Name</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {students.map((student, idx) => (
                    <tr key={student.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-2.5 text-xs text-slate-400">{idx + 1}</td>
                      <td className="px-4 py-2.5 font-mono font-bold text-indigo-600">{student.roll_no}</td>
                      <td className="px-4 py-2.5 text-slate-800 font-medium">
                        {editingStudentId === student.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveEdit(student);
                                if (e.key === 'Escape') handleCancelEdit();
                              }}
                              className="text-sm border border-indigo-300 rounded-md px-2 py-1 focus:ring-2 focus:ring-indigo-500 outline-none w-40"
                              autoFocus
                            />
                            <button
                              onClick={() => handleSaveEdit(student)}
                              className="text-[11px] font-semibold bg-indigo-600 hover:bg-indigo-700 text-white px-2 py-0.5 rounded cursor-pointer transition-colors"
                            >
                              Save
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              className="text-[11px] font-semibold text-slate-500 hover:text-slate-700 px-1 cursor-pointer transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          student.name
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {editingStudentId !== student.id && (
                            <button
                              onClick={() => handleStartEdit(student)}
                              className="text-slate-400 hover:text-indigo-600 p-1 cursor-pointer transition-colors"
                              title={`Edit name for ${student.roll_no}`}
                            >
                              ✎
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteStudent(student)}
                            className="text-slate-400 hover:text-red-600 p-1 font-bold cursor-pointer transition-colors"
                            title={`Delete ${student.roll_no}`}
                          >
                            ✕
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

