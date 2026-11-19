import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiService } from '../api/client';

const RoomContext = createContext();

export function RoomProvider({ children }) {
  const [rooms, setRooms] = useState([]);
  const [students, setStudents] = useState([]);
  const [activeRoom, setActiveRoomState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRooms = useCallback(async () => {
    try {
      const res = await apiService.getRooms();
      setRooms(res.data);
      // Auto-restore active room from localStorage or default to first
      const savedRoomId = localStorage.getItem('activeRoomId');
      if (res.data.length > 0) {
        if (savedRoomId) {
          const found = res.data.find(r => String(r.id) === String(savedRoomId));
          setActiveRoomState(found || res.data[0]);
        } else {
          setActiveRoomState(prev => prev || res.data[0]);
        }
      } else {
        setActiveRoomState(null);
      }
    } catch (err) {
      console.error('Failed to load rooms:', err);
      setError('Unable to load rooms from backend. Ensure Django is running on port 8000.');
    }
  }, []);

  const fetchStudents = useCallback(async (roomId) => {
    const targetRoomId = roomId !== undefined ? roomId : activeRoom?.id;
    if (!targetRoomId) {
      setStudents([]);
      return;
    }
    try {
      const res = await apiService.getStudents(targetRoomId);
      setStudents(res.data);
    } catch (err) {
      console.error('Failed to load students:', err);
    }
  }, [activeRoom?.id]);

  const setActiveRoom = (room) => {
    setActiveRoomState(room);
    if (room && room.id) {
      localStorage.setItem('activeRoomId', String(room.id));
    } else {
      localStorage.removeItem('activeRoomId');
    }
  };

  // Re-fetch students whenever active room changes
  useEffect(() => {
    if (activeRoom?.id) {
      fetchStudents(activeRoom.id);
    } else {
      setStudents([]);
    }
  }, [activeRoom?.id, fetchStudents]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchRooms();
      setLoading(false);
    };
    init();
  }, [fetchRooms]);

  return (
    <RoomContext.Provider
      value={{
        rooms,
        activeRoom,
        setActiveRoom,
        students,
        fetchRooms,
        fetchStudents,
        loading,
        error,
        setError,
      }}
    >
      {children}
    </RoomContext.Provider>
  );
}

export function useRoom() {
  const context = useContext(RoomContext);
  if (!context) {
    throw new Error('useRoom must be used within a RoomProvider');
  }
  return context;
}
