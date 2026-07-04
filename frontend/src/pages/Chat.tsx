import React, { useRef, useEffect, useState } from 'react';
import { Typography, Input } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi } from '../api';
import { useChatStore } from '../stores/chatStore';
import DAGPanel from '../components/DAGPanel';
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
  const { messages, sessionId, streaming, addMessage, appendContent, setSessionId, setStreaming } = useChatStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

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
      const res = await chatApi(currentInput, sessionId || undefined);
      const { session_id, answer, task_id, sources } = res.data;
      if (session_id) setSessionId(session_id);
      for (const char of answer) {
        appendContent(assistantId, char);
        await new Promise((r) => setTimeout(r, 12));
      }
      if (task_id) appendContent(assistantId, `\n\n> 任务ID: \`${task_id}\``);
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

        {/* 消息列表 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px', position: 'relative', zIndex: 1 }}>
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
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
            <Input.TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
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
      <DAGPanel />
    </>
  );
};

export default ChatPage;
