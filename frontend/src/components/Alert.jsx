import React from 'react';

export default function Alert({ type = 'error', message, onClose }) {
  if (!message) return null;

  const styles = {
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  };

  const icons = {
    error: '✕',
    warning: '⚠',
    success: '✓',
    info: 'ℹ',
  };

  return (
    <div className={`p-4 rounded-lg border flex items-start justify-between shadow-sm my-3 ${styles[type] || styles.info}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className="font-bold">{icons[type]}</span>
        <span>{message}</span>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-xs font-semibold hover:opacity-75 ml-4 cursor-pointer"
        >
          Dismiss
        </button>
      )}
    </div>
  );
}
