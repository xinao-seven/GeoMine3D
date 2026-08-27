# GeoMine3D 重构问题记录

本文档持续记录 `codex/geomine-workbench-fastapi` 分支重构期间发现的问题、决策、处理结果与待办事项。

## 记录格式

- 状态：`待处理` / `处理中` / `已解决` / `接受风险`
- 范围：前端 / Three.js / 后端 / 数据 / 工程化
- 每条问题记录现象、影响、处理方案和验证方式。

---

## ISSUE-001：工作区存在非本次任务的未提交内容

- 状态：接受风险
- 范围：工程化
- 发现时间：2026-08-27
- 现象：创建重构分支前，工作区已经存在 `BoreholeModelLoader.ts` 的纯缩进变化，以及若干未跟踪的 Markdown、JavaScript 和 `AGENTS.md` 文件。
- 影响：若直接执行 `git add .`，可能把用户已有内容混入重构提交。
- 处理：保留所有既有文件和修改，不回滚；本分支始终使用明确路径暂存，只提交本次重构涉及的文件。
- 验证：每次提交前检查 `git diff --cached --name-status`。

## ISSUE-002：当前后端实现与目标技术栈不一致

- 状态：处理中
- 范围：后端
- 发现时间：2026-08-27
- 现象：当前业务数据主要来自 JSON/Excel 文件，后端并非目标的 FastAPI + SQLAlchemy + MySQL 持久化架构。
- 影响：前端 API、数据模型、错误格式和文件访问方式需要重新定义。
- 处理：建立新的 FastAPI 模块化单体，使用 SQLAlchemy 2.0、Alembic 与 MySQL；保留现有数据作为迁移源，不在第一阶段删除旧实现。
- 验证：API 健康检查、数据库建表、核心 CRUD 与 OpenAPI 文档可用。

## ISSUE-003：Three.js 生命周期清理不完整

- 状态：待处理
- 范围：Three.js
- 发现时间：2026-08-27
- 现象：`ModelManager.clear()` 只将对象移出场景并清空 Map，没有递归释放模型内部的 geometry、material 和 texture。
- 影响：反复进入、退出或重新加载场景时可能产生 GPU 资源泄漏。
- 计划：引入 `ResourceTracker`，明确共享资源所有权并统一释放。
- 验证：重复装载/卸载场景后，`renderer.info.memory.geometries/textures` 不持续增长。

## ISSUE-004：现有 SceneCanvas 承担过多编排职责

- 状态：待处理
- 范围：前端 / Three.js
- 发现时间：2026-08-27
- 现象：组件直接创建并协调大量 Manager、Tool、watcher 和生命周期逻辑。
- 影响：UI、业务状态和渲染运行时耦合，后续工作台面板联动难以维护。
- 计划：增加 `GeoEngine` 门面和类型化业务事件，Vue 组件只负责容器生命周期与命令转发。
- 验证：工作台组件不直接操作 Mesh/Material，Three.js 原生对象不进入普通 Pinia 响应式状态。

## ISSUE-005：性能数字尚无可复现基线

- 状态：待处理
- 范围：Three.js / 工程化
- 发现时间：2026-08-27
- 现象：简历描述包含 FPS 与 Draw Call 优化数字，但仓库内没有固定数据集、测试设备和前后对照记录，当前钻孔仍为普通 Mesh。
- 影响：无法验证“12 FPS 到 60 FPS”“12000+ 到约 10”等指标。
- 计划：完成实例化钻孔后建立性能基线文档，记录设备、浏览器、分辨率、模型数量、三角形数、Draw Call 和帧耗时。
- 验证：保留可重复执行的测试数据与结果截图/日志。

## ISSUE-006：新旧后端需要短期共存

- 状态：处理中
- 范围：后端 / 工程化
- 发现时间：2026-08-27
- 现象：现有 Django 文件读取服务承载着当前演示数据，而新的 FastAPI 数据库尚未完成数据迁移。
- 影响：立即删除旧后端会使现有前端失去数据来源，也不利于核对业务规则。
- 处理：在 `backend/app` 中建立 FastAPI 应用，旧 Django 目录暂时保留为迁移参照；新的 `requirements.txt`、启动方式和数据库迁移以 FastAPI 为准，完成数据迁移与前端切换后再移除旧入口。
- 验证：迁移期间两套源码互不导入；前端切换后所有 `/api/v1` 请求均由 FastAPI 提供。

## ISSUE-007：系统 Python 命令不可用且运行时尚未安装后端依赖

- 状态：已解决
- 范围：工程化 / 后端
- 发现时间：2026-08-27
- 现象：系统 `python` 指向 Windows 商店占位程序；工作区自带 Python 可以执行语法编译，但尚未安装 FastAPI、SQLAlchemy 等项目依赖。
- 影响：当前只能完成 Python 字节码编译检查，暂时不能执行应用导入、OpenAPI 生成和 API 测试。
- 处理：使用 Codex 工作区提供的 Python，在 `backend/.venv` 中安装 `requirements.txt` 依赖；`.venv` 已加入忽略规则。
- 验证：FastAPI 应用已成功导入并生成 `/api/v1/projects` 路由；健康检查与 OpenAPI 自动测试通过。项目 CRUD 的真实数据库测试将在 MySQL 迁移完成后补充。

## ISSUE-008：Service 方法名遮蔽 Python 内置 `list`

- 状态：已解决
- 范围：后端
- 发现时间：2026-08-27
- 现象：`BoreholeService` 已定义名为 `list` 的方法，类体后续注解 `list[BoreholeSegmentInput]` 在运行时把 `list` 解析成了该方法，导致模块导入失败。
- 影响：FastAPI 无法启动和生成 OpenAPI。
- 处理：启用 `from __future__ import annotations`，推迟注解求值，避免类命名空间遮蔽内置泛型。
- 验证：应用导入与 OpenAPI 测试恢复通过。

## ISSUE-009：仓库中缺少旧业务数据目录

- 状态：待处理
- 范围：数据
- 发现时间：2026-08-27
- 现象：项目约定的 `backend/data` 目录当前不存在，无法读取 `models_meta.json`、钻孔 Excel 和工作面 JSON。
- 影响：暂时不能生成可验证的自动迁移脚本，也不能用真实项目数据做数据库联调。
- 计划：先完成导入接口和数据库结构；数据文件恢复后再增加一次性迁移命令，并以文件条数、钻孔层段数和坐标范围进行校验。
- 验证：迁移前后项目、模型、钻孔、层段和工作面数量一致，抽样坐标与深度一致。

## ISSUE-010：当前环境没有可用的 Docker/MySQL 服务

- 状态：接受风险
- 范围：后端 / 工程化
- 发现时间：2026-08-27
- 现象：本机 `docker version` 无服务端输出，无法启动 `docker-compose.yml` 中的 MySQL。
- 影响：本轮只能验证 SQLAlchemy 模型导入、OpenAPI、纯 HTTP 健康检查和 Alembic 的 MySQL 离线 SQL，不能执行真实 MySQL CRUD 集成测试。
- 处理：保留 Docker Compose 和 `.env.example`；Alembic 初始迁移已使用 MySQL 方言成功生成离线 SQL。
- 验证：在具备 Docker/MySQL 的环境运行 `docker compose up -d mysql`、`alembic upgrade head` 和后续数据库集成测试。
