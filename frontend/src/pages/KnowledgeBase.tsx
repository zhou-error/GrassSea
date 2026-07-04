import React, { useState } from 'react';
import { Input, Upload, Tag, Typography, message } from 'antd';
import { SearchOutlined, FilePdfOutlined, FileTextOutlined, UploadOutlined } from '@ant-design/icons';
import { uploadDocumentApi } from '../api';

const { Text } = Typography;

const iconMap: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ color: '#E06C6C', fontSize: 18 }} />,
  txt: <FileTextOutlined style={{ color: 'var(--accent-glacier)', fontSize: 18 }} />,
  md: <FileTextOutlined style={{ color: 'var(--accent-sage)', fontSize: 18 }} />,
};

const dummyFiles = [
  { key: '1', name: 'CCS钢质海船入级规范2024.pdf', size: '12.5 MB', type: 'pdf', kb: '规范标准库', status: '已索引', date: '2026-07-03' },
  { key: '2', name: '散货船型值表_v2.xlsx', size: '856 KB', type: 'xlsx', kb: '项目知识库', status: '已索引', date: '2026-07-04' },
  { key: '3', name: 'SOLAS_Consolidated_2024.pdf', size: '8.2 MB', type: 'pdf', kb: '规范标准库', status: '索引中', date: '2026-07-04' },
  { key: '4', name: '型线设计手册_2025版.pdf', size: '3.1 MB', type: 'pdf', kb: '船舶设计库', status: '已索引', date: '2026-07-02' },
  { key: '5', name: 'IMO_MARPOL_Annex_VI.pdf', size: '4.8 MB', type: 'pdf', kb: '规范标准库', status: '已索引', date: '2026-07-01' },
];

const KnowledgePage: React.FC = () => {
  const [search, setSearch] = useState('');

  const handleUpload = async (file: File) => {
    try { await uploadDocumentApi(file, '项目知识库'); message.success(`${file.name} 上传成功`); }
    catch { message.error('上传失败'); }
    return false;
  };

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
            <Text type="secondary" style={{ fontSize: 12 }}>管理规范标准、船舶设计、学术文献等知识资源</Text>
          </div>
          <Upload beforeUpload={handleUpload as any} showUploadList={false}>
            <button style={{
              height: 36, padding: '0 18px', border: '1px solid var(--accent-sage)', borderRadius: 'var(--radius-md)',
              background: 'rgba(193,213,192,0.10)', color: '#3D5A45', fontSize: 13, fontWeight: 500,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              transition: 'var(--transition)',
            }}>
              <UploadOutlined /> 上传文档
            </button>
          </Upload>
        </div>

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
        {dummyFiles.filter((f) => !search || f.name.includes(search)).map((file) => (
          <div
            key={file.key}
            style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 18px',
              borderRadius: 'var(--radius-md)',
              marginBottom: 6,
              background: 'transparent',
              transition: 'var(--transition)',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(193,213,192,0.06)'; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
          >
            {iconMap[file.type] || <FileTextOutlined style={{ fontSize: 18, color: 'var(--text-muted)' }} />}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--text-primary)' }}>{file.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                {file.size} · {file.date}
              </div>
            </div>
            <Tag style={{
              background: 'rgba(193,213,192,0.18)', border: 'none',
              color: '#3D5A45', borderRadius: 20, fontSize: 11,
            }}>
              {file.kb}
            </Tag>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: file.status === '已索引' ? 'var(--status-green)' : '#D4A853',
            }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)', width: 40, textAlign: 'right' }}>
              {file.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KnowledgePage;
