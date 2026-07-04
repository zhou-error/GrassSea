import React from 'react';
import { useAuthStore } from '../stores/authStore';

const TopNav: React.FC = () => (
  <nav
    className="glass"
    style={{
      height: 52,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      zIndex: 100,
      flexShrink: 0,
      margin: '8px 12px 0 12px',
      borderRadius: 'var(--radius-lg)',
      position: 'relative',
    }}
  >
    {/* 左侧 Logo */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: 200 }}>
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <defs>
          <linearGradient id="logoGrad" x1="0" y1="0" x2="28" y2="28">
            <stop offset="0%" stopColor="#C1D5C0" />
            <stop offset="100%" stopColor="#B5D6E0" />
          </linearGradient>
        </defs>
        <path d="M4 22 Q8 10 14 6 Q20 10 24 22" stroke="url(#logoGrad)" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        <path d="M6 18 Q10 12 14 10 Q18 12 22 18" stroke="url(#logoGrad)" strokeWidth="1.2" fill="none" strokeLinecap="round" opacity="0.6" />
      </svg>
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>
        白草沧智
      </span>
    </div>

    {/* 居中品牌 */}
    <span style={{
      fontSize: 15,
      fontWeight: 700,
      letterSpacing: '0.04em',
      color: 'var(--text-primary)',
      position: 'absolute',
      left: '50%',
      transform: 'translateX(-50%)',
    }}>
      GrassSea AI
    </span>

    {/* 右侧状态 */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: 200, justifyContent: 'flex-end' }}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: 'var(--status-green)',
          display: 'inline-block',
          animation: 'dotPulse 2s ease-in-out infinite',
        }}
      />
      <span style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.03em' }}>在线</span>
    </div>
  </nav>
);

export default TopNav;
