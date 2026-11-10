import React from 'react';
import { NavLink } from 'react-router-dom';
import { useRoom } from '../context/RoomContext';

export default function Navbar() {
  const { activeRoom, rooms, setActiveRoom } = useRoom();

  const navItems = [
    { label: '1. Setup', path: '/' },
    { label: '2. Constraints', path: '/constraints' },
    { label: '3. Generate & Results', path: '/generate' },
    { label: '4. Risk Model (ML)', path: '/risk-model' },
  ];

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top Header line */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between py-3 gap-2 border-b border-slate-100">
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span className="bg-indigo-600 text-white p-1 rounded font-mono text-xs">CSP</span>
              Derange
            </h1>

          </div>

          {/* Active Room Selector / Badge */}
          <div className="flex items-center gap-3">
            {rooms.length > 0 ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Active Room:
                </span>
                <select
                  value={activeRoom?.id || ''}
                  onChange={(e) => {
                    const found = rooms.find(r => String(r.id) === e.target.value);
                    setActiveRoom(found || null);
                  }}
                  className="text-xs font-semibold bg-indigo-50 text-indigo-900 border border-indigo-200 rounded px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                >
                  {rooms.map(r => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.rows}×{r.cols} = {r.total_seats} seats)
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                No rooms created yet
              </span>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-6">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `py-3 text-sm font-medium border-b-2 transition-colors duration-150 ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 font-semibold'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
