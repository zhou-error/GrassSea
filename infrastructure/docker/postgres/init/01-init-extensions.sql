# ============================================================
# PostgreSQL 初始化脚本 — 创建 TimescaleDB 扩展
# ============================================================
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建时序统计数据库（独立 schema，方便管理）
CREATE SCHEMA IF NOT EXISTS timeseries;
