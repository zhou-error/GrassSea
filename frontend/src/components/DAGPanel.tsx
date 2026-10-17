import React, { useEffect, useMemo, useState } from 'react';
import { getTaskStatusApi } from '../api';
import type { TaskStatusResponse, TaskStep } from '../api';

interface DAGPanelProps {
  /** 当前对话绑定的任务 ID；为空时展示空状态而不是伪造拓扑 */
  taskId?: string | null;
}

type StepState = 'completed' | 'failed' | 'skipped' | 'running' | 'pending';

interface LaidOutStep {
  id: string;
  label: string;
  fullLabel: string;
  state: StepState;
  x: number;
  y: number;
  deps: string[];
  /** 首选工具（tool_ids[0]），无工具时为空 */
  toolId: string;
  /** 指派给哪个 agent */
  agentId: string;
}

interface GraphLayout {
  nodes: LaidOutStep[];
  width: number;
  height: number;
  parallelGroups: number;
}

/** 状态配色：已完成/失败/跳过/运行中/未知 */
const STATE_COLORS: Record<StepState, string> = {
  completed: 'var(--status-green)',
  failed: '#E06C6C',
  skipped: '#D4A853',
  running: 'var(--accent-glacier)',
  pending: 'var(--text-muted)',
};

const STATE_TEXT: Record<StepState, string> = {
  completed: '已完成',
  failed: '失败',
  skipped: '已跳过',
  running: '运行中',
  pending: '等待中',
};

const STATUS_TEXT: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

const NODE_R = 16;
const COL_W = 78;
const ROW_H = 96;
const PAD_X = 34;
const PAD_TOP = 44;
const PAD_BOTTOM = 46;
const MIN_W = 240;
const MIN_H = 170;
const MAX_LABEL_CHARS = 10;

/** 节点标签取 action -> description -> step_id，并截断到约 10 个字符 */
const shortLabel = (step: TaskStep): string => {
  const raw = (step.action || step.description || step.step_id || '').trim() || '未命名';
  const chars = Array.from(raw);
  return chars.length > MAX_LABEL_CHARS ? chars.slice(0, MAX_LABEL_CHARS).join('') + '…' : raw;
};

/** 工具名过长时截断，保留可读性 */
const shortTool = (toolId: string): string => {
  if (!toolId) return '';
  return toolId.length > 12 ? toolId.slice(0, 11) + '…' : toolId;
};

const isNotFound = (err: unknown): boolean =>
  (err as { response?: { status?: number } } | undefined)?.response?.status === 404;

/** 按最长依赖链深度分层，并把同层节点水平居中分布 */
const buildLayout = (steps: TaskStep[], status: TaskStatusResponse | null): GraphLayout => {
  const result = status?.result ?? null;
  const taskState = (status?.status || '').toLowerCase();
  const unfinished = taskState === 'pending' || taskState === 'running' || taskState === '';
  const byId = new Map(steps.map((s) => [s.step_id, s]));

  const levelCache = new Map<string, number>();
  const levelOf = (id: string, seen: Set<string>): number => {
    const cached = levelCache.get(id);
    if (cached !== undefined) return cached;
    if (seen.has(id)) return 0;
    const step = byId.get(id);
    if (!step) return 0;
    seen.add(id);
    const deps = (step.dependencies ?? []).filter((d) => d !== id && byId.has(d));
    const level = deps.length === 0 ? 0 : Math.max(...deps.map((d) => levelOf(d, seen) + 1));
    seen.delete(id);
    levelCache.set(id, level);
    return level;
  };

  const stateOf = (id: string): StepState => {
    if (!result) return unfinished ? 'running' : 'pending';
    if (result.completed?.includes(id)) return 'completed';
    if (result.failed?.includes(id)) return 'failed';
    if (result.skipped?.includes(id)) return 'skipped';
    return unfinished ? 'running' : 'pending';
  };

  const rows = new Map<number, string[]>();
  steps.forEach((s) => {
    const level = levelOf(s.step_id, new Set());
    const row = rows.get(level);
    if (row) row.push(s.step_id);
    else rows.set(level, [s.step_id]);
  });

  const levelCount = rows.size === 0 ? 0 : Math.max(...Array.from(rows.keys())) + 1;
  const rowSizes = Array.from(rows.values()).map((r) => r.length);
  const maxRow = Math.max(1, ...rowSizes);
  const width = Math.max(MIN_W, maxRow * COL_W + PAD_X * 2);
  const height = Math.max(MIN_H, PAD_TOP + Math.max(0, levelCount - 1) * ROW_H + PAD_BOTTOM);
  const inner = Math.max(1, width - PAD_X * 2);

  const nodes: LaidOutStep[] = [];
  rows.forEach((ids, level) => {
    const y = PAD_TOP + level * ROW_H;
    ids.forEach((id, i) => {
      const step = byId.get(id);
      if (!step) return;
      const x = ids.length === 1 ? PAD_X + inner / 2 : PAD_X + (inner * i) / (ids.length - 1);
      const full = (step.action || step.description || step.step_id || '').trim() || step.step_id;
      nodes.push({
        toolId: (step.tool_ids && step.tool_ids[0]) || '',
        agentId: step.agent_id || '',
        id,
        label: shortLabel(step),
        fullLabel: full,
        state: stateOf(id),
        x,
        y,
        deps: (step.dependencies ?? []).filter((d) => d !== id && byId.has(d)),
      });
    });
  });

  return { nodes, width, height, parallelGroups: rowSizes.filter((n) => n > 1).length };
};

/** 详情卡片的一行 */
const Row: React.FC<{ label: string; value: string; mono?: boolean }> = ({ label, value, mono }) => (
  <div style={{ display: 'flex', gap: 6 }}>
    <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{label}：</span>
    <span style={{ wordBreak: 'break-all', fontFamily: mono ? 'var(--font-mono)' : undefined }}>{value}</span>
  </div>
);

/** 工具 / 依赖标签；highlight 表示这一步实际执行的就是它 */
const Chip: React.FC<{ text: string; highlight?: boolean }> = ({ text, highlight }) => (
  <span style={{
    display: 'inline-block', margin: '0 4px 2px 0', padding: '0 5px',
    borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)',
    background: highlight ? 'rgba(193,213,192,0.45)' : 'rgba(193,213,192,0.16)',
    border: highlight ? '1px solid var(--accent-sage)' : 'none',
    color: 'var(--text-secondary)',
  }}>{text}</span>
);

/** 输出摘要：截断长文本，避免撑破卡片 */
const previewJson = (v: unknown, max = 160): string => {
  let s: string;
  try { s = typeof v === 'string' ? v : JSON.stringify(v); } catch { s = String(v); }
  if (!s) return '—';
  return s.length > max ? s.slice(0, max) + '…' : s;
};
const DAGPanel: React.FC<DAGPanelProps> = ({ taskId }) => {
  const [hovered, setHovered] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  // 拉取任务状态：pending/running 每 2s 轮询，终态、404 或卸载时停止
  useEffect(() => {
    if (!taskId) {
      setStatus(null);
      setError(null);
      setNotFound(false);
      setLoading(false);
      return;
    }

    let cancelled = false;
    let inFlight = false;
    let timer: number | null = null;

    const stop = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const poll = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const res = await getTaskStatusApi(taskId);
        if (cancelled) return;
        const data = res.data;
        setStatus(data);
        setError(null);
        setNotFound(false);
        setLoading(false);
        const s = (data.status || '').toLowerCase();
        if (s !== 'pending' && s !== 'running') stop();
      } catch (err) {
        if (cancelled) return;
        setLoading(false);
        if (isNotFound(err)) {
          setStatus(null);
          setError(null);
          setNotFound(true);
          stop();
        } else {
          setError('任务状态获取失败');
        }
      } finally {
        inFlight = false;
      }
    };

    setLoading(true);
    setStatus(null);
    setError(null);
    setNotFound(false);
    void poll();
    timer = window.setInterval(() => void poll(), 2000);

    return () => {
      cancelled = true;
      stop();
    };
  }, [taskId]);

  const steps = useMemo<TaskStep[]>(
    () => (Array.isArray(status?.steps) ? status.steps : []),
    [status]
  );
  const layout = useMemo(() => buildLayout(steps, status), [steps, status]);
  const [selected, setSelected] = useState<string | null>(null);

  /** 取某一步的执行结果（tool_id / reason / output 都在这里） */
  const stepResultOf = (id: string): Record<string, unknown> | null => {
    const results = (status?.result as { results?: Record<string, Record<string, unknown>> } | null)?.results;
    return (results && results[id]) || null;
  };
  const { nodes, width, height, parallelGroups } = layout;

  /** 各状态计数，用于页脚摘要 */
  const counts = useMemo(() => {
    const c: Record<StepState, number> = { completed: 0, failed: 0, skipped: 0, running: 0, pending: 0 };
    nodes.forEach((n) => { c[n.state] += 1; });
    return c;
  }, [nodes]);

  const selectedNode = nodes.find((n) => n.id === selected) || null;
  const selectedStep = steps.find((s) => s.step_id === selected) || null;
  const selectedResult = selected ? stepResultOf(selected) : null;

  const statusKey = (status?.status || '').toLowerCase();
  const footer = loading
    ? '加载中'
    : notFound
      ? '任务不存在或已过期'
      : status
        ? steps.length + ' 步 · ' + parallelGroups + ' 并行组 · ' + (STATUS_TEXT[statusKey] ?? '未知')
          + '（成 ' + counts.completed + ' / 败 ' + counts.failed + ' / 跳 ' + counts.skipped + '）'
        : '暂无任务';

  const emptyState = (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: 12, padding: '40px 8px', textAlign: 'center',
    }}>
      <svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true">
        <circle cx="23" cy="9" r="6" fill="none" stroke="var(--accent-glacier)" strokeWidth="1.2" strokeDasharray="3 3" />
        <circle cx="10" cy="35" r="6" fill="none" stroke="var(--accent-glacier)" strokeWidth="1.2" strokeDasharray="3 3" />
        <circle cx="36" cy="35" r="6" fill="none" stroke="var(--accent-glacier)" strokeWidth="1.2" strokeDasharray="3 3" />
        <line x1="20" y1="14" x2="12" y2="29" stroke="#C1D5C0" strokeWidth="1" strokeDasharray="3 3" />
        <line x1="26" y1="14" x2="34" y2="29" stroke="#C1D5C0" strokeWidth="1" strokeDasharray="3 3" />
      </svg>
      <span style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.7 }}>
        暂无任务，发起一个任务后会显示执行拓扑
      </span>
    </div>
  );

  return (
    <div style={{
      width: 330,
      flexShrink: 0,
      background: 'var(--bg-white)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-card)',
      padding: '20px 16px',
      display: 'flex',
      flexDirection: 'column',
      maxHeight: '100%',
    }}>
      <h5 style={{ marginBottom: 4 }}>任务拓扑可视化</h5>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 16 }}>
        DAG 依赖 · 节点下方为工具名 · 点击节点看工具链与结果
      </span>

      {!taskId && emptyState}

      {taskId && notFound && (
        <div style={{ padding: '28px 8px', textAlign: 'center' }}>
          <span style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.7 }}>
            未找到该任务的执行拓扑（任务可能已过期）
          </span>
        </div>
      )}

      {taskId && !notFound && (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <svg
            width={width}
            height={height}
            viewBox={'0 0 ' + width + ' ' + height}
            style={{ display: 'block', margin: '0 auto' }}
          >
            {/* 连接线：每个依赖一条虚线 */}
            {nodes.map((node) =>
              node.deps.map((depId) => {
                const dep = nodes.find((n) => n.id === depId);
                if (!dep) return null;
                return (
                  <line
                    key={depId + '-' + node.id}
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
            {nodes.map((node) => (
              <g
                key={node.id}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => setSelected(selected === node.id ? null : node.id)}
                style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                transform={hovered === node.id
                  ? 'translate(' + node.x + ', ' + (node.y - 2) + ')'
                  : 'translate(' + node.x + ', ' + node.y + ')'
                }
              >
                <title>
                  {node.fullLabel + '（' + STATE_TEXT[node.state] + '）'
                    + (node.agentId ? '\nAgent: ' + node.agentId : '')
                    + (node.toolId ? '\n工具: ' + node.toolId : '')
                    + '\n（点击查看详情）'}
                </title>
                {/* 光晕 */}
                {(hovered === node.id || selected === node.id) && (
                  <circle cx={0} cy={0} r={22} fill="rgba(181,214,224,0.18)" />
                )}
                {selected === node.id && (
                  <circle cx={0} cy={0} r={NODE_R + 5} fill="none"
                    stroke={STATE_COLORS[node.state]} strokeWidth={1} strokeDasharray="2 2" opacity={0.8} />
                )}
                {/* 节点圆 */}
                <circle
                  cx={0} cy={0} r={NODE_R}
                  fill="var(--bg-white)"
                  stroke={STATE_COLORS[node.state]}
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
                  fill={node.state === 'pending' ? 'var(--text-muted)' : 'var(--text-primary)'}
                  fontSize={10}
                  fontWeight={500}
                  fontFamily="var(--font-family)"
                  letterSpacing="0.03em"
                >
                  {node.label}
                </text>
                {/* 工具名：让工具链直接可见，不必逐个点开 */}
                {node.toolId && (
                  <text
                    y={30}
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize={8}
                    fontFamily="var(--font-mono)"
                    letterSpacing="0.02em"
                  >
                    {shortTool(node.toolId)}
                  </text>
                )}
              </g>
            ))}
          </svg>
        </div>
      )}

      {/* 选中步骤详情：工具链 + 依赖 + 执行结果 */}
      {taskId && !notFound && selectedNode && (
        <div style={{
          marginTop: 10, padding: '10px 12px',
          background: 'var(--bg-white)',
          border: '1px solid rgba(193,213,192,0.6)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 11, lineHeight: 1.75,
          maxHeight: 220, overflow: 'auto',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: STATE_COLORS[selectedNode.state], flexShrink: 0 }} />
            <span style={{ fontWeight: 600, fontSize: 11.5 }}>{selectedNode.fullLabel}</span>
            <span style={{ color: STATE_COLORS[selectedNode.state], fontSize: 10.5 }}>
              {STATE_TEXT[selectedNode.state]}
            </span>
            <span
              onClick={() => setSelected(null)}
              style={{ marginLeft: 'auto', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 12 }}
            >
              ×
            </span>
          </div>

          <Row label="步骤 ID" value={selectedNode.id} mono />
          {selectedStep?.agent_id && <Row label="智能体" value={selectedStep.agent_id} mono />}
          {selectedStep?.action && <Row label="动作" value={selectedStep.action} mono />}
          {selectedStep?.description && <Row label="描述" value={selectedStep.description} />}

          <div style={{ marginTop: 6 }}>
            <span style={{ color: 'var(--text-muted)' }}>工具链：</span>
            {selectedStep?.tool_ids && selectedStep.tool_ids.length > 0 ? (
              selectedStep.tool_ids.map((t) => (
                <Chip key={t} text={t} highlight={String(selectedResult?.tool_id || '') === t} />
              ))
            ) : (
              <span style={{ color: 'var(--text-muted)' }}>（无，走智能体）</span>
            )}
          </div>

          {selectedStep?.dependencies && selectedStep.dependencies.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <span style={{ color: 'var(--text-muted)' }}>依赖：</span>
              {selectedStep.dependencies.map((d) => <Chip key={d} text={d} />)}
            </div>
          )}

          {selectedResult && (
            <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed rgba(193,213,192,0.5)' }}>
              {selectedResult.tool_id != null && <Row label="实际执行" value={String(selectedResult.tool_id)} mono />}
              {selectedResult.status != null && <Row label="返回状态" value={String(selectedResult.status)} mono />}
              {(selectedResult.reason != null || selectedResult.message != null) && (
                <Row label="说明" value={String(selectedResult.reason ?? selectedResult.message)} />
              )}
              {selectedResult.output != null && (
                <Row label="输出摘要" value={previewJson(selectedResult.output)} />
              )}
            </div>
          )}
        </div>
      )}
      <div style={{
        marginTop: 8,
        padding: '8px 12px',
        background: 'rgba(193,213,192,0.12)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 11,
        color: 'var(--text-secondary)',
        letterSpacing: '0.02em',
      }}>
        {error && !notFound ? error : footer}
      </div>
    </div>
  );
};

export default DAGPanel;
