import React, { useCallback, useEffect, useState } from 'react';
import { DownloadOutlined, ReloadOutlined, FileWordOutlined, FilePdfOutlined } from '@ant-design/icons';

interface OutputFile {
  path: string;
  name: string;
  size: number;
  mtime: number;
  ext: string;
}

interface FilesResponse {
  root: string;
  total: number;
  files: OutputFile[];
}

/** 下载地址：走 chat_service 的 /api/files/download（桌面形态带 /api 前缀） */
const downloadUrl = (path: string) => '/api/files/download?path=' + encodeURIComponent(path);

const fmtSize = (n: number): string =>
  n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';

const fmtTime = (ts: number): string => {
  const d = new Date(ts * 1000);
  const p = (x: number) => String(x).padStart(2, '0');
  return (d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
};

const iconFor = (ext: string) => {
  if (ext === '.docx' || ext === '.doc') return <FileWordOutlined style={{ color: '#4A6FA5' }} />;
  if (ext === '.pdf') return <FilePdfOutlined style={{ color: '#C0605C' }} />;
  return <DownloadOutlined style={{ color: 'var(--text-muted)' }} />;
};

/** 生成文件面板：列出工作文件夹里的成果并直接下载 */
const FilesPanel: React.FC = () => {
  const [data, setData] = useState<FilesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch('/api/files');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      setData(await res.json());
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const files = data?.files ?? [];

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
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
        <h5 style={{ margin: 0 }}>生成文件</h5>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {data ? data.total + ' 个' : ''}
        </span>
        <span
          onClick={() => void load()}
          style={{ marginLeft: 'auto', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 12 }}
          title="刷新"
        >
          <ReloadOutlined spin={loading} />
        </span>
        <span
          onClick={() => setOpen((v) => !v)}
          style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: 12 }}
        >
          {open ? '收起' : '展开'}
        </span>
      </div>
      <span style={{
        fontSize: 10.5, color: 'var(--text-muted)', marginBottom: 10,
        wordBreak: 'break-all', lineHeight: 1.6,
      }}>
        {data?.root || '工作文件夹'}
      </span>

      {open && (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {err && (
            <div style={{ fontSize: 11, color: '#C0605C', padding: '8px 0' }}>
              无法读取文件列表：{err}
            </div>
          )}
          {!err && files.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '16px 0', lineHeight: 1.7 }}>
              还没有生成文件。让助手生成 Word 或 PDF 后会自动出现在这里。
            </div>
          )}
          {files.map((f) => (
            <a
              key={f.path}
              href={downloadUrl(f.path)}
              download={f.name}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 8px', borderRadius: 'var(--radius-sm)',
                textDecoration: 'none', marginBottom: 2,
                background: 'rgba(193,213,192,0.10)',
              }}
              title={'下载 ' + f.name}
            >
              <span style={{ fontSize: 14, flexShrink: 0 }}>{iconFor(f.ext)}</span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                  display: 'block', fontSize: 11.5, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {f.name}
                </span>
                <span style={{ display: 'block', fontSize: 9.5, color: 'var(--text-muted)' }}>
                  {fmtSize(f.size)} · {fmtTime(f.mtime)}
                </span>
              </span>
              <DownloadOutlined style={{ fontSize: 12, color: 'var(--accent-sage)', flexShrink: 0 }} />
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default FilesPanel;
