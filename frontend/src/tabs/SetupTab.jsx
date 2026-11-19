import React, { useState, useEffect, useCallback } from 'react';
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

  // Department Roster State
  const [rosters, setRosters] = useState([]);
  const [rosterErrors, setRosterErrors] = useState([]);
  const [rostersLoading, setRostersLoading] = useState(false);
  const [openSlug, setOpenSlug] = useState(null);
  const [rosterDetails, setRosterDetails] = useState({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedUsns, setSelectedUsns] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [addingStudents, setAddingStudents] = useState(false);

  // Manual Student Form State
  const [manualExpanded, setManualExpanded] = useState(false);
  const [studentName, setStudentName] = useState('');
  const [studentRollNo, setStudentRollNo] = useState('');
  const [studentSubmitting, setStudentSubmitting] = useState(false);

  // Feedback State
  const [alertInfo, setAlertInfo] = useState(null);

  // Inline Edit State
  const [editingStudentId, setEditingStudentId] = useState(null);
  const [editingName, setEditingName] = useState('');

  // Fetch department rosters on mount
  const fetchRostersList = useCallback(async () => {
    setRostersLoading(true);
    try {
      const res = await apiService.getRosters();
      setRosters(res.data?.rosters || []);
      setRosterErrors(res.data?.errors || []);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load department rosters.';
      setAlertInfo({ type: 'error', message: msg });
    } finally {
      setRostersLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRostersList();
  }, [fetchRostersList]);

  // Compute capacity and enrolled sets
  const roomCapacity = activeRoom ? (activeRoom.total_seats || activeRoom.rows * activeRoom.cols) : 0;
  const remainingSeats = activeRoom ? Math.max(0, roomCapacity - students.length) : 0;
  const enrolledUsnSet = new Set(students.map((s) => s.roll_no.toUpperCase()));

  // Toggle department accordion
  const handleToggleDepartment = async (slug) => {
    if (openSlug === slug) {
      setOpenSlug(null);
      return;
    }
    setOpenSlug(slug);
    setSelectedUsns(new Set());
    setSearchTerm('');

    if (!rosterDetails[slug]) {
      setDetailLoading(true);
      try {
        const res = await apiService.getRosterDetail(slug);
        setRosterDetails((prev) => ({
          ...prev,
          [slug]: res.data?.students || [],
        }));
      } catch (err) {
        const msg = err.response?.data?.error || `Failed to load students for ${slug}.`;
        setAlertInfo({ type: 'error', message: msg });
      } finally {
        setDetailLoading(false);
      }
    }
  };

  // Filtered students for open department
  const currentStudents = openSlug ? rosterDetails[openSlug] || [] : [];
  const filteredStudents = currentStudents.filter((s) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return s.name.toLowerCase().includes(term) || s.usn.toLowerCase().includes(term);
  });

  // Selectable filtered students (excluding already enrolled)
  const selectableFiltered = filteredStudents.filter(
    (s) => !enrolledUsnSet.has(s.usn.toUpperCase())
  );

  const allFilteredSelected =
    selectableFiltered.length > 0 &&
    selectableFiltered.every((s) => selectedUsns.has(s.usn));

  const handleToggleSelectAll = () => {
    if (allFilteredSelected) {
      // Unselect all selectable filtered
      setSelectedUsns((prev) => {
        const next = new Set(prev);
        selectableFiltered.forEach((s) => next.delete(s.usn));
        return next;
      });
    } else {
      // Select all selectable filtered
      setSelectedUsns((prev) => {
        const next = new Set(prev);
        selectableFiltered.forEach((s) => next.add(s.usn));
        return next;
      });
    }
  };

  const handleToggleSingle = (usn) => {
    setSelectedUsns((prev) => {
      const next = new Set(prev);
      if (next.has(usn)) {
        next.delete(usn);
      } else {
        next.add(usn);
      }
      return next;
    });
  };

  const exceedsCapacity = activeRoom && selectedUsns.size > remainingSeats;

  // Add selected roster students to active room
  const handleAddSelectedRosterStudents = async () => {
    if (!activeRoom) {
      setAlertInfo({ type: 'error', message: 'Please select an active room first.' });
      return;
    }
    if (selectedUsns.size === 0) return;
    if (exceedsCapacity) {
      setAlertInfo({
        type: 'error',
        message: `Cannot add ${selectedUsns.size} students: only ${remainingSeats} seat(s) remaining in ${activeRoom.name}.`,
      });
      return;
    }

    setAddingStudents(true);
    try {
      const res = await apiService.addRosterStudents(activeRoom.id, {
        slug: openSlug,
        usns: Array.from(selectedUsns),
      });
      const added = res.data?.added_count ?? selectedUsns.size;
      const skipped = res.data?.skipped_count ?? 0;
      let msg = `Successfully added ${added} student(s) to ${activeRoom.name}!`;
      if (skipped > 0) {
        msg += ` (${skipped} already present were skipped)`;
      }
      setAlertInfo({ type: 'success', message: msg });
      setSelectedUsns(new Set());
      await fetchStudents();
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        'Failed to add roster students to room.';
      setAlertInfo({ type: 'error', message: msg });
    } finally {
      setAddingStudents(false);
    }
  };

  // Create Room
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
      setActiveRoom(res.data);
    } catch (err) {
      const errorMsg = err.response?.data?.name?.[0] || err.response?.data?.error || 'Failed to create room.';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setRoomSubmitting(false);
    }
  };

  // Manual Single Student Creation
  const handleCreateStudent = async (e) => {
    e.preventDefault();
    if (!activeRoom) {
      setAlertInfo({ type: 'error', message: 'Please select or create an active room first.' });
      return;
    }
    if (!studentName.trim() || !studentRollNo.trim()) {
      setAlertInfo({ type: 'error', message: 'Both student name and roll number are required.' });
      return;
    }

    setStudentSubmitting(true);
    try {
      const res = await apiService.createStudent({
        room: activeRoom.id,
        name: studentName.trim(),
        roll_no: studentRollNo.trim().toUpperCase(),
      });
      setAlertInfo({ type: 'success', message: `Student ${res.data.roll_no} (${res.data.name}) added!` });
      setStudentName('');
      setStudentRollNo('');
      await fetchStudents();
    } catch (err) {
      const errorMsg =
        err.response?.data?.roll_no?.[0] ||
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.error ||
        'Failed to add student (Roll number may already exist in this room).';
      setAlertInfo({ type: 'error', message: errorMsg });
    } finally {
      setStudentSubmitting(false);
    }
  };

  // Delete & Edit Handlers for Students
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

      {/* Roster load errors banner if any */}
      {rosterErrors.length > 0 && (
        <Alert
          type="warning"
          message={`Roster warnings: ${rosterErrors.join(' | ')}`}
          onClose={() => setRosterErrors([])}
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
                        Capacity: {room.total_seats || room.rows * room.cols} seats
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

      {/* SECTION 2: STUDENT MANAGEMENT & ROSTERS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Department Rosters Accordion + Manual Add */}
        <div className="space-y-6">
          {/* Main Card: Add Students from Department Roster */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
            <div className="mb-4">
              <h2 className="text-base font-bold text-slate-900 mb-1">
                Add Students from Department Roster
              </h2>
              <p className="text-xs text-slate-500">
                Choose students from verified institutional rosters to enroll in the active room.
              </p>
            </div>

            {rostersLoading ? (
              <div className="text-center py-8 text-xs text-slate-400">
                Loading department rosters...
              </div>
            ) : rosters.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg">
                No department rosters found.
              </div>
            ) : (
              <div className="space-y-3">
                {rosters.map((dept) => {
                  const isOpen = openSlug === dept.slug;
                  return (
                    <div
                      key={dept.slug}
                      className="border border-slate-200 rounded-xl overflow-hidden transition-all"
                    >
                      {/* Department Accordion Header */}
                      <button
                        type="button"
                        onClick={() => handleToggleDepartment(dept.slug)}
                        className={`w-full flex items-center justify-between p-3.5 text-left transition-colors cursor-pointer select-none ${
                          isOpen
                            ? 'bg-indigo-50/80 border-b border-indigo-100'
                            : 'bg-white hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-xs font-bold text-slate-800">
                            {dept.department}
                          </span>
                          <span className="text-[10px] font-semibold bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
                            {dept.count}
                          </span>
                        </div>
                        <svg
                          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
                            isOpen ? 'rotate-180 text-indigo-600' : ''
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </button>

                      {/* Accordion Content */}
                      {isOpen && (
                        <div className="p-3.5 bg-white space-y-3">
                          {detailLoading && !rosterDetails[dept.slug] ? (
                            <div className="text-center py-6 text-xs text-slate-400">
                              Loading students...
                            </div>
                          ) : (
                            <>
                              {/* Filter Bar & Selection Counter */}
                              <div className="space-y-2 p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                                <input
                                  type="text"
                                  placeholder="Search by name or USN..."
                                  value={searchTerm}
                                  onChange={(e) => setSearchTerm(e.target.value)}
                                  className="w-full text-xs bg-white border border-slate-300 rounded-md px-2.5 py-1.5 focus:ring-2 focus:ring-indigo-500 outline-none"
                                />

                                <div className="flex items-center justify-between text-xs pt-0.5">
                                  <label className="flex items-center gap-1.5 text-slate-700 font-medium cursor-pointer select-none">
                                    <input
                                      type="checkbox"
                                      checked={allFilteredSelected}
                                      disabled={selectableFiltered.length === 0}
                                      onChange={handleToggleSelectAll}
                                      className="h-3.5 w-3.5 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer disabled:cursor-not-allowed"
                                    />
                                    <span className="text-[11px]">
                                      Select all (filtered)
                                    </span>
                                  </label>

                                  <div className="text-[11px] font-semibold">
                                    <span className="text-indigo-600 font-bold">
                                      {selectedUsns.size}
                                    </span>{' '}
                                    selected /{' '}
                                    {activeRoom ? (
                                      <span
                                        className={
                                          remainingSeats === 0
                                            ? 'text-rose-600'
                                            : 'text-slate-700'
                                        }
                                      >
                                        {remainingSeats} seats left
                                      </span>
                                    ) : (
                                      <span className="text-amber-600 italic">
                                        No active room
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {/* Scrollable Students List */}
                              <div className="max-h-[320px] overflow-y-auto space-y-1 border border-slate-100 rounded-lg p-1.5 pr-2">
                                {filteredStudents.length === 0 ? (
                                  <div className="text-center py-6 text-xs text-slate-400">
                                    No students match your search.
                                  </div>
                                ) : (
                                  filteredStudents.map((student) => {
                                    const isEnrolled = enrolledUsnSet.has(
                                      student.usn.toUpperCase()
                                    );
                                    const isSelected = selectedUsns.has(student.usn);

                                    return (
                                      <label
                                        key={student.usn}
                                        className={`flex items-center gap-2.5 p-2 rounded-md text-xs transition-colors ${
                                          isEnrolled
                                            ? 'bg-slate-50 text-slate-400 opacity-60 cursor-not-allowed'
                                            : isSelected
                                            ? 'bg-indigo-50/80 text-indigo-950 font-medium cursor-pointer'
                                            : 'hover:bg-slate-50 text-slate-700 cursor-pointer'
                                        }`}
                                      >
                                        <input
                                          type="checkbox"
                                          checked={isEnrolled || isSelected}
                                          disabled={isEnrolled}
                                          onChange={() =>
                                            !isEnrolled && handleToggleSingle(student.usn)
                                          }
                                          className="h-3.5 w-3.5 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer disabled:cursor-not-allowed"
                                        />
                                        <span className="font-mono text-[11px] truncate flex-1">
                                          {student.name.toUpperCase()} - {student.usn.toUpperCase()}
                                        </span>
                                        {isEnrolled && (
                                          <span className="text-[9px] uppercase font-semibold bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">
                                            Enrolled
                                          </span>
                                        )}
                                      </label>
                                    );
                                  })
                                )}
                              </div>

                              {/* Capacity Warning */}
                              {exceedsCapacity && (
                                <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 font-medium">
                                  Selection of {selectedUsns.size} students exceeds remaining capacity ({remainingSeats} seat{remainingSeats === 1 ? '' : 's'} left in {activeRoom.name}).
                                </div>
                              )}

                              {/* Add to Room Button */}
                              <button
                                type="button"
                                onClick={handleAddSelectedRosterStudents}
                                disabled={
                                  !activeRoom ||
                                  selectedUsns.size === 0 ||
                                  exceedsCapacity ||
                                  addingStudents
                                }
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs py-2 px-3 rounded-lg transition-colors shadow-2xs cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {addingStudents
                                  ? 'Adding to room...'
                                  : `Add to room (${selectedUsns.size})`}
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Collapsible Card: Add Manually (Advanced) */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <button
              type="button"
              onClick={() => setManualExpanded(!manualExpanded)}
              className="w-full flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 transition-colors text-left cursor-pointer"
            >
              <div>
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                  Add Manually (Advanced)
                </span>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Register individual custom student name and roll number
                </p>
              </div>
              <svg
                className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${
                  manualExpanded ? 'rotate-180' : ''
                }`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {manualExpanded && (
              <div className="p-5 border-t border-slate-200">
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
            )}
          </div>
        </div>

        {/* Right Column: Enrolled Students List Table */}
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
              No students in this room yet. Open a department above and tick the students to add.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[460px] border border-slate-100 rounded-lg">
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
