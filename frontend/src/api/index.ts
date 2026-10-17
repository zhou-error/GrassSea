import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (res) => res,
  (err) => Promise.reject(err)
);

// Chat

/** 模型自主调用一次工具的记录 */
export interface ToolCallTrace {
  round: number;
  tool: string;
  arguments: Record<string, unknown>;
  status: string;
  elapsed_ms: number;
  message?: string | null;
}

export interface ChatResponse {
  session_id: string;
  intent: string;
  answer: string;
  task_id?: string | null;
  sources?: RagSourceChunk[];
  /** 仅当模型自主调用工具时非空 */
  tool_trace?: ToolCallTrace[];
}

/** 附件描述符（由 POST /attachments 返回） */
export interface AttachmentDescriptor {
  attachment_id: string;
  filename: string;
  media_type: string;
  size: number;
  kind: 'text' | 'pdf' | 'table' | 'image' | 'binary';
  chars: number;
  text: string;
  truncated: boolean;
  note: string;
}

export interface AttachmentLimits {
  max_attachment_bytes: number;
  max_text_chars_per_file: number;
  image_understood: boolean;
  note: string;
}

export const chatApi = (
  message: string,
  sessionId?: string,
  attachments: AttachmentDescriptor[] = []
) =>
  api.post<ChatResponse>('/chat', {
    message,
    session_id: sessionId,
    ...(attachments.length > 0 ? { attachments } : {}),
  });

// ---- 附件上传 ----

export const uploadAttachmentApi = (
  file: File,
  onProgress?: UploadProgressHandler
): Promise<{ data: AttachmentDescriptor }> => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<AttachmentDescriptor>('/attachments', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    onUploadProgress: onProgress
      ? (e) => {
          const total = typeof e.total === 'number' && e.total > 0 ? e.total : e.loaded;
          if (!total || total <= 0) return;
          onProgress(Math.max(0, Math.min(100, Math.round((e.loaded * 100) / total))));
        }
      : undefined,
  });
};

export const attachmentLimitsApi = () => api.get<AttachmentLimits>('/attachments/limits');

// ---- 桌面模式与工作文件夹 ----

export interface DesktopStatus {
  desktop_mode: boolean;
  workspace_selected: boolean;
  workspace_root: string;
}

export interface WorkspaceInfo {
  selected: boolean;
  root: string;
  tree: string[];
  truncated: boolean;
  cancelled?: boolean;
}

export const desktopStatusApi = () => api.get<DesktopStatus>('/desktop/status');

export const workspaceInfoApi = () => api.get<WorkspaceInfo>('/workspace');

export const workspaceSetApi = (path: string) =>
  api.post<WorkspaceInfo>('/workspace/set', { path });

/** 弹出系统原生文件夹对话框（仅桌面模式） */
export const workspaceSelectApi = () =>
  api.post<WorkspaceInfo>('/workspace/select', {}, { timeout: 180000 });

// RAG
export interface RagDocumentSource {
  [key: string]: unknown;
}

export interface RagDocument {
  document_id: string;
  filename: string;
  knowledge_base: string;
  chunks: number;
  status: string;
}

export interface RagDocumentListResponse {
  total: number;
  documents: RagDocument[];
}

export interface RagUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  chunks_count: number;
}

export interface RagDeleteResponse {
  document_id: string;
  deleted_chunks: number;
  status: string;
}

export interface RagSourceChunk {
  chunk_id: string;
  text: string;
  score: number;
  source: RagDocumentSource;
  chunk_index: number;
}

export interface RagQueryResponse {
  query: string;
  answer: string;
  sources: RagSourceChunk[];
  retrieval_time_ms: number;
  generation_time_ms: number;
}

export const ragQueryApi = (query: string, topK = 5, knowledgeBases?: string[]) =>
  api.post<RagQueryResponse>('/rag/query', {
    query,
    top_k: topK,
    ...(knowledgeBases && knowledgeBases.length > 0 ? { knowledge_bases: knowledgeBases } : {}),
  });

export const listDocumentsApi = (kb?: string) =>
  api.get<RagDocumentListResponse>('/rag/documents', {
    params: kb ? { knowledge_base: kb } : undefined,
  });

export const deleteDocumentApi = (documentId: string) =>
  api.delete<RagDeleteResponse>(`/rag/documents/${encodeURIComponent(documentId)}`);

/** 上传进度回调：整型 0-100 */
export type UploadProgressHandler = (percent: number) => void;

export const uploadDocumentApi = (file: File, kb: string, onProgress?: UploadProgressHandler) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<RagUploadResponse>(`/rag/documents?knowledge_base=${encodeURIComponent(kb)}`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
      ? (e) => {
          const total = typeof e.total === 'number' && e.total > 0 ? e.total : e.loaded;
          if (!total || total <= 0) return;
          const percent = Math.round((e.loaded * 100) / total);
          onProgress(Math.max(0, Math.min(100, percent)));
        }
      : undefined,
  });
};

// Task / Agent
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface TaskSummary {
  task_id: string;
  title: string;
  intent: string;
  status: TaskStatus;
  progress: number;
  steps_total: number;
  created_at: string;
  session_id: string;
}

export interface TaskListResponse {
  total: number;
  tasks: TaskSummary[];
}

export interface TaskStep {
  step_id: string;
  action: string;
  description: string;
  agent_id?: string;
  tool_ids?: string[];
  dependencies?: string[];
}

export interface TaskResult {
  /** step_id -> 该步骤产出的原始结果，结构由后端决定 */
  results: Record<string, unknown>;
  completed: string[];
  failed: string[];
  skipped: string[];
  /** 后端预格式化的“一步一行”可读摘要；可能不存在 */
  summary?: string[];
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress: number;
  result: TaskResult | null;
  error: string | null;
  steps: TaskStep[];
}

export interface AgentInfo {
  agent_id: string;
  name: string;
  role: string;
  status: string;
  version: string;
  capabilities: string[];
  last_heartbeat: number;
}

export interface AgentListResponse {
  total: number;
  agents: AgentInfo[];
}

export const listTasksApi = () => api.get<TaskListResponse>('/tasks');

export const getTaskStatusApi = (taskId: string) =>
  api.get<TaskStatusResponse>(`/task/${encodeURIComponent(taskId)}/status`);

export const listAgentsApi = () => api.get<AgentListResponse>('/agents');

// Tools —— 供模型自主调用的工具清单
export interface ToolDefinition {
  tool_id: string;
  name: string;
  description: string;
  category: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  timeout_ms: number;
  version: string;
  /** 是否已暴露给模型自主调用 */
  exposed_to_model: boolean;
}

export interface ToolListResponse {
  total: number;
  tool_calling_enabled: boolean;
  exposed_to_model: number;
  tools: ToolDefinition[];
}

export const listToolsApi = () => api.get<ToolListResponse>('/tools');

// ---- Word / PDF 文档能力 ----

export interface DocTemplateInfo {
  name: string;
  user_path: string;
  repo_path: string;
  active_path: string;
  user_exists: boolean;
  repo_exists: boolean;
  base_dir: string;
}

export interface DocStatus {
  pdf_converter: string;
  converters: { word: boolean; libreoffice: boolean; libreoffice_path: string };
  template: DocTemplateInfo;
  output_dir: string;
  desktop_mode: boolean;
}

export const docStatusApi = () => api.get<DocStatus>('/doc/status');

// ---- 排版模板（可视化编辑）----

export interface DocTemplatePayload {
  name: string;
  paths: DocTemplateInfo;
  exists: boolean;
  active_path?: string;
  yaml_text: string;
  data: Record<string, unknown>;
}

export const docTemplateApi = (name?: string) =>
  api.get<DocTemplatePayload>('/config/template', { params: name ? { name } : undefined });

export const saveDocTemplateApi = (payload: { name?: string; yaml_text?: string; data?: Record<string, unknown> }) =>
  api.put<{ status: string; saved_to: string; note: string }>('/config/template', payload);

/** 在文件管理器中打开模板目录（仅桌面模式） */
export const docOpenFolderApi = (path?: string) =>
  api.post<{ status: string; path: string }>('/doc/open-folder', path ? { path } : {});

export default api;
