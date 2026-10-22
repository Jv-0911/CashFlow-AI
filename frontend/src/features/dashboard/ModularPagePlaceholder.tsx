import { Link } from 'react-router-dom';
import { ArrowLeft, Clock, type LucideIcon, Sparkles } from 'lucide-react';

interface ModularPagePlaceholderProps {
  title: string;
  milestone: string;
  description: string;
  icon: LucideIcon;
}

export function ModularPagePlaceholder({
  title,
  milestone,
  description,
  icon: Icon,
}: ModularPagePlaceholderProps) {
  return (
    <div className="dashboard-content">
      <div className="modular-stub-container">
        <div className="stub-icon-circle">
          <Icon size={28} />
        </div>

        <span className="demo-banner-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Clock size={12} />
          <span>{milestone}</span>
        </span>

        <h1 className="stub-title">{title}</h1>

        <p className="stub-desc">{description}</p>

        <div className="overview-demo-banner" style={{ width: '100%', boxSizing: 'border-box' }}>
          <div className="demo-banner-text" style={{ fontSize: '11px' }}>
            <Sparkles size={14} color="#7896B0" />
            <span>
              Architecture is partitioned cleanly for modular development without monolithic coupling.
            </span>
          </div>
        </div>

        <Link to="/dashboard" className="rescue-action-btn" style={{ textDecoration: 'none', maxWidth: 220 }}>
          <ArrowLeft size={14} />
          <span>Return to Overview</span>
        </Link>
      </div>
    </div>
  );
}
