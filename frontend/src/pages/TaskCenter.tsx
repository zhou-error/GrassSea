import React from 'react';
import { Typography, Progress } from 'antd';

const { Text } = Typography;

const dummyTasks = [
  { id: '1', title: '稳性计算与报告生成', type: '专业任务', status: 'completed', progress: 100, agent: 'naval_arch_agent', time: '10:30' },
  { id: '2', title: 'CCS 规范合规审查', type: '工具调用', status: 'running', progress: 68, agent: 'review_agent', time: '10:35' },
  { id: '3', title: '散货船型线设计优化', type: '子代理编排', status: 'running', progress: 42, agent: 'pm_agent', time: '10:38' },
  { id: '4', title: '文献检索：船型改造技术', type: '知识查询', status: 'pending', progress: 0, agent: 'research_agent', time: '10:40' },
];

const statusStyle: Record<string, { bg: string; color: string; dot: string }> = {
  completed: { bg: 'rgba(125,187,138,0.10)', color: '#3D5A3F', dot: 'var(--status-green)' },
  running: { bg: 'rgba(181,214,224,0.12)', color: '#3D5A5F', dot: '#7BB5D0' },
  pending: { bg: 'rgba(0,0,0,0.03)', color: '#888', dot: '#ccc' },
  failed: { bg: 'rgba(224,108,108,0.08)', color: '#8B3A3A', dot: '#E06C6C' },
};

const TaskCenterPage: React.FC = () => (
  <div style={{ flex: 1, overflow: 'auto' }}>
    <div style={{
      background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-card)', padding: '24px 28px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h3 style={{ marginBottom: 2 }}>智能体任务</h3>
          <Text type="secondary" style={{ fontSize: 12 }}>多智能体协同任务执行状态与进度</Text>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: 'var(--status-green)',
            display: 'inline-block', marginTop: 5,
          }} />
          <Text type="secondary" style={{ fontSize: 11 }}>2 个智能体在线</Text>
        </div>
      </div>

      {dummyTasks.map((task) => {
        const st = statusStyle[task.status] || statusStyle.pending;
        return (
          <div
            key={task.id}
            style={{
              padding: '16px 20px',
              borderRadius: 'var(--radius-md)',
              marginBottom: 8,
              background: task.status === 'running' ? 'rgba(181,214,224,0.04)' : 'transparent',
              transition: 'var(--transition)',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(193,213,192,0.05)'; }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = task.status === 'running' ? 'rgba(181,214,224,0.04)' : 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: st.dot, flexShrink: 0 }} />
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 500, color: 'var(--text-primary)' }}>
                {task.title}
              </span>
              <span style={{
                fontSize: 10.5, padding: '2px 10px', borderRadius: 20,
                background: st.bg, color: st.color, fontWeight: 500,
              }}>
                {task.status === 'completed' ? '已完成' : task.status === 'running' ? '运行中' : '等待中'}
              </span>
            </div>
            <Progress
              percent={task.progress}
              size="small"
              showInfo={false}
              strokeColor={{
                '0%': '#B5D6E0',
                '100%': '#C1D5C0',
              }}
              trailColor="rgba(0,0,0,0.04)"
              style={{ marginBottom: 6 }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                <span className="mono" style={{ fontSize: 11 }}>{task.agent}</span>
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>{task.time}</Text>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

export default TaskCenterPage;
