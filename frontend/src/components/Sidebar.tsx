import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface NavItem {
  key: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  {
    key: '/chat',
    label: '项目',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="2" y="2" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.3" />
        <path d="M6 7h6M6 10h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    key: '/knowledge',
    label: '知识库',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M3 5a2 2 0 012-2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V5z" stroke="currentColor" strokeWidth="1.3" />
        <path d="M6 7h6M6 10h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    key: '/tasks',
    label: '智能体',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <circle cx="5" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="13" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="9" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.3" />
        <path d="M7 6.5l1.5 3M11 6.5l-1.5 3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
      </svg>
    ),
  },
];

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside
      className="glass"
      style={{
        width: 88,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '24px 0',
        gap: 8,
        margin: '6px 0 8px 12px',
        borderRadius: 'var(--radius-xl)',
        position: 'relative',
        zIndex: 10,
      }}
    >
      {/* 侧面光晕 */}
      <div style={{
        position: 'absolute',
        top: '20%',
        right: -20,
        width: 40,
        height: '60%',
        background: 'radial-gradient(ellipse at center, rgba(181,214,224,0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {navItems.map((item) => {
        const active = location.pathname.startsWith(item.key);
        return (
          <button
            key={item.key}
            onClick={() => navigate(item.key)}
            style={{
              width: 56,
              height: 56,
              border: 'none',
              borderRadius: 'var(--radius-md)',
              background: active ? 'rgba(193,213,192,0.22)' : 'transparent',
              color: active ? '#3D5A45' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              fontSize: 10,
              fontWeight: active ? 600 : 400,
              letterSpacing: '0.03em',
              transition: 'var(--transition)',
              position: 'relative',
            }}
          >
            {item.icon}
            {item.label}
            {active && (
              <span style={{
                position: 'absolute',
                left: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                width: 2.5,
                height: 16,
                borderRadius: 4,
                background: 'var(--accent-sage)',
              }} />
            )}
          </button>
        );
      })}

      {/* 底部设置 */}
      <div style={{ flex: 1 }} />
      <button
        onClick={() => navigate('/settings')}
        style={{
          width: 56, height: 44, border: 'none', borderRadius: 'var(--radius-sm)',
          background: location.pathname === '/settings' ? 'rgba(193,213,192,0.22)' : 'transparent',
          color: 'var(--text-muted)', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, gap: 2, transition: 'var(--transition)',
        }}
      >
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <circle cx="7.5" cy="7.5" r="2.8" stroke="currentColor" strokeWidth="1.2" />
          <path d="M7.5 1.5v2M7.5 11.5v2M1.5 7.5h2M11.5 7.5h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        配置
      </button>
    </aside>
  );
};

export default Sidebar;
