import React from 'react';
import { ShieldCheck, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface EmptyRescueStateProps {
  safetyReserveCents: number;
  currency: string;
}

export const EmptyRescueState: React.FC<EmptyRescueStateProps> = () => {
  return (
    <div className="rescue-empty-state-card">
      <div className="empty-shield-wrapper">
        <ShieldCheck size={36} className="text-safe" />
      </div>
      <h3 className="empty-title">Safety Reserve Fully Protected</h3>
      <p className="empty-description">
        The deterministic cash forecast projects that all closing balances remain strictly above
        your configured safety reserve. No liquidity rescue actions or emergency financing
        interventions are required for this horizon.
      </p>
      <div className="empty-actions-row">
        <Link to="/dashboard/forecast" className="empty-primary-btn">
          <span>Review Forecast Horizon</span>
          <ArrowRight size={14} />
        </Link>
        <Link to="/dashboard/overview" className="empty-secondary-btn">
          <span>Return to Overview</span>
        </Link>
      </div>
    </div>
  );
};
