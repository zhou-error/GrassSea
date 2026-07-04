import React, { useState } from 'react';

interface DAGNode {
  id: string;
  label: string;
  x: number;
  y: number;
  deps: string[];
}

const dagNodes: DAGNode[] = [
  { id: 'n1', label: 'DAG', x: 140, y: 40,  deps: [] },
  { id: 'n2', label: 'DAG', x: 60,  y: 120, deps: ['n1'] },
  { id: 'n3', label: 'DAG', x: 220, y: 120, deps: ['n1'] },
  { id: 'n4', label: 'DAG', x: 140, y: 200, deps: ['n2', 'n3'] },
  { id: 'n5', label: 'File', x: 140, y: 280, deps: ['n4'] },
];

const DAGPanel: React.FC = () => {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div style={{
      width: 280,
      flexShrink: 0,
      background: 'var(--bg-white)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-card)',
      padding: '20px 16px',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <h5 style={{ marginBottom: 4 }}>任务拓扑可视化</h5>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 16 }}>
        DAG 任务依赖流程图
      </span>

      <svg width="100%" height="340" viewBox="0 0 280 340" style={{ flex: 1 }}>
        {/* 连接线 */}
        {dagNodes.map((node) =>
          node.deps.map((depId) => {
            const dep = dagNodes.find((n) => n.id === depId);
            if (!dep) return null;
            return (
              <line
                key={`${depId}-${node.id}`}
                x1={dep.x} y1={dep.y + 20}
                x2={node.x} y2={node.y - 6}
                stroke="#C1D5C0"
                strokeWidth={1.2}
                strokeDasharray="4 3"
                opacity={0.7}
              />
            );
          })
        )}

        {/* 节点 */}
        {dagNodes.map((node) => (
          <g
            key={node.id}
            onMouseEnter={() => setHovered(node.id)}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
            transform={hovered === node.id
              ? `translate(${node.x}, ${node.y - 2})`
              : `translate(${node.x}, ${node.y})`
            }
          >
            {/* 光晕 */}
            {hovered === node.id && (
              <circle cx={0} cy={0} r={22} fill="rgba(181,214,224,0.18)" />
            )}
            {/* 节点圆 */}
            <circle
              cx={0} cy={0} r={16}
              fill="var(--bg-white)"
              stroke="var(--accent-glacier)"
              strokeWidth={1.2}
              style={{
                filter: hovered === node.id
                  ? 'drop-shadow(0 2px 6px rgba(0,0,0,0.08))'
                  : 'drop-shadow(0 1px 2px rgba(0,0,0,0.03))',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            />
            {/* 标签 */}
            <text
              y={-24}
              textAnchor="middle"
              fill={node.label === 'File' ? 'var(--text-secondary)' : 'var(--text-primary)'}
              fontSize={10}
              fontWeight={500}
              fontFamily="var(--font-family)"
              letterSpacing="0.03em"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>

      <div style={{
        marginTop: 8,
        padding: '8px 12px',
        background: 'rgba(193,213,192,0.12)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 11,
        color: 'var(--text-secondary)',
        letterSpacing: '0.02em',
      }}>
        5 节点 · 2 并行组 · 状态: 运行中
      </div>
    </div>
  );
};

export default DAGPanel;
