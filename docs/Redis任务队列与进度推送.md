# Redis 任务队列与实时进度

把「上传钻孔 Excel → 生成三维地质模型」这条 25s~数分钟的长任务,从**进程内 fire-and-forget
协程**改造成**可重试、可自愈、进度可订阅**的后端任务编排。

本文档记录设计取舍、键空间契约、接口契约、降级策略、真实故障记录与量化数据。

---

## 1. 为什么改

改造前(`spawn_modeling_job` + `asyncio.Semaphore` + 前端 2.5s 轮询)的真实问题:

| 问题 | 表现 |
|---|---|
| 任务随进程消亡 | 服务重启/崩溃 → `lifespan` 里把 `pending/running` 一律标 failed,用户必须重传 |
| 无重试 | 引擎偶发失败(内存不足、数据边界情况)只能人工重传 |
| 并发闸门不跨进程 | `asyncio.Semaphore` 只在单进程内有效,`modeling_max_concurrent=1` 在多 worker 下形同虚设 |
| 进度靠猜 | 前端只有 `stage/message` 文本,没有百分比,长任务看起来像卡死 |
| 轮询放大 | N 个打开的项目中心页面 = N×QPS 打 DB,进度最长延迟 2.5s |
| 注册半成品 | 引擎直接写最终交付包目录,DB 注册失败会留下“磁盘有、库里没有(或版本错)”的中间态 |

改造后:Redis Stream 做队列、心跳做存活判定、指数退避 + 死信做重试、SSE 推真实百分比、
交付包内容寻址 + 原子切指针做一致性。

---

## 2. 端到端链路

```
POST /api/v1/modeling-jobs            (202, 立即返回 job)
        │ 写 modeling_jobs 行 + 保存两个 Excel
        ▼
dispatch_modeling_job(job_id)
        │ Redis 可用 ──▶ XADD modeling:jobs {job_id}
        │ 否则      ──▶ 进程内 asyncio.create_task(降级路径)
        ▼
ModelingWorker (lifespan 启动, consumer group = modeling-workers)
        │ ① XAUTOCLAIM 认领“被读走但没 ACK”的僵死消息
        │ ② XREADGROUP > 取新消息
        │ ③ SET NX PX lease:<job> 抢租约(同任务不并发)
        │ ④ 等并发槽位 slot:<i>
        ▼
run_modeling_job(job_id)   attempts += 1
        │ asyncio.create_subprocess_exec(python -m modeling_engine.generate)
        │   子进程独立 GIL,事件循环只做管道泵
        │   stdout: [progress] {"stage","percent","message"}  ──▶ Redis Hash 快照 + Redis Stream 事件
        │           [modeling] 人类可读日志                    ──▶ engine.log + DB message(节流 commit)
        ▼
发布交付包(内容寻址 + 原子生效)
        │ 引擎写 projects/<pid>/.tmp-<job>/ → 校验 catalog → 算内容指纹
        │ move 到 projects/<pid>/packages/<hash16>/   (不可变)
        ▼
注册数据(单个事务:钻孔 + 分层 + 模型资产 + 任务完成状态)
        │ commit 成功之后才 os.replace projects/<pid>/active.json 指针
        │ prune 旧 packages/<其它hash>/
        ▼
XACK + XDEL          →   SSE 推 event: done  →  前端进度条到 100%
```

---

## 3. Redis 键空间

前缀 `settings.redis_key_prefix`(默认 `geomine`)。

| 键 | 类型 | 说明 |
|---|---|---|
| `geomine:modeling:jobs` | stream | 待执行任务,字段 `job_id`;`MAXLEN ~10000` |
| `geomine:modeling:delayed` | zset | 退避重试队列,score = 下次可见时间戳 |
| `geomine:modeling:dead` | stream | 超过 `modeling_max_attempts` 的任务,需人工介入 |
| `geomine:modeling:lease:<job_id>` | string | 运行租约(TTL = `modeling_heartbeat_ttl_seconds`) |
| `geomine:modeling:slot:<i>` | string | 分布式并发闸门(TTL = 4×心跳,心跳续期) |
| `geomine:modeling:progress:<job_id>` | hash | 当前进度快照,TTL 1 天 |
| `geomine:modeling:progress:stream:<job_id>` | stream | 进度事件历史,`MAXLEN ~500`,TTL 1 天(SSE 续传用) |
| `geomine:cache:<namespace>:<inputhash>` | string | 分析结果缓存(TTL 1 小时) |
| `geomine:cache:<namespace>:<inputhash>:lock` | string | single-flight 锁(TTL 10s) |

---

## 4. 三层防护(别混,各管一件事)

| 机制 | 解决的问题 | 失效代价 |
|---|---|---|
| **PEL + XAUTOCLAIM** | 消息被读走但没 ACK(worker 被 kill)→ 空闲超过 `modeling_reclaim_idle_ms`(默认 60s)后换人重做 | 任务被重复执行一次(注册幂等,见 §5) |
| **租约 `lease:<job>`** | 同一任务被两个 worker 同时执行 | 重复建模 25s |
| **DB 心跳 `last_heartbeat_at`** | 进程重启后无从判断“上次谁在跑”→ 心跳超过 TTL 未刷新即视为僵死 | 重启后任务永久卡在 running |

`recover_pending_jobs()` 在 lifespan 启动时执行:心跳新的跳过(有人在跑),心跳过期的
重新 XADD(attempts 未超限)或进死信。

> 为什么不用 `LPUSH/BRPOP` list:消息一出队就消失,worker 崩溃即丢任务;Stream 有
> consumer group + PEL,才有“至少一次投递”。

> 为什么重试用 ZSet 而不是 Stream 的延迟特性:Stream 本身没有延迟投递,用
> `ZADD score=到期时间` + 一个 promoter 协程到期搬回 Stream 是最小实现。

---

## 5. 幂等:重试为什么不会把数据写乱

- **交付包内容寻址**:同一份输入 → 同一个 `packages/<hash16>/`,重复发布会直接丢弃暂存区;
- **资产 identity = (project_id, catalog_code)** 而不是文件路径(内容寻址后路径每次都变);
  重复注册只更新版本指向,资产行数不变(测试见 `tests/test_modeling_register.py`);
- **注册与“完成状态”在同一个事务里 commit**,之后才切 `active.json` 指针;失败则回滚 +
  清理暂存区,旧交付包继续生效(读者永远看不到半成品);
- **重复投递已完成任务只 ACK 丢弃**(`run_modeling_job` 返回 `skipped`)。

`active.json` 用**单文件 `os.replace`** 而不是 rename 目录:Windows/NTFS 上把非空目录
rename 成已存在的目录不是原子操作,单文件替换是。

---

## 6. 进度与 SSE 契约

引擎按阶段给出百分比(前端不估算):

| 阶段 | 百分比 |
|---|---|
| 解析输入 | 0 → 5 |
| 界面插值(按 i/N 递进) | 5 → 40 |
| 保序投影与尖灭折叠 | 45 |
| TIN-GTP 建模 | 55 |
| 自洽断言校验 | 75 |
| 导出交付包(按层数递进) | 78 → 92 |
| 注册数据 | 95 |
| 完成 / 失败 | 100 |

引擎输出行:`[progress] {"stage": "...", "percent": 21.3, "message": "..."}`(百分比单调不回退)。

接口:`GET /api/v1/modeling-jobs/{job_id}/events`(`text/event-stream`)

```
id: 1793885649502-0            ← Redis Stream entry id,重连时浏览器自动回传
event: progress
data: {"stage": "界面插值", "percent": 21.3, "message": "界面插值 5/15 ..."}
```

- 首次连接(无 `Last-Event-ID`):先补一帧当前快照,晚打开页面也能立刻看到进度;
- 带 `Last-Event-ID` 重连:只补发该 id 之后的事件(**断线期间不丢帧**);
- 每 15s 一条 `: keep-alive` 注释行,防代理掐长连接;
- 任务进入终态:补一帧 `event: done` 后关闭;
- 响应头:`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`。

> 为什么用 Stream + `XRANGE` 而不是 Pub/Sub:pub/sub 断线即丢事件,而且“读快照 → 订阅”
> 之间有窗口期;Stream 有 id,`Last-Event-ID` 天然对应,续传是免费的。

进度也通过普通接口暴露(轮询降级用):`GET /api/v1/modeling-jobs/{id}` 返回 `percent`。

---

## 7. 降级:Redis 挂掉会怎样

| 场景 | 行为 |
|---|---|
| `REDIS_ENABLED=false` 或 Redis 连不上 | 上传仍然成功;`dispatch_modeling_job` 退回进程内 task;启动时按旧逻辑把中断任务标 failed |
| SSE 端点不可用(代理不支持/后端降级) | 前端连续 3 次 error 后自动退回 2.5s 轮询;轮询响应里同样带 `percent` |
| 进度写入失败 | 只丢展示,建模继续(`record_progress` 吞异常) |
| 缓存读写失败 | 按未命中处理,直接计算 |

Redis 是**加速与协同层**,不是数据源:交付包在磁盘、任务状态在 MySQL。

---

## 8. 运维手册

```bash
# 队列水位(积压/延迟/死信/未 ACK)
curl -s http://127.0.0.1:8000/api/v1/modeling-queue

# 看死信里的任务与原因
docker exec geomine3d-redis redis-cli XRANGE geomine:modeling:dead - + COUNT 5

# 看某任务进度快照
docker exec geomine3d-redis redis-cli HGETALL geomine:modeling:progress:<job_id>

# 清理分析缓存(数据修复后)
python -c "import asyncio;from app.services.analysis_cache import invalidate_namespace;print(asyncio.run(invalidate_namespace('contours')))"

# 指标
curl -s http://127.0.0.1:8000/metrics | grep geomine_
```

| 指标 | 含义 |
|---|---|
| `geomine_modeling_job_duration_seconds` | 建模任务时长直方图 |
| `geomine_modeling_job_results_total{status}` | 完成/失败/跳过计数 |
| `geomine_analysis_cache_hits_total{namespace}` / `..._misses_total` | 缓存命中率 |
| `geomine_analysis_cache_shared_total` | single-flight 等到别人结果的次数(省下的重复计算) |

---

## 9. 踩过的坑(真实复盘)

1. **槽位 TTL 不能取“任务超时时间”**。第一版 `slot:<i>` 的 TTL 用了
   `modeling_timeout_seconds + 300 = 2100s`,结果 worker 被强杀后槽位占了 35 分钟,
   `max_concurrent=1` 时整个队列被一个死进程堵死(实测撞到)。改成 4×心跳(约 60s)
   + 心跳续期,死进程最多堵 1 分钟。
2. **MySQL REPEATABLE READ 让“刷新”看不到别人的提交**。`session.refresh()` 复用同一
   事务快照,worker 提交的新状态读不到;跨会话观察状态必须开新会话(SSE 循环里每轮
   新会话查状态,而不是长期持有请求级会话)。
3. **MySQL DATETIME 不存时区**。`last_heartbeat_at` 读回来是 naive,和 aware 的
   `deadline` 比较会 `TypeError`;统一按 UTC 归一后再比较。
4. **Windows 上目录 rename 非原子**。交付包切换用单文件 `active.json` +
   `os.replace`,不用目录改名。
5. **SSE 长连接与阻塞调用抢同一个事件循环**。注册阶段原本同步解析 Excel、算 GLB 哈希,
   改成 `asyncio.to_thread`;否则进度条会卡顿(每个连接都在等 CPU)。
6. **`XPENDING` 之外还要 `XDEL`**。只 ACK 不删条目,`XLEN` 会把已完成任务也算成积压。

---

## 10. 量化(本机实测,锦界数据 182 孔 / 14 层 / 16641 节点)

| 项 | 改造前 | 改造后 |
|---|---|---|
| 建模单次耗时 | ~26s | ~26s(未变,优化的是可靠性) |
| 进度延迟 | 最长 2.5s(轮询)+ 无百分比 | 逐阶段推送,首帧即时;断线续传不丢帧 |
| 重启后任务 | 一律 failed,需重传 | 心跳过期 → 自动重入队(实测 attempts=2 后完成) |
| 引擎失败 | 无重试 | 指数退避重试 3 次,超限进死信 |
| 等值线接口 | 715ms | 命中缓存 ~80ms(**≈9×**) |
| 勘探线剖面接口 | 冷启动 563ms / 热进程未命中 180ms | 命中 44.5ms(**4×**) |
| 合并模型重复进入工作台 | 每次重下 20MB+ | 带 `?v=` 的 URL immutable;`/models/{id}/file` 命中 ETag → **304(0 字节)** |
| 单测数量 | 49 | 112(+63) |
