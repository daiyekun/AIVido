# 电商 AI 多媒体创意平台 —— 架构设计文档

| 项目 | 内容 |
| --- | --- |
| 文档名称 | 电商 AI 多媒体创意平台 架构设计文档 |
| 文档版本 | V1.0.1 |
| 编制日期 | 2026-10-08 |
| 关联文档 | 《电商 AI 多媒体创意平台 MVP 需求说明书 V0.5.1》 |
| 文档定位 | 指导后端工程搭建、部署实施与后续演进的技术基线 |
| 后端语言 | Python 3.11 |
| Web 框架 | FastAPI + Uvicorn |
| 关系型数据库 | **PostgreSQL 16** |
| 对象存储 | **MinIO** |
| 消息中间件 | **RabbitMQ 3.13**（任务框架 Celery 5.4） |
| 缓存 | Redis 7 |
| 链路追踪 | **OpenTelemetry 埋点（暂不部署可视化后端）** |
| 部署形态 | **Docker Compose 起步 + Kubernetes 演进路径** |

---

## 版本变更记录

| 版本 | 日期 | 变更内容 |
| --- | --- | --- |
| V1.0 | 2026-10-08 | 首版架构设计。相对需求文档 V0.5 完成 4 项关键选型变更，详见第 17 章 ADR |
| V1.0.1 | 2026-10-08 | 与需求说明书完成一致性对齐（用户确认）：① 素材上传改为全量后端中转，取消预签名直传与 `/api/v1/upload/presign`；② `sys_user` 增加 `is_admin` 并复用现有登录体系；③ 新增任务取消接口约定；④ 队列优先级改为默认不启用；⑤ 日志字段名统一为 `timestamp`/`message`；⑥ 单任务产物按 1 张/个修正；⑦ 待确认事项与附录 B 同步更新 |

### 相对需求文档 V0.5 的技术选型变更（重要）

| 项 | 需求文档 V0.5 | 本架构文档 | 影响 |
| --- | --- | --- | --- |
| 关系型数据库 | MySQL 8.0 | **PostgreSQL 16** | 全量 DDL 重写；jsonb 替代 json；引入部分唯一索引与 CHECK 约束 |
| 任务队列 Broker | Redis | **RabbitMQ** | 消息层重新设计（交换机/队列/死信/延迟）；Redis 职责收敛为缓存与限流 |
| 对象存储 | MinIO / 云 OSS | **MinIO**（明确主选） | 桶结构、生命周期、签名 URL 访问方案落地；素材上传由后端中转写入 |
| 链路追踪 | 可选 Jaeger，最低日志串联 | **OpenTelemetry SDK 埋点，暂不部署后端** | 代码按标准埋点，Span 导出到日志；后续接 Jaeger/Tempo 零改造 |
| 模型推理 | 第三方 API | **仅第三方 API**（不做 GPU 自建推理预留） | 模型层只保留适配器抽象，不设计推理服务层 |

---

## 目录

1. [架构目标与设计原则](#1-架构目标与设计原则)
2. [技术栈选型](#2-技术栈选型)
3. [总体架构](#3-总体架构)
4. [核心链路时序](#4-核心链路时序)
5. [后端工程分层与模块架构](#5-后端工程分层与模块架构)
6. [数据架构（PostgreSQL + MinIO）](#6-数据架构postgresql--minio)
7. [消息与任务架构（RabbitMQ + Celery）](#7-消息与任务架构rabbitmq--celery)
8. [模型网关架构](#8-模型网关架构)
9. [链路追踪架构（OpenTelemetry）](#9-链路追踪架构opentelemetry)
10. [安全架构](#10-安全架构)
11. [可扩展性设计](#11-可扩展性设计)
12. [性能与容量设计](#12-性能与容量设计)
13. [部署架构](#13-部署架构)
14. [可观测性与运维](#14-可观测性与运维)
15. [高可用、备份与容灾](#15-高可用备份与容灾)
16. [环境变量与配置清单](#16-环境变量与配置清单)
17. [关键架构决策记录（ADR）](#17-关键架构决策记录adr)
18. [风险与待确认事项](#18-风险与待确认事项)

---

## 1 架构目标与设计原则

### 1.1 架构目标

| 目标 | 衡量方式 |
| --- | --- |
| 最小闭环可交付 | 注册登录 → 提交生成 → 异步执行 → 结果预览下载，全链路跑通 |
| 模型可替换 | 新增/替换底层 AI 模型**不改业务代码、不改前端**，仅新增适配器 + 后台配置 |
| 策略可运营 | 系统提示词后台可维护，按业务类型自动匹配，运营可独立调整 |
| 问题可追溯 | 任意一次失败任务，可凭 TraceID 还原完整调用链与耗时 |
| 可水平扩展 | 应用层与 Worker 层无状态，可通过增加副本提升吞吐 |
| 可平滑演进 | 从单机 Compose 迁移到 K8s 不需要改动业务代码 |

### 1.2 设计原则

1. **业务与模型解耦**：业务层只认 `model_id`，模型能力差异全部收敛在适配器层。
2. **同步薄、异步厚**：HTTP 请求只做校验与入队，重活全部交给 Worker。
3. **配置外置**：模型能力、提示词、价格全部存数据库；密钥、连接串全部走环境变量。
4. **配置快照**：任务入队即冻结当时的模型配置与提示词配置（写入任务记录），避免运行期漂移。
5. **失败可重试、重试可终止**：区分可重试错误与终态错误，重试次数与延迟可控，最终进死信队列。
6. **可观测优先**：TraceID 从 HTTP 入口贯穿到 Worker 与第三方调用，日志、任务、消息三方均可关联。
7. **不为未确定的需求过度设计**：不做自建 GPU 推理层，不引入工作流引擎、不引入微服务拆分。

---

## 2 技术栈选型

### 2.1 选型清单

| 层次 | 组件 | 版本 | 选型理由 |
| --- | --- | --- | --- |
| 接入层 | Nginx | 1.25+ | 反向代理、静态资源、TLS 终止、限流前置 |
| Web 框架 | FastAPI | 0.115+ | 原生 async、Pydantic 校验、自动生成 OpenAPI |
| ASGI 服务器 | Uvicorn | 0.32+ | 高性能 ASGI，配合 Gunicorn 做多进程管理 |
| 任务框架 | Celery | 5.4+ | 成熟的分布式任务框架，重试、路由、优先级、监控齐全 |
| 消息中间件 | RabbitMQ | 3.13 | 可靠投递、灵活路由、原生死信与优先级队列 |
| 关系型数据库 | PostgreSQL | 16 | 强一致、jsonb 半结构化查询、部分索引、事务与分区能力 |
| ORM | SQLAlchemy | 2.0 | 支持 async、类型化查询、Alembic 迁移 |
| 缓存 | Redis | 7 | 模型配置缓存、限流计数、分布式锁、会话摘要缓存 |
| 对象存储 | MinIO | RELEASE.2024+ | S3 兼容、自建可控、签名 URL 访问与生命周期策略 |
| 链路追踪 | OpenTelemetry SDK | 1.27+ | 厂商中立，暂不部署后端，后续可平滑接入任意后端 |
| 日志 | structlog / python-json-logger | — | 结构化 JSON 日志，统一注入 trace_id |
| 监控指标 | Prometheus + Grafana | — | 应用指标、队列积压、MinIO 容量监控（预留，可后置） |
| 容器编排 | Docker Compose / Kubernetes | — | Compose 起步，K8s 演进 |
| 数据库迁移 | Alembic | 1.13+ | DDL 版本化管理，替代人工执行 SQL |

### 2.2 组件版本兼容性说明

- Celery 5.4 支持 Python 3.11，需显式安装 `celery[amqp]` 或直接依赖 `kombu` 的 AMQP 传输；
- SQLAlchemy 2.0 async 需搭配 `asyncpg` 驱动（注意：asyncpg **不支持** `psycopg2` 风格的 `%s` 占位与部分 DDL 自动提交，迁移脚本建议用同步 `psycopg2`/`psycopg`）；
- OpenTelemetry 的 FastAPI / Celery / httpx 三个 instrumentation 包版本需与 `opentelemetry-sdk` 主版本一致，避免 Context 传播失败。

---

## 3 总体架构

### 3.1 逻辑分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│  客户端层        Web 前端（浏览器）  ·  管理后台（内部）              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTPS / JSON · multipart
┌───────────────────────────▼─────────────────────────────────────────┐
│  接入层          Nginx：TLS 终止 · 反向代理 · 静态资源 · 前置限流     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│  应用层（无状态，可水平扩展）  FastAPI                                 │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────────┐   │
│  │ 用户模块  │ 模型管理  │ 提示词    │ 会话模块  │ 任务提交与查询    │   │
│  │          │ (admin)  │ (admin)  │          │                  │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 横切：JWT 鉴权 · 参数与文件校验 · 敏感词过滤 · OTel 埋点 · 日志 │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────┬───────────────────┬──────────────────┬──────────────────────┘
       │                   │                  │
       │ 入队(Celery)       │ 读写             │ 流式写入/签名读取
┌──────▼──────────┐ ┌──────▼──────────┐ ┌────▼──────────────────────┐
│  消息中间件层    │ │  数据持久层      │ │  对象存储层               │
│  RabbitMQ        │ │  PostgreSQL 16  │ │  MinIO                    │
│  · 任务交换机    │ │  · 账号/模型     │ │  · ai-input（临时素材）    │
│  · 图片/视频队列 │ │  · 任务/会话     │ │  · ai-output（生成产物）   │
│  · 重试/死信     │ │  · 提示词/积分   │ │  · 生命周期策略 · 签名URL  │
└──────┬──────────┘ └─────────────────┘ └───────────────────────────┘
       │                                     ▲
┌──────▼──────────────────────────────────┐  │
│  异步执行层（无状态，可水平扩展）         │  │ 产物回传
│  Celery Worker（image / video / chat）   │──┘
│  Celery Beat（定时清理、对账，可选）      │
│  ┌────────────────────────────────────┐ │
│  │ 模型网关 → 适配器注册表 → 第三方API │ │
│  └────────────────────────────────────┘ │
└──────────────┬──────────────────────────┘
               │ HTTPS
┌──────────────▼──────────────────────────────────────────────────────┐
│  外部服务层     第三方 AI 模型 API（图片大模型 / 视频大模型）         │
└─────────────────────────────────────────────────────────────────────┘

  旁路（旁挂，不参与主链路）：Redis 7（缓存/限流/锁）· OTel Collector（后续接 Jaeger/Tempo）
```

### 3.2 运行时组件清单

| 组件 | 容器/进程 | 副本策略 | 说明 |
| --- | --- | --- | --- |
| `nginx` | 单容器 | 1（K8s: Ingress 替代） | 入口 |
| `api` | Uvicorn 进程 | Compose: 1~2；K8s: HPA 2~8 | 无状态 |
| `worker-image` | Celery Worker | Compose: 2；K8s: HPA 2~10 | 消费图片队列，并发适中 |
| `worker-video` | Celery Worker | Compose: 2；K8s: HPA 2~6 | 消费视频队列，长任务，prefetch=1 |
| `worker-chat` | Celery Worker | Compose: 1；K8s: 1~4 | 消费对话队列，低延迟优先 |
| `beat` | Celery Beat | **1（唯一）** | 定时清理临时素材、超时任务兜底 |
| `postgres` | PostgreSQL | 1（K8s: StatefulSet） | 主库；高可用方案见第 15 章 |
| `rabbitmq` | RabbitMQ | 1（K8s: StatefulSet） | 需持久化 `/var/lib/rabbitmq` |
| `redis` | Redis | 1 | 缓存与限流，可容忍丢失 |
| `minio` | MinIO | 1（K8s: 4 节点纠删码） | 需持久化数据卷 |
| `otel-collector` | 可选 | 0（暂不部署） | 当前 Span 导出到日志 |

---

## 4 核心链路时序

### 4.1 图片 / 视频生成主链路

```
前端            API(FastAPI)        PostgreSQL      RabbitMQ      Worker         模型API     MinIO
 │                  │                   │             │            │              │          │
 │─①POST /generate─▶│                   │             │            │              │          │
 │  (含素材/X-Trace-Id)                  │             │            │              │          │
 │                  │─②鉴权/校验/敏感词──│             │            │              │          │
 │                  │─③推断 task_type   │             │            │              │          │
 │                  │─④匹配提示词模板───▶│             │            │              │          │
 │                  │─⑤素材经后端流式写入 MinIO（multipart 中转）────┼──────────────────────▶│
 │                  │─⑥写入任务(pending)▶│             │            │              │          │
 │                  │─⑦入队(routing key)─────────────▶ │            │              │          │
 │◀─⑧返回 task_id──│                   │             │            │              │          │
 │─⑨轮询 /task/{id}▶│─⑩查询状态────────▶│             │            │              │          │
 │                  │                   │             │─⑪投递─────▶│              │          │
 │                  │                   │             │            │─⑫状态=running ▶│          │
 │                  │                   │             │            │─⑬调模型(带trace)▶│        │
 │                  │                   │             │            │◀─⑭返回资源/任务号─│        │
 │                  │                   │             │            │─⑮下载/产物上传─────────▶│
 │                  │                   │             │            │─⑯状态=success + URL▶│   │
 │◀─轮询到 success─│◀─⑰读取产物签名URL─│             │            │              │          │
 │─⑱预览 / 下载──────────────────────────────────────────────────────────────────────────▶│
```

**关键设计点**

1. 第 ⑤ 步：**素材上传统一经 API 服务器中转**（`multipart/form-data`），后端边接收边流式写入 MinIO，不做客户端直传。代价是 200 MB 上限的视频会占用应用带宽与临时内存，因此必须同步约束三处：Nginx `client_max_body_size`、Uvicorn 请求体上限、以及提交接口的独立限流（详见 10.3 与 13.1.3）。取舍理由见 ADR-003。
2. 第 ⑧ 步：HTTP 请求在**入队后立即返回**，不等待模型结果，接口响应稳定在百毫秒级。
3. 第 ⑯ 步：任务状态与产物 URL **在同一次数据库事务内**写入，避免「状态成功但无产物」的中间态。
4. 第三方模型支持「提交任务 + 异步回调/轮询」模式时，Worker 内做轮询；若支持回调，则预留 `/api/v1/callback/model/{provider}` 接收回调（MVP 暂以轮询为主，回调接口预留）。

### 4.2 会话多轮对话链路

```
前端           API               PostgreSQL        RabbitMQ        Worker(chat)      模型API
 │              │                    │                │                │               │
 │─①创建会话───▶│─②写入 session────▶│                │                │               │
 │◀─session_id─│                    │                │                │               │
 │─③发消息(带 model_id)─▶│          │                │                │               │
 │              │─④校验模型启用─────▶│                │                │               │
 │              │─⑤存 user 消息────▶│                │                │               │
 │              │─⑥匹配 chat_general 提示词─────────▶│                │               │
 │              │─⑦组装上下文(截断)  │                │                │               │
 │              │─⑧入队────────────────────────────▶ │                │               │
 │◀─消息已受理──│                    │                │─⑨投递────────▶│               │
 │              │                    │                │                │─⑩chat_completion▶│
 │              │                    │                │                │◀─⑪回复文本─────│
 │              │                    │                │                │─⑫存 assistant 消息▶│
 │              │                    │                │                │  (必要时内部创建生成任务) │
 │─⑬轮询/拉取消息──────────────────────────────────────────────────────┘
```

**关键设计点**

- `model_id` 属于**消息**，不属于会话；每轮请求独立校验与记录；
- 上下文按 `context_window_size` 截断，采用「保留 system + 最近 N 轮 + 最早 1 轮」策略，避免丢失话题开端；
- 对话链路与生成链路**共用同一个 Worker 框架与模型网关**，仅队列与并发参数不同。

---

## 5 后端工程分层与模块架构

### 5.1 工程目录结构

```
app/
├── main.py                      # FastAPI 应用装配、中间件注册、路由挂载
├── core/
│   ├── config.py                # Pydantic Settings，读取环境变量
│   ├── logging.py               # 结构化日志 + trace_id 注入
│   ├── tracing.py               # OpenTelemetry 初始化与 Span 工具
│   ├── security.py              # JWT 签发/校验、管理员鉴权依赖
│   ├── exceptions.py            # 业务异常体系与统一异常处理器
│   └── response.py              # 统一响应包装（code/msg/trace_id/data）
├── api/
│   ├── deps.py                  # 依赖注入：DB 会话、当前用户、分页
│   └── v1/
│       ├── user.py              # 注册/登录/登出
│       ├── model.py             # 普通用户模型列表
│       ├── generate.py          # 统一生成接口（gen_type）
│       ├── task.py              # 任务列表/详情
│       ├── chat.py              # 会话与消息
│       ├── upload.py            # 素材上传（后端中转，流式写入 MinIO）
│       └── admin/               # 管理后台：模型 CRUD、提示词 CRUD
├── domain/                      # 领域层：纯业务逻辑，不依赖框架
│   ├── model_config.py          # 模型配置实体与校验
│   ├── prompt.py                # 系统提示词匹配策略
│   ├── task_machine.py          # 任务状态机与合法性校验
│   └── gen_type_resolver.py     # gen_type → task_type 推断器
├── services/                    # 应用服务层：编排
│   ├── auth_service.py
│   ├── model_service.py
│   ├── prompt_service.py
│   ├── session_service.py
│   ├── task_service.py
│   └── billing_service.py       # 计费骨架：预估积分
├── infrastructure/              # 基础设施层：外部依赖实现
│   ├── db/
│   │   ├── base.py              # SQLAlchemy async engine / sessionmaker
│   │   ├── models/              # ORM 模型（与 DDL 一一对应）
│   │   └── repositories/        # 仓储实现
│   ├── cache/redis_client.py
│   ├── storage/minio_client.py  # 上传、下载、预签名、生命周期
│   ├── mq/publisher.py          # Celery 任务发布封装
│   ├── gateway/                 # 模型网关
│   │   ├── registry.py          # adapter_key → 适配器类
│   │   ├── base.py              # BaseModelAdapter 抽象
│   │   ├── adapters/            # 各厂商适配器实现
│   │   └── client.py            # 统一 HTTP 客户端（超时/重试/埋点）
│   └── filter/sensitive.py      # 敏感词过滤
├── workers/
│   ├── celery_app.py            # Celery 实例、队列路由、序列化配置
│   ├── tasks_image.py
│   ├── tasks_video.py
│   ├── tasks_chat.py
│   └── tasks_housekeeping.py    # 临时素材清理、超时任务兜底
└── migrations/                  # Alembic 迁移脚本
```

### 5.2 分层依赖规则（强制）

```
api  ──▶  services  ──▶  domain
 │            │
 └────────────┴──▶  infrastructure
```

| 规则 | 说明 |
| --- | --- |
| `domain` 不依赖任何外层 | 纯 Python，可单测，不 import FastAPI / SQLAlchemy / Celery |
| `services` 只依赖 `domain` 与 `infrastructure` 接口 | 负责事务边界与业务编排 |
| `api` 不做业务判断 | 只做参数校验、鉴权、调用 service、包装响应 |
| `workers` 复用 `services` | Worker 与 API **共用同一套 service 与 gateway**，避免逻辑双写 |
| 禁止反向依赖 | `domain` 出现框架 import 视为架构违规，CI 中加入检查（import-linter） |

### 5.3 统一响应与异常

```python
# app/core/response.py（要点）
from typing import Any
from app.core.tracing import current_trace_id

def ok(data: Any = None, msg: str = "success") -> dict:
    return {"code": 0, "msg": msg, "trace_id": current_trace_id(), "data": data}

def fail(code: int, msg: str) -> dict:
    return {"code": code, "msg": msg, "trace_id": current_trace_id(), "data": None}
```

业务错误码分段（建议）：

| 区段 | 含义 |
| --- | --- |
| `1xxxx` | 通用与鉴权（10001 未登录、10002 Token 过期、10003 无权限） |
| `2xxxx` | 参数与文件校验（20001 参数非法、20002 文件类型不支持、20003 文件超限） |
| `3xxxx` | 模型与配置（30001 模型不存在、30002 模型已禁用、30003 能力不支持、30004 规格超出模型范围） |
| `4xxxx` | 任务与队列（40001 任务不存在、40002 任务状态非法、40003 队列提交失败） |
| `5xxxx` | 第三方与存储（50001 模型调用失败、50002 模型超时、50003 存储写入失败） |
| `6xxxx` | 合规（60001 提示词命中敏感词） |

---

## 6 数据架构（PostgreSQL + MinIO）

### 6.1 PostgreSQL 数据库设计

#### 6.1.1 设计要点

| 要点 | 说明 |
| --- | --- |
| 主键策略 | 用户、模型等业务实体用 `bigint IDENTITY`；任务、会话、消息用 `uuid`（`gen_random_uuid()`），便于跨库合并与对外暴露 |
| 时间类型 | 统一 `timestamptz`，应用与数据库时区统一 `UTC`，前端做本地化展示 |
| 半结构化数据 | 全部使用 `jsonb`（支持 GIN 索引与包含查询），替代 MySQL 的 `json` |
| 枚举约束 | 关键枚举用 `CHECK` 约束，防止脏值写入，同时保留扩展需改约束的显式成本 |
| 软删除 | 用户表使用 `is_deleted`，并在唯一索引上加 `WHERE is_deleted = false`，**允许手机号注销后重新注册** |
| 外键 | 保留外键（任务→用户/模型），MVP 数据量下无性能问题，换取数据一致性 |

#### 6.1.2 完整 DDL

```sql
-- ============================================================
--  电商 AI 多媒体创意平台 · PostgreSQL 16 DDL
--  说明：已在应用层统一 UTC 时区；主键采用 GENERATED BY DEFAULT AS IDENTITY（PG10+ 标准语法）
-- ============================================================

-- ---------- 0. 建库与库级参数 ----------
-- 以下三条在 postgres 库中执行（只需一次）：
--   CREATE DATABASE ainew WITH ENCODING 'UTF8' TEMPLATE template0;
--   ALTER DATABASE ainew SET timezone TO 'UTC';
--   ALTER DATABASE ainew SET statement_timeout = '5s';        -- 慢查询保护
--
-- 说明：gen_random_uuid() 自 PostgreSQL 13 起为内置函数，无需安装 pgcrypto 扩展。

-- ---------- 1. 用户账号表 ----------
CREATE TABLE sys_user (
    id                  bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    phone               varchar(20)  NOT NULL,
    jwt_salt            varchar(64)  NOT NULL DEFAULT '',
    credit_balance      numeric(12, 2) NOT NULL DEFAULT 0.00,
    user_type           smallint     NOT NULL DEFAULT 1,
    enterprise_name     varchar(255) NOT NULL DEFAULT '',
    business_license_no varchar(128) NOT NULL DEFAULT '',
    is_admin            boolean      NOT NULL DEFAULT false,
    is_deleted          boolean      NOT NULL DEFAULT false,
    create_time         timestamptz  NOT NULL DEFAULT now(),
    update_time         timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_sys_user_type CHECK (user_type IN (1, 2))
);

COMMENT ON TABLE  sys_user IS '用户账号表';
COMMENT ON COLUMN sys_user.credit_balance IS '积分余额；MVP 阶段仅预留，不参与真实扣减';
COMMENT ON COLUMN sys_user.is_admin IS '管理员标识；MVP 由运维在库中直接标记，复用手机号+验证码登录，登录后校验该字段';

-- 部分唯一索引：允许用户注销（软删）后以同一手机号重新注册
CREATE UNIQUE INDEX uk_sys_user_phone ON sys_user (phone) WHERE is_deleted = false;

-- ---------- 2. AI 模型配置表（后台维护） ----------
CREATE TABLE ai_model (
    model_id           bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    model_name         varchar(128) NOT NULL,
    model_type         varchar(16)  NOT NULL,
    adapter_key        varchar(64)  NOT NULL,
    is_enable          boolean      NOT NULL DEFAULT true,
    sort               int          NOT NULL DEFAULT 0,
    support_resolution jsonb        NOT NULL DEFAULT '[]'::jsonb,
    support_duration   jsonb        NOT NULL DEFAULT '[]'::jsonb,
    config_json        jsonb        NOT NULL DEFAULT '{}'::jsonb,
    price_config_json  jsonb        NOT NULL DEFAULT '{}'::jsonb,
    remark             varchar(512) NOT NULL DEFAULT '',
    create_time        timestamptz  NOT NULL DEFAULT now(),
    update_time        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_ai_model_type CHECK (model_type IN ('image', 'video'))
);

COMMENT ON TABLE  ai_model IS 'AI 模型后台配置表';
COMMENT ON COLUMN ai_model.adapter_key IS '适配器标识，与代码 ADAPTER_REGISTRY 的 key 一一对应';
COMMENT ON COLUMN ai_model.config_json IS '适配器配置：API 地址、超时、环境变量 key；禁止明文存密钥';

CREATE INDEX idx_ai_model_type_enable ON ai_model (model_type, is_enable, sort);

-- ---------- 3. 后台系统提示词模板表 ----------
CREATE TABLE ai_system_prompt (
    prompt_id     bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    prompt_name   varchar(128) NOT NULL,
    task_type     varchar(64)  NOT NULL,
    bind_model_id bigint       NULL REFERENCES ai_model (model_id),
    system_content text        NOT NULL,
    is_enable     boolean      NOT NULL DEFAULT true,
    sort          int          NOT NULL DEFAULT 0,
    remark        varchar(512) NOT NULL DEFAULT '',
    create_time   timestamptz  NOT NULL DEFAULT now(),
    update_time   timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_prompt_task_type CHECK (
        task_type IN ('txt2img','img2img','txt2vid','vid2vid','vid_edit','img2vid','chat_general')
    )
);

COMMENT ON TABLE  ai_system_prompt IS '系统提示词模板表；bind_model_id 为 NULL 表示该 task_type 全局通用';
COMMENT ON COLUMN ai_system_prompt.sort IS '匹配优先级，数值越大优先级越高';

-- 匹配查询主索引：覆盖「按 task_type + 启用 + 绑定模型 + 优先级排序」的取数路径
CREATE INDEX idx_prompt_match ON ai_system_prompt (task_type, is_enable, bind_model_id, sort DESC);

-- ---------- 4. AI 生成任务表 ----------
CREATE TABLE ai_generate_task (
    task_id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           bigint       NOT NULL REFERENCES sys_user (id),
    model_id          bigint       NOT NULL REFERENCES ai_model (model_id),
    task_type         varchar(32)  NOT NULL,
    status            varchar(16)  NOT NULL DEFAULT 'pending',
    input_params      jsonb        NOT NULL DEFAULT '{}'::jsonb,
    input_asset_urls  jsonb        NOT NULL DEFAULT '[]'::jsonb,
    output_asset_urls jsonb        NOT NULL DEFAULT '[]'::jsonb,
    expect_credit     numeric(12, 2) NOT NULL DEFAULT 0.00,
    -- 配置快照：任务入队即冻结，避免后台改配置导致执行期漂移
    snapshot_config   jsonb        NOT NULL DEFAULT '{}'::jsonb,
    system_prompt_id  bigint       NULL,
    retry_count       smallint     NOT NULL DEFAULT 0,
    error_code        varchar(32)  NOT NULL DEFAULT '',
    error_msg         text         NOT NULL DEFAULT '',
    trace_id          varchar(64)  NOT NULL,
    queued_at         timestamptz  NULL,
    started_at        timestamptz  NULL,
    finished_at       timestamptz  NULL,
    create_time       timestamptz  NOT NULL DEFAULT now(),
    update_time       timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_task_type CHECK (
        task_type IN ('txt2img','img2img','txt2vid','vid2vid','vid_edit','img2vid')
    ),
    CONSTRAINT ck_task_status CHECK (
        status IN ('pending','queued','running','success','failed','canceled')
    )
);

COMMENT ON TABLE  ai_generate_task IS 'AI 生成任务表';
COMMENT ON COLUMN ai_generate_task.snapshot_config IS '提交时刻的模型配置与提示词快照，供 Worker 使用，保证配置快照语义';
COMMENT ON COLUMN ai_generate_task.trace_id IS '链路追踪 ID，与日志、消息表关联';

-- 用户任务列表（按时间倒序翻页）
CREATE INDEX idx_task_user_create  ON ai_generate_task (user_id, create_time DESC);
-- 运维排查：按状态找积压/失败任务
CREATE INDEX idx_task_status_time  ON ai_generate_task (status, create_time);
-- 按 TraceID 反查任务
CREATE INDEX idx_task_trace        ON ai_generate_task (trace_id);
-- 按模型统计调用量与失败率
CREATE INDEX idx_task_model_time   ON ai_generate_task (model_id, create_time DESC);
-- 兜底扫描：长时间处于 running 的任务
CREATE INDEX idx_task_running      ON ai_generate_task (status, started_at)
    WHERE status IN ('queued', 'running');

-- ---------- 5. 会话主表 ----------
CREATE TABLE ai_chat_session (
    session_id          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             bigint       NOT NULL REFERENCES sys_user (id),
    title               varchar(256) NOT NULL DEFAULT '',
    context_window_size int          NOT NULL DEFAULT 4096,
    is_deleted          boolean      NOT NULL DEFAULT false,
    create_time         timestamptz  NOT NULL DEFAULT now(),
    update_time         timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE ai_chat_session IS '多轮对话会话表；会话不绑定模型';

CREATE INDEX idx_session_user ON ai_chat_session (user_id, update_time DESC)
    WHERE is_deleted = false;

-- ---------- 6. 会话消息表 ----------
CREATE TABLE ai_chat_message (
    msg_id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       uuid         NOT NULL REFERENCES ai_chat_session (session_id),
    role             varchar(16)  NOT NULL,
    model_id         bigint       NOT NULL REFERENCES ai_model (model_id),
    content_text     text         NOT NULL DEFAULT '',
    asset_urls       jsonb        NOT NULL DEFAULT '[]'::jsonb,
    related_task_id  uuid         NULL,
    trace_id         varchar(64)  NOT NULL,
    expect_credit    numeric(12, 2) NOT NULL DEFAULT 0.00,
    system_prompt_id bigint       NULL,
    error_msg        text         NOT NULL DEFAULT '',
    create_time      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_msg_role CHECK (role IN ('user', 'assistant', 'system'))
);

COMMENT ON TABLE  ai_chat_message IS '会话消息表；model_id 属于单条消息，同一会话内可逐轮不同';
COMMENT ON COLUMN ai_chat_message.related_task_id IS '该轮消息触发生成任务时，关联 ai_generate_task.task_id';

CREATE INDEX idx_msg_session_time ON ai_chat_message (session_id, create_time);

-- ---------- 7. 积分操作日志表（MVP 仅记录，不改余额） ----------
CREATE TABLE ai_credit_log (
    id           bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id      bigint       NOT NULL REFERENCES sys_user (id),
    task_id      uuid         NULL,
    msg_id       uuid         NULL,
    change_type  smallint     NOT NULL,
    change_value numeric(12, 2) NOT NULL DEFAULT 0.00,
    remark       varchar(512) NOT NULL DEFAULT '',
    create_time  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_credit_type CHECK (change_type IN (1, 2))
);

COMMENT ON TABLE ai_credit_log IS '积分流水；MVP 仅记录预估扣减，不更新 sys_user.credit_balance';

CREATE INDEX idx_credit_user_time ON ai_credit_log (user_id, create_time DESC);

-- ---------- 8. update_time 自动维护（MySQL 迁移最易遗漏项） ----------
-- 重要：PostgreSQL 没有 MySQL 的 ON UPDATE CURRENT_TIMESTAMP 语义。
-- 若漏掉下面这一步，update_time 将永远停留在 INSERT 时的值，
-- 进而导致：会话列表按 update_time 排序失效、配置"最后修改人/时间"不可信、
-- 依赖更新时间做的增量同步与缓存判断全部出错。
-- 这是一个不会报错、只会静默产生错误数据的迁移陷阱，必须在建表阶段一并落地。
CREATE OR REPLACE FUNCTION trg_set_update_time()
RETURNS trigger AS $$
BEGIN
    NEW.update_time := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_update_time BEFORE UPDATE ON sys_user
    FOR EACH ROW EXECUTE FUNCTION trg_set_update_time();
CREATE TRIGGER set_update_time BEFORE UPDATE ON ai_model
    FOR EACH ROW EXECUTE FUNCTION trg_set_update_time();
CREATE TRIGGER set_update_time BEFORE UPDATE ON ai_system_prompt
    FOR EACH ROW EXECUTE FUNCTION trg_set_update_time();
CREATE TRIGGER set_update_time BEFORE UPDATE ON ai_generate_task
    FOR EACH ROW EXECUTE FUNCTION trg_set_update_time();
CREATE TRIGGER set_update_time BEFORE UPDATE ON ai_chat_session
    FOR EACH ROW EXECUTE FUNCTION trg_set_update_time();

-- 注：ai_chat_message 与 ai_credit_log 为追加型表，无 update_time 字段，无需触发器。
-- 另注：若后续改用 SQLAlchemy 的 onupdate 维护 update_time，则需移除这些触发器，
--      避免"应用层与数据库层双重赋值"造成的语义混乱——二者只能选其一，不要并存。
```

#### 6.1.3 任务状态机

```
                ┌──────────┐
   提交校验通过  │ pending  │  落库
   ──────────▶  └────┬─────┘
                     │ 入队成功
                     ▼
                ┌──────────┐   入队失败（Broker 不可用）
                │ queued   │──────────────▶ failed
                └────┬─────┘
                     │ Worker 取到
                     ▼
                ┌──────────┐   可重试错误 → retry
                │ running  │──────────────┐
                └────┬─────┘              │ 延迟重投（retry_count +1）
                     │                    └──▶ queued
        ┌────────────┴────────────┐
        │ 成功                     │ 终态错误 / 重试耗尽
        ▼                          ▼
   ┌──────────┐              ┌──────────┐
   │ success  │              │ failed   │
   └──────────┘              └──────────┘
                                   ▲
                         用户取消   │
                    ┌──────────┐   │
                    │ canceled │───┘（仅 pending/queued 可取消）
                    └──────────┘
```

| 状态 | 是否终态 | 允许的后续状态 |
| --- | --- | --- |
| `pending` | 否 | `queued`、`failed`、`canceled` |
| `queued` | 否 | `running`、`failed`、`canceled` |
| `running` | 否 | `success`、`failed`、`queued`（重试） |
| `success` / `failed` / `canceled` | 是 | 无 |

> 状态迁移必须经 `domain/task_machine.py` 校验，禁止在任意位置直接 UPDATE status。

### 6.2 MinIO 对象存储架构

#### 6.2.1 桶（Bucket）规划

| 桶名 | 用途 | 访问策略 | 生命周期 |
| --- | --- | --- | --- |
| `ai-input` | 用户上传的临时素材（参考图、参考视频） | 私有，服务端写入，仅签名 URL 读取 | **7 天自动过期删除** |
| `ai-output` | AI 生成产物（图片、视频） | 私有，服务端写入，仅签名 URL 读取 | 长期保留；用户取消关联后由定时任务回收 |
| `ai-thumb` | 产物缩略图（列表页展示） | 私有，可长缓存 | 长期 |
| `ai-backup` | 数据库与配置的定期备份（可选） | 私有 | 按备份策略 |

#### 6.2.2 对象 Key 命名规范

```
{user_id}/{yyyy}/{MM}/{dd}/{uuid}.{ext}

示例：
ai-input :  1024/2026/10/08/7f3a1c2e-....mp4
ai-output:  1024/2026/10/08/9b2d4e6f-....png
ai-thumb :  1024/2026/10/08/9b2d4e6f-....jpg
```

**为什么这样设计**

- 按 `user_id` 前缀便于用户级资源统计与批量清理；
- 按日期分层避免单目录文件过多（S3/MinIO 虽为扁平结构，但前缀分层利于运维排查与分批扫描）；
- 文件名用 UUID，避免用户原始文件名带来的重名、中文编码、路径穿越问题；
- 原始文件名保存在业务表 `input_params` 中，仅用于展示。

#### 6.2.3 上传通道设计

**决策：素材上传全部经 API 服务器中转，不启用客户端直传。**

| 项 | 方案 |
| --- | --- |
| 通道 | 前端 `multipart/form-data` → API → 边接收边流式写入 MinIO（`upload_fileobj`，不落地临时文件） |
| 适用 | 图片（≤ 10 MB）与视频（≤ 200 MB）统一走此通道，不做大小分流 |
| 上限控制 | Nginx `client_max_body_size 210m`；应用层按 `UPLOAD_IMAGE_MAX_MB` / `UPLOAD_VIDEO_MAX_MB` 二次校验，超限立即中断连接 |
| 类型校验 | 读取文件头魔数判断真实类型，不信任 `Content-Type`；白名单见 10.3 |
| 命名 | 服务端重命名为 `{user_id}/{yyyy}/{MM}/{dd}/{uuid}.{ext}`，丢弃用户原始路径 |
| 超时 | 上传接口单独放宽 `proxy_read_timeout`，并复用提交接口的独立限流区（`submit_limit`） |

**为什么不采用预签名直传**

| 维度 | 后端中转（本方案） | 预签名直传（未采用） |
| --- | --- | --- |
| 前端复杂度 | 一次请求，无额外状态机 | 申请 → 直传 → 确认三步，需处理部分失败 |
| 服务端校验时机 | 接收过程中即可校验与中断，违规流量不落存储 | 只能在确认阶段事后 HEAD 校验，对象可能已产生 |
| 内容安全 | 可就地做敏感内容检测与二次编码（剥离 EXIF） | 无法在写入前介入 |
| 带宽与内存 | 占用应用带宽与临时内存 | 不占用应用带宽与内存 |
| 运维复杂度 | 低，无对外域名与签名主机一致性风险 | 需保证 `MINIO_PUBLIC_ENDPOINT` 与签名主机一致，否则校验失败 |

> **代价与缓解**：选择后端中转的代价是应用服务器承担上传带宽。缓解措施：① 提交接口独立限流（2 r/s）；② 视频上限 200 MB，超限直接拒绝；③ 上传与生成解耦——上传完成并校验通过后才允许提交任务，避免长连接与模型调用同时占用资源；④ 若后续上传带宽成为瓶颈，可在**不改业务接口**的前提下切换为预签名直传（届时恢复 `/api/v1/upload/presign` 与确认接口）。

#### 6.2.4 访问与鉴权

- 桶全部为**私有**，禁止匿名读取；
- 对外一律通过**预签名 GET URL**（默认有效期 1 小时，列表页缩略图可缩短至 10 分钟）；
- 应用侧使用独立的 MinIO 服务账号，只授予必要桶的读写权限，禁止使用 root 凭证；
- 生产环境必须启用 HTTPS（MinIO + Nginx 或 Ingress TLS 终止）。

---

## 7 消息与任务架构（RabbitMQ + Celery）

### 7.1 RabbitMQ 拓扑设计

```
                        ┌──────────────────────────────┐
   提交任务 ────────────▶│ exchange: gen.task.exchange  │  type = direct
                        │      durable = true          │
                        └───────┬──────────┬───────────┘
                                │          │
        routing_key=gen.image   │          │   routing_key=gen.video
                                ▼          ▼
                     ┌──────────────┐  ┌──────────────┐
                     │ q.gen.image  │  │ q.gen.video  │
                     │ prefetch=1   │  │ prefetch=1   │
                     │ priority off │  │ priority off │
                     └──────┬───────┘  └──────┬───────┘
                            │                 │
                            ▼                 ▼
                     worker-image       worker-video
                            │                 │
             失败(可重试)    │                 │   失败(可重试)
                     ┌──────┴─────────────────┴───────┐
                     ▼                                │
        ┌──────────────────────────┐                  │
        │ exchange: gen.retry.ex   │ type = direct    │
        │ routing_key 由重试档位决定 │                  │
        └───────────┬──────────────┘                  │
                    │                                 │
      ┌─────────────┼─────────────┐                   │
      ▼             ▼             ▼                   │
 q.retry.*.30s  q.retry.*.2m  q.retry.*.10m           │
 TTL = 30s      TTL = 120s    TTL = 600s             │
      │             │             │                   │
      └─────────────┴─────────────┘                   │
                    │ TTL 到期后，由各自的              │
                    │ x-dead-letter-routing-key        │
                    │ 精确重投回 gen.task.exchange ─────┘
                    │
                    │ 重试耗尽 / 终态错误
                    ▼
        ┌────────────────────────────┐
        │ exchange: gen.dlx.exchange │ type = fanout
        └───────────┬────────────────┘
                    ▼
               ┌──────────┐
               │ q.gen.dlq│  死信队列：人工介入与告警
               └──────────┘

   对话链路同理：routing_key=gen.chat → q.gen.chat → worker-chat
   * 重试队列按「业务类型 × 延迟档位」展开，共 9 个，见 7.2 表
```

### 7.2 队列与路由定义

| 交换机 | 类型 | 持久化 | 路由键 | 对应队列 |
| --- | --- | --- | --- | --- |
| `gen.task.exchange` | direct | 是 | `gen.image` | `q.gen.image` |
| | | | `gen.video` | `q.gen.video` |
| | | | `gen.chat` | `q.gen.chat` |
| `gen.retry.exchange` | direct | 是 | `retry.image.30s` / `.2m` / `.10m` | `q.retry.image.30s` / `.2m` / `.10m` |
| | | | `retry.video.30s` / `.2m` / `.10m` | `q.retry.video.30s` / `.2m` / `.10m` |
| | | | `retry.chat.30s` / `.2m` / `.10m` | `q.retry.chat.30s` / `.2m` / `.10m` |
| `gen.dlx.exchange` | fanout | 是 | — | `q.gen.dlq` |

**队列参数（关键）**

| 队列 | `x-max-priority` | `x-message-ttl` | 死信配置 | 说明 |
| --- | --- | --- | --- | --- |
| `q.gen.image` | **不启用** | 无 | → `gen.dlx.exchange` | MVP 无加急场景，默认不声明该参数（见 18.2 Q5） |
| `q.gen.video` | **不启用** | 无 | → `gen.dlx.exchange` | 同上 |
| `q.gen.chat` | 无 | 无 | → `gen.dlx.exchange` | 对话要求低延迟，不做优先级 |
| `q.retry.image.30s` / `.2m` / `.10m` | 无 | 30 000 / 120 000 / 600 000 ms | → `gen.task.exchange`，`x-dead-letter-routing-key = gen.image` | 图片任务三档延迟重试 |
| `q.retry.video.30s` / `.2m` / `.10m` | 无 | 同上三档 | → 同上，`x-dead-letter-routing-key = gen.video` | 视频任务三档延迟重试 |
| `q.retry.chat.30s` / `.2m` / `.10m` | 无 | 同上三档 | → 同上，`x-dead-letter-routing-key = gen.chat` | 对话任务三档延迟重试 |
| `q.gen.dlq` | 无 | 无 | 无 | 人工排查与告警 |

> 为什么不用 RabbitMQ 的 `rabbitmq_delayed_message_exchange` 插件：该项目要求尽量少的运维特化。TTL + DLX 是核心特性组合，无需安装插件，且能覆盖「分级延迟重试」需求。若后续确需任意精度延迟，可再引入插件。

#### ⚠️ 必须按「业务类型 × 延迟档位」拆分重试队列的原因

RabbitMQ 在消息 TTL 到期触发死信时，投递到 `x-dead-letter-exchange` 所使用的 routing key，**默认沿用原消息的 routing key**，或使用队列参数 `x-dead-letter-routing-key` 指定的固定值。

由此推出两条硬约束：

1. `x-dead-letter-routing-key` 是**队列级参数**，一个队列只能配置一个值。若 image / video / chat 共用同一个重试队列，则三者中必然有两个无法路由回各自的业务队列；
2. 若退而使用「原 routing key」重投（即消息带着 `retry.image.30s` 回到 `gen.task.exchange`），该 key 在业务交换机上**没有任何绑定**，消息会被判定为 unroutable 而**静默丢弃**——任务就此消失，且默认无任何告警。

因此每个重试队列必须固定自己的 `x-dead-letter-routing-key`（`gen.image` / `gen.video` / `gen.chat`），这是本架构中最容易踩、且踩中后表现为「任务莫名消失」的坑。

> **配套保障**：生产环境必须开启 RabbitMQ 的 `publish_unroutable` 告警或启用 `mandatory` 发布标志 + `basic.return` 处理，确保 unroutable 消息不再静默丢失。Compose 形态下由监控项「队列积压 + 死信非空」间接兜住，K8s 形态建议直接采集 `rabbitmq_channel_messages_unroutable` 指标。

### 7.3 重试与延迟策略

| 重试次数 | 延迟 | 适用错误 |
| --- | --- | --- |
| 第 1 次 | 30 秒 | 网络抖动、第三方 5xx、连接超时 |
| 第 2 次 | 2 分钟 | 第三方限流、临时不可用 |
| 第 3 次 | 10 分钟 | 第三方恢复期 |
| 超过 3 次 | — | 转入 `q.gen.dlq`，任务置 `failed` |

**可重试 vs 终态错误判定**

| 类型 | 示例 | 处理 |
| --- | --- | --- |
| 可重试 | 连接超时、第三方 502/503/504、限流 429、对象存储短暂不可用 | 延迟重投，`retry_count + 1` |
| 终态错误 | 参数非法、模型已禁用、适配器未实现、内容审核拒绝、余额不足（V1.0） | 直接 `failed`，不重试 |
| 需人工 | 适配器返回结构无法解析（疑似厂商接口变更） | 直接 `failed` + 进 DLQ + 告警 |

> 判定规则集中在 `infrastructure/gateway/errors.py` 的 `is_retryable(exc) -> bool`，**禁止在任务代码里散落 `if` 判断**。

### 7.4 Celery 配置

```python
# app/workers/celery_app.py
import os
from celery import Celery

BROKER_URL = os.environ["MQ_URL"]          # amqp://user:pass@rabbitmq:5672/ainew

celery_app = Celery("ainew", broker=BROKER_URL, backend=None)

celery_app.conf.update(
    # ---- 序列化：只允许 JSON，避免 pickle 安全风险 ----
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # ---- 时区 ----
    timezone="UTC",
    enable_utc=True,

    # ---- 可靠性：消息不丢、任务可重投 ----
    task_acks_late=True,                    # 任务执行完成才 ack
    task_reject_on_worker_lost=True,        # Worker 崩溃时消息重回队列
    worker_prefetch_multiplier=1,           # 长任务场景必须为 1，避免任务堆积在单个 Worker 内存
    task_track_started=True,

    # ---- AMQP 传输层参数 ----
    broker_transport_options={
        "visibility_timeout": 3600,         # 与最长任务耗时匹配
        "confirm_publish": True,            # 发布确认，确保入队成功
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.5,
    },
    broker_connection_retry_on_startup=True,
    broker_heartbeat=30,

    # ---- 队列与路由 ----
    task_default_exchange="gen.task.exchange",
    task_default_exchange_type="direct",
    task_default_queue="q.gen.image",
    task_default_routing_key="gen.image",
    task_queues=None,                       # 由拓扑初始化脚本声明（见 7.5）
    task_create_missing_queues=False,       # 关键：禁止 Celery 自动建队列，避免与脚本声明产生参数不一致的同名队列

    task_routes={
        "workers.tasks_image.*": {"exchange": "gen.task.exchange",
                                  "exchange_type": "direct",
                                  "routing_key": "gen.image",
                                  "queue": "q.gen.image"},
        "workers.tasks_video.*": {"exchange": "gen.task.exchange",
                                  "exchange_type": "direct",
                                  "routing_key": "gen.video",
                                  "queue": "q.gen.video"},
        "workers.tasks_chat.*":  {"exchange": "gen.task.exchange",
                                  "exchange_type": "direct",
                                  "routing_key": "gen.chat",
                                  "queue": "q.gen.chat"},
    },

    # ---- 任务级超时（硬性上限，防止 Worker 被单个任务占死） ----
    task_time_limit=900,                    # 15 分钟硬超时
    task_soft_time_limit=840,               # 14 分钟软超时，抛 SoftTimeLimitExceeded 可清理

    # ---- 不自动重试，由业务侧显式重投（走 retry 队列控制延迟） ----
    task_acks_on_failure_or_timeout=False,
)

# 显式导入任务模块，保证 Worker 能发现任务
celery_app.autodiscover_tasks(["app.workers"], related_name=None)
```

### 7.5 队列拓扑声明脚本

```python
# scripts/init_mq_topology.py
# 通过 AMQP 管理 HTTP API 或 kombu 声明交换机、队列与绑定关系（幂等，可重复执行）
import os
import httpx

MQ_API = os.environ["MQ_API"]               # http://rabbitmq:15672/api
AUTH = (os.environ["MQ_USER"], os.environ["MQ_PASS"])
VHOST = os.environ.get("MQ_VHOST", "ainew")

EXCHANGES = [
    {"name": "gen.task.exchange",  "type": "direct", "durable": True},
    {"name": "gen.retry.exchange", "type": "direct", "durable": True},
    {"name": "gen.dlx.exchange",   "type": "fanout", "durable": True},
]

# 主队列
# 队列优先级默认不启用：MVP 需求中没有加急/付费插队场景（见 18.2 Q5）。
# 若后续确认需要，把 "x-max-priority": 9 加回下列 args 后重建队列（重建前须清空消息）。
MAIN_QUEUES = [
    {"name": "q.gen.image", "args": {"x-dead-letter-exchange": "gen.dlx.exchange"}},
    {"name": "q.gen.video", "args": {"x-dead-letter-exchange": "gen.dlx.exchange"}},
    {"name": "q.gen.chat",  "args": {"x-dead-letter-exchange": "gen.dlx.exchange"}},
]

# 重试队列：按「业务类型 × 延迟档位」展开
# 元组含义：(业务类型, 档位名, TTL 毫秒, 死信重投的 routing key)
RETRY_SPECS = [
    ("image", "30s", 30_000,  "gen.image"),
    ("image", "2m",  120_000, "gen.image"),
    ("image", "10m", 600_000, "gen.image"),
    ("video", "30s", 30_000,  "gen.video"),
    ("video", "2m",  120_000, "gen.video"),
    ("video", "10m", 600_000, "gen.video"),
    ("chat",  "30s", 30_000,  "gen.chat"),
    ("chat",  "2m",  120_000, "gen.chat"),
    ("chat",  "10m", 600_000, "gen.chat"),
]

RETRY_QUEUES = [
    {
        "name": f"q.retry.{biz}.{tier}",
        "args": {
            "x-message-ttl": ttl,
            "x-dead-letter-exchange": "gen.task.exchange",
            # 关键：决定 TTL 到期后消息能否回到正确的业务队列
            "x-dead-letter-routing-key": dlrk,
        },
    }
    for biz, tier, ttl, dlrk in RETRY_SPECS
]

BINDINGS = [
    ("gen.task.exchange", "q.gen.image", "gen.image"),
    ("gen.task.exchange", "q.gen.video", "gen.video"),
    ("gen.task.exchange", "q.gen.chat",  "gen.chat"),
    ("gen.dlx.exchange",  "q.gen.dlq",   ""),
] + [
    ("gen.retry.exchange", q["name"], f"retry.{biz}.{tier}")
    for (biz, tier, _, _), q in zip(RETRY_SPECS, RETRY_QUEUES)
]


def declare_all() -> None:
    """幂等声明：交换机 → 队列 → 绑定，可重复执行。"""
    for ex in EXCHANGES:
        httpx.put(
            f"{MQ_API}/exchanges/{VHOST}/{ex['name']}",
            json={"type": ex["type"], "durable": ex["durable"],
                  "auto_delete": False, "internal": False, "arguments": {}},
            auth=AUTH, timeout=10,
        ).raise_for_status()

    for q in MAIN_QUEUES + RETRY_QUEUES + [{"name": "q.gen.dlq", "args": {}}]:
        httpx.put(
            f"{MQ_API}/queues/{VHOST}/{q['name']}",
            json={"durable": True, "auto_delete": False, "arguments": q["args"]},
            auth=AUTH, timeout=10,
        ).raise_for_status()

    for ex_name, q_name, rk in BINDINGS:
        httpx.post(
            f"{MQ_API}/bindings/{VHOST}/e/{ex_name}/q/{q_name}",
            json={"routing_key": rk, "arguments": {}},
            auth=AUTH, timeout=10,
        ).raise_for_status()


if __name__ == "__main__":
    declare_all()
    print("RabbitMQ topology declared (3 exchanges / 13 queues / 13 bindings).")
```

> **延迟重试的两种实现方式与取舍**
>
> 1. **多级重试队列（本架构采用）**：每档延迟一个独立队列，`x-message-ttl` 固定，路由由业务侧按 `retry_count` 选择，行为确定；
> 2. 单队列 + 消息级 `expiration`：队列数量少，但存在**队头阻塞**——队首是 10 分钟 TTL 的消息时，其后面 30 秒 TTL 的消息必须等它先过期才能被判定为死信，实际延迟不可控。
>
> 多级队列的代价是队列数量增加到 13 个（3 主队列 + 9 重试队列 + 1 死信队列），换来延迟精度与行为可预测性。该量级下运维成本可忽略。

业务侧重投代码：

```python
# app/infrastructure/mq/publisher.py（重试发布要点）
from app.workers.celery_app import publish_task

# 按 retry_count 从高到低匹配档位
RETRY_TIERS = [(3, "10m"), (2, "2m"), (1, "30s")]


def publish_retry(task_id: str, biz: str, retry_count: int, trace_id: str) -> None:
    """把失败任务投递到对应的延迟重试队列。"""
    tier = next((t for cnt, t in RETRY_TIERS if retry_count >= cnt), "30s")
    routing_key = f"retry.{biz}.{tier}"        # 必须与 RETRY_SPECS 的绑定键一致

    publish_task.apply_async(
        kwargs={"task_id": task_id, "trace_id": trace_id},
        exchange="gen.retry.exchange",
        routing_key=routing_key,
        retry=False,                            # 入队失败不再递归重投，交给兜底任务处理
    )
```

### 7.6 Worker 部署与并发模型

| Worker | 消费队列 | 并发参数 | 说明 |
| --- | --- | --- | --- |
| `worker-image` | `q.gen.image` | `--concurrency=8 --prefetch-multiplier=1` | 图片 API 多为秒级到分钟级，可适当提高并发 |
| `worker-video` | `q.gen.video` | `--concurrency=4 --prefetch-multiplier=1` | 视频任务耗时长，并发过高会触发第三方限流 |
| `worker-chat` | `q.gen.chat` | `--concurrency=8 --prefetch-multiplier=1` | 低延迟优先 |

> **关于 `prefetch_multiplier` 的说明**：Celery 默认 `prefetch = concurrency × 4`，对耗时任务会导致「消息被大量预取到某个 Worker，其他 Worker 空闲而队列显示为空」的假象。因此长任务场景**必须设为 1**。

**Worker 是否用 gevent/eventlet？**

- 需要调用第三方 API（I/O 密集）时，推荐 `--pool=gevent --concurrency=20`，可显著提升单容器吞吐；
- 但 gevent 与部分同步库（如某些 SDK、`boto3` 的同步调用）存在兼容坑；
- **本架构选型：使用默认 prefork 池 + 异步 HTTP 客户端（httpx.AsyncClient）**，通过 `asyncio.run()` 在任务内驱动异步调用。复杂度更低、行为可预测。若后续吞吐不足，再评估 gevent。

### 7.7 任务幂等设计

| 风险 | 场景 | 对策 |
| --- | --- | --- |
| 消息重投导致重复执行 | Worker 崩溃、ack 超时 | 任务执行前校验 `status`，仅 `queued` 状态允许执行；执行前用 Redis 锁 `lock:task:{task_id}`（TTL = 任务超时）抢占 |
| 重复扣费 | 重试执行 | 积分日志以 `task_id` 唯一约束去重（或写前校验） |
| 产物重复上传 | 重试 | 产物对象 Key 使用 `task_id` 派生，重复上传覆盖同名对象，历史记录以最后一次为准 |

---

## 8 模型网关架构

### 8.1 适配器模式结构

```
                    ┌──────────────────────────────┐
   业务层（service） │  ModelGatewayService         │
   只传 model_id    │  .dispatch(model_id,         │
                    │            task_type,        │
                    │            params, trace_id) │
                    └──────────────┬───────────────┘
                                   │ 1) 取配置（Redis 缓存 → PG）
                                   ▼
                    ┌──────────────────────────────┐
                    │  ModelConfigRepository       │
                    │  返回 ai_model 记录           │
                    │  （含 adapter_key、能力、价格）│
                    └──────────────┬───────────────┘
                                   │ 2) 按 adapter_key 查注册表
                                   ▼
                    ┌──────────────────────────────┐
                    │  ADAPTER_REGISTRY            │
                    │  "wanxiang3.0" → WanXiangAdp │
                    │  "minimax_video" → MiniMaxAdp│
                    └──────────────┬───────────────┘
                                   │ 3) 实例化（注入 config）
                                   ▼
                    ┌──────────────────────────────┐
                    │  BaseModelAdapter (ABC)      │
                    │  txt2img / img2img           │
                    │  txt2vid / img2vid           │
                    │  vid2vid / vid_edit          │
                    │  chat_completion             │
                    └──────────────┬───────────────┘
                                   │ 4) 统一 HTTP 客户端
                                   │    （超时/重试/限流/OTel Span）
                                   ▼
                           第三方 AI 模型 API
```

### 8.2 关键接口定义

```python
# app/infrastructure/gateway/base.py
from abc import ABC, abstractmethod

class BaseModelAdapter(ABC):
    """模型适配器抽象基类。新增厂商只需实现本类并注册。"""

    def __init__(self, model_conf: dict):
        self.model_conf = model_conf          # ai_model 记录快照
        self.config = model_conf["config_json"]

    # ---- 能力自查：网关据此做参数与能力校验 ----
    def supports(self, task_type: str) -> bool:
        return callable(getattr(self, task_type, None))

    @abstractmethod
    def txt2img(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def img2img(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def txt2vid(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def img2vid(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def vid2vid(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def vid_edit(self, params: dict, trace_id: str) -> dict: ...
    @abstractmethod
    def chat_completion(self, messages: list, params: dict, trace_id: str) -> dict: ...
```

**统一返回契约**（所有适配器必须返回同一结构，业务层无需区分厂商）：

```python
{
    "content_text": "对话场景的回答文本，生成场景为 None",
    "asset_urls": ["http://minio/ai-output/.../x.png"],   # 已落 MinIO 的产物
    "provider_task_id": "厂商侧任务号（异步模式）",
    "raw": {...},                                          # 厂商原始响应，仅落日志与审计
}
```

### 8.3 配置加载与缓存

| 项 | 策略 |
| --- | --- |
| 读路径 | Redis 缓存（key: `cfg:model:{model_id}`，TTL 300s）→ 未命中查 PG → 回填缓存 |
| 写路径 | 后台改配置后**主动删除**对应缓存 key（`DEL cfg:model:{id}`），保证即时生效 |
| 快照语义 | 任务入队时把模型配置与提示词一并写入 `ai_generate_task.snapshot_config`，Worker 只读快照，**不读缓存** |
| 通配失效 | 提示词模板按 `task_type` 匹配，后台改动后 `DEL cfg:prompt:{task_type}:*` |

> 这里有一个刻意的设计取舍：**Worker 读快照而非实时配置**。代价是快照字段占用少量存储，收益是彻底消除「任务执行到一半配置被改」的竞态，这是需求文档第 8.6 节「配置快照原则」在架构上的落地方式。

### 8.4 超时、重试、限流

| 控制项 | 取值 | 实现位置 |
| --- | --- | --- |
| 连接超时 | 10s | httpx `Timeout(connect=10)` |
| 读取超时（图片） | 120s | 按能力区分 |
| 读取超时（视频） | 600s | 视频生成耗时长 |
| 读取超时（对话） | 60s | — |
| 传输层重试 | 2 次，仅重试连接失败 | httpx transport retries |
| 业务层重试 | 见 7.3 分级延迟 | Celery 任务 |
| 单模型并发限流 | Redis 令牌桶 `rate:model:{model_id}` | 网关入口 |
| 熔断 | 连续 10 次失败 → 熔断 60 秒 | Redis 计数 + 状态位 |

> 熔断是**重要保护**：某个第三方模型批量故障时，避免 Worker 全部阻塞在该供应商，也避免把失败任务快速灌满重试队列。

---

## 9 链路追踪架构（OpenTelemetry）

### 9.1 选型说明与当前形态

按决策，采用 **OpenTelemetry SDK 标准埋点，但暂不部署 Collector / Jaeger 后端**。Span 通过 `ConsoleSpanExporter`（开发环境）或**自定义导出器写入结构化日志**（生产环境）输出，配合日志中的 `trace_id` 即可完成排查。

**这个选择的收益**：零额外组件运维成本，排查靠日志检索。

**这个选择的代价（必须承认）**：没有调用拓扑视图与 Span 瀑布图，跨服务耗时分析需要从日志时间戳人工拼接。

**切换成本几乎为零**：后续只要部署 OTel Collector + Jaeger（或 Tempo），把 `SpanExporter` 从日志导出器换成 `OTLPSpanExporter` 即可，**业务代码零改动**。这正是选 OTel 而非自研 TraceID 方案的核心原因。

### 9.2 埋点组件矩阵

| 组件 | instrumentation 包 | 覆盖内容 |
| --- | --- | --- |
| FastAPI | `opentelemetry-instrumentation-fastapi` | HTTP 入口 Span、请求耗时、状态码 |
| httpx | `opentelemetry-instrumentation-httpx` | 第三方模型调用 Span（自动带 URL、状态码、耗时） |
| Celery | `opentelemetry-instrumentation-celery` | 任务入队与执行 Span，**自动通过消息 headers 传播 Context** |
| SQLAlchemy | `opentelemetry-instrumentation-sqlalchemy` | 数据库语句 Span（可选开启，注意语句参数脱敏） |
| Redis | `opentelemetry-instrumentation-redis` | 缓存调用 Span（可选） |

### 9.3 初始化代码

```python
# app/core/tracing.py
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

_TRACER: trace.Tracer | None = None


def init_tracing(app=None) -> None:
    global _TRACER

    resource = Resource.create({
        SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "ainew-api"),
        "service.version": os.environ.get("APP_VERSION", "1.0.0"),
        "deployment.environment": os.environ.get("ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)

    # 当前阶段：导出到控制台 / 日志采集
    # 后续切换为 OTLP 时，仅需把下面两行替换为 OTLPSpanExporter 配置
    #   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    #   provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=...)))
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("ainew")

    # 自动埋点
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    CeleryInstrumentor().instrument()       # 打通 API → 队列 → Worker 的 Context


def get_tracer() -> trace.Tracer:
    return _TRACER or trace.get_tracer("ainew")


def current_trace_id() -> str:
    """提取当前 Span 的 trace_id（32 位十六进制），用于写入响应体与日志。"""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.is_valid:
        return ""
    return format(ctx.trace_id, "032x")
```

### 9.4 跨进程 Context 传播

| 链路 | 传播载体 | 是否需手工处理 |
| --- | --- | --- |
| 浏览器 → API | HTTP Header `traceparent`（W3C 标准） | 否，FastAPI instrumentation 自动解析 |
| API → RabbitMQ → Worker | AMQP message headers（`traceparent`） | 否，Celery instrumentation 自动注入与提取 |
| Worker → 第三方 API | HTTP Header `traceparent` | 否，HTTPXClientInstrumentor 自动注入 |
| 前端展示用 TraceID | 响应体 `trace_id` 字段 | 是，由 `current_trace_id()` 提取 |

> **一致性要求**：需求文档中约定的自定义头 `X-Trace-Id` 与 W3C 标准的 `traceparent` 并存处理：入口中间件优先读取 `traceparent`（标准优先），若不存在则读取 `X-Trace-Id` 并作为 `trace_id` 使用；响应体统一返回 32 位 hex 的 `trace_id`，同时回写响应头 `X-Trace-Id` 便于前端记录。
>
> **前端实现约定（已确认）**：MVP 前端只需发送自定义头 `X-Trace-Id`；若前端后续接入 OTel Web SDK，则改发标准 `traceparent`，**后端无需任何改动**。两文档对 TraceID 来源与格式的口径以此条为准。

### 9.5 手工 Span 规划

自动埋点覆盖不到的关键业务阶段，需补手工 Span：

| Span 名称 | 位置 | 关键属性（attributes） |
| --- | --- | --- |
| `resolve_task_type` | `domain/gen_type_resolver.py` | `gen_type`、`has_asset`、`video_sub_mode`、`resolved_task_type` |
| `match_system_prompt` | `services/prompt_service.py` | `task_type`、`model_id`、`matched_prompt_id`、`matched_scope`（model/global/fallback） |
| `persist_task` | `services/task_service.py` | `task_id`、`user_id`、`expect_credit` |
| `publish_task` | `infrastructure/mq/publisher.py` | `queue`、`routing_key`、`retry_count` |
| `model_call` | 适配器内 | `model_id`、`adapter_key`、`task_type`、`provider_task_id` |
| `upload_output` | `infrastructure/storage/minio_client.py` | `bucket`、`object_key`、`size_bytes` |
| `update_task_status` | `services/task_service.py` | `from_status`、`to_status`、`error_code` |

**敏感信息脱敏（硬性）**：Span attributes 与日志中**禁止出现**提示词全文、用户手机号、第三方 API Key。提示词只记录长度与哈希前缀（如 `prompt_sha8=3f7a1c2e`），必要时由运营通过任务详情页在后台按权限查看。

---

## 10 安全架构

### 10.1 认证与授权

| 层 | 机制 |
| --- | --- |
| 用户认证 | 手机号 + 短信验证码 → JWT（HS256，`sub` = user_id，有效期 7 天，支持续期） |
| 管理员认证 | `sys_user.is_admin = true` 标识管理员，**复用现有手机号 + 验证码登录体系**，登录后由 `require_admin` 依赖校验；**所有 `/api/v1/admin/**` 必须挂载该依赖**。MVP 不引入独立管理员表与独立登录入口 |
| 接口授权 | FastAPI 依赖 `get_current_user` / `require_admin`，**默认全站需登录**，白名单显式开放在路由装饰器上 |
| 越权防护 | 所有按 ID 查询的接口必须带 `user_id` 条件（`WHERE task_id = :tid AND user_id = :uid`），禁止先查后判 |

### 10.2 密钥与凭证管理

| 凭证 | 存储方式 |
| --- | --- |
| 数据库/中间件连接串 | 环境变量 / K8s Secret |
| JWT 签名密钥 | 环境变量，长度 ≥ 32 字节，**禁止硬编码** |
| 第三方模型 API Key | **环境变量**；`ai_model.config_json` 只存 `{"api_key_env": "WANXIANG_API_KEY"}` 这样的引用 |
| MinIO 访问凭证 | 环境变量，使用最小权限服务账号 |

> 后台管理界面中，`config_json` 的密钥字段在回显时做掩码处理（`******`），提交时若为掩码值则不覆盖原值。

### 10.3 上传安全

| 检查项 | 规则 |
| --- | --- |
| 扩展名白名单 | 图片：`jpg/jpeg/png/webp`；视频：`mp4/mov` |
| MIME 校验 | 读取文件头魔数校验真实类型，不信任 `Content-Type` |
| 大小上限 | 图片 ≤ 10 MB；视频 ≤ 200 MB（可配置） |
| 文件名 | 服务端重命名为 UUID，**丢弃用户原始路径**，防止路径穿越 |
| 恶意内容 | 禁止可执行文件；图片可选做二次编码（剥离 EXIF 与嵌入脚本） |
| 上传流控 | 按用户与 IP 限制并发上传数；接收过程中累计字节数超限立即中断连接并回收已写入对象 |

### 10.4 应用安全

| 风险 | 对策 |
| --- | --- |
| SQL 注入 | 全量使用 SQLAlchemy 参数化查询，禁止字符串拼接 SQL |
| 敏感词与合规 | 提交入口做提示词过滤，命中即拒绝且不调用模型 |
| 接口刷量 | Nginx 层 IP 限流 + 应用层用户级限流（Redis 计数器） |
| 短信轰炸 | 同一手机号 60 秒 1 条、单日上限 10 条；发送前校验图形验证码 |
| 响应信息泄露 | 生产环境关闭详细堆栈；第三方原始响应只落审计日志，不返回前端 |
| 对象越权 | 签名 GET URL 由服务端按 `user_id` 校验归属后签发；对象 Key 含 `user_id` 前缀，服务端禁止跨用户拼接 Key |

---

## 11 可扩展性设计

### 11.1 新增一个 AI 模型的完整流程（零业务改造）

| 步骤 | 动作 | 改动范围 |
| --- | --- | --- |
| 1 | 在 `adapters/` 新增适配器类，实现 `BaseModelAdapter` | 仅新增文件 |
| 2 | 在 `ADAPTER_REGISTRY` 注册 `adapter_key` | 一行配置 |
| 3 | 后台新增模型配置（名称、类型、能力、价格、`config_json`） | 仅数据 |
| 4 | 后台启用模型 | 仅数据 |

**结论**：前端页面、业务接口、数据库结构均无改动。这是本架构最核心的扩展性保证。

### 11.2 其他扩展点

| 扩展场景 | 预留设计 |
| --- | --- |
| 新增任务类型（商品套图、抠图、换装） | `task_type` 的 CHECK 约束显式扩充 + 新增适配器方法 + 新增队列；`extra` 字段承载新参数 |
| 新增生成大类 | `gen_type` 扩展，`gen_type_resolver` 增加分支 |
| 新增模型能力参数 | 模型表 `support_*` 字段与 `price_config_json` 结构扩展，前端按能力渲染控件 |
| 接入第二家对象存储 | `storage` 层抽象为接口，MinIO 与云 OSS 各一个实现，配置切换 |
| 拆分微服务 | 当前已按模块边界组织（用户/模型/会话/任务），且 `domain` 层无框架依赖，可按模块拆分独立服务 |
| 引入工作流引擎 | 任务表已记录 `trace_id` 与状态机；若未来需要多步编排，可在 `services` 层之上引入，不影响适配器层 |

### 11.3 反过度设计声明

以下能力**本架构明确不做**，避免 MVP 阶段复杂度失控：

- 不引入 DDD 的聚合/领域事件总线（业务复杂度不足以支撑其成本）；
- 不引入微服务与 RPC（单体足以支撑单日千级任务）；
- 不引入 Kafka（单日千级任务量，RabbitMQ 的路由与死信能力更契合需求）；
- 不做自建 GPU 推理服务；
- 不做多租户数据隔离（预留 `user_type` 字段，未来按行级隔离策略扩展）。

---

## 12 性能与容量设计

### 12.1 容量假设与估算

| 指标 | 假设值 | 说明 |
| --- | --- | --- |
| 日生成任务量 | 1,000 ~ 3,000 | 需求文档口径：单日千级 |
| 峰值时段占比 | 20% 任务集中在 2 小时内 | 电商运营作息 |
| 峰值任务吞吐 | 约 0.3 ~ 0.5 任务/秒 | 3000 × 20% ÷ 7200s ≈ 0.08 ~ 0.25，取上浮余量 |
| 图片单任务耗时 | 10 ~ 60 秒 | 生成 + 上传 |
| 视频单任务耗时 | 60 ~ 300 秒 | 生成 + 上传 |
| 视频并发上限 | 约 6 并发 | 受第三方限流约束，非受本系统约束 |
| 单任务平均产物 | 图片 2 MB × 1 张；视频 20 MB | MVP 单次生成固定 1 张/个，接口预留 `n` 字段 |
| 日存储增量 | 图片约 24 GB/日；视频约 24 GB/日 | 按 3000 任务、图文各半估算 |

> 上述为估算口径，用于容量规划。**实际上线后需以真实埋点数据校正**，矫正方法见 14.2 指标清单。

### 12.2 连接池配置

| 资源 | 参数 | 取值 | 说明 |
| --- | --- | --- | --- |
| PostgreSQL | `pool_size` | 10（API）/ 5（Worker） | 单实例连接数上限约 100，需按副本数预留 |
| | `max_overflow` | 10 | 峰值临时连接 |
| | `pool_timeout` | 30s | 获取连接超时 |
| | `pool_recycle` | 1800s | 避免长连接被中间件断开 |
| | `pool_pre_ping` | True | 取连接前探活，避免使用失效连接 |
| Redis | `max_connections` | 50 | 单实例 |
| httpx | `max_connections` | 100 | 第三方调用连接池 |
| | `max_keepalive_connections` | 20 | — |
| MinIO | 客户端连接池 | 20 | 上传并发受带宽约束 |

**连接数总账（重要）**：`(API 副本数 × 10) + (Worker 副本数 × 5) + 运维连接 < PostgreSQL max_connections`。按 API 2 副本 + Worker 5 副本计算为 45，而 13.1.2 的 compose 将 `max_connections` 设为 200，余量充足。

但扩容时必须重新核对这条约束——它是最容易被忽略的扩容天花板：API 副本扩到 8（K8s HPA 上限）+ Worker 8 副本时，连接数需求升至 120，加上迁移、备份、运维连接后已接近安全边界。因此**调整任何一层的副本数上限时，都要同步复核 PostgreSQL 的 `max_connections`**，必要时引入 PgBouncer 做连接池复用。

### 12.3 超时与降级

| 场景 | 超时 | 降级行为 |
| --- | --- | --- |
| API 请求 | 30s（Nginx 60s） | 返回 504 并记录 trace_id |
| 模型调用 | 见 8.4 | 重试 / 熔断 / 任务置失败 |
| 数据库查询 | 5s（statement_timeout） | 中断慢查询，记录告警 |
| MinIO 上传 | 300s | 重试 2 次后任务失败 |
| 第三方熔断 | 连续 10 次失败 | 熔断 60s，快速失败并写入明确错误码 |

### 12.4 性能优化要点

1. **接口不阻塞**：生成接口只做校验与入队，实测应稳定在 200 ms 内；
2. **轮询降频**：前端轮询间隔建议 2s 起、逐步退避到 10s；更优方案是接入 SSE 推送（列为 V1.1 优化项）；
3. **列表查询分页**：任务列表强制分页（默认 20 条），并使用 `idx_task_user_create` 覆盖排序；
4. **大字段隔离**：`input_params`、`output_asset_urls` 等 jsonb 字段在列表查询中**不返回全量**，详情接口才返回；
5. **缩略图**：图片列表使用 `ai-thumb` 桶的缩略图，避免列表页加载原图。

---

## 13 部署架构

### 13.1 形态一：Docker Compose（起步方案）

#### 13.1.1 拓扑

```
主机（单台，建议 8C16G 起）
┌───────────────────────────────────────────────────────────────┐
│  docker network: ainew-net                                    │
│                                                               │
│   nginx:80/443 ──▶ api:8000 ──┬──▶ postgres:5432              │
│                               ├──▶ redis:6379                 │
│                               └──▶ rabbitmq:5672/15672        │
│                                                               │
│   worker-image ──┐                                            │
│   worker-video ──┼──▶ rabbitmq / postgres / redis / minio     │
│   worker-chat  ──┤                                            │
│   beat         ──┘                                            │
│                                                               │
│   minio:9000/9001                                             │
└───────────────────────────────────────────────────────────────┘
        持久化卷：pg-data · mq-data · redis-data · minio-data
```

#### 13.1.2 docker-compose.yml

```yaml
# docker-compose.yml
name: ainew

x-app-env: &app-env
  ENV: ${ENV:-dev}
  DATABASE_URL: postgresql+asyncpg://ainew:${PG_PASS}@postgres:5432/ainew
  REDIS_URL: redis://redis:6379/0
  MQ_URL: amqp://ainew:${MQ_PASS}@rabbitmq:5672/ainew
  MINIO_ENDPOINT: minio:9000
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
  JWT_SECRET: ${JWT_SECRET}
  OTEL_SERVICE_NAME: ainew

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ainew
      POSTGRES_USER: ainew
      POSTGRES_PASSWORD: ${PG_PASS}
      TZ: UTC
      # 时区与慢查询保护
      POSTGRES_INITDB_ARGS: "--data-checksums"
    command: >
      postgres
      -c max_connections=200
      -c shared_buffers=1GB
      -c work_mem=16MB
      -c maintenance_work_mem=256MB
      -c statement_timeout=5000
      -c log_min_duration_statement=1000
      -c timezone=UTC
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ainew -d ainew"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: ainew
      RABBITMQ_DEFAULT_PASS: ${MQ_PASS}
      RABBITMQ_DEFAULT_VHOST: ainew
    volumes:
      - mq-data:/var/lib/rabbitmq
    ports:
      - "15672:15672"      # 管理台，生产建议仅内网暴露
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 15s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 15s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # 一次性任务：建桶与生命周期策略
  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
      mc mb -p local/ai-input local/ai-output local/ai-thumb local/ai-backup || true &&
      mc ilm rule add --expire-days 7 local/ai-input || true &&
      mc anonymous set none local/ai-input local/ai-output local/ai-thumb || true &&
      echo 'minio init done'
      "
    restart: "no"

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      <<: *app-env
    command: >
      gunicorn app.main:app
      -k uvicorn.workers.UvicornWorker
      -w 2 -b 0.0.0.0:8000
      --timeout 120 --graceful-timeout 30 --access-logfile -
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
      redis:    {condition: service_healthy}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 15s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  worker-image:
    build: {context: ., dockerfile: Dockerfile}
    environment:
      <<: *app-env
    command: celery -A app.workers.celery_app:celery_app worker
             -Q q.gen.image -c 8 --prefetch-multiplier=1 -l info -n image@%h
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
    restart: unless-stopped

  worker-video:
    build: {context: ., dockerfile: Dockerfile}
    environment:
      <<: *app-env
    command: celery -A app.workers.celery_app:celery_app worker
             -Q q.gen.video -c 4 --prefetch-multiplier=1 -l info -n video@%h
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
    restart: unless-stopped

  worker-chat:
    build: {context: ., dockerfile: Dockerfile}
    environment:
      <<: *app-env
    command: celery -A app.workers.celery_app:celery_app worker
             -Q q.gen.chat -c 8 --prefetch-multiplier=1 -l info -n chat@%h
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
    restart: unless-stopped

  beat:
    build: {context: ., dockerfile: Dockerfile}
    environment:
      <<: *app-env
    command: celery -A app.workers.celery_app:celery_app beat -l info
    depends_on:
      rabbitmq: {condition: service_healthy}
    restart: unless-stopped

  nginx:
    image: nginx:1.25-alpine
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./deploy/certs:/etc/nginx/certs:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  pg-data:
  mq-data:
  redis-data:
  minio-data:
```

> **关于 `beat` 单实例**：Celery Beat 必须保证全局唯一，多副本会导致定时任务重复触发。Compose 下固定 1 副本；K8s 下使用 `strategy: Recreate` + `replicas: 1`，或用分布式锁确保只有一个实例实际调度。

#### 13.1.3 Nginx 关键配置

```nginx
# deploy/nginx.conf
upstream ainew_api {
    server api:8000;
    keepalive 32;
}

# 限流区：IP 维度
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=submit_limit:10m rate=2r/s;

server {
    listen 80;
    server_name _;
    client_max_body_size 210m;      # 视频上传上限

    # 统一传递与回写 TraceID
    location /api/ {
        limit_req zone=api_limit burst=40 nodelay;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 若上游未携带 traceparent，则由 Nginx 透传客户端值或留空由应用生成
        proxy_set_header traceparent       $http_traceparent;
        proxy_set_header X-Trace-Id        $http_x_trace_id;

        proxy_http_version 1.1;
        proxy_connect_timeout 10s;
        proxy_read_timeout    120s;
        proxy_send_timeout    120s;

        proxy_pass http://ainew_api;
    }

    # 生成提交接口：更严格限流
    location = /api/v1/generate/task {
        limit_req zone=submit_limit burst=5 nodelay;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_pass http://ainew_api;
    }

    location /healthz { proxy_pass http://ainew_api; }
}
```

### 13.2 形态二：Kubernetes（演进方案）

#### 13.2.1 工作负载规划

| 工作负载 | 类型 | 副本 | 说明 |
| --- | --- | --- | --- |
| `ainew-api` | Deployment | 2 → HPA 8 | 无状态，CPU 70% 触发扩容 |
| `ainew-worker-image` | Deployment | 2 → HPA 10 | 扩容指标建议用**队列长度**而非 CPU |
| `ainew-worker-video` | Deployment | 2 → HPA 6 | 同上，且受第三方限流约束 |
| `ainew-worker-chat` | Deployment | 1 → HPA 4 | — |
| `ainew-beat` | Deployment | **1** | `strategy: Recreate`，禁止多副本 |
| `postgres` | StatefulSet | 1（主） | 生产建议用托管 PG 或 CloudNativePG Operator |
| `rabbitmq` | StatefulSet | 1（或 3 节点集群） | 需 `volumeClaimTemplates` |
| `redis` | StatefulSet / 托管 | 1 | — |
| `minio` | StatefulSet | 4（纠删码） | 或使用 S3 兼容的对象存储服务 |
| `otel-collector` | Deployment | 1 | **当前阶段不部署**，预留 |

#### 13.2.2 API Deployment（节选）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ainew-api
spec:
  replicas: 2
  selector:
    matchLabels: {app: ainew-api}
  template:
    metadata:
      labels: {app: ainew-api}
    spec:
      containers:
        - name: api
          image: registry.example.com/ainew/api:1.0.0
          command:
            - gunicorn
            - app.main:app
            - -k
            - uvicorn.workers.UvicornWorker
            - -w
            - "2"
            - -b
            - 0.0.0.0:8000
            - --timeout
            - "120"
          ports:
            - {containerPort: 8000}
          envFrom:
            - configMapRef: {name: ainew-config}
            - secretRef:    {name: ainew-secret}
          resources:
            requests: {cpu: "500m", memory: "512Mi"}
            limits:   {cpu: "2",    memory: "2Gi"}
          livenessProbe:
            httpGet: {path: /healthz, port: 8000}
            initialDelaySeconds: 20
            periodSeconds: 15
          readinessProbe:
            httpGet: {path: /readyz, port: 8000}
            initialDelaySeconds: 10
            periodSeconds: 10
```

#### 13.2.3 基于队列长度的 HPA（KEDA）

Worker 的扩容依据应是**积压消息数**，而不是 CPU——Worker 大部分时间在等待第三方 API 响应，CPU 占用很低，用 CPU 扩容会失效。

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker-video-scaler
spec:
  scaleTargetRef:
    name: ainew-worker-video
  minReplicaCount: 2
  maxReplicaCount: 6
  cooldownPeriod: 300          # 视频任务长，缩容要滞后，避免抖动
  triggers:
    - type: rabbitmq
      metadata:
        protocol: amqp
        queueName: q.gen.video
        mode: QueueLength
        value: "10"            # 每副本约 10 条积压
      authenticationRef:
        name: rabbitmq-auth
```

> 注意 `maxReplicaCount` 要受第三方模型并发配额约束——否则扩容只会把请求打成 429。

#### 13.2.4 从 Compose 迁移到 K8s 的清单

| 项 | Compose | K8s | 需要改代码？ |
| --- | --- | --- | --- |
| 服务发现 | 容器名 DNS | Service DNS | 否（都用环境变量注入地址） |
| 配置注入 | `.env` | ConfigMap / Secret | 否 |
| 存储 | Docker Volume | PVC / 托管服务 | 否（只改连接串） |
| 入口 | Nginx 容器 | Ingress | 否 |
| 扩容 | 手动改副本 | HPA / KEDA | 否 |
| 定时任务 | beat 单容器 | beat 单副本 Deployment | 否 |

**结论**：迁移只涉及编排文件与环境变量，不涉及业务代码——这是把连接串、密钥、地址全部外置的直接收益。

---

## 14 可观测性与运维

### 14.1 日志规范

统一 **JSON 结构化日志**，单行输出，每条日志必带链路字段。**字段名与需求说明书 V0.5.1 的日志规范保持一致**：使用完整字段名 `timestamp` / `message`，不使用 `ts` / `msg`：

```json
{
  "timestamp": "2026-10-08T06:12:33.421Z",
  "level": "INFO",
  "service": "ainew-worker-video",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "task_id": "9b2d4e6f-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  "user_id": 1024,
  "model_id": 10,
  "adapter_key": "minimax_video",
  "system_prompt_id": 15,
  "message": "model_call_succeeded",
  "duration_ms": 42310,
  "provider_task_id": "mmx-88771"
}
```

```python
# app/core/logging.py（要点）
import json, logging, time
from app.core.tracing import current_trace_id, trace

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "service": getattr(record, "service", "ainew"),
            "trace_id": current_trace_id(),
            "span_id": format(ctx.span_id, "016x") if ctx and ctx.is_valid else "",
            "message": record.getMessage(),
        }
        # 业务侧通过 extra 传入 task_id / model_id 等字段
        for k in ("task_id", "user_id", "model_id", "adapter_key",
                  "system_prompt_id", "duration_ms", "error_code"):
            v = getattr(record, k, None)
            if v is not None:
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
```

**日志留存**：应用日志按天轮转，保留 30 天；审计类日志（任务、积分、后台配置变更）保留 1 年。

### 14.2 指标清单（Prometheus 预留）

| 类别 | 指标 | 用途 |
| --- | --- | --- |
| 接口 | `http_request_duration_seconds{path,method,status}` | 接口 RT 与错误率 |
| 任务 | `gen_task_total{task_type,model_id,status}` | 任务量与成功率 |
| 任务 | `gen_task_duration_seconds{task_type,model_id}` | 生成耗时分布（P50/P95/P99） |
| 队列 | `rabbitmq_queue_messages_ready{queue}` | **积压深度——扩容的核心依据** |
| 队列 | `rabbitmq_queue_messages_unacknowledged{queue}` | 卡住的任务 |
| 模型 | `model_call_total{model_id,adapter_key,result}` | 各模型成功率 |
| 模型 | `model_call_duration_seconds{model_id}` | 各模型响应耗时对比 |
| 存储 | `minio_bucket_usage_bytes{bucket}` | 容量增长趋势 |
| 数据库 | `pg_stat_activity_count{state}` | 连接池水位 |
| 业务 | `credit_expect_total{model_id}` | 预估消耗统计（用于 V1.0 定价校对） |

### 14.3 告警项

| 告警 | 条件 | 级别 |
| --- | --- | --- |
| 队列积压 | 任一队列 `messages_ready > 200` 持续 10 分钟 | P1 |
| 任务失败率 | 5 分钟窗口失败率 > 20% | P1 |
| 死信队列非空 | `q.gen.dlq` 消息数 > 0 | P1 |
| 模型熔断触发 | 任一模型进入熔断 | P1 |
| 数据库连接池耗尽 | 使用率 > 85% | P1 |
| 磁盘水位 | MinIO 数据盘 > 80% | P2 |
| 接口 P95 超阈值 | `/generate/task` P95 > 1s | P2 |
| 长时间运行任务 | `running` 状态超过 30 分钟的任务数 > 0 | P2 |

---

## 15 高可用、备份与容灾

### 15.1 单点分析（MVP 阶段的诚实评估）

| 组件 | Compose 形态 | 风险 | 缓解措施 |
| --- | --- | --- | --- |
| PostgreSQL | **单点** | 宕机即全站不可用 | 定期备份 + 快速恢复演练；阶段二迁移到托管 PG 或主从 |
| RabbitMQ | **单点** | 任务无法提交与消费 | 启用持久化（`durable` + `delivery_mode=2`），重启后消息不丢 |
| Redis | 单点 | 缓存失效、限流失效 | **可容忍**：Redis 只做缓存与限流，不承载业务真相，宕机时降级为直查数据库 |
| MinIO | 单点 | 素材与产物不可访问 | 数据卷备份；阶段二上 4 节点纠删码 |
| API / Worker | 无状态 | 单副本故障 | Compose 可起多副本；K8s 由 Deployment 自愈 |

> **关键设计原则**：**Redis 不承载业务真相**。任务状态在 PostgreSQL，消息在 RabbitMQ，文件在 MinIO。Redis 挂掉只影响性能与限流，不影响数据正确性——这是把 Redis 从 Broker 降级为缓存的额外收益。

### 15.2 备份策略

| 对象 | 方式 | 频率 | 保留 |
| --- | --- | --- | --- |
| PostgreSQL | `pg_dump -Fc` 全量 + WAL 归档（如启用） | 每日 03:00 全量 | 30 天 |
| PostgreSQL | 备份文件同步到 `ai-backup` 桶 | 随全量 | 30 天 |
| MinIO 元数据与配置 | `mc mirror` 关键桶到异地 | 每日 | 7 天 |
| 应用配置 | Git 版本管理 + K8s ConfigMap 版本记录 | 变更即提交 | 永久 |
| 密钥 | 独立密钥管理，不入 Git | — | — |

**恢复演练**：每季度执行一次「从备份恢复 PostgreSQL 到空环境」的演练，并记录 RTO。仅备份不演练等于没有备份。

### 15.3 故障处置预案

| 故障 | 影响 | 处置 |
| --- | --- | --- |
| RabbitMQ 不可用 | 无法入队，新任务提交失败 | 接口返回明确错误码；恢复后重投 `pending` 状态任务（兜底脚本按 `pending + create_time` 扫描） |
| PostgreSQL 不可用 | 全站不可用 | 切备库 / 恢复备份；应用层快速失败，返回 503 |
| 第三方模型不可用 | 生成任务失败 | 熔断 + 自动重试；后台一键禁用该模型，前端下拉即时消失 |
| Worker 全部宕机 | 任务积压，状态停留 queued | 拉起 Worker；消息在 RabbitMQ 中持久化，不会丢失 |
| MinIO 不可用 | 产物无法回传，任务失败 | 任务置失败并提示可重试；恢复后用户点击重试 |
| Redis 不可用 | 缓存与限流失效 | 降级直查数据库；限流退化为 Nginx 层 IP 限流 |

### 15.4 定时兜底任务（Celery Beat）

| 任务 | 频率 | 作用 |
| --- | --- | --- |
| `clean_expired_input_asset` | 每小时 | 清理超过 7 天的 `ai-input` 对象（与桶生命周期策略双保险） |
| `rescue_stuck_tasks` | 每 10 分钟 | 扫描 `queued/running` 超过 30 分钟的任务，重新入队或置失败 |
| `reconcile_pending_tasks` | 每 30 分钟 | 扫描 `pending` 超过 5 分钟的任务（入队失败残留），补投队列 |
| `refresh_model_cache` | 每 10 分钟 | 主动刷新模型配置缓存，兜住缓存主动失效的遗漏 |

```python
# app/workers/celery_app.py（续）
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "clean-expired-input-asset": {
        "task": "workers.tasks_housekeeping.clean_expired_input_asset",
        "schedule": crontab(minute=0),                  # 每小时整点
    },
    "rescue-stuck-tasks": {
        "task": "workers.tasks_housekeeping.rescue_stuck_tasks",
        "schedule": crontab(minute="*/10"),
    },
    "reconcile-pending-tasks": {
        "task": "workers.tasks_housekeeping.reconcile_pending_tasks",
        "schedule": crontab(minute="*/30"),
    },
    "refresh-model-cache": {
        "task": "workers.tasks_housekeeping.refresh_model_cache",
        "schedule": crontab(minute="*/10"),
    },
}
```

> **Beat 唯一性是硬约束**：多副本 Beat 会让上述任务重复触发。「清理临时素材」重复执行尚可容忍，但**「补投 pending 任务」重复执行会造成同一任务被多次入队**。因此 Beat 必须保持单实例；若因高可用要求不得不部署多副本，必须给这四个任务各自加 Redis 分布式锁（`SET key value NX EX ttl`），抢到锁的实例才真正执行，这是二次保护而非可选项。

---

## 16 环境变量与配置清单

| 变量 | 示例 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ENV` | `dev` / `prod` | 是 | 环境标识，影响日志与 Trace 属性 |
| `APP_VERSION` | `1.0.0` | 否 | 写入 Trace 资源属性 |
| `DATABASE_URL` | `postgresql+asyncpg://ainew:pwd@postgres:5432/ainew` | 是 | AsyncPG 连接串 |
| `DATABASE_POOL_SIZE` | `10` | 否 | 连接池大小 |
| `DATABASE_MAX_OVERFLOW` | `10` | 否 | 溢出连接 |
| `REDIS_URL` | `redis://redis:6379/0` | 是 | 缓存与限流 |
| `MQ_URL` | `amqp://ainew:pwd@rabbitmq:5672/ainew` | 是 | Celery Broker |
| `MQ_API` | `http://rabbitmq:15672/api` | 否 | 拓扑初始化脚本使用 |
| `MQ_VHOST` | `ainew` | 否 | 虚拟主机 |
| `MINIO_ENDPOINT` | `minio:9000` | 是 | MinIO 地址 |
| `MINIO_PUBLIC_ENDPOINT` | `https://minio.example.com` | 是 | **对外预签名 URL 的域名**（与内网地址不同） |
| `MINIO_ACCESS_KEY` | `ainew-app` | 是 | 应用服务账号（非 root） |
| `MINIO_SECRET_KEY` | `******` | 是 | — |
| `MINIO_BUCKET_INPUT` | `ai-input` | 否 | 默认桶名 |
| `MINIO_BUCKET_OUTPUT` | `ai-output` | 否 | 默认桶名 |
| `JWT_SECRET` | `******` | 是 | ≥ 32 字节 |
| `JWT_EXPIRE_DAYS` | `7` | 否 | Token 有效期 |
| `SMS_PROVIDER_KEY` | `******` | 是 | 短信服务凭证 |
| `SENSITIVE_WORDS_PATH` | `/app/data/sensitive.txt` | 否 | 敏感词库路径 |
| `OTEL_SERVICE_NAME` | `ainew-api` | 否 | 服务名 |
| `OTEL_EXPORTER` | `log` / `otlp` | 否 | 导出方式，切换后端只改此值 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | 否 | 启用 OTLP 时使用 |
| `UPLOAD_IMAGE_MAX_MB` | `10` | 否 | 图片上限 |
| `UPLOAD_VIDEO_MAX_MB` | `200` | 否 | 视频上限 |
| `MODEL_CALL_TIMEOUT_IMAGE` | `120` | 否 | 图片调用超时（秒） |
| `MODEL_CALL_TIMEOUT_VIDEO` | `600` | 否 | 视频调用超时（秒） |
| `TASK_RETRY_DELAYS` | `30,120,600` | 否 | 重试延迟序列（秒） |
| `WANXIANG_API_KEY` | `******` | 按需 | 第三方密钥，被 `config_json` 以环境变量名引用 |

---

## 17 关键架构决策记录（ADR）

### ADR-001 关系型数据库选用 PostgreSQL 16

| 项 | 内容 |
| --- | --- |
| **决策** | 采用 PostgreSQL 16 替代需求文档中的 MySQL 8.0 |
| **背景** | 业务存在大量半结构化参数（模型能力、价格配置、任务输入输出），且需要灵活的查询与约束 |
| **理由** | ① `jsonb` 支持索引与包含查询，模型能力与价格配置可查询、可校验，优于 MySQL 的 JSON；② 部分唯一索引（`WHERE is_deleted = false`）可优雅解决「软删后手机号重新注册」；③ CHECK 约束、`timestamptz`、`gen_random_uuid()` 均为内置能力；④ 后续若需任务表分区、全文检索，PG 能力更强 |
| **代价** | 团队若熟悉 MySQL，需适应少量语法与运维差异（备份、扩展、连接数配置） |
| **影响** | 全量 DDL 重写；ORM 层用 SQLAlchemy 2.0 + asyncpg；迁移工具 Alembic |

### ADR-002 任务队列采用 RabbitMQ（Celery 保留为任务框架）

| 项 | 内容 |
| --- | --- |
| **决策** | Broker 由 Redis 改为 RabbitMQ 3.13，Celery 继续作为任务框架 |
| **背景** | 生成任务需要细粒度路由（图片/视频/对话分队列）、分级延迟重试、优先级插队、死信人工介入 |
| **理由** | ① Redis 作为 Broker 时，延迟队列要靠 `zset` 自研、消息无原生确认语义、无优先级与死信概念；② RabbitMQ 的 Exchange/Queue/Binding 天然匹配多队列路由；③ TTL + DLX 可零插件实现分级延迟重试；④ 未来若需加急任务，`x-max-priority` 可直接启用（MVP 无此业务场景，默认不启用）；⑤ 死信队列让「无法自动恢复」的任务有人工出口 |
| **代价** | 多一个中间件组件需运维；`prefetch` 配置不当会导致任务分配不均（已通过 `prefetch_multiplier=1` 规避） |
| **影响** | Redis 职责收敛为缓存、限流、分布式锁；需新增拓扑初始化脚本 |

### ADR-003 对象存储采用 MinIO；素材上传走后端中转，产物读取走签名 URL

| 项 | 内容 |
| --- | --- |
| **决策** | MinIO 作为对象存储主选；**素材上传统一经 API 服务器中转写入**（不启用客户端直传）；素材与产物的**读取**一律通过签名 GET URL |
| **背景** | 需要在「前端流程简单、服务端校验可控」与「应用服务器带宽占用」之间取舍。已确认选择前者 |
| **理由** | ① S3 兼容，未来可无痛切换到云对象存储；② 私有桶 + 签名 URL 满足素材与产物的访问控制要求；③ 桶生命周期策略可自动清理临时素材；④ 后端中转可在写入前完成魔数校验、体积限制与内容安全处理，违规内容不落存储；⑤ 前端只发一次请求，无「申请—直传—确认」三步状态机与部分失败处理 |
| **代价** | 应用服务器承担上传带宽与临时内存（视频上限 200 MB）；需配套约束 Nginx `client_max_body_size`、Uvicorn 请求体上限与上传接口限流 |
| **影响** | **不提供** `/api/v1/upload/presign` 接口；`MINIO_PUBLIC_ENDPOINT` 仅用于签名 GET URL 的对外域名。若后续上传带宽成为瓶颈，可在不改业务接口的前提下切换为预签名直传 |

### ADR-004 链路追踪采用 OpenTelemetry 埋点，暂不部署可视化后端

| 项 | 内容 |
| --- | --- |
| **决策** | 使用 OTel SDK + 自动埋点，Span 导出到日志；暂不部署 Collector / Jaeger |
| **理由** | ① MVP 阶段优先控制组件数量与运维成本；② OTel 是厂商中立标准，未来接入 Jaeger / Tempo / 商业 APM 时**业务代码零改动**；③ 日志中的 `trace_id` + `span_id` 已满足「按 TraceID 串联排查」的核心诉求 |
| **代价** | 当前没有 Span 瀑布图与调用拓扑，跨服务耗时分析需从日志时间戳人工拼接；排查体验弱于有可视化后端 |
| **影响** | 导出方式通过 `OTEL_EXPORTER` 环境变量切换；日志格式必须携带 `trace_id` 与 `span_id` |

### ADR-005 仅对接第三方模型 API，不做自建 GPU 推理

| 项 | 内容 |
| --- | --- |
| **决策** | 模型层只保留适配器抽象，不设计推理服务层与 GPU 节点 |
| **理由** | 需求阶段能力验证优先，自建推理涉及 GPU 资源、模型部署、显存调度、推理性能优化，成本远超 MVP 收益 |
| **代价** | 生成成本随第三方计价波动；受第三方并发配额限制，扩容上限不由本系统决定 |
| **影响** | 适配器层的抽象边界保持「一次调用换取一个结果」，未引入批处理、队列式推理等只对自建推理有意义的抽象；若未来自建，只需新增一个适配器实现（指向内部推理服务） |

### ADR-006 采用单体分层架构，不拆分微服务

| 项 | 内容 |
| --- | --- |
| **决策** | 单体应用（API + Worker 同代码库、同镜像，不同启动命令） |
| **理由** | ① 业务规模（单日千级任务）远未到微服务收益阈值；② API 与 Worker 复用同一套 service 与 gateway，避免逻辑双写；③ `domain` 层无框架依赖，为将来可能的拆分保留了清晰边界 |
| **代价** | 单一镜像同时承载 API 与 Worker 依赖，镜像体积略大；无法按模块独立扩容 |
| **影响** | 通过容器启动命令区分角色；扩容粒度是「API 副本」与「Worker 副本」 |

### ADR-007 Worker 使用 prefork 池而非 gevent

| 项 | 内容 |
| --- | --- |
| **决策** | Celery Worker 采用默认 prefork 池，任务内通过 `httpx.AsyncClient` + `asyncio.run()` 驱动异步 I/O |
| **理由** | ① gevent 与部分同步 SDK（如 boto3、某些厂商官方 SDK）存在兼容问题，容易产生难以定位的阻塞；② prefork 行为可预测、调试友好；③ 单任务耗时较长（秒到分钟级），进程级并发的吞吐瓶颈主要来自第三方 API 而非本地 |
| **代价** | 单容器吞吐低于 gevent 方案；进程内存开销更大 |
| **影响** | 通过 `--concurrency` 与副本数横向扩容；若后续吞吐不足，再评估 gevent 或调整任务内异步化程度 |

---

## 18 风险与待确认事项

### 18.1 技术风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 第三方模型 API 稳定性不可控 | 任务失败率上升，用户体验受损 | 熔断 + 分级重试 + 后台一键禁用 + 多模型冗余（前端可切换） |
| 第三方并发配额未知 | 扩容无法线性提升吞吐 | 上线前与各厂商确认 QPS/并发上限，写入 `ai_model.config_json` 并作为限流依据 |
| 视频任务耗时长且结果不可预测 | Worker 长期占用，队列积压 | 独立队列 + `prefetch=1` + 独立 Worker 副本 + 按队列长度扩容 |
| 对象存储容量增长快 | 磁盘打满导致服务异常 | 临时素材 7 天生命周期 + 容量监控告警 + 定期归档策略 |
| PostgreSQL 单点 | 宕机全站不可用 | 备份 + 恢复演练；阶段二迁移托管 PG 或主从 |
| Span 随日志写入导致日志量激增 | 日志存储成本上升、检索变慢 | 生产环境对 OTel 采样率做限制（如 10% 采样 + 失败请求全采） |
| 敏感词库准确性 | 误拦正常提示词或漏拦违规内容 | 词库可热更新；命中记录留档便于回溯与补充 |

### 18.2 待确认事项（需业务/运营确认）

| 编号 | 事项 | 影响 |
| --- | --- | --- |
| Q1 | 各第三方模型的**并发配额与计费单价** | 直接决定限流参数与 `price_config_json` 取值 |
| Q2 | 生成产物的**保留期限**与超期处理（自动删除还是仅隐藏） | 影响 MinIO 容量规划与生命周期策略 |
| Q3 | 用户上传素材的保留期是否确认为 7 天 | 影响 `ai-input` 桶生命周期规则 |
| Q4 | 是否需要对生成内容做**人工复核**（发布前审核） | 若需要，将引入审核状态与审核队列，任务状态机需扩展 |
| Q5 | 是否存在**加急/优先级**业务需求（付费插队） | 当前**默认不启用**队列优先级（需求文档无此场景）。若确认需要，加回 `x-max-priority: 9` 并重建队列 |
| Q6 | 管理后台是否需要独立域名与更强鉴权（如 IP 白名单） | 影响 Nginx 与鉴权设计 |
| Q7 | 单日任务量是否有明确的**增长预期**（半年/一年后） | 影响扩容方案与是否提前上 K8s |
| Q8 | 是否需要**多语言**（提示词或界面） | 影响提示词模板是否需要按语言维度设计 |

### 18.3 已明确不做（避免范围蔓延）

- 自建 GPU 推理服务；
- 微服务拆分与 RPC；
- Kafka / 工作流引擎；
- 多租户数据隔离；
- 多地域部署与异地双活。

---

## 附录 A 关键配置速查

| 场景 | 命令 / 配置 |
| --- | --- |
| 启动全部服务 | `docker compose up -d` |
| 查看队列拓扑 | `docker compose exec rabbitmq rabbitmqctl list_queues -p ainew name messages messages_ready messages_unacknowledged` |
| 查看队列参数（TTL/死信配置） | `docker compose exec rabbitmq rabbitmqctl list_queues -p ainew name arguments` |
| 声明/重建队列拓扑 | `python scripts/init_mq_topology.py` |
| 查看死信队列 | `docker compose exec rabbitmq rabbitmqctl list_queues -p ainew name messages` |
| 手工重投死信 | 管理台 `http://<host>:15672` → Queues → `q.gen.dlq` → Get messages → 复制 payload → 重新发布至 `gen.task.exchange` |
| 执行数据库迁移 | `alembic upgrade head` |
| 生成迁移脚本 | `alembic revision --autogenerate -m "描述"` |
| 扩容视频 Worker | `docker compose up -d --scale worker-video=4` |
| 检查 MinIO 桶 | `docker compose exec minio mc ls local/` |
| Worker 任务列表 | `celery -A app.workers.celery_app:celery_app inspect active` |
| 队列积压检查 | `celery -A app.workers.celery_app:celery_app inspect reserved` |

## 附录 B 术语与需求文档的对照

| 本架构文档 | 需求说明书 V0.5.1 | 备注 |
| --- | --- | --- |
| `ai_generate_task.task_id`（uuid） | `task_id`（varchar(64)） | 类型优化，对外接口仍以字符串传递 |
| `ai_generate_task.status` 六态（含 `queued`、`canceled`） | 四态 `pending/running/success/failed` | 需求文档 V0.5.1 已同步为六态；前端 UI 可把 `pending`/`queued` 合并显示为「排队中」 |
| `ai_generate_task.snapshot_config` | 未定义 | 架构新增，落地「配置快照原则」 |
| `ai_generate_task.retry_count` / `error_code` | 未定义 | 架构新增，支撑重试与错误分类 |
| `ai_generate_task.queued_at` / `started_at` / `finished_at` | 未定义 | 架构新增，支撑耗时分析与兜底扫描 |
| `sys_user.is_admin` | 原仅写「简易管理员机制」，未定义字段 | 需求文档 V0.5.1 已同步：复用手机号 + 验证码登录，登录后校验该字段 |
| `POST /api/v1/task/{task_id}/cancel` | 原无取消能力 | 需求文档 V0.5.1 已补充；仅 `pending`/`queued` 允许取消 |
| 素材上传：后端中转（`multipart/form-data`） | `multipart/form-data` | **两文档口径一致**；原预签名直传方案已按决策取消 |
| `/api/v1/callback/model/{provider}` | 未定义 | 架构预留第三方异步回调，MVP 暂以轮询为主 |
| V1.0 预留表（`ai_asset`、订单、会员等） | 原写「预留建表」 | 两文档统一为：**MVP 不建表**，由 V1.0 迁移脚本创建；需求文档 V0.5.1 已同步措辞 |
| `ai_chat_message.related_task_id` | 已有（varchar） | 类型改为 uuid，**刻意不加外键约束**：消息与任务并非强绑定关系 |
| `update_time` 自动维护 | MySQL `ON UPDATE CURRENT_TIMESTAMP` | PostgreSQL 触发器 `trg_set_update_time()`，**必须显式实现**，否则静默产生错误数据 |
| 日志字段名 | `timestamp` / `message` | 两文档统一使用完整字段名，不使用 `ts` / `msg` |
| 上传大小上限 | 图片 JPG/PNG ≤ 10 MB（视频未定义） | 统一为图片 jpg/jpeg/png/webp ≤ 10 MB、视频 mp4/mov ≤ 200 MB |

---

**文档结束**

> 配套可继续产出的材料：
> 1. Alembic 迁移脚本与初始化数据（默认模型、默认提示词模板）;
> 2. 各厂商适配器实现的具体对接说明与鉴权方式对照表；
> 3. Prometheus 指标埋点与 Grafana 看板 JSON；
> 4. CI/CD 流水线（镜像构建、镜像扫描、灰度发布）。
