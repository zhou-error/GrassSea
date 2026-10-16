# 04 - CI/CD 流水线

> ⚠️ **范围说明（项目定位：个人使用）**
>
> 本章讲解的集群部署 / CI/CD / 可观测性属于通用工程知识，**当前项目不包含这部分能力**：
> 相关流水线与部署清单已从仓库移除，对应容器配置也已从 `docker-compose.yml` 移除。
> 本章可作为学习资料阅读，但无需在本项目中落地。

## 学习目标

1. 理解 CI/CD（持续集成/持续部署）的核心概念
2. 掌握 GitHub Actions 工作流文件的基本结构
3. 能够读懂 GrassSea 的 CI/CD 流水线配置
4. 了解 Docker 镜像构建和 K3s 部署的自动化流程

## 前置知识

- 了解 Git 的基本操作（push、pull、branch）
- 了解 Docker 镜像的基本概念（阶段十二第3章）
- 了解什么是自动化测试

## 概念讲解

### CI/CD 是什么？

CI = Continuous Integration（持续集成）—— 每次提交代码，自动构建和测试。
CD = Continuous Deployment（持续部署）—— 测试通过后，自动部署到服务器。

```
传统开发流程:
  开发 → 手动测试 → 手动打包 → 手动上传 → 手动部署
  问题: 每个步骤都是手动的，容易出错，费时费力

CI/CD 流程:
  Git Push → GitHub Actions 自动触发
    ├── 自动运行 lint (代码格式检查)
    ├── 自动运行测试 (单元测试 + 集成测试)
    ├── 自动构建 Docker 镜像
    └── 自动部署到 K3s 集群
  优势: 全自动，每次提交都经过同样的质量检查
```

### GitHub Actions 工作流结构

一个 GitHub Actions 工作流文件定义了一系列在特定事件触发时执行的任务：

```
.github/workflows/ci.yml 的结构:

  name: CI/CD                    ← 工作流名称

  on:                           ← 触发条件
    push:
      branches: [master, develop]
    pull_request:
      branches: [master]

  jobs:                         ← 任务列表
    test:                       ← 任务1: 测试
      runs-on: ubuntu-latest   ← 运行环境
      services:                 ← 依赖服务（数据库等）
        postgres: ...
        redis: ...
      steps:                    ← 执行步骤
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
        - run: pip install ...
        - run: pytest ...

    build:                      ← 任务2: 构建（依赖 test 完成）
      needs: test
      if: github.ref == ...    ← 只在特定分支执行
      steps:
        - run: docker build ...
        - run: docker push ...

    deploy:                     ← 任务3: 部署（依赖 build 完成）
      needs: build
      steps:
        - run: kubectl set image ...
```

### Job 之间的依赖关系

```
  Jobs 的执行顺序:

  ┌─────────┐
  │  test   │  ← 第一步：运行 lint + 类型检查 + pytest
  └────┬────┘
       │ needs: test
       ▼
  ┌─────────┐
  │  build  │  ← 第二步：构建并推送 Docker 镜像
  └────┬────┘  （只在 master/develop 分支执行）
       │ needs: build
       ▼
  ┌─────────┐
  │ deploy  │  ← 第三步：部署到 K3s
  └─────────┘  （只在 master 分支执行）

  如果 test 失败 → build 和 deploy 不会执行
  如果 build 失败 → deploy 不会执行
  这是一个"质量门控"机制
```

## 项目代码精讲

### 触发条件配置

```yaml
# .github/workflows/ci.yml 第1-7行
name: CI/CD

on:
  push:
    branches: [master, develop]
  pull_request:
    branches: [master]
```

**逐段解析**：
1. `on: push: branches: [master, develop]` — 当有人向 master 或 develop 分支推送代码时触发。
2. `on: pull_request: branches: [master]` — 当有人创建指向 master 分支的 Pull Request 时触发。

这个配置实现了两条自动化路径：
- **开发分支（develop）**：提交代码 → 自动测试 → 自动构建镜像
- **主分支（master）**：提交代码/合并 PR → 自动测试 → 自动构建 → 自动部署

### Test Job 详解

```yaml
# 第13-38行
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:2.14.2-pg15
        env:
          POSTGRES_USER: grasssea
          POSTGRES_PASSWORD: grasssea
          POSTGRES_DB: grasssea
        ports: ["5432:5432"]
      redis:
        image: redis:7.2-alpine
        ports: ["6379:6379"]
```

**逐段解析**：

1. `runs-on: ubuntu-latest` — 在 GitHub 提供的最新 Ubuntu 虚拟机上运行。GitHub 负责提供和维护这些环境。

2. `services:` — 声明 Job 需要的"服务容器"。这些是 Docker 容器，在 Job 运行期间启动，提供数据库、缓存等服务。

3. `postgres: ...` — 启动一个 TimescaleDB 容器（PostgreSQL 15 + 时序扩展）。GitHub Actions 会自动处理容器启动、健康检查和清理。

4. `env: POSTGRES_USER: grasssea` — 设置数据库的环境变量（用户名、密码、数据库名）。测试代码通过这些信息连接数据库。

5. `ports: ["5432:5432"]` — 将容器的 5432 端口映射到主机的 5432 端口。测试代码通过 `localhost:5432` 连接。

```yaml
    steps:
      - uses: actions/checkout@v4    # 拉取代码
      - uses: actions/setup-python@v5 # 安装 Python
        with: { python-version: "3.11" }
      - name: Install
        run: pip install -e ".[dev]"   # 安装依赖
      - name: Lint
        run: ruff check .              # 代码格式检查
      - name: Type check
        run: mypy shared/ services/ ... --ignore-missing-imports
      - name: Test
        run: pytest tests/ -v --cov --cov-report=xml
        env:
          POSTGRES_HOST: localhost
          DEEPSEEK_API_KEY: test-key
```

测试步骤的执行顺序：

```
Step1: checkout ──────▶ 拉取代码到 /home/runner/work/
Step2: setup-python ──▶ 安装 Python 3.11
Step3: Install ───────▶ pip install -e ".[dev]"
Step4: Lint ──────────▶ ruff 检查代码格式
Step5: Type check ────▶ mypy 类型检查
Step6: Test ──────────▶ pytest 运行所有测试

任何一步失败 → 整个 test job 失败
```

- `ruff check .` — ruff 是超快的 Python linter，检查代码是否符合风格规范（如未使用的变量、格式问题）
- `mypy ... --ignore-missing-imports` — 静态类型检查。`--ignore-missing-imports` 跳过第三方库的类型检查（因为不一定都有类型标注）
- `--cov --cov-report=xml` — 生成覆盖率报告（XML 格式），可上传到 Codecov 等服务

### Build Job 详解

```yaml
# 第40-55行
build:
  needs: test
  if: github.ref == 'refs/heads/master' || github.ref == 'refs/heads/develop'
  runs-on: ubuntu-latest
  strategy:
    matrix:
      service: [model-gateway, chat-service, agent-service, knowledge-service]
```

**逐段解析**：

1. `needs: test` — 声明依赖：test job 必须成功完成，才会执行 build job。这是"质量门控"。

2. `if: github.ref == 'refs/heads/master' || ...` — 条件执行：只在 master 或 develop 分支执行构建。PR 的测试不触发构建。

3. `strategy: matrix:` — **矩阵构建**。定义了一个数组 `[model-gateway, ...]`，GitHub Actions 会为每个服务并行创建独立的 build 任务（4 个任务同时运行）。

```yaml
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: |
          docker build -f infrastructure/docker/Dockerfile \
            -t $REGISTRY/$IMAGE_PREFIX/${{ matrix.service }}:${{ github.sha }} .
      - name: Push image
        run: |
          echo "${{ secrets.HARBOR_PASSWORD }}" | \
            docker login $REGISTRY -u ${{ secrets.HARBOR_USER }} --password-stdin
          docker push $REGISTRY/$IMAGE_PREFIX/${{ matrix.service }}:${{ github.sha }}
```

**关键细节**：
- `${{ matrix.service }}` — 矩阵变量，在每次循环中被替换为具体服务名
- `${{ github.sha }}` — GitHub 内置变量，当前提交的 SHA 哈希。用作镜像标签，保证每次构建的镜像可追溯
- `${{ secrets.HARBOR_PASSWORD }}` — **安全凭证**。GitHub Secrets 是加密存储的敏感信息，不会在日志中暴露。`--password-stdin` 通过管道传入密码，比 `-p` 命令行参数更安全（命令行参数可能出现在进程列表中）

### Deploy Job 详解

```yaml
# 第57-70行
deploy:
  needs: build
  if: github.ref == 'refs/heads/master'
  steps:
    - name: Deploy to K3s
      run: |
        mkdir -p ~/.kube
        echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config
        for svc in model-gateway chat-service agent-service knowledge-service; do
          kubectl set image deployment/$svc \
            $svc=$REGISTRY/$IMAGE_PREFIX/$svc:${{ github.sha }} -n grasssea
        done
        kubectl rollout status deployment -n grasssea
```

**逐段解析**：

1. `if: github.ref == 'refs/heads/master'` — 只有 master 分支触发部署。develop 分支只构建不部署。

2. `echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config` — 从 Secret 中解码 K3s 集群的 kubeconfig 文件。`base64 -d` 解码，写入 `~/.kube/config`（kubectl 的默认配置路径）。

3. `kubectl set image deployment/$svc $svc=...:${{ github.sha }}` — 更新 K3s Deployment 的镜像。这触发了 K3s 的滚动更新（逐步替换旧 Pod）。

4. `kubectl rollout status deployment -n grasssea` — 等待滚动更新完成。如果更新失败（如新镜像启动后健康检查不通过），这个命令会报错，deploy job 失败。

## 手把手实践

### 实验一：在 GitHub Actions 的视角理解流水线

1. 打开 `.github/workflows/ci.yml`
2. 画一张流程图，标注每个 Job 的触发条件和依赖关系
3. 回答：如果 develop 分支推送了代码，哪些 Job 会执行？哪些不会？

### 实验二：理解 Secrets

1. 阅读 CI 配置中所有使用 `${{ secrets.XXX }}` 的地方
2. 回答：为什么 `HARBOR_PASSWORD` 和 `KUBECONFIG` 需要用 Secrets 而不是写在配置文件里？
3. 思考：如果不小心把 Secret 打印到了日志中，应该怎么处理？

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "GitHub Actions 入门教程" -- 从零学习 CI/CD
- "Docker 镜像 CI/CD 自动化" -- 学习自动构建 Docker
- "kubectl 滚动更新 部署" -- 学习 K8s 部署策略
- "GitHub Actions Secrets 安全" -- 了解凭证管理

## 常见问题与排错

**Q1：PR 的测试通过了，但 merge 到 master 后构建失败，为什么？**

A：最常见原因是 Secrets 的访问权限。PR 来自 fork 仓库时不传递 Secrets（安全机制），所以 PR 中的 build job 被 `if` 条件跳过了。merge 后从仓库内分支触发，Secrets 可用。

**Q2：矩阵构建时某个服务失败了怎么办？**

A：GitHub Actions 默认允许其他矩阵任务继续运行。但 deploy job 依赖整个 build job，如果一个服务构建失败，deploy 不会执行（所有服务都不更新）。

**Q3：`kubectl rollout status` 卡住了？**

A：可能是新 Pod 无法启动（镜像问题、配置错误、资源不足）。`kubectl rollout status` 会等待直到全部 Pod 就绪或超时。可以在 K3s 集群中查看 Pod 状态和日志排查。

## 练习任务

1. **概念题**：CI 和 CD 分别代表什么？它们之间的区别是什么？
2. **分析题**：阅读 CI 配置，列出从"开发者 push 代码到 master"到"服务部署到 K3s"的完整自动化流程。
3. **配置题**：修改 CI 配置，在 test job 中添加一个步骤：运行 `pytest tests/unit/ -v --cov --cov-report=term`（在终端输出覆盖率报告，不生成 XML）。
4. **设计题**：如果要添加一个"通知"步骤——部署完成后通过企业微信发送通知，应该放在哪个 Job 的哪个位置？需要什么配置？
