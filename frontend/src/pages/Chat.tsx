import React, { useRef, useEffect, useState } from 'react';
import { Typography, Input, Tooltip, message as antdMessage } from 'antd';
import { SendOutlined, PaperClipOutlined, FolderOpenOutlined, DeleteOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  attachmentLimitsApi,
  chatApi,
  desktopStatusApi,
  getTaskStatusApi,
  uploadAttachmentApi,
  workspaceInfoApi,
  workspaceSelectApi,
} from '../api';
import type { AttachmentDescriptor, TaskStatusResponse } from '../api';
import { useChatStore } from '../stores/chatStore';
import DAGPanel from '../components/DAGPanel';
import ToolTraceCard from '../components/ToolTraceCard';
import { bulletText, stepOutputLines, summaryLines } from '../components/stepOutput';
import dayjs from 'dayjs';

const { Text } = Typography;

// 胶囊形引用标签
const CapsuleTag: React.FC<{ label: string }> = ({ label }) => (
  <span
    style={{
      display: 'inline-block',
      padding: '4px 14px',
      margin: '3px 4px',
      background: 'rgba(193,213,192,0.28)',
      color: '#2D3A30',
      borderRadius: 20,
      fontSize: 11.5,
      fontWeight: 500,
      letterSpacing: '0.02em',
      cursor: 'pointer',
      transition: 'var(--transition)',
      animation: 'floatUp 3s ease-in-out infinite',
    }}
    onMouseEnter={(e) => { (e.target as HTMLElement).style.transform = 'translateY(-2px)'; }}
    onMouseLeave={(e) => { (e.target as HTMLElement).style.transform = 'translateY(0)'; }}
  >
    {label}
  </span>
);

const ChatPage: React.FC = () => {
  const { messages, sessionId, streaming, addMessage, appendContent, setSessionId, setStreaming, setToolTrace } = useChatStore();
  const [input, setInput] = useState('');
  // 当前对话绑定的任务 ID，用于右侧 DAG 拓扑面板
  const [taskId, setTaskId] = useState<string | null>(null);
  // 附件与工作文件夹
  const [attachments, setAttachments] = useState<AttachmentDescriptor[]>([]);
  const [uploading, setUploading] = useState(false);
  const [desktopMode, setDesktopMode] = useState(false);
  const [workspace, setWorkspace] = useState<{ selected: boolean; root: string }>({
    selected: false,
    root: '',
  });
  const [dragging, setDragging] = useState(false);
  const [imageUnderstood, setImageUnderstood] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollTimerRef = useRef<number | null>(null);
  const pollGenRef = useRef(0);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // 初始化：探测桌面模式 / 工作文件夹 / 附件限制
  useEffect(() => {
    void (async () => {
      try {
        const st = (await desktopStatusApi()).data;
        setDesktopMode(st.desktop_mode);
        if (st.desktop_mode) {
          setWorkspace({ selected: st.workspace_selected, root: st.workspace_root });
        }
      } catch {
        setDesktopMode(false);
      }
      try {
        const lim = (await attachmentLimitsApi()).data;
        setImageUnderstood(lim.image_understood);
      } catch {
        /* 后端未就绪时忽略 */
      }
    })();
  }, []);

  /** 上传一批文件为附件 */
  const handleFiles = async (files: File[]) => {
    if (files.length === 0 || uploading) return;
    setUploading(true);
    for (const file of files) {
      try {
        const res = await uploadAttachmentApi(file);
        setAttachments((prev) => [...prev, res.data]);
      } catch (err) {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        antdMessage.error(detail || `${file.name} 上传失败`);
      }
    }
    setUploading(false);
  };

  /** 选择工作文件夹（桌面模式下弹系统原生对话框） */
  const pickWorkspace = async () => {
    try {
      const res = await workspaceSelectApi();
      if (res.data.cancelled) return;
      setWorkspace({ selected: res.data.selected, root: res.data.root });
      antdMessage.success(`工作文件夹已设为：${res.data.root}`);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      antdMessage.error(detail || '无法打开文件夹对话框');
    }
  };

  const removeAttachment = (id: string) =>
    setAttachments((prev) => prev.filter((a) => a.attachment_id !== id));

  // 组件卸载时停止任务轮询
  useEffect(
    () => () => {
      pollGenRef.current += 1;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    },
    []
  );

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      pollTimerRef.current = window.setTimeout(() => {
        pollTimerRef.current = null;
        resolve();
      }, ms);
    });

  const countOf = (value: string[] | undefined) => (Array.isArray(value) ? value.length : 0);

  /** 轮询任务状态并把进度追加到对应的助手消息中，最多约 60 秒 */
  const pollTask = async (taskId: string, assistantId: string, gen: number) => {
    const startedAt = Date.now();
    const MAX_POLL_MS = 60000;
    let lastProgress = -1;

    while (pollGenRef.current === gen && Date.now() - startedAt < MAX_POLL_MS) {
      await sleep(2000);
      if (pollGenRef.current !== gen) return;

      let data: TaskStatusResponse;
      try {
        data = (await getTaskStatusApi(taskId)).data;
      } catch {
        if (pollGenRef.current !== gen) return;
        appendContent(assistantId, '\n\n> ⚠️ 任务状态查询失败，请到任务中心查看进度');
        return;
      }
      if (pollGenRef.current !== gen) return;

      const status = (data.status || '').toLowerCase();
      const progress =
        typeof data.progress === 'number' && Number.isFinite(data.progress) ? Math.round(data.progress) : 0;
      const finished = status === 'completed' || status === 'failed' || status === 'cancelled';

      if (!finished && progress !== lastProgress) {
        appendContent(assistantId, `\n> 任务执行中… ${progress}%`);
        lastProgress = progress;
      }

      if (finished) {
        const label = status === 'completed' ? '已完成' : status === 'failed' ? '失败' : '已取消';
        const result = data.result;
        appendContent(
          assistantId,
          result
            ? `\n> 任务${label}：完成 ${countOf(result.completed)} 步 · 失败 ${countOf(result.failed)} 步 · 跳过 ${countOf(result.skipped)} 步`
            : `\n> 任务${label}`
        );
        if (result) {
          // 优先用后端预格式化的 summary，缺失时自行把 steps 产出转成可读行
          const summary = summaryLines(result.summary);
          const lines =
            summary.length > 0
              ? summary
              : Object.entries(result.results ?? {}).flatMap(([stepId, payload]) => {
                  const detail = stepOutputLines(payload);
                  return detail.length > 0 ? [`${stepId}｜${detail.join('，')}`] : [];
                });
          if (lines.length > 0) appendContent(assistantId, bulletText(lines));
        }
        if (status === 'failed') {
          appendContent(assistantId, `\n> ❌ 失败原因：${data.error || '后端未返回错误信息'}`);
        }
        return;
      }
    }

    if (pollGenRef.current === gen) {
      appendContent(assistantId, '\n> ⏱️ 任务仍在执行，请到任务中心查看最新进度');
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || streaming) return;
    const userMsg = { id: `u_${Date.now()}`, role: 'user' as const, content: input.trim(), timestamp: Date.now() };
    addMessage(userMsg);
    const currentInput = input.trim();
    setInput('');
    setStreaming(true);

    const assistantId = `a_${Date.now()}`;
    addMessage({ id: assistantId, role: 'assistant', content: '', timestamp: Date.now() });

    try {
      const res = await chatApi(currentInput, sessionId || undefined, attachments);
      setAttachments([]);
      const { session_id, answer, task_id, sources, tool_trace } = res.data;
      if (session_id) setSessionId(session_id);
      // 模型自主调用过工具时展示调用轨迹
      if (tool_trace && tool_trace.length > 0) setToolTrace(assistantId, tool_trace);
      for (const char of answer) {
        appendContent(assistantId, char);
        await new Promise((r) => setTimeout(r, 12));
      }
      if (task_id) {
        appendContent(assistantId, `\n\n> 任务ID: \`${task_id}\``);
        // 右侧拓扑面板跟随本次任务
        setTaskId(task_id);
        // 取消上一个任务的轮询，改为跟踪本次任务
        pollGenRef.current += 1;
        const gen = pollGenRef.current;
        void pollTask(task_id, assistantId, gen);
      }
    } catch {
      appendContent(assistantId, '抱歉，服务暂时不可用。');
    } finally {
      setStreaming(false);
    }
  };

  return (
    <>
      {/* 中间：对话画布 */}
      <div style={{
        flex: 1,
        background: 'var(--bg-white)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
      }}>
        {/* 点阵纹理背景 */}
        <div style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity: 0.035,
          backgroundImage: 'radial-gradient(circle, #999 1px, transparent 1px)',
          backgroundSize: '18px 18px',
        }} />

        {/* 工作文件夹栏（仅桌面模式） */}
        {desktopMode && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '9px 24px',
              borderBottom: '1px solid rgba(0,0,0,0.05)',
              background: 'rgba(193,213,192,0.14)',
              fontSize: 12,
              position: 'relative',
              zIndex: 1,
              flexWrap: 'wrap',
            }}
          >
            <FolderOpenOutlined style={{ color: 'var(--accent-sage)' }} />
            <span style={{ color: '#5b6b60' }}>工作文件夹：</span>
            <span
              style={{
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                color: workspace.selected ? '#2D3A30' : 'var(--text-muted)',
                wordBreak: 'break-all',
              }}
            >
              {workspace.selected ? workspace.root : '未选择（模型无法读写本地文件）'}
            </span>
            <button
              onClick={pickWorkspace}
              style={{
                marginLeft: 'auto',
                padding: '3px 12px',
                borderRadius: 12,
                border: '1px solid rgba(0,0,0,0.08)',
                background: '#fff',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              {workspace.selected ? '更换文件夹' : '选择文件夹'}
            </button>
          </div>
        )}

        {/* 消息列表（同时作为拖拽上传区域） */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const files = Array.from(e.dataTransfer.files || []);
            if (files.length > 0) void handleFiles(files);
          }}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px 28px',
            position: 'relative',
            zIndex: 1,
            outline: dragging ? '2px dashed var(--accent-glacier)' : 'none',
            outlineOffset: -8,
            background: dragging ? 'rgba(228,238,240,0.5)' : 'transparent',
          }}
        >
          {messages.length === 0 && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              height: '100%', gap: 16, opacity: 0.7,
            }}>
              {/* 中央大尺寸渐变AI气泡 */}
              <div style={{
                maxWidth: 560,
                width: '100%',
                padding: '36px 32px',
                borderRadius: 'var(--radius-xl)',
                background: 'linear-gradient(135deg, #E8F3F0 0%, #E4EEF0 100%)',
                boxShadow: 'var(--shadow-soft)',
                textAlign: 'center',
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--accent-sage), var(--accent-glacier))',
                  margin: '0 auto 16px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18,
                }}>
                  🌊
                </div>
                <h3 style={{ marginBottom: 8 }}>工程对话画布</h3>
                <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.7 }}>
                  输入您的问题，AI 将基于规范标准库与专业知识图谱进行智能分析。
                  支持稳性计算、型线设计、规范审查等专业任务。
                </Text>
                <div style={{ marginTop: 20 }}>
                  <CapsuleTag label="规范引用" />
                  <CapsuleTag label="船舶结构力学" />
                  <CapsuleTag label="海况数据" />
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                gap: 10,
                marginBottom: 18,
                animation: 'fadeIn 0.3s ease-out',
              }}
            >
              {/* 聊天气泡 */}
              <div
                style={{
                  maxWidth: '72%',
                  padding: '14px 20px',
                  borderRadius: msg.role === 'user'
                    ? 'var(--radius-lg) 4px var(--radius-lg) var(--radius-lg)'
                    : '4px var(--radius-lg) var(--radius-lg) var(--radius-lg)',
                  background: msg.role === 'user'
                    ? 'var(--bubble-right)'
                    : 'var(--bubble-left)',
                  boxShadow: 'var(--shadow-soft)',
                }}
              >
                {msg.toolTrace && msg.toolTrace.length > 0 && (
                  <ToolTraceCard trace={msg.toolTrace} />
                )}
                <div className="markdown-body" style={{ fontSize: '13.5px', lineHeight: 1.75 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content || (streaming ? '...' : '')}
                  </ReactMarkdown>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6, textAlign: 'right' }}>
                  {dayjs(msg.timestamp).format('HH:mm')}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div style={{
          padding: '14px 24px',
          borderTop: '1px solid rgba(0,0,0,0.04)',
          background: 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(8px)',
          position: 'relative',
          zIndex: 1,
        }}>
          {/* 已选附件 */}
          {attachments.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {attachments.map((a) => (
                <span
                  key={a.attachment_id}
                  title={a.note || `${a.kind} · ${a.chars} 字符`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 8px',
                    borderRadius: 10,
                    background: a.kind === 'image' ? 'rgba(214,178,110,0.18)' : 'rgba(120,180,140,0.16)',
                    fontSize: 11.5,
                    color: '#2D3A30',
                  }}
                >
                  <span>{a.filename}</span>
                  <span style={{ color: 'var(--text-muted)' }}>
                    {a.kind === 'image' ? '图片·不可解析' : `${a.chars} 字`}
                  </span>
                  <DeleteOutlined
                    onClick={() => removeAttachment(a.attachment_id)}
                    style={{ cursor: 'pointer', fontSize: 10, opacity: 0.6 }}
                  />
                </span>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
            {/* 附件选择 */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => {
                void handleFiles(Array.from(e.target.files || []));
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
            />
            <Tooltip title="添加附件（图片 / PDF / 文本 / 表格）">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={streaming || uploading}
                style={{
                  width: 40, height: 40, borderRadius: '50%',
                  border: '1px solid rgba(0,0,0,0.08)',
                  background: 'var(--bg-base)',
                  color: uploading ? '#bbb' : '#5b6b60',
                  cursor: streaming || uploading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <PaperClipOutlined />
              </button>
            </Tooltip>
            <Input.TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onPaste={(e) => {
                const files = Array.from(e.clipboardData?.files || []);
                if (files.length > 0) {
                  e.preventDefault();
                  void handleFiles(files);
                }
              }}
              onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="输入工程问题，Enter 发送，Shift+Enter 换行..."
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={streaming}
              style={{
                flex: 1,
                borderRadius: 'var(--radius-lg)',
                border: '1px solid rgba(0,0,0,0.08)',
                background: 'var(--bg-base)',
                fontSize: 13.5,
                padding: '10px 16px',
                resize: 'none',
              }}
            />
            <button
              onClick={sendMessage}
              disabled={streaming}
              style={{
                width: 40, height: 40, borderRadius: '50%',
                border: 'none',
                background: streaming ? '#e0e0e0' : 'linear-gradient(135deg, var(--accent-sage), var(--accent-glacier))',
                color: '#fff',
                cursor: streaming ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'var(--transition)',
                flexShrink: 0,
              }}
            >
              <SendOutlined />
            </button>
          </div>
          <Text type="secondary" style={{ fontSize: 10, marginTop: 6, display: 'block', textAlign: 'center' }}>
            输出内容基于 AI 生成，请以规范原文为准
          </Text>
        </div>
      </div>

      {/* 右侧 DAG 拓扑面板 */}
      <DAGPanel taskId={taskId} />
    </>
  );
};

export default ChatPage;
