import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Modal, Progress, Spin, Tag, Typography, message } from 'antd';
import { InboxOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getTaskStatusApi, listAgentsApi, listTasksApi } from '../api';
import type { AgentInfo, TaskResult, TaskStatusResponse, TaskSummary } from '../api';
import { LineList, stepOutputLines, summaryLines } from '../components/stepOutput';

const { Text } = Typography;

const REFRESH_INTERVAL_MS = 3000;

/** 任务状态 -> 中文标签与配色 */
const statusMeta: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  pending: { label: '等待中', color: '#8A8A8A', bg: 'rgba(0,0,0,0.04)', dot: '#C4C4C4' },
  running: { label: '运行中', color: '#3D5A5F', bg: 'rgba(181,214,224,0.16)', dot: '#7BB5D0' },
  completed: { label: '已完成', color: '#3D5A3F', bg: 'rgba(125,187,138,0.12)', dot: 'var(--status-green)' },
  failed: { label: '失败', color: '#8B3A3A', bg: 'rgba(224,108,108,0.10)', dot: '#E06C6C' },
  cancelled: { label: '已取消', color: '#8A7350', bg: 'rgba(212,168,83,0.14)', dot: '#D4A853' },
};

const fallbackMeta = { label: '未知', color: '#8A8A8A', bg: 'rgba(0,0,0,0.04)', dot: '#C4C4C4' };

const metaOf = (status: string) => statusMeta[(status || '').toLowerCase()] ?? fallbackMeta;

/** 视为“不在线”的智能体状态；其余状态计入在线数 */
const OFFLINE_AGENT_STATUS = ['offline', 'stopped', 'error', 'inactive', 'disconnected'];
const isAgentOnline = (agent: AgentInfo) =>
  !OFFLINE_AGENT_STATUS.includes((agent.status || '').toLowerCase());

/** 从 axios 错误中提取可读信息，避免依赖 any */
const errorText = (err: unknown, fallback: string): string => {
  const e = err as {
    response?: { data?: { detail?: unknown; message?: unknown } };
    message?: unknown;
  };
  const detail = e?.response?.data?.detail ?? e?.response?.data?.message;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (typeof e?.message === 'string' && e.message.trim() && e.message !== 'Network Error') return e.message;
  return fallback;
};

const progressPercent = (value: number): number => {
  const n = typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : 0;
  return Math.max(0, Math.min(100, n));
};

const createdText = (iso: string): string => {
  const d = dayjs(iso);
  return d.isValid() ? d.format('MM-DD HH:mm:ss') : iso || '—';
};

const listOf = <T,>(value: T[] | undefined | null): T[] => (Array.isArray(value) ? value : []);

const stepCount = (task: TaskSummary): number =>
  typeof task.steps_total === 'number' && Number.isFinite(task.steps_total) ? task.steps_total : 0;

/** 步骤状态：优先用 result 中的完成/失败/跳过名单判定 */
const stepState = (
  stepId: string,
  result: TaskResult | null,
  taskStatus: string
): { label: string; color: string; bg: string; dot: string } => {
  if (result) {
    if (listOf(result.completed).includes(stepId)) {
      return { label: '已完成', color: '#3D5A3F', bg: 'rgba(125,187,138,0.12)', dot: 'var(--status-green)' };
    }
    if (listOf(result.failed).includes(stepId)) {
      return { label: '失败', color: '#8B3A3A', bg: 'rgba(224,108,108,0.10)', dot: '#E06C6C' };
    }
    if (listOf(result.skipped).includes(stepId)) {
      return { label: '跳过', color: '#8A7350', bg: 'rgba(212,168,83,0.14)', dot: '#D4A853' };
    }
  }
  return metaOf(taskStatus);
};

const secondaryButtonStyle: React.CSSProperties = {
  height: 34,
  padding: '0 16px',
  border: '1px solid rgba(0,0,0,0.10)',
  borderRadius: 'var(--radius-md)',
  background: 'transparent',
  color: 'var(--text-secondary)',
  fontSize: 12.5,
  fontWeight: 500,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  transition: 'var(--transition)',
};

const statusPillStyle = (meta: { color: string; bg: string }): React.CSSProperties => ({
  fontSize: 10.5,
  padding: '2px 10px',
  borderRadius: 20,
  background: meta.bg,
  color: meta.color,
  fontWeight: 500,
  flexShrink: 0,
});

const TaskCenterPage: React.FC = () => {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentsError, setAgentsError] = useState(false);

  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TaskStatusResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailReloadKey, setDetailReloadKey] = useState(0);

  const loadTasks = useCallback(async (silent: boolean) => {
    if (!silent) setLoading(true);
    try {
      const res = await listTasksApi();
      const list = res.data?.tasks;
      setTasks(Array.isArray(list) ? list : []);
      setLoadError(null);
    } catch (err) {
      const msg = errorText(err, '任务列表加载失败，请确认后端服务可用');
      setLoadError(msg);
      if (!silent) message.error(msg);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const res = await listAgentsApi();
      const list = res.data?.agents;
      setAgents(Array.isArray(list) ? list : []);
      setAgentsError(false);
    } catch {
      setAgents([]);
      setAgentsError(true);
    }
  }, []);

  // 首次加载 + 每 3 秒自动刷新，离开页面时清理定时器
  useEffect(() => {
    void loadTasks(false);
    void loadAgents();
    const timer = window.setInterval(() => {
      void loadTasks(true);
      void loadAgents();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [loadTasks, loadAgents]);

  // 详情弹窗：打开期间同步轮询，关闭即停止
  useEffect(() => {
    if (!detailId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    let alive = true;
    const load = async (silent: boolean) => {
      if (!silent) setDetailLoading(true);
      try {
        const res = await getTaskStatusApi(detailId);
        if (!alive) return;
        setDetail(res.data);
        setDetailError(null);
      } catch (err) {
        if (!alive) return;
        setDetailError(errorText(err, '任务详情加载失败，请稍后重试'));
      } finally {
        if (alive && !silent) setDetailLoading(false);
      }
    };
    void load(false);
    const timer = window.setInterval(() => void load(true), REFRESH_INTERVAL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [detailId, detailReloadKey]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([loadTasks(true), loadAgents()]);
    setRefreshing(false);
  };

  const onlineAgents = useMemo(() => agents.filter(isAgentOnline).length, [agents]);

  const agentSummary = agentsError
    ? '智能体状态不可用'
    : agents.length === 0
      ? '暂无在线智能体'
      : `${onlineAgents} 个智能体在线`;

  const detailTask = useMemo(
    () => (detailId ? tasks.find((t) => t.task_id === detailId) : undefined),
    [tasks, detailId]
  );
  const detailStatus = detail?.status ?? detailTask?.status ?? 'pending';
  const detailMeta = metaOf(detailStatus);
  // 后端预格式化的一步一行摘要（可能不存在）
  const detailSummary = useMemo(() => summaryLines(detail?.result?.summary), [detail]);

  return (
    <div style={{ flex: 1, overflow: 'auto' }}>
      <div style={{
        background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-card)', padding: '24px 28px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, gap: 16 }}>
          <div>
            <h3 style={{ marginBottom: 2 }}>智能体任务</h3>
            <Text type="secondary" style={{ fontSize: 12 }}>
              多智能体协同任务执行状态与进度
              {!loading && !loadError && ` · 共 ${tasks.length} 个任务`}
            </Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: agentsError ? 'var(--text-muted)' : 'var(--status-green)',
                display: 'inline-block',
              }} />
              <Text type="secondary" style={{ fontSize: 11 }}>{agentSummary}</Text>
            </div>
            <button
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              style={{ ...secondaryButtonStyle, cursor: refreshing ? 'not-allowed' : 'pointer', opacity: refreshing ? 0.6 : 1 }}
            >
              <ReloadOutlined spin={refreshing} /> {refreshing ? '刷新中...' : '刷新'}
            </button>
          </div>
        </div>

        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '48px 0' }}>
            <Spin />
            <Text type="secondary" style={{ fontSize: 12 }}>正在加载任务列表...</Text>
          </div>
        )}

        {!loading && loadError && tasks.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary" style={{ fontSize: 12.5, display: 'block', marginBottom: 14 }}>{loadError}</Text>
            <button onClick={() => void loadTasks(false)} style={secondaryButtonStyle}>重新加载</button>
          </div>
        )}

        {!loading && !loadError && tasks.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
            padding: '44px 0', opacity: 0.85,
          }}>
            <InboxOutlined style={{ fontSize: 28, color: 'var(--text-muted)' }} />
            <Text type="secondary" style={{ fontSize: 12.5 }}>暂无任务，去对话页发起一个任务吧</Text>
          </div>
        )}

        {!loading && tasks.map((task) => {
          const st = metaOf(task.status);
          const pct = progressPercent(task.progress);
          const running = (task.status || '').toLowerCase() === 'running';
          return (
            <div
              key={task.task_id}
              onClick={() => setDetailId(task.task_id)}
              style={{
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                marginBottom: 8,
                background: running ? 'rgba(181,214,224,0.04)' : 'transparent',
                transition: 'var(--transition)',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(193,213,192,0.05)'; }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = running ? 'rgba(181,214,224,0.04)' : 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: st.dot, flexShrink: 0 }} />
                <span style={{
                  flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 500, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {task.title || '未命名任务'}
                </span>
                {task.intent && (
                  <Tag style={{
                    background: 'rgba(193,213,192,0.18)', border: 'none',
                    color: '#3D5A45', borderRadius: 20, fontSize: 11, marginInlineEnd: 0, flexShrink: 0,
                  }}>
                    {task.intent}
                  </Tag>
                )}
                <span style={statusPillStyle(st)}>{st.label}</span>
              </div>
              <Progress
                percent={pct}
                size="small"
                showInfo={false}
                strokeColor={{ '0%': '#B5D6E0', '100%': '#C1D5C0' }}
                trailColor="rgba(0,0,0,0.04)"
                style={{ marginBottom: 6 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                  <Text type="secondary" style={{ fontSize: 11, flexShrink: 0 }}>
                    {pct}% · {stepCount(task)} 步
                  </Text>
                  <span className="mono" style={{
                    fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden',
                    textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 240,
                  }}>
                    {task.task_id}
                  </span>
                </div>
                <Text type="secondary" style={{ fontSize: 11, flexShrink: 0 }}>
                  {createdText(task.created_at)}
                </Text>
              </div>
            </div>
          );
        })}
      </div>

      <Modal
        open={detailId !== null}
        title={detail ? (detailTask?.title || detail.task_id) : (detailTask?.title || detailId || '任务详情')}
        onCancel={() => setDetailId(null)}
        footer={null}
        width={720}
        styles={{ body: { maxHeight: '62vh', overflow: 'auto' } }}
      >
        {detailLoading && !detail && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '32px 0' }}>
            <Spin />
            <Text type="secondary" style={{ fontSize: 12 }}>正在加载任务详情...</Text>
          </div>
        )}

        {!detailLoading && detailError && !detail && (
          <div style={{ textAlign: 'center', padding: '28px 0' }}>
            <Text type="secondary" style={{ fontSize: 12.5, display: 'block', marginBottom: 14 }}>{detailError}</Text>
            <button onClick={() => setDetailReloadKey((k) => k + 1)} style={secondaryButtonStyle}>重新加载</button>
          </div>
        )}

        {detail && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: detailMeta.dot, flexShrink: 0 }} />
              <span style={statusPillStyle(detailMeta)}>{detailMeta.label}</span>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {progressPercent(detail.progress)}% · 共 {listOf(detail.steps).length} 步
              </Text>
              <span style={{ flex: 1 }} />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{detail.task_id}</span>
            </div>

            <Progress
              percent={progressPercent(detail.progress)}
              size="small"
              showInfo={false}
              strokeColor={{ '0%': '#B5D6E0', '100%': '#C1D5C0' }}
              trailColor="rgba(0,0,0,0.04)"
            />

            {detailError && (
              <div style={{ marginTop: 10, fontSize: 11.5, color: '#8B7350' }}>
                状态刷新失败，以下为最近一次获取的结果：{detailError}
              </div>
            )}

            {detail.error && (
              <div style={{
                marginTop: 14, padding: '10px 14px', borderRadius: 'var(--radius-md)',
                background: 'rgba(224,108,108,0.06)', color: '#8B3A3A', fontSize: 12.5, lineHeight: 1.7,
                whiteSpace: 'pre-wrap',
              }}>
                {detail.error}
              </div>
            )}

            {detailSummary.length > 0 && (
              <div style={{
                marginTop: 14, padding: '12px 14px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-base)', borderLeft: '2px solid var(--accent-sage)',
              }}>
                <div style={{ marginBottom: 6 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>任务结果摘要</Text>
                </div>
                <LineList
                  lines={detailSummary}
                  style={{
                    fontSize: 12, lineHeight: 1.75, color: 'var(--text-secondary)',
                    paddingLeft: 14,
                  }}
                />
              </div>
            )}

            <div style={{ marginTop: 18, marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>步骤详情</Text>
            </div>

            {listOf(detail.steps).length === 0 && (
              <div style={{ padding: '20px 0', textAlign: 'center' }}>
                <Text type="secondary" style={{ fontSize: 12.5 }}>
                  {detail.result === null ? '任务仍在执行中，暂无步骤产出' : '该任务没有记录步骤'}
                </Text>
              </div>
            )}

            {listOf(detail.steps).map((step) => {
              const st = stepState(step.step_id, detail.result, detail.status);
              const outputLines = detail.result ? stepOutputLines(detail.result.results?.[step.step_id]) : [];
              return (
                <div
                  key={step.step_id}
                  style={{
                    padding: '12px 16px', marginBottom: 8,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-base)',
                    borderLeft: `2px solid ${st.dot}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                      {step.step_id}
                    </span>
                    <span style={{
                      flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {step.action || step.description || '未命名步骤'}
                    </span>
                    <span style={statusPillStyle(st)}>{st.label}</span>
                  </div>
                  {step.action && step.description && (
                    <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginBottom: 4 }}>{step.description}</div>
                  )}
                  {step.agent_id && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                      智能体 <span className="mono">{step.agent_id}</span>
                    </div>
                  )}
                  {outputLines.length > 0 && (
                    <div style={{
                      marginTop: 6, padding: '10px 12px', borderRadius: 'var(--radius-md)',
                      background: 'var(--bg-white)', fontSize: 12,
                      color: 'var(--text-secondary)', maxHeight: 220, overflow: 'auto',
                    }}>
                      <LineList lines={outputLines} />
                    </div>
                  )}
                </div>
              );
            })}

            {/* 后端未提供 summary 时，按步骤汇总一份可读产出 */}
            {detail.result && detailSummary.length === 0 && listOf(detail.steps).length > 0 && (
              <div style={{
                marginTop: 14, padding: '12px 14px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-base)', borderLeft: '2px solid var(--accent-sage)',
              }}>
                <div style={{ marginBottom: 6 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>任务结果摘要</Text>
                </div>
                <LineList
                  lines={listOf(detail.steps).flatMap((step) => {
                    const lines = stepOutputLines(detail.result?.results?.[step.step_id]);
                    return lines.length > 0
                      ? [`${step.step_id}｜${step.action || step.description || '未命名步骤'}`, ...lines]
                      : [];
                  })}
                  style={{
                    fontSize: 12, lineHeight: 1.75, color: 'var(--text-secondary)',
                    paddingLeft: 14,
                  }}
                />
              </div>
            )}

            {detail.result === null && listOf(detail.steps).length > 0 && (
              <Text type="secondary" style={{ fontSize: 11.5 }}>
                任务仍在执行中，下方步骤产出会随进度更新
              </Text>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TaskCenterPage;
