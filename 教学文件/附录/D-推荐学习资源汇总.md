# 附录D - 推荐学习资源汇总

> GrassSea 项目所需技能的推荐学习资源，从入门到进阶。所有资源均可在 B站（bilibili.com）或在线阅读。

## 学习路线建议

```
零基础入门（你已经会的）:
  Python 基础 → FastAPI 基础

需要补的基础（跟着教学文件学）:
  HTTP 协议 → RESTful API → JSON/YAML → Docker 基础

阶段式学习（跟着教学文件的顺序）:
  阶段一 → 阶段二 → ... → 阶段十二 → 附录
```

## Python 进阶

### 必读书籍

- **《Python编程：从入门到实践》** (Eric Matthes) — 最适合初学者的 Python 书
- **《流畅的Python》** (Luciano Ramalho) — Python 进阶必读，深入理解语言特性
- **《Python Cookbook》** (David Beazley) — 实用代码片段和最佳实践

### B站视频

请在 B站（bilibili.com）搜索以下关键词：
- "Python 异步编程 asyncio" — 理解 async/await 的核心原理
- "Python 类型注解 typing" — 学习 Optional、Union、Protocol 等类型
- "Python dataclass pydantic" — 数据模型和校验
- "Python 上下文管理器 async with" — 理解资源管理

### 在线文档

- [Python 官方文档](https://docs.python.org/zh-cn/3/) — 权威参考
- [Python 异步编程指南](https://docs.python.org/zh-cn/3/library/asyncio.html) — 官方 asyncio 文档

## FastAPI

### B站视频

- "FastAPI 入门到放弃" — 从零搭建 API 服务
- "FastAPI 项目实战" — 完整项目搭建
- "FastAPI 依赖注入" — 理解 Depends 和中间件

### 在线文档

- [FastAPI 官方文档](https://fastapi.tiangolo.com/zh/) — 最好的 Web 框架教程之一
- [Pydantic 文档](https://docs.pydantic.dev/latest/) — 数据校验

## Git 版本控制

### B站视频

- "Git 入门教程" — Git 基本操作
- "Git 分支管理策略" — Git Flow / GitHub Flow
- "GitHub Pull Request 工作流" — 协作开发流程

### 在线文档

- [Git 官方文档](https://git-scm.com/book/zh/v2) — Pro Git 中文版
- [Learn Git Branching](https://learngitbranching.js.org/) — 交互式学习 Git 分支

## Docker

### B站视频

- "Docker 入门教程" — Docker 基本概念
- "Docker Compose 编排" — 多容器管理
- "Docker 多阶段构建" — 镜像优化技巧

### 在线文档

- [Docker 官方文档](https://docs.docker.com/) — 权威参考
- [Docker — 从入门到实践](https://yeasy.gitbook.io/docker_practice/) — 中文社区经典

## 数据库

### PostgreSQL

- **B站**: "PostgreSQL 入门教程" / "PostgreSQL 索引优化"
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/15/index.html)

### MongoDB

- **B站**: "MongoDB 入门教程" / "MongoDB 聚合管道"
- [MongoDB University](https://learn.mongodb.com/) — 免费官方课程

### Redis

- **B站**: "Redis 入门教程" / "Redis 数据结构详解"
- [Redis 官方文档](https://redis.io/docs/latest/)

## RAG / 向量检索

### B站视频

- "RAG 检索增强生成 原理" — RAG 基础理论
- "LangChain RAG 实战" — 动手实现 RAG
- "Milvus 向量数据库 入门" — 向量存储
- "Embedding 向量嵌入 通俗解释" — 文本到向量

### 在线资源

- [LangChain 文档](https://python.langchain.com/docs/get_started/introduction)
- [Milvus 文档](https://milvus.io/docs/zh/)
- [DeepLearning.AI LangChain 课程](https://www.deeplearning.ai/short-courses/) — 免费短课程

## 多智能体系统

### B站视频

- "AI Agent 智能体 原理" — 理解 Agent 概念
- "Multi-Agent 多智能体协作" — 多 Agent 协作模式
- "CrewAI 多智能体框架" — 类似 GrassSea 的参考框架

### 在线资源

- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)

## 安全与认证

### B站视频

- "JWT 认证原理 通俗" — JWT 三段结构和签名
- "OAuth 2.0 授权流程" — 授权协议
- "Web 安全 XSS CSRF" — 常见 Web 攻击和防御

### 在线资源

- [JWT.io](https://jwt.io/) — 在线 JWT 调试工具
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — Web 安全十大风险

## 可观测性

### B站视频

- "OpenTelemetry 分布式追踪 入门" — 追踪基础
- "Prometheus 入门 监控" — 指标采集
- "Grafana 入门教程 搭建看板" — 可视化

### 在线资源

- [OpenTelemetry 文档](https://opentelemetry.io/docs/)
- [Prometheus 文档](https://prometheus.io/docs/introduction/overview/)
- [Grafana 文档](https://grafana.com/docs/)

## 测试

### B站视频

- "pytest 入门教程 fixture" — 测试框架
- "测试驱动开发 TDD pytest" — 先写测试再写代码

### 在线资源

- [pytest 官方文档](https://docs.pytest.org/)
- [Python 测试指南](https://docs.python-guide.org/writing/tests/)

## Kubernetes / K3s

### B站视频

- "Kubernetes 入门 通俗" — 理解 K8s 核心概念
- "K3s 部署 实战" — K3s 安装和配置
- "Kubernetes Ingress 路由" — 流量管理

### 在线资源

- [Kubernetes 官方教程](https://kubernetes.io/docs/tutorials/)
- [K3s 文档](https://docs.k3s.io/)
- [Kubernetes 中文文档](https://kubernetes.io/zh-cn/docs/home/)

## CI/CD

### B站视频

- "GitHub Actions 入门教程" — CI/CD 自动化
- "Docker 镜像 CI/CD 自动化" — 自动构建

### 在线资源

- [GitHub Actions 文档](https://docs.github.com/actions)
- [GitHub Actions Marketplace](https://github.com/marketplace?type=actions)

## 船舶与海洋工程领域

### 书籍

- **《船舶原理》** (盛振邦) — 船舶静力学、阻力、推进
- **《船舶结构力学》** (陈铁云) — 船体结构分析
- **《船舶设计原理》** (顾敏童) — 船舶设计方法论
- **CCS《钢质海船入级规范》** — 中国船级社入级规范
- **IACS 统一要求** — 国际船级社协会统一要求

### B站视频

- "船舶原理 入门" — 浮性、稳性、抗沉性
- "船舶设计 CAD" — 船舶 CAD 工具使用

## 常用网站和社区

| 网站 | 用途 |
|------|------|
| [GitHub](https://github.com) | 代码托管和协作 |
| [Stack Overflow](https://stackoverflow.com) | 编程问答 |
| [PyPI](https://pypi.org) | Python 包仓库 |
| [Docker Hub](https://hub.docker.com) | Docker 镜像仓库 |
| [知乎](https://zhihu.com) | 技术文章和讨论 |
| [掘金](https://juejin.cn) | 中文技术社区 |
| [CSDN](https://csdn.net) | 中文技术博客 |
| [Server 酱](https://sct.ftqq.com/) | 免费微信消息推送 |

## 工具推荐

| 工具 | 用途 |
|------|------|
| VS Code | 代码编辑器（免费、功能强大） |
| PyCharm Community | Python IDE（免费社区版） |
| Postman / Bruno | API 调试工具 |
| DBeaver | 数据库管理工具（免费） |
| Docker Desktop | Docker 图形化管理 |
| Tabby / Warp | 现代终端模拟器 |
| Obsidian / Notion | 笔记和知识管理 |
