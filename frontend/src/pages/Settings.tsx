import React, { useEffect, useState } from 'react';
import { Input, InputNumber, Select, Button, Typography, message, Alert, Collapse, Tag, Spin } from 'antd';
import { SaveOutlined, ReloadOutlined, FolderOpenOutlined, FileWordOutlined } from '@ant-design/icons';
import { docOpenFolderApi, docStatusApi } from '../api';
import type { DocStatus } from '../api';
import axios from 'axios';

const { Title, Text } = Typography;

interface ConfigItem {
  key: string; label: string; value: string; category: string;
  type: string; sensitive: boolean; default?: string; options?: string[];
}

const categoryInfo: Record<string, { icon: string; desc: string }> = {
  LLM:  { icon: '🔑', desc: '大语言模型 API 密钥与接口配置' },
  模型: { icon: '🧠', desc: 'Embedding 模型与向量化参数' },
  RAG:  { icon: '📚', desc: '检索增强生成参数调优' },
  会话: { icon: '💬', desc: '对话会话管理设置' },
  搜索: { icon: '🔍', desc: '联网搜索引擎 API 密钥' },
};

const SettingsPage: React.FC = () => {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [edited, setEdited] = useState<Record<string, string>>({});
  const [testMsg, setTestMsg] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [docStatus, setDocStatus] = useState<DocStatus | null>(null);
  const [openingFolder, setOpeningFolder] = useState(false);

  useEffect(() => { loadConfigs(); loadDocStatus(); }, []);

  const loadDocStatus = async () => {
    try {
      const res = await docStatusApi();
      setDocStatus(res.data);
    } catch { /* 后端未就绪时忽略 */ }
  };

  const openTemplateFolder = async (path?: string) => {
    setOpeningFolder(true);
    try {
      const res = await docOpenFolderApi(path);
      message.success('已打开：' + res.data.path);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(detail || '无法打开文件夹（该功能仅桌面模式可用）');
    } finally {
      setOpeningFolder(false);
    }
  };

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/config/schema');
      setConfigs(res.data);
      setEdited(Object.fromEntries(res.data.map((c: ConfigItem) => [c.key, c.sensitive ? '' : c.value])));
    } catch { message.error('加载配置失败'); }
    finally { setLoading(false); }
  };

  const handleSave = async (key: string) => {
    if (!edited[key]) { message.warning('请输入值'); return; }
    setSaving((s) => ({ ...s, [key]: true }));
    try {
      await axios.put('/api/config/update', { key, value: edited[key] });
      message.success('已保存');
      setConfigs((p) => p.map((c) => c.key === key ? { ...c, value: c.sensitive ? '****' : edited[key] } : c));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally { setSaving((s) => ({ ...s, [key]: false })); }
  };

  const testLLM = async () => {
    setTesting(true); setTestMsg(null);
    try {
      const res = await axios.post('/api/config/test-llm');
      setTestMsg({ type: res.data.status === 'ok' ? 'success' : 'error', msg: res.data.message });
    } catch {
      setTestMsg({ type: 'error', msg: '测试请求失败' });
    } finally { setTesting(false); }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />;

  const grouped: Record<string, ConfigItem[]> = {};
  configs.forEach((c) => { (grouped[c.category] = grouped[c.category] || []).push(c); });

  return (
    <div style={{ flex: 1, overflow: 'auto' }}>
      <div style={{
        background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-card)', padding: '28px',
      }}>
        <h3 style={{ marginBottom: 4 }}>系统配置</h3>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 24 }}>
          修改配置后需重启服务生效。敏感字段不完整回显。
        </Text>

        <Collapse
          ghost
          expandIconPosition="end"
          items={Object.entries(grouped).map(([cat, items]) => ({
            key: cat,
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span>{categoryInfo[cat]?.icon || '⚙️'}</span>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{cat}</span>
                <Tag style={{ background: 'rgba(193,213,192,0.18)', border: 'none', color: '#3D5A45', borderRadius: 20 }}>
                  {items.length} 项
                </Tag>
              </div>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingLeft: 8 }}>
                {items.map((item) => (
                  <div key={item.key} style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    <div style={{ width: 170, flexShrink: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{item.label}</div>
                      <Text type="secondary" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{item.key}</Text>
                    </div>
                    <div style={{ flex: 1 }}>
                      {item.type === 'select' && item.options ? (
                        <Select
                          value={edited[item.key] || item.value}
                          onChange={(v) => setEdited((p) => ({ ...p, [item.key]: v }))}
                          options={item.options.map((o) => ({ value: o, label: o }))}
                          style={{ width: '100%', borderRadius: 'var(--radius-sm)' }}
                        />
                      ) : item.type === 'number' ? (
                        <InputNumber
                          value={Number(edited[item.key] || item.value)}
                          onChange={(v) => setEdited((p) => ({ ...p, [item.key]: String(v ?? '') }))}
                          style={{ width: '100%', borderRadius: 'var(--radius-sm)' }}
                        />
                      ) : item.type === 'password' ? (
                        <Input.Password
                          placeholder={item.sensitive && item.value ? '**** (已设置)' : `输入 ${item.label}`}
                          value={edited[item.key]}
                          onChange={(e) => setEdited((p) => ({ ...p, [item.key]: e.target.value }))}
                          style={{ borderRadius: 'var(--radius-sm)' }}
                        />
                      ) : (
                        <Input
                          value={edited[item.key] || item.value}
                          onChange={(e) => setEdited((p) => ({ ...p, [item.key]: e.target.value }))}
                          style={{ borderRadius: 'var(--radius-sm)' }}
                        />
                      )}
                    </div>
                    <Button
                      icon={<SaveOutlined />}
                      onClick={() => handleSave(item.key)}
                      loading={saving[item.key]}
                      style={{
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid rgba(0,0,0,0.1)',
                        background: 'transparent',
                        color: 'var(--text-secondary)',
                      }}
                    />
                  </div>
                ))}
              </div>
            ),
          }))}
        />

        {/* LLM 测试 */}
        <div style={{
          marginTop: 24, padding: '16px 20px',
          background: 'rgba(245,245,245,0.6)', borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button
              icon={<ReloadOutlined />}
              onClick={testLLM}
              loading={testing}
              style={{
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--accent-sage)',
                background: 'rgba(193,213,192,0.08)',
                color: '#3D5A45',
              }}
            >
              测试 LLM 连接
            </Button>
            {testMsg && <Alert type={testMsg.type} message={testMsg.msg} showIcon style={{ flex: 1 }} />}
          </div>
        </div>

        {/* Word / PDF 文档能力 */}
        {docStatus && (
          <div style={{
            marginTop: 24, padding: '16px 20px',
            background: 'rgba(245,245,245,0.6)', borderRadius: 'var(--radius-md)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <FileWordOutlined style={{ color: '#3D5A45' }} />
              <Text strong style={{ fontSize: 13.5 }}>Word 文档能力</Text>
              <Tag color={docStatus.converters.word || docStatus.converters.libreoffice ? 'green' : 'orange'}>
                PDF 转换：{docStatus.pdf_converter}
              </Tag>
            </div>

            <div style={{ fontSize: 12.5, lineHeight: 2, color: '#3D4A40' }}>
              <div>
                转换引擎：
                <Tag color={docStatus.converters.word ? 'green' : 'default'}>Word</Tag>
                <Tag color={docStatus.converters.libreoffice ? 'green' : 'default'}>LibreOffice</Tag>
                {!docStatus.converters.word && !docStatus.converters.libreoffice && (
                  <Text type="danger" style={{ fontSize: 12 }}>两者均不可用，PDF 转换会报错</Text>
                )}
              </div>
              <div style={{ wordBreak: 'break-all' }}>
                排版模板：
                <Text code style={{ fontSize: 11.5 }}>
                  {docStatus.template.active_path || '未找到模板文件（将使用内置默认排版）'}
                </Text>
                {docStatus.template.user_exists && <Tag style={{ marginLeft: 6 }}>用户覆盖</Tag>}
              </div>
              <div style={{ wordBreak: 'break-all' }}>
                仓库默认模板：<Text code style={{ fontSize: 11.5 }}>{docStatus.template.repo_path}</Text>
              </div>
              <div style={{ wordBreak: 'break-all' }}>
                输出目录：<Text code style={{ fontSize: 11.5 }}>{docStatus.output_dir}</Text>
              </div>
            </div>

            <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button
                size="small"
                icon={<FolderOpenOutlined />}
                loading={openingFolder}
                disabled={!docStatus.desktop_mode}
                onClick={() => openTemplateFolder(docStatus.template.base_dir)}
                style={{ borderRadius: 'var(--radius-sm)' }}
              >
                打开模板文件夹
              </Button>
              <Button size="small" onClick={loadDocStatus} icon={<ReloadOutlined />} style={{ borderRadius: 'var(--radius-sm)' }}>
                刷新状态
              </Button>
              {!docStatus.desktop_mode && (
                <Text type="secondary" style={{ fontSize: 11.5, alignSelf: 'center' }}>
                  「打开文件夹」仅桌面模式可用
                </Text>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsPage;
