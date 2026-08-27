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
