import React from 'react';

export function formatPercent(value) {
  if (value == null) return '—';
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export function formatCgpa(value) {
  if (value == null) return '—';
  return Number(value).toFixed(2);
}

export function StatCard({ label, value, hint }) {
  return (
    <article className="stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {hint && <p className="stat-hint">{hint}</p>}
    </article>
  );
}

export function LoadingBlock({ label = 'Loading...' }) {
  return <div className="loading-block">{label}</div>;
}

export function ErrorBlock({ message, onRetry }) {
  return (
    <div className="error-block" role="alert">
      <p>{message}</p>
      {onRetry && <button className="logout-button" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function EmptyState({ message }) {
  return <div className="empty-state">{message}</div>;
}
