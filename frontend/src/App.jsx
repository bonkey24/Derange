import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { RoomProvider } from './context/RoomContext';
import Navbar from './components/Navbar';

import SetupTab from './tabs/SetupTab';
import ConstraintsTab from './tabs/ConstraintsTab';
import GenerateTab from './tabs/GenerateTab';
import RiskModelTab from './tabs/RiskModelTab';

export default function App() {
  return (
    <RoomProvider>
      <Router>
        <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
          {/* Persistent Navigation */}
          <Navbar />

          {/* Main Tab Body */}
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<SetupTab />} />
              <Route path="/constraints" element={<ConstraintsTab />} />
              <Route path="/generate" element={<GenerateTab />} />
              <Route path="/risk-model" element={<RiskModelTab />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>


        </div>
      </Router>
    </RoomProvider>
  );
}
