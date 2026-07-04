import React from 'react';

const ShimmerBar: React.FC = () => (
  <div
    style={{
      height: 3,
      flexShrink: 0,
      margin: '0 12px 8px 12px',
      borderRadius: 6,
      background: 'linear-gradient(90deg, var(--accent-glacier), var(--accent-sage), var(--accent-glacier))',
      backgroundSize: '200% 100%',
      animation: 'shimmer 4s ease-in-out infinite',
      position: 'relative',
      zIndex: 10,
      opacity: 0.8,
    }}
  />
);

export default ShimmerBar;
