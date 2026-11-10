import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiService = {
  // Rooms
  getRooms: () => api.get('/rooms/'),
  createRoom: (data) => api.post('/rooms/', data),
  deleteRoom: (id) => api.delete(`/rooms/${id}/`),

  // Students
  getStudents: () => api.get('/students/'),
  createStudent: (data) => api.post('/students/', data),
  updateStudent: (id, data) => api.patch(`/students/${id}/`, data),
  deleteStudent: (id) => api.delete(`/students/${id}/`),

  // Constraints
  getConflictPairs: () => api.get('/conflict-pairs/'),
  createConflictPair: (data) => api.post('/conflict-pairs/', data),
  deleteConflictPair: (id) => api.delete(`/conflict-pairs/${id}/`),

  getForbiddenConstraints: () => api.get('/forbidden-constraints/'),
  createForbiddenConstraint: (data) => api.post('/forbidden-constraints/', data),
  deleteForbiddenConstraint: (id) => api.delete(`/forbidden-constraints/${id}/`),

  // Seating calculation endpoints
  generateSeating: (data) => api.post('/generate-seating/', data),
  generateRetest: (data) => api.post('/generate-retest/', data),
  getSeatingResults: (roomId) => api.get(`/seating-results/${roomId}/`),

  // Risk scoring
  trainRiskModel: (data) => api.post('/train-risk-model/', data),

  // Math explainer
  getMathExplainer: (roomId) => api.get(`/math-explainer/${roomId}/`),
};

export default api;
