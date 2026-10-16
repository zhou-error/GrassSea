import React from 'react';

/**
 * 步骤产出（结构由后端决定）到可读文本的共享格式化工具。
 * Chat.tsx 与 TaskCenter.tsx 共用，避免两处重复实现。
 */

/** 一次最多展示的结果键值对数量（超出部分以省略号提示） */
export const MAX_RESULT_PAIRS = 8;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toText = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => toText(item)).filter(Boolean).join('、');
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

/** 规范化后端的 summary 字段：非数组或空数组一律视为“没有 summary” */
export const summaryLines = (summary: unknown): string[] =>
  Array.isArray(summary)
    ? summary.filter((line): line is string => typeof line === 'string' && line.trim() !== '')
    : [];

/** 把 results 中的键值对渲染成 “key=value” 列表 */
const formatKeyValues = (
  values: unknown,
  limit: number = MAX_RESULT_PAIRS
): string[] => {
  if (!isRecord(values)) return [];
  const entries = Object.entries(values);
  const lines = entries.slice(0, limit).map(([key, value]) => {
    const text = toText(value);
    return text ? `${key}=${text}` : key;
  });
  if (entries.length > limit) lines.push(`… 其余 ${entries.length - limit} 项已省略`);
  return lines;
};

/**
 * 把单步产出的原始 payload 转成可读文本数组：
 * - 跳过 / 未实现：展示 reason 或 output.message
 * - 有 output.results：展示 key=value 列表
 * - output 是字符串：直接展示
 * - 其余情况：JSON 字符串仅作为最后兜底（限长），绝不整块 dump
 */
export const stepOutputLines = (value: unknown): string[] => {
  if (value === null || value === undefined) return [];
  if (typeof value === 'string') return value.trim() ? [value] : [];
  if (typeof value === 'number' || typeof value === 'boolean') return [String(value)];
  if (!isRecord(value)) return [String(value)];

  const output = isRecord(value.output) ? value.output : undefined;

  const reason =
    typeof value.reason === 'string' && value.reason.trim()
      ? value.reason
      : output && typeof output.message === 'string' && output.message.trim()
        ? output.message
        : '';

  const payload = output ?? value;

  const results =
    isRecord(payload.results) && Object.keys(payload.results).length > 0
      ? formatKeyValues(payload.results)
      : [];

  if (results.length > 0) return reason ? [reason, ...results] : results;

  const text =
    typeof payload.text === 'string' && payload.text.trim()
      ? payload.text
      : typeof payload.summary === 'string' && payload.summary.trim()
        ? payload.summary
        : '';

  const lines: string[] = [];
  if (reason) lines.push(reason);
  if (text && text !== reason) lines.push(text);
  if (lines.length > 0) return lines;

  try {
    const blob = JSON.stringify(value);
    return blob && blob !== '{}' ? [blob.slice(0, 400)] : [];
  } catch {
    return ['[无法解析的产出]'];
  }
};

/** 追加到聊天气泡的文本：每个条目一行，用 “  • ” 前缀 */
export const bulletText = (lines: string[], indent = '  '): string =>
  lines.map((line) => `\n${indent}• ${line}`).join('');

/** 逐行展示的可读文本块，替代 JSON dump */
export const LineList: React.FC<{
  lines: string[];
  style?: React.CSSProperties;
}> = ({ lines, style }) => {
  if (lines.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, ...style }}>
      {lines.map((line, index) => (
        <div
          key={`${index}-${line}`}
          style={{ lineHeight: 1.7, wordBreak: 'break-word' }}
        >
          {line}
        </div>
      ))}
    </div>
  );
};
