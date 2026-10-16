import React from 'react';
import type { ToolCallTrace } from '../api';

/**
 * 模型自主调用工具的轨迹卡片。
 * 展示「第几轮 / 调用了哪个工具 / 参数 / 结果状态 / 耗时」，让调用过程可见。
 * 仅当后端返回 tool_trace 非空时渲染（即走的是模型自主调用路径）。
 */

const STATUS_STYLE: Record<string, { text: string; color: string; bg: string }> = {
  completed: { text: '成功', color: '#2f6b4f', bg: 'rgba(120,180,140,0.18)' },
  not_implemented: { text: '未实现', color: '#8a6d3b', bg: 'rgba(214,178,110,0.22)' },
  error: { text: '失败', color: '#a04b4b', bg: 'rgba(214,120,120,0.18)' },
};

/** 参数压缩成一行，过长时截断 */
const formatArgs = (args: Record<string, unknown> | undefined): string => {
  const entries = Object.entries(args ?? {});
  if (entries.length === 0) return '()';
  const body = entries
    .map(([key, value]) => {
      const text =
        value !== null && typeof value === 'object' ? JSON.stringify(value) : String(value);
      return `${key}=${text}`;
    })
    .join(', ');
  return `(${body.length > 90 ? `${body.slice(0, 90)}…` : body})`;
};

const ToolTraceCard: React.FC<{ trace: ToolCallTrace[] }> = ({ trace }) => {
  if (!trace || trace.length === 0) return null;

  return (
    <div
      style={{
        marginBottom: 10,
        padding: '8px 12px',
        borderRadius: 10,
        background: 'rgba(0,0,0,0.028)',
        border: '1px solid rgba(0,0,0,0.05)',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: '#5b6b60',
          marginBottom: 6,
          letterSpacing: '0.02em',
        }}
      >
        🔧 模型自主调用工具 {trace.length} 次
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {trace.map((item, index) => {
          const style =
            STATUS_STYLE[item.status] ?? {
              text: item.status || '未知',
              color: '#5b6b60',
              bg: 'rgba(0,0,0,0.05)',
            };
          return (
            <div
              key={`${index}-${item.tool}`}
              style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 11.5, flexWrap: 'wrap' }}
            >
              <span
                style={{
                  padding: '1px 7px',
                  borderRadius: 6,
                  background: style.bg,
                  color: style.color,
                  fontWeight: 600,
                  flexShrink: 0,
                }}
              >
                {style.text}
              </span>
              <code
                style={{
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  color: '#2D3A30',
                  wordBreak: 'break-all',
                }}
              >
                {item.tool}
                {formatArgs(item.arguments)}
              </code>
              <span style={{ color: 'var(--text-muted)' }}>{item.elapsed_ms} ms</span>
              {item.message ? (
                <span style={{ color: style.color, opacity: 0.9 }}>
                  {String(item.message).slice(0, 90)}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ToolTraceCard;
