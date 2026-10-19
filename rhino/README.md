# Rhino 8 桥接

让 GrassSea 在**你已打开的 Rhino 8 文档**里建模：创建曲线、挤出实体、布尔运算、删除、查询。

> ⚠️ **验证状态**：本脚本按 Rhino 8（CPython 3）编写，**尚未通过真机端到端验证**。
> 首次使用请按文末 10 项验收清单逐条核对，有问题把 Rhino 输出窗口的文字发回。

---

## 1. 安装

1. 打开 Rhino 8。
2. 运行命令 `ScriptEditor`（RhinoCode）。
3. 新建 **Python 3** 脚本，粘贴本目录 `bridge.py` 全部内容，点击 Run。
4. 输出窗口应出现：

```
[GrassSea] 令牌已写入: <数据目录>\bridge.token
[GrassSea] Rhino 桥接已启动: http://127.0.0.1:8765
[GrassSea] 文档单位: millimeters | Rhino: 8.x
```

脚本停止 = 桥接停止。Rhino 关闭也会断开。

---

## 2. 数据目录

令牌默认写到 `~/GrassSea/bridge.token`。如果你的 GrassSea 在别的目录，
启动 Rhino 前设置环境变量，或在脚本顶部改 `TOKEN_FILE`：

```
set GRASSEA_DATA_DIR=F:\GrassSea\data
```

GrassSea 侧默认读 `<DATA_DIR>/bridge.token`，两边必须指向同一个文件。

---

## 3. 在 GrassSea 开启

设置页 →「CAD」分类 → 把 **启用 Rhino 桥接** 打开（或 `.env` 里设 `RHINO_BRIDGE_ENABLED=true`）。

其余三项一般不用改：

| 配置 | 默认 |
|---|---|
| `RHINO_BRIDGE_URL` | `http://127.0.0.1:8765` |
| `RHINO_BRIDGE_TIMEOUT_MS` | `30000` |
| `RHINO_BRIDGE_TOKEN_FILE` | 留空 = `<DATA_DIR>/bridge.token` |

---

## 4. 让它干活

对 GrassSea 说：

> 用这几个点建一条曲线：(0,0,0) (10000,0,0) (15000,3000,0) (20000,0,0)，然后向上挤出 5000mm。

或者直接调工具：

```json
{ "operation": "create_curve",
  "params": { "points": [[0,0,0],[10000,0,0],[15000,3000,0],[20000,0,0]] },
  "bake": true }
```

**破坏性操作要确认**：`boolean` 与 `delete` 在 `bake=true` 时必须带 `"confirm": true`，
否则工具返回 `confirmation_required`。这是防止误删与提示词注入的硬约束。

---

## 5. 参数速查

| 操作 | params | 说明 |
|---|---|---|
| `create_curve` | `points`, `degree?`, `closed?` | degree 省略时自动取上限（2 点→1 阶…） |
| `extrude` | `curve_id`, `height`, `cap?` | 沿**曲线平面法向**挤出；布尔前保持 cap=true |
| `boolean` | `brep_id_a`, `brep_id_b`, `operation`, `tolerance` | tolerance 按文档单位 |
| `delete` | `object_ids` | 忽略 bake，需 confirm |
| `query` | `object_ids` | 返回 type / bounding_box / brep_face_count |

长度阈值按**文档单位换算到米**判断：0.001–1000 m。
所以 mm 文档里 400000（=400 m 船体）是合法的。

---

## 6. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `bridge_unreachable` | Rhino 没开 / 脚本没跑 | 重跑脚本；确认端口 8765 未被占用 |
| `unauthorized` | 令牌不一致 | 重启桥接脚本（会生成新令牌），并把 GrassSea 指向同一文件 |
| `busy` | 队列满（32） | 等几秒重试 |
| `geometry_failure` | 对象非闭合 / 不相交 / 容差不当 | 调整形状或 tolerance |
| `not_found` | object_id 不存在 | 先 `query` 确认 |

---

## 7. 真机验收清单（10 项）

| # | 操作 | 期望 |
|---|---|---|
| 1 | 脚本启动 | 打印令牌与端口，无异常 |
| 2 | `GET /hello`（GrassSea 设置页刷新） | 返回 protocol=1、Rhino 版本、文档单位 |
| 3 | create_curve 4 点 | 生成曲线，返回 GUID |
| 4 | extrude cap=true | 生成闭合实体 |
| 5 | boolean union | 返回 1 个实体 |
| 6 | delete 不存在的 id | `not_found`，Rhino 不崩 |
| 7 | 共面布尔（应失败） | `geometry_failure`，文档**无残留** |
| 8 | 同 request_id 提交两次 | 只执行一次 |
| 9 | 关闭 Rhino 后调用 | `bridge_unreachable`，GrassSea 不崩 |
| 10 | 不带令牌调用 | 401 |

---

## 8. 已知限制

- 不支持 Grasshopper 组件操作
- 不支持自定义 operation（白名单硬编码在脚本里）
- 不支持一次调用多步操作（一次一个 operation）
- 只支持单个活动文档（多文档场景尚未处理）
