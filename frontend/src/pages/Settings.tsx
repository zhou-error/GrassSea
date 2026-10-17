import React, { useEffect, useState } from 'react';
import { Input, InputNumber, Select, Button, Typography, message, Alert, Collapse, Tag, Spin } from 'antd';
import { SaveOutlined, ReloadOutlined, FolderOpenOutlined, FileWordOutlined } from '@ant-design/icons';
import { createBackupApi, docOpenFolderApi, docStatusApi, docTemplateApi, diagnosticsUrl, saveDocTemplateApi } from '../api';
import type { DocStatus } from '../api';
import axios from 'axios';

const { Title, Text } = Typography;

interface ConfigItem {
  key: string; label: string; label_en?: string; value: string; category: string;
  type: string; sensitive: boolean; default?: string; options?: string[];
}

const categoryInfo: Record<string, { icon: string; desc: string }> = {
  LLM:  { icon: '🔑', desc: '大语言模型 API 密钥与接口 / LLM API keys & endpoints' },
  模型: { icon: '🧠', desc: 'Embedding 与向量后端 / Embedding & vector backend' },
  RAG:  { icon: '📚', desc: '检索增强生成参数 / Retrieval parameters' },
  会话: { icon: '💬', desc: '对话会话设置 / Session settings' },
  搜索: { icon: '🔍', desc: '联网搜索引擎 API 密钥 / Search engine API keys' },
  工具调用: { icon: '🛠️', desc: '模型自主调用工具 / Autonomous tool calling' },
  文档: { icon: '📄', desc: 'Word 排版与 PDF 转换 / Word layout & PDF conversion' },
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
  const [tplYaml, setTplYaml] = useState('');
  const [tplActive, setTplActive] = useState('');
  const [tplLoading, setTplLoading] = useState(false);
  const [tplSaving, setTplSaving] = useState(false);
  const [backingUp, setBackingUp] = useState(false);

  const doBackup = async () => {
    setBackingUp(true);
    try {
      const res = await createBackupApi();
      message.success(`备份完成：${res.data.path}（${res.data.size_mb} MB）`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(detail || '备份失败');
    } finally { setBackingUp(false); }
  };

  useEffect(() => { loadConfigs(); loadDocStatus(); loadTemplate(); }, []);

  const loadTemplate = async () => {
    setTplLoading(true);
    try {
      const res = await docTemplateApi();
      setTplYaml(res.data.yaml_text || '');
      setTplActive(res.data.active_path || res.data.paths?.user_path || '');
    } catch { /* 忽略 */ }
    finally { setTplLoading(false); }
  };

  const saveTemplate = async () => {
    setTplSaving(true);
    try {
      const res = await saveDocTemplateApi({ yaml_text: tplYaml });
      message.success('模板已保存：' + res.data.saved_to);
      await loadTemplate();
      await loadDocStatus();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(detail || '模板保存失败');
    } finally { setTplSaving(false); }
  };

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
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{categoryInfo[cat]?.desc?.split(' / ')[1] || ''}</span>
                <Tag style={{ background: 'rgba(193,213,192,0.18)', border: 'none', color: '#3D5A45', borderRadius: 20 }}>
                  {items.length} 项
                </Tag>
              </div>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingLeft: 8 }}>
                {items.map((item) => (
                  <div key={item.key} style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    <div style={{ width: 210, flexShrink: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{item.label}</div>
                      {item.label_en && item.label_en !== item.label && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{item.label_en}</div>
                      )}
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

        {/* 排版模板编辑器 */}
        <div style={{
          marginTop: 24, padding: '16px 20px',
          background: 'rgba(245,245,245,0.6)', borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <FileWordOutlined style={{ color: '#3D5A45' }} />
            <Text strong style={{ fontSize: 13.5 }}>排版模板</Text>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Layout Template</span>
            {tplLoading && <Spin size="small" />}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginBottom: 8, lineHeight: 1.7 }}>
            直接编辑 YAML 即可调整页边距、正文字体/字号/行距、各级标题样式与封面字号；保存后下次生成文档自动生效。
            <br />
            Edit the YAML below to change margins, body font/size/line-spacing, heading styles and cover font sizes.
            Changes take effect on the next document generation.
          </div>
          <div style={{ fontSize: 11.5, marginBottom: 8, wordBreak: 'break-all' }}>
            保存到 / Saved to：<Text code style={{ fontSize: 11 }}>{tplActive || '（尚未确定）'}</Text>
          </div>
          <Input.TextArea
            value={tplYaml}
            onChange={(e) => setTplYaml(e.target.value)}
            autoSize={{ minRows: 12, maxRows: 24 }}
            spellCheck={false}
            style={{
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              fontSize: 12, lineHeight: 1.6, borderRadius: 'var(--radius-sm)',
              background: '#fff',
            }}
          />
          <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button
              type="primary"
              size="small"
              loading={tplSaving}
              onClick={saveTemplate}
              icon={<SaveOutlined />}
              style={{ borderRadius: 'var(--radius-sm)' }}
            >
              保存模板 / Save
            </Button>
            <Button size="small" onClick={loadTemplate} icon={<ReloadOutlined />} style={{ borderRadius: 'var(--radius-sm)' }}>
              重新加载 / Reload
            </Button>
            <Button
              size="small"
              onClick={() => openTemplateFolder(tplActive ? tplActive.replace(/[/\\][^/\\]+$/, '') : undefined)}
              disabled={!docStatus?.desktop_mode}
              icon={<FolderOpenOutlined />}
              style={{ borderRadius: 'var(--radius-sm)' }}
            >
              打开目录 / Open Folder
            </Button>
          </div>
        </div>

        {/* 数据与诊断 */}
        <div style={{
          marginTop: 24, padding: '16px 20px',
          background: 'rgba(245,245,245,0.6)', borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <SaveOutlined style={{ color: '#3D5A45' }} />
            <Text strong style={{ fontSize: 13.5 }}>数据与诊断</Text>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Backup &amp; Diagnostics</span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.7 }}>
            备份包含知识库向量、附件、生成文档、排版模板、加密密钥与 .env；不包含可重新下载的模型缓存。
            <br />
            Backup covers vector store, uploads, generated documents, templates, encrypted keys and .env.
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button
              size="small"
              loading={backingUp}
              onClick={doBackup}
              icon={<SaveOutlined />}
              style={{ borderRadius: 'var(--radius-sm)' }}
            >
              立即备份数据 / Backup Now
            </Button>
            <Button
              size="small"
              icon={<FileWordOutlined />}
              onClick={() => window.open(diagnosticsUrl(), '_blank')}
              style={{ borderRadius: 'var(--radius-sm)' }}
            >
              导出诊断包 / Diagnostics
            </Button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
            命令行等价操作：<Text code style={{ fontSize: 11 }}>uv run python scripts/backup.py</Text>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
