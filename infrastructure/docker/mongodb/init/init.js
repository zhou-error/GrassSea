// ============================================================
// MongoDB 初始化脚本 — 创建索引
// ============================================================
db = db.getSiblingDB("grasssea");

// 对话历史集合
db.createCollection("conversation_history");
db.conversation_history.createIndex({ "session_id": 1, "created_at": -1 });
db.conversation_history.createIndex({ "user_id": 1 });
db.conversation_history.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7776000 }); // 90天 TTL

// 审查报告集合
db.createCollection("review_reports");
db.review_reports.createIndex({ "project_id": 1, "created_at": -1 });
db.review_reports.createIndex({ "user_id": 1 });

// Agent 配置集合
db.createCollection("agent_configs");
db.agent_configs.createIndex({ "agent_id": 1 }, { unique: true });
db.agent_configs.createIndex({ "capabilities.name": 1 });

// 任务 DAG 集合
db.createCollection("task_dags");
db.task_dags.createIndex({ "task_id": 1 }, { unique: true });
db.task_dags.createIndex({ "session_id": 1 });
db.task_dags.createIndex({ "status": 1 });

// 调研报告集合
db.createCollection("research_reports");
db.research_reports.createIndex({ "user_id": 1, "created_at": -1 });
db.research_reports.createIndex({ "topics": 1 });

// LLM 调用日志集合
db.createCollection("llm_call_logs");
db.llm_call_logs.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7776000 }); // 90天 TTL
db.llm_call_logs.createIndex({ "user_id": 1 });
db.llm_call_logs.createIndex({ "model": 1 });
