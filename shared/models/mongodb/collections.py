"""MongoDB 集合定义与索引

使用 Motor (async) 操作 MongoDB。
定义集合名称常量和对应的 JSON Schema 描述。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---- 集合名称常量 ----
class MongoCollections:
    CONVERSATION_HISTORY = "conversation_history"
    REVIEW_REPORTS = "review_reports"
    AGENT_CONFIGS = "agent_configs"
    TASK_DAGS = "task_dags"
    RESEARCH_REPORTS = "research_reports"
    LLM_CALL_LOGS = "llm_call_logs"


# ---- 集合索引定义 ----
COLLECTION_INDEXES = {
    MongoCollections.CONVERSATION_HISTORY: [
        (["session_id", "created_at"], {"unique": False}),
        (["user_id"], {"unique": False}),
        (["created_at"], {"unique": False, "expireAfterSeconds": 7776000}),  # 90天 TTL
    ],
    MongoCollections.REVIEW_REPORTS: [
        (["project_id", "created_at"], {"unique": False}),
        (["user_id"], {"unique": False}),
    ],
    MongoCollections.AGENT_CONFIGS: [
        (["agent_id"], {"unique": True}),
        (["capabilities.name"], {"unique": False}),
    ],
    MongoCollections.TASK_DAGS: [
        (["task_id"], {"unique": True}),
        (["session_id"], {"unique": False}),
        (["status"], {"unique": False}),
    ],
    MongoCollections.RESEARCH_REPORTS: [
        (["user_id", "created_at"], {"unique": False}),
        (["topics"], {"unique": False}),
    ],
    MongoCollections.LLM_CALL_LOGS: [
        (["created_at"], {"unique": False, "expireAfterSeconds": 7776000}),  # 90天 TTL
        (["user_id"], {"unique": False}),
        (["model"], {"unique": False}),
    ],
}


# ---- 文档 Schema（供参考，MongoDB 不强制 schema）----

CONVERSATION_SCHEMA = {
    "session_id": str,       # 会话 ID
    "user_id": str,          # 用户 ID
    "messages": list[dict],  # 消息列表 [{role, content, timestamp, sources}]
    "intent": str | None,    # 识别的意图
    "state": str,            # 会话状态 (IDLE, PARSING, ...)
    "token_usage": dict,     # Token 统计 {prompt, completion, total}
    "created_at": datetime,
    "updated_at": datetime,
}

REVIEW_REPORT_SCHEMA = {
    "project_id": str,
    "user_id": str,
    "title": str,
    "summary": str,
    "violations": list[dict],  # 不合规项列表
    "suggestions": list[dict], # 修改建议
    "references": list[dict],  # 引用的规范条文
    "attachments": list[str],  # 附件 MinIO 路径
    "status": str,             # draft / final
    "created_at": datetime,
    "updated_at": datetime,
}

AGENT_CONFIG_SCHEMA = {
    "agent_id": str,
    "name": str,
    "role": str,
    "capabilities": list[dict],   # AgentCapability 列表
    "model_preference": str,
    "max_concurrent_tasks": int,
    "version": str,
    "tools": list[str],           # 关联工具 ID 列表
    "status": str,                # online / offline / degraded
    "last_heartbeat": datetime,
}

TASK_DAG_SCHEMA = {
    "task_id": str,
    "session_id": str,
    "dag": dict,                  # DAG 结构 {nodes: [...], edges: [...]}
    "status": str,                # pending / running / completed / failed
    "current_step": str | None,
    "results": dict,              # 各步骤结果 {step_id: result}
    "progress": float,            # 0.0 - 100.0
    "created_at": datetime,
    "updated_at": datetime,
}

RESEARCH_REPORT_SCHEMA = {
    "user_id": str,
    "title": str,
    "abstract": str,
    "topics": list[str],
    "sources": list[dict],        # 引用的文献列表
    "content": str,               # Markdown 格式
    "created_at": datetime,
}

LLM_CALL_LOG_SCHEMA = {
    "user_id": str,
    "session_id": str,
    "model": str,
    "task_type": str,
    "input_tokens": int,
    "output_tokens": int,
    "total_tokens": int,
    "latency_ms": float,
    "status": str,                # success / error
    "error_message": str | None,
    "created_at": datetime,
}
