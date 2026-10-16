import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Input, Upload, Tag, Typography, message, Popconfirm, Spin, Progress } from 'antd';
import type { UploadProps } from 'antd';
import {
  SearchOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FilePptOutlined,
  FileOutlined,
  UploadOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { deleteDocumentApi, listDocumentsApi, ragQueryApi, uploadDocumentApi } from '../api';
import type { RagDocument, RagQueryResponse, RagSourceChunk } from '../api';

const { Text } = Typography;

/** 上传默认落库的知识库（与后端 POST /rag/documents?knowledge_base= 对应） */
const DEFAULT_KB = '项目知识库';

/** 单次上传的进度状态：上传中 -> 服务端索引中（POST 返回后） -> 结束 */
type UploadPhase = 'uploading' | 'indexing' | 'error';

interface UploadItem {
  id: string;
  name: string;
  percent: number;
  phase: UploadPhase;
}

const iconMap: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ color: '#E06C6C', fontSize: 18 }} />,
  doc: <FileWordOutlined style={{ color: '#7BB5D0', fontSize: 18 }} />,
  docx: <FileWordOutlined style={{ color: '#7BB5D0', fontSize: 18 }} />,
  xls: <FileExcelOutlined style={{ color: '#7DBB8A', fontSize: 18 }} />,
  xlsx: <FileExcelOutlined style={{ color: '#7DBB8A', fontSize: 18 }} />,
  csv: <FileExcelOutlined style={{ color: '#7DBB8A', fontSize: 18 }} />,
  ppt: <FilePptOutlined style={{ color: '#D4A853', fontSize: 18 }} />,
  pptx: <FilePptOutlined style={{ color: '#D4A853', fontSize: 18 }} />,
  txt: <FileTextOutlined style={{ color: 'var(--accent-glacier)', fontSize: 18 }} />,
  md: <FileTextOutlined style={{ color: 'var(--accent-sage)', fontSize: 18 }} />,
};

const fileIcon = (filename: string): React.ReactNode => {
  const dot = filename.lastIndexOf('.');
  const ext = dot >= 0 ? filename.slice(dot + 1).toLowerCase() : '';
  return iconMap[ext] ?? <FileOutlined style={{ fontSize: 18, color: 'var(--text-muted)' }} />;
};

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

const sourceLabel = (source: RagSourceChunk['source'], index: number): string => {
  for (const key of ['filename', 'source', 'name', 'path']) {
    const value = source?.[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return `来源 ${index + 1}`;
};

const scoreText = (score: number): string =>
  typeof score === 'number' && Number.isFinite(score) ? score.toFixed(4) : '—';

const secondaryButtonStyle: React.CSSProperties = {
  height: 36,
  padding: '0 18px',
  border: '1px solid rgba(0,0,0,0.10)',
  borderRadius: 'var(--radius-md)',
  background: 'transparent',
  color: 'var(--text-secondary)',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
  transition: 'var(--transition)',
};

const KnowledgePage: React.FC = () => {
  const [search, setSearch] = useState('');
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const uploadTimersRef = useRef<number[]>([]);

  const [ragQuery, setRagQuery] = useState('');
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<RagQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await listDocumentsApi();
      const list = res.data?.documents;
      setDocuments(Array.isArray(list) ? list : []);
    } catch (err) {
      setDocuments([]);
      const msg = errorText(err, '文档列表加载失败，请确认后端服务可用');
      setLoadError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  // 卸载时清掉上传进度的收尾定时器
  useEffect(
    () => () => {
      uploadTimersRef.current.forEach((id) => window.clearTimeout(id));
      uploadTimersRef.current = [];
    },
    []
  );

  const removeUpload = useCallback((id: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== id));
  }, []);

  /** 上传：0-100 实时进度；POST 返回后进入“正在索引”，列表刷新完成才移除 */
  const handleUpload: UploadProps['beforeUpload'] = async (file) => {
    const id = `up_${Date.now()}_${file.name}`;
    setUploads((prev) => [...prev, { id, name: file.name, percent: 0, phase: 'uploading' }]);
    const patch = (next: Partial<UploadItem>) =>
      setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...next } : u)));

    try {
      const res = await uploadDocumentApi(file, DEFAULT_KB, (percent) =>
        patch({ percent, phase: 'uploading' })
      );
      // 上传已完成，服务端仍在切分/建索引
      patch({ percent: 100, phase: 'indexing' });
      const chunks = res.data?.chunks_count;
      message.success(
        typeof chunks === 'number'
          ? `${file.name} 上传成功，已索引 ${chunks} 个片段`
          : `${file.name} 上传成功`
      );
      await loadDocuments();
      removeUpload(id);
    } catch (err) {
      patch({ phase: 'error' });
      message.error(errorText(err, '上传失败'));
      const timer = window.setTimeout(() => removeUpload(id), 4000);
      uploadTimersRef.current.push(timer);
    }
    return false;
  };

  const handleDelete = async (doc: RagDocument) => {
    setDeletingId(doc.document_id);
    try {
      const res = await deleteDocumentApi(doc.document_id);
      const deleted = res.data?.deleted_chunks;
      message.success(
        typeof deleted === 'number'
          ? `已删除 ${doc.filename}（${deleted} 个片段）`
          : `已删除 ${doc.filename}`
      );
      await loadDocuments();
    } catch (err) {
      message.error(errorText(err, '删除失败'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleRagQuery = async () => {
    const q = ragQuery.trim();
    if (!q || querying) return;
    setQuerying(true);
    setQueryError(null);
    try {
      // 不传 knowledge_bases = 检索全部知识库
      const res = await ragQueryApi(q);
      setQueryResult(res.data);
    } catch (err) {
      setQueryResult(null);
      const msg = errorText(err, '检索失败，请稍后重试');
      setQueryError(msg);
      message.error(msg);
    } finally {
      setQuerying(false);
    }
  };

  const keyword = search.trim().toLowerCase();
  const filtered = useMemo(
    () => (keyword ? documents.filter((d) => d.filename.toLowerCase().includes(keyword)) : documents),
    [documents, keyword]
  );

  const uploadButton = (
    <button
      style={{
        height: 36, padding: '0 18px', border: '1px solid var(--accent-sage)', borderRadius: 'var(--radius-md)',
        background: 'rgba(193,213,192,0.10)', color: '#3D5A45', fontSize: 13, fontWeight: 500,
        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
        transition: 'var(--transition)',
      }}
    >
      <UploadOutlined /> 上传文档
    </button>
  );

  return (
    <div style={{ flex: 1, overflow: 'auto' }}>
      <div style={{
        background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-card)', padding: '24px 28px',
      }}>
        {/* 顶部操作栏 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h3 style={{ marginBottom: 2 }}>知识库</h3>
            <Text type="secondary" style={{ fontSize: 12 }}>
              管理规范标准、船舶设计、学术文献等知识资源
              {!loading && !loadError && ` · 共 ${documents.length} 个文档`}
            </Text>
          </div>
          <Upload beforeUpload={handleUpload} showUploadList={false}>
            {uploadButton}
          </Upload>
        </div>

        {/* 上传进度 */}
        {uploads.length > 0 && (
          <div style={{ marginBottom: 18, animation: 'fadeIn 0.3s ease-out' }}>
            {uploads.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 14px', marginBottom: 6,
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-base)',
                }}
              >
                {fileIcon(item.name)}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 12.5, color: 'var(--text-primary)', marginBottom: 2,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {item.name}
                  </div>
                  <Progress
                    percent={item.percent}
                    size="small"
                    showInfo={false}
                    status={item.phase === 'error' ? 'exception' : 'active'}
                    strokeColor={item.phase === 'error'
                      ? { '0%': '#E06C6C', '100%': '#E06C6C' }
                      : { '0%': 'var(--accent-sage)', '100%': 'var(--accent-glacier)' }}
                  />
                </div>
                <span style={{ fontSize: 11, color: item.phase === 'error' ? '#E06C6C' : 'var(--text-muted)', flexShrink: 0 }}>
                  {item.phase === 'uploading'
                    ? `上传中 ${item.percent}%`
                    : item.phase === 'indexing'
                      ? '正在索引…'
                      : '上传失败'}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* 搜索 */}
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--text-muted)' }} />}
          placeholder="搜索文件..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(0,0,0,0.06)',
            background: 'var(--bg-base)',
            marginBottom: 20,
            maxWidth: 360,
          }}
        />

        {/* 文件列表 */}
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '48px 0' }}>
            <Spin />
            <Text type="secondary" style={{ fontSize: 12 }}>正在加载文档列表...</Text>
          </div>
        )}

        {!loading && loadError && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary" style={{ fontSize: 12.5, display: 'block', marginBottom: 14 }}>
              {loadError}
            </Text>
            <button onClick={() => void loadDocuments()} style={secondaryButtonStyle}>
              重新加载
            </button>
          </div>
        )}

        {!loading && !loadError && documents.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
            padding: '44px 0', opacity: 0.85,
          }}>
            <FileOutlined style={{ fontSize: 28, color: 'var(--text-muted)' }} />
            <Text type="secondary" style={{ fontSize: 12.5 }}>暂无文档，请上传</Text>
            <Upload beforeUpload={handleUpload} showUploadList={false}>
              {uploadButton}
            </Upload>
          </div>
        )}

        {!loading && !loadError && documents.length > 0 && filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary" style={{ fontSize: 12.5 }}>未找到与「{search}」匹配的文档</Text>
          </div>
        )}

        {!loading && !loadError && filtered.map((doc) => (
          <div
            key={doc.document_id}
            style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 18px',
              borderRadius: 'var(--radius-md)',
              marginBottom: 6,
              background: 'transparent',
              transition: 'var(--transition)',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(193,213,192,0.06)'; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
          >
            {fileIcon(doc.filename)}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13.5, fontWeight: 500, color: 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {doc.filename}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                {typeof doc.chunks === 'number' ? `${doc.chunks} 个片段` : '片段数未知'}
              </div>
            </div>
            <Tag style={{
              background: 'rgba(193,213,192,0.18)', border: 'none',
              color: '#3D5A45', borderRadius: 20, fontSize: 11,
            }}>
              {doc.knowledge_base || '未分类'}
            </Tag>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: doc.status === 'indexed' ? 'var(--status-green)' : '#D4A853',
            }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 40, textAlign: 'right' }}>
              {doc.status === 'indexed' ? '已索引' : doc.status || '未知'}
            </span>
            <Popconfirm
              title="删除该文档？"
              description="将同时移除其全部索引片段"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => handleDelete(doc)}
            >
              <button
                aria-label="删除文档"
                disabled={deletingId === doc.document_id}
                style={{
                  width: 28, height: 28, borderRadius: '50%', border: 'none',
                  background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'var(--transition)',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = '#E06C6C'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'; }}
              >
                <DeleteOutlined />
              </button>
            </Popconfirm>
          </div>
        ))}
      </div>

      {/* 检索测试 */}
      <div style={{
        background: 'var(--bg-white)', borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-card)', padding: '24px 28px', marginTop: 16,
      }}>
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 2 }}>检索测试</h3>
          <Text type="secondary" style={{ fontSize: 12 }}>
            跨全部知识库检索，验证上传的文档是否可被召回
          </Text>
        </div>

        <div style={{ display: 'flex', gap: 10, maxWidth: 640 }}>
          <Input
            prefix={<SearchOutlined style={{ color: 'var(--text-muted)' }} />}
            placeholder="输入检索问题，例如：钢质海船入级规范对结构强度的要求"
            value={ragQuery}
            onChange={(e) => setRagQuery(e.target.value)}
            onPressEnter={() => void handleRagQuery()}
            disabled={querying}
            style={{
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(0,0,0,0.06)',
              background: 'var(--bg-base)',
            }}
          />
          <button
            onClick={() => void handleRagQuery()}
            disabled={querying || !ragQuery.trim()}
            style={{
              height: 32, padding: '0 20px', border: 'none', borderRadius: 'var(--radius-md)',
              background: querying || !ragQuery.trim()
                ? 'rgba(0,0,0,0.06)'
                : 'linear-gradient(135deg, var(--accent-sage), var(--accent-glacier))',
              color: querying || !ragQuery.trim() ? 'var(--text-muted)' : '#fff',
              fontSize: 13, fontWeight: 500, flexShrink: 0,
              cursor: querying || !ragQuery.trim() ? 'not-allowed' : 'pointer',
              transition: 'var(--transition)',
            }}
          >
            {querying ? '检索中...' : '检索'}
          </button>
        </div>

        {querying && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
            <Spin size="small" />
            <Text type="secondary" style={{ fontSize: 12 }}>正在检索知识库...</Text>
          </div>
        )}

        {!querying && queryError && (
          <div style={{
            marginTop: 18, padding: '12px 16px', borderRadius: 'var(--radius-md)',
            background: 'rgba(224,108,108,0.06)', color: '#8B3A3A', fontSize: 12.5,
          }}>
            {queryError}
          </div>
        )}

        {!querying && queryResult && (
          <div style={{ marginTop: 18, animation: 'fadeIn 0.3s ease-out' }}>
            <div style={{
              padding: '14px 18px', borderRadius: 'var(--radius-md)',
              background: 'var(--bubble-left)', fontSize: 13.5, lineHeight: 1.75,
              color: 'var(--text-primary)', whiteSpace: 'pre-wrap',
            }}>
              {queryResult.answer || '（本次检索未返回生成结果）'}
            </div>

            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              margin: '14px 0 8px',
            }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                命中片段（{queryResult.sources?.length ?? 0}）
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                检索 {Math.round(queryResult.retrieval_time_ms ?? 0)} ms · 生成 {Math.round(queryResult.generation_time_ms ?? 0)} ms
              </Text>
            </div>

            {(queryResult.sources ?? []).length === 0 && (
              <Text type="secondary" style={{ fontSize: 12 }}>未命中任何片段，可尝试调整问题或先上传相关文档。</Text>
            )}

            {(queryResult.sources ?? []).map((src, i) => (
              <div
                key={src.chunk_id || `${i}`}
                style={{
                  padding: '12px 16px', marginBottom: 8,
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-base)',
                  borderLeft: '2px solid var(--accent-sage)',
                }}
              >
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  gap: 12, marginBottom: 6,
                }}>
                  <span style={{
                    fontSize: 11.5, color: 'var(--text-secondary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    #{typeof src.chunk_index === 'number' ? src.chunk_index : i} · {sourceLabel(src.source, i)}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: '#3D5A45', flexShrink: 0 }}>
                    score {scoreText(src.score)}
                  </span>
                </div>
                <div style={{
                  fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.7,
                  maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
                }}>
                  {src.text}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgePage;
