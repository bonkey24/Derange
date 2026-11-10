import React from 'react';

export default function SeatingGrid({ rows, cols, assignment = {}, students = [], title = 'Classroom Seating Chart' }) {
  if (!rows || !cols) return null;

  // Student roll_no to name lookup
  const studentMap = {};
  students.forEach(s => {
    studentMap[s.roll_no] = s.name;
  });

  const numRows = Number(rows);
  const numCols = Number(cols);
  const totalSeats = numRows * numCols;
  const occupiedCount = Object.keys(assignment).length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-6 border-b border-slate-100 gap-2">
        <div>
          <h3 className="text-base font-bold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500">
            {numRows} Rows × {numCols} Columns ({totalSeats} Total Desks)
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-100 border border-indigo-300"></span>
            <span className="text-slate-600 font-medium">Occupied: {occupiedCount}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-slate-50 border border-dashed border-slate-300"></span>
            <span className="text-slate-600 font-medium">Empty: {totalSeats - occupiedCount}</span>
          </span>
        </div>
      </div>

      {/* Front of Room indicator */}
      <div className="mb-6 flex justify-center">
        <div className="w-3/4 max-w-md py-1.5 px-4 bg-slate-100 border border-slate-300 text-slate-600 text-center rounded-md font-semibold text-xs uppercase tracking-widest shadow-2xs">
          ▲ Front of Room / Blackboard / Proctor Desk ▲
        </div>
      </div>

      {/* 2D Grid Layout */}
      <div className="overflow-x-auto pb-4">
        <div className="inline-block min-w-full">
          <div
            className="grid gap-3 mx-auto"
            style={{
              gridTemplateColumns: `repeat(${numCols}, minmax(110px, 1fr))`,
            }}
          >
            {Array.from({ length: numRows }).map((_, r) => (
              <React.Fragment key={`row-${r}`}>
                {Array.from({ length: numCols }).map((_, c) => {
                  const seatIndex = r * numCols + c;
                  const rollNo = assignment[String(seatIndex)] || assignment[seatIndex];
                  const studentName = rollNo ? studentMap[rollNo] : null;
                  const isOccupied = Boolean(rollNo);
                  const colLetter = String.fromCharCode(65 + c);

                  return (
                    <div
                      key={`seat-${seatIndex}`}
                      className={`relative flex flex-col justify-between p-3 rounded-lg border transition-all duration-150 min-h-[90px] ${
                        isOccupied
                          ? 'bg-indigo-50/70 border-indigo-300 hover:border-indigo-400 shadow-2xs'
                          : 'bg-slate-50/50 border-dashed border-slate-200 text-slate-400'
                      }`}
                    >
                      {/* Seat Metadata Header */}
                      <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                        <span>R{r + 1}C{colLetter}</span>
                        <span className="bg-white/80 px-1 py-0.5 rounded border border-slate-200">
                          #{seatIndex}
                        </span>
                      </div>

                      {/* Student Body */}
                      <div className="my-1.5 text-center">
                        {isOccupied ? (
                          <div>
                            <div className="inline-block font-mono font-bold text-sm bg-indigo-600 text-white px-2 py-0.5 rounded shadow-2xs">
                              {rollNo}
                            </div>
                            {studentName && (
                              <div className="text-[11px] text-slate-600 truncate mt-1 font-medium" title={studentName}>
                                {studentName}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs italic text-slate-400">Empty</span>
                        )}
                      </div>

                      {/* Desk foot bar graphic */}
                      <div className={`h-1 w-full rounded-full ${isOccupied ? 'bg-indigo-300' : 'bg-slate-200'}`} />
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
