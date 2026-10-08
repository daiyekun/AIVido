# 电商 AI 多媒体创意平台 —— MVP 需求说明书（含详细设计）

| 项目 | 内容 |
| --- | --- |
| 文档名称 | 电商 AI 多媒体创意平台 MVP 需求说明书 |
| 文档版本 | V0.5.1 |
| 编制日期 | 2026-10-08 |
| 文档状态 | 需求评审稿 |
| 后端技术栈 | Python 3.11 + FastAPI + Celery 5.4 + RabbitMQ 3.13 + Redis 7 + PostgreSQL 16 + MinIO |
| 前端架构 | 前后端分离（Vue 3 / React 任选），通过 RESTful API 交互 |
| 核心特性 | 账号体系、图片生成、视频生成、**后台可配置 AI 模型**、**后台可维护系统提示词**、**会话多轮对话（每轮可切换模型）**、**全链路调用追踪**、面向扩展的架构预留 |
| 对标参考 | 《电商 AI 多媒体创意平台产品需求说明书 V1.0》（对标简绘 AI） |

---

## 版本变更记录

| 版本 | 日期 | 变更内容 |
| --- | --- | --- |
| V0.1 | 2026-10-08 | MVP 基础版本：账号体系、图片/视频生成、异步任务、调用链路追踪 |
| V0.2 | 2026-10-08 | 新增后台模型配置管理，前端下拉选择模型，支持替换底层模型而不改代码 |
| V0.3 | 2026-10-08 | 新增会话多轮对话能力，同一会话中每条消息可独立指定模型 |
| V0.4 | 2026-10-08 | 新增后台系统提示词模板维护，业务按类型自动匹配系统提示词 |
| V0.5 | 2026-10-08 | 前端交互简化：仅暴露「生成图片」「生成视频」两大入口，细分任务类型由后端自动推断 |
| V0.5.1 | 2026-10-08 | 与《架构设计文档 V1.0.1》完成一致性对齐（用户确认）：① 技术栈同步为 PostgreSQL + RabbitMQ + MinIO + OpenTelemetry；② 建表 SQL 全量改为 PostgreSQL 并与架构文档逐字一致；③ 任务状态由 4 态扩展为 6 态并明确分级延迟重试；④ 补充任务取消能力；⑤ 移出任务记录删除功能；⑥ 明确管理员账号机制（`sys_user.is_admin`）；⑦ 明确素材上传统一走 `multipart/form-data` 后端中转；⑧ 明确单次生成 1 张/个；⑨ 明确会话内生成任务为显式按钮触发 |

---

## 目录

1. [文档概述](#1-文档概述)
2. [产品总体说明](#2-产品总体说明)
3. [系统整体架构](#3-系统整体架构)
4. [业务核心流程](#4-业务核心流程)
5. [数据库设计](#5-数据库设计)
6. [功能详细需求](#6-功能详细需求)
7. [API 接口总览](#7-api-接口总览)
8. [业务规则](#8-业务规则)
9. [非功能需求](#9-非功能需求)
10. [MVP 范围边界](#10-mvp-范围边界)
11. [测试重点场景](#11-测试重点场景)
12. [交付里程碑](#12-交付里程碑)
13. [附录：模型网关适配器设计](#13-附录模型网关适配器设计)

---

## 1 文档概述

### 1.1 编写目的

本文档为电商 AI 多媒体创意平台 MVP 版本的完整需求与详细设计说明，作为产品、前端、后端、测试团队的统一开发基线。

MVP 需要交付的最小业务闭环：

**用户注册登录 → 选择生成图片 / 生成视频 → 上传素材（可选）→ 选择模型 → 提交任务 → 异步调用第三方 AI 模型 → 结果落对象存储 → 预览下载**，并配套**后台模型配置、后台系统提示词配置、会话多轮对话、全链路调用追踪**四项支撑能力。

### 1.2 MVP 的定位

MVP 不是"做一个小功能"，而是要**一次把底座搭对**：

1. 业务范围做最小，只保留图片与视频两大类生成能力；
2. 底层能力做完整，模型、提示词、追踪、任务体系全部工程化落地；
3. 架构预留充分，后续叠加电商套图、模板市场、会员积分等能力时**不需要重构主流程**。

### 1.3 重要范围声明

> **计费说明**：MVP 只实现"预估积分计算 + 计费日志记录"的**计费骨架**，**不实现支付充值、不做用户余额真实扣减**。数据库字段与日志表预先落地，V1.0 开启真实计费。
>
> **不在 MVP 范围**：模板市场、完整素材资产库、会员体系、积分商城、企业营业执照审核、客服工单、创作者生态等，详见第 10 章。

### 1.4 术语定义

| 术语 | 说明 |
| --- | --- |
| TraceID | 全链路追踪 ID，一次完整请求唯一，贯穿前端 → 网关 → 后端服务 → 队列 → 第三方模型全流程 |
| SpanID | 链路分段 ID，标记后端内部每一个具体调用阶段 |
| TaskID | AI 生成任务唯一业务 ID，每一次生图 / 生视频分配一个 TaskID |
| SessionID | 会话唯一 ID，用于多轮对话场景 |
| model_id | 模型唯一编号，业务层全部使用 model_id，**禁止硬编码模型名称** |
| adapter_key | 模型适配器标识，模型网关据此路由到对应第三方模型实现 |
| gen_type | **前端对外的大类枚举**：`image_gen`（生成图片）/ `video_gen`（生成视频） |
| task_type | **后端内部细分任务枚举**：`txt2img` / `img2img` / `txt2vid` / `vid2vid` / `vid_edit` / `img2vid` / `chat_general` |
| prompt_id | 后台系统提示词模板 ID |
| Credits | 积分，MVP 仅做预估消耗记录，不真实扣费 |
| 模型网关 | Python 实现的模型转发层，屏蔽不同 AI 模型厂商差异，便于后续新增模型 |

---

## 2 产品总体说明

### 2.1 MVP 产品定位

面向电商经营者、电商运营、内容创作者的**最小可用 AI 多媒体创意工作台**：用户以最低学习成本完成 AI 图片与短视频生成，平台侧以最低维护成本完成底层模型替换与提示词策略调整。

### 2.2 MVP 目标用户

| 用户类型 | 说明 |
| --- | --- |
| 电商卖家 / 个体工商户 / 企业 | 主用户群，需要商品图、商品短视频素材 |
| 电商运营 / 内容创作者 | 需要批量创意素材 |

> MVP 阶段不做营业执照人工审核，注册时仅勾选合规协议；数据库中预留企业资质字段，V1.0 实现企业准入审核。

### 2.3 MVP 核心价值

1. **用户侧简单**：前端只区分「生成图片」和「生成视频」，用户不需要理解文生图 / 图生图 / 视频复刻 / 视频编辑的差异，上传素材与否由系统自动判定模式。
2. **运营侧灵活**：AI 模型全部后台可视化配置，新增或替换底层大模型只需新增适配器 + 后台配置一条记录，**前端页面与业务接口无需改动、无需重新发布**。
3. **策略可运营**：系统提示词模板后台维护，按业务类型（必要时精确到具体模型）自动匹配，运营可以独立调整生成效果而不用改代码。
4. **对话式创作**：支持会话多轮对话，同一个会话内每一轮消息都可以切换不同模型，兼顾连贯上下文与灵活试验。
5. **问题可追溯**：全链路 TraceID 追踪，模型调用、任务执行、异常失败均可按 TraceID 完整串联排查。

---

## 3 系统整体架构

### 3.1 架构总图

```
┌──────────────────────────┐
│        Web 前端          │
│   Vue 3 / React          │
└────────────┬─────────────┘
             │ HTTP / HTTPS
             │ Header: X-Trace-Id、Authorization(JWT)
┌────────────▼──────────────────────────────────────────────┐
│                  Python FastAPI 后端                       │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │ 用户服务    │  │ 模型管理服务│  │  链路追踪中间件      │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │ 会话服务    │  │ 任务调度服务│  │  模型网关服务        │  │
│  │            │  │  (Celery)  │  │  (适配器模式)        │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
│  ┌────────────┐  ┌────────────┐                            │
│  │系统提示词服务│  │ 计费骨架服务│                           │
│  └────────────┘  └────────────┘                            │
└──────┬────────────────┬───────────────────────┬────────────┘
       │                │                       │
┌──────▼──────┐  ┌──────▼──────────────┐  ┌─────▼──────────────┐
│  RabbitMQ   │  │ PostgreSQL 数据库    │  │ 对象存储 MinIO      │
│ 任务消息队列 │  │ 用户/模型/任务/会话   │  │ 素材与生成产物       │
└─────────────┘  └─────────────────────┘  └─────┬──────────────┘
                                                 │
                                    ┌────────────▼───────────────┐
                                    │  第三方 AI 模型 API 集群    │
                                    │  图片大模型 / 视频大模型     │
                                    └────────────────────────────┘
```

> 旁路组件（不参与主链路）：**Redis 7**（模型配置缓存 / 限流计数 / 分布式锁）。

### 3.2 核心模块职责

| 模块 | 职责 |
| --- | --- |
| 用户服务 | 注册、登录、JWT 签发与鉴权、用户信息 |
| 模型管理服务 | 后台维护 `ai_model` 配置表（增删改查、启用/禁用）；普通用户只读获取启用模型列表 |
| 系统提示词服务 | 后台维护 `ai_system_prompt` 模板；业务侧按 `task_type + model_id` 自动匹配系统提示词 |
| 会话服务 | 会话与消息管理、多轮上下文组装与截断；每条消息独立记录 model_id |
| 任务调度服务 | 基于 Celery + RabbitMQ 的异步任务队列；任务入队、执行、**分级延迟重试（30 秒 / 2 分钟 / 10 分钟，共 3 次）**、状态回写 |
| 模型网关服务 | **核心**。按 model_id 读取配置 → 匹配 adapter_key → 调用对应适配器 → 屏蔽第三方差异；新增模型只新增适配器类 |
| 计费骨架服务 | 依据模型价格配置计算预估积分，写任务记录与积分日志，**不操作用户余额** |
| 链路追踪中间件 | 请求入口生成/透传 TraceID，内部生成 SpanID，日志统一携带链路标识 |
| 对象存储 | 存储用户上传的临时素材与 AI 生成产物；临时素材设置自动过期清理 |

### 3.3 技术约束（硬性）

1. **后端语言必须为 Python**，Web 框架推荐 FastAPI（异步、自动生成 OpenAPI 文档）；
2. 异步任务：Celery 5.4，**Broker 使用 RabbitMQ 3.13**；结果后端使用 Redis；
3. 数据库：**PostgreSQL 16**（业务数据）；Redis 仅承担缓存、限流与分布式锁，**不承载业务数据、不作消息队列**；
4. 对象存储：**MinIO**（自建），素材上传经后端中转写入，生成资源以**签名 URL** 形式对外读取；
5. 模型网关必须遵循适配器模式，业务代码禁止硬编码任何模型名称、价格与能力参数；
6. 全部数据库表预留扩展字段，兼容 V1.0 的资产库、会员、模板等能力。

---

## 4 业务核心流程

### 4.1 图片 / 视频生成主流程

```
用户登录
   └─→ 进入工作台，切换【生成图片】/【生成视频】
        └─→ 拉取启用模型列表（下拉框，按 sort 排序）
             └─→ 选择 model_id，填写提示词
                  └─→ 可选上传素材（图片 / 视频）
                       └─→ 设置分辨率、时长等参数（受模型能力约束动态过滤）
                            └─→ 前端展示预估消耗积分（后端计算返回）
                                 └─→ 提交：请求头携带 X-Trace-Id
                                      └─→ 后端：JWT 鉴权 → 文件校验 → 敏感词校验
                                           └─→ 后端自动推断内部 task_type
                                                └─→ 按 task_type + model_id 匹配系统提示词
                                                     └─→ 创建 task_id，落库（含 trace_id、system_prompt_id）
                                                          └─→ 任务入 Celery 队列，返回 task_id
                                                               └─→ 前端轮询任务状态
                                                                    └─→ Worker 调用模型网关
                                                                         └─→ 适配器调用第三方模型 API
                                                                              └─→ 产物上传对象存储 → 回写任务状态与产物 URL
                                                                                   └─→ 记录预估积分日志
                                                                                        └─→ 前端预览 / 下载
```

**异常分支**：模型调用失败或超时 → **自动重试 3 次（延迟 30 秒 / 2 分钟 / 10 分钟）；重试期间任务状态保持 `running`，前端界面只显示「生成中」，用户无感知** → 3 次仍失败才置为 `failed` → 记录 `error_code`、`error_msg`、`retry_count` 与 `trace_id` → 页面展示错误原因并提供 TraceID 一键复制。

> 不可重试的终态错误（参数非法、模型已禁用、适配器未实现、内容审核拒绝）**直接置 `failed`，不进入重试**。完整状态机与重试规则见 8.7。

> **配置快照原则**：任务一旦入队，其后台模型配置与系统提示词配置**以提交时刻为准**，后台修改不影响执行中的任务。

### 4.2 前端大类到后端细分任务的推断规则

前端只传 `gen_type`，后端依据"是否上传素材 + 视频子模式"自动推断内部 `task_type`：

**生成图片（gen_type = image_gen）**

| 用户行为 | 推断 task_type | 说明 |
| --- | --- | --- |
| 未上传参考图片 | `txt2img` | 纯文生图 |
| 上传 1 张参考图片 | `img2img` | 图 + 提示词生成图片，重绘强度参数生效 |

**生成视频（gen_type = video_gen）**

| 用户行为 | 推断 task_type | 说明 |
| --- | --- | --- |
| 未上传任何素材 | `txt2vid` | 文生视频 |
| 上传 1 张图片 | `img2vid` | 图片生成动态视频 |
| 上传 1 个视频 + 选择「参考该视频做风格复刻」 | `vid2vid` | 视频生成视频 |
| 上传 1 个视频 + 选择「编辑修改这个视频画面」 | `vid_edit` | 视频修改重绘 |

> 前端仅在"上传视频素材"时才多出一个单选（复刻 / 编辑修改），其余场景用户无需做任何模式选择。

### 4.3 会话多轮对话流程

1. 用户新建会话，生成 `session_id`；**会话本身不绑定任何模型**；
2. 用户每一轮发送消息时，**本轮独立选择 model_id**，可附带图片 / 视频素材；
3. 后端保存 user 消息；按 `chat_general + model_id` 匹配系统提示词；组装上下文；
4. 调用模型网关 `chat_completion`，保存 assistant 回复消息；
5. 每条消息独立记录 `model_id`、`trace_id`、`system_prompt_id`、`expect_credit`；
6. 若该轮消息目标是生成图片 / 视频，则内部复用生成任务流程，消息记录 `related_task_id`；
7. 前端渲染完整对话历史，下一轮可切换任意其他 model_id。

**上下文控制**：后端读取历史消息后按 `context_window_size` 做截断，防止 token 无限膨胀；前端展示完整历史，传给模型的是截断后的上下文。系统提示词只置于上下文头部，不在每轮重复追加。

### 4.4 全链路追踪约束

1. HTTP 请求头约定 `X-Trace-Id`：**前端 MVP 只需发送该头**，未传入则由后端入口自动生成；后端入口**优先识别 W3C 标准头 `traceparent`**（若前端后续接入 OTel Web SDK 则改发它，后端无需改动）；
2. `trace_id` 统一为 **32 位十六进制字符串**；响应体每次携带 `trace_id`，并回写响应头 `X-Trace-Id`；
3. 后端每个内部阶段生成 SpanID（OpenTelemetry Span）；
4. 任务表 `ai_generate_task` 与消息表 `ai_chat_message` 均持久化 `trace_id`；
5. 日志强制输出字段：`timestamp | trace_id | span_id | task_id | user_id | model_id | adapter_key | system_prompt_id | duration_ms | level | message`；
6. 用户侧任务列表与失败提示支持 TraceID 一键复制，便于问题反馈；
7. **采用 OpenTelemetry SDK 标准埋点，MVP 不部署 Collector / Jaeger**，Span 导出到结构化日志（`OTEL_EXPORTER=log`）；后续需要可视化链路时只改环境变量即可接入，业务代码零改动。

---

## 5 数据库设计

### 5.1 数据表总览

| 表名 | 用途 | MVP 是否使用 |
| --- | --- | --- |
| `sys_user` | 用户账号 | 使用 |
| `ai_model` | AI 模型配置（后台维护） | 使用 |
| `ai_system_prompt` | 系统提示词模板（后台维护） | 使用 |
| `ai_generate_task` | AI 生成任务主表 | 使用 |
| `ai_chat_session` | 会话主表 | 使用 |
| `ai_chat_message` | 会话消息表 | 使用 |
| `ai_credit_log` | 积分操作日志（仅记录预估） | 使用（只写不扣） |
| `ai_asset` 等资产 / 订单 / 会员表 | V1.0 能力 | **预留设计，MVP 不建表**，由 V1.0 迁移脚本创建（MVP 只建上表 7 张） |

### 5.2 建表 SQL（PostgreSQL 16）

> **说明**：以下 DDL 与《架构设计文档 V1.0.1》第 6.1.2 节**逐字一致**，修改时必须同步两处。脚本可直接在 PostgreSQL 16 上执行（已完成真实实例验证）。

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

**DDL 要点（与 MySQL 版的关键差异）**

| 项 | 说明 |
| --- | --- |
| 主键 | 业务实体用 `bigint GENERATED BY DEFAULT AS IDENTITY`；任务 / 会话 / 消息用 `uuid` + `gen_random_uuid()` |
| 时间类型 | 统一 `timestamptz`，库与应用统一 UTC，前端本地化展示 |
| 半结构化数据 | `jsonb` 替代 MySQL 的 `json`，支持 GIN 索引与包含查询 |
| 软删除 | `sys_user` / `ai_chat_session` 用 `is_deleted` 布尔字段 + **部分唯一索引**，允许手机号注销后重新注册 |
| `update_time` | PostgreSQL **没有** `ON UPDATE CURRENT_TIMESTAMP`，必须用触发器 `trg_set_update_time()` 实现；漏掉不会报错，只会静默产生错误数据 |
| 枚举 | 关键枚举用 `CHECK` 约束固化；扩展 `task_type` 需显式修改约束（对应 9.3 节的「枚举预留扩展值」） |
| 管理员 | `sys_user.is_admin` 标识管理员，复用手机号 + 验证码登录 |
| 消息角色 | `ai_chat_message.role` 的 CHECK 约束允许 `user` / `assistant` / `system` 三值；`system` 仅用于**组装模型上下文时标记系统提示词位置**，不落库为消息记录（系统提示词正文由 `ai_system_prompt` 管理，消息表只记 `system_prompt_id`） |

### 5.3 系统提示词匹配优先级（后端逻辑）

当一个 `task_type` 存在多条启用模板时，按以下顺序匹配：

| 优先级 | 匹配条件 | 结果 |
| --- | --- | --- |
| 1 | `task_type` 完全匹配 + `bind_model_id = 当前 model_id` + `is_enable = 1` | 使用该模板 |
| 2 | `task_type` 完全匹配 + `bind_model_id IS NULL` + `is_enable = 1` | 使用全局通用模板 |
| 3 | 无任何匹配 | **不追加系统提示词，仅用用户提示词执行（兜底，不阻断业务）** |

**示例**

- `task_type=txt2img, model_id=2`：存在绑定 model_id=2 的模板 → 优先使用该条；
- 不存在绑定 model_id=2 的模板 → 使用 `txt2img` 的全局模板；
- `txt2img` 下无任何启用模板 → 直接用用户提示词，不附加 system 内容。

---

## 6 功能详细需求

### 6.1 用户账号模块

#### 6.1.1 用户注册

1. 支持手机号 + 短信验证码注册；
2. **必须勾选**三项协议：用户协议、隐私政策、生成式 AI 使用声明；
3. 同一手机号禁止重复注册；
4. 注册成功创建账号记录；数据库预留企业名称、营业执照号字段（MVP 页面不展示）。

#### 6.1.2 用户登录

1. 手机号 + 验证码登录；
2. 登录成功下发 JWT Token，后续请求通过 `Authorization: Bearer {token}` 携带；
3. 处理 Token 过期（前端跳转登录 / 后端返回 401）；
4. 提供退出登录接口。

> MVP 暂不实现邮箱登录、密码登录，接口预留字段，后续迭代增加。

#### 6.1.3 个人信息

仅展示账号手机号。会员等级、用户类型（个人 / 企业）字段预留，页面暂不展示。

### 6.2 模型配置管理（管理员后台）

> 仅管理员访问；普通用户只能通过只读接口获取**已启用**模型列表。

#### 6.2.1 模型列表页

展示字段：`model_id`、模型名称、模型类型（image / video）、adapter_key、是否启用、排序、支持分辨率、支持时长、备注、更新时间。
操作：新增、编辑、启用 / 禁用、查看详情。

#### 6.2.2 新增 / 编辑模型

| 表单字段 | 必填 | 说明 |
| --- | --- | --- |
| 对外展示名称 `model_name` | 是 | 前端下拉显示的名称 |
| 模型类型 `model_type` | 是 | 图片 / 视频 单选 |
| 适配器标识 `adapter_key` | 是 | 必须与后端代码中的适配器注册 key 一致 |
| 是否启用 `is_enable` | 是 | 启用后普通用户下拉可见 |
| 排序 `sort` | 否 | 数字越小越靠前 |
| 支持分辨率 `support_resolution` | 是 | 多选，如 1K / 2K / 4K |
| 支持时长 `support_duration` | 视频必填 | 多选，如 4 / 6 / 8 秒；图片模型隐藏该输入 |
| 适配器配置 `config_json` | 是 | JSON 编辑，含 API 地址、超时等；**密钥仅存环境变量 key，禁止明文入库** |
| 计价配置 `price_config_json` | 是 | JSON，不同规格档位对应预估积分 |
| 内部备注 `remark` | 否 | 运维备注 |

#### 6.2.3 启用 / 禁用规则

- 禁用后：普通用户模型列表接口立即不再返回该模型，新任务无法选择；
- 历史任务记录仍保留 `model_id`，用于链路追溯；
- 编辑与禁用均**即时生效**，不需要重启服务，**但已入队任务沿用提交时刻的配置快照**。

> **能力价值**：替换底层模型只需三步 —— ① 开发对应适配器类；② 后台新增一条模型配置；③ 启用。前端自动出现新模型，业务代码零改动。

### 6.3 系统提示词管理（管理员后台）

#### 6.3.1 提示词模板列表

展示：`prompt_id`、模板名称、task_type、绑定模型（模型名 / 全局通用）、提示词内容预览、是否启用、优先级 sort、备注、更新时间。
操作：新增、编辑、启用 / 禁用、查看详情。

#### 6.3.2 新增 / 编辑模板

| 字段 | 说明 |
| --- | --- |
| 模板名称 `prompt_name` | 后台识别名称，例如「电商-文生图-商品白底图」 |
| 业务 task_type | 下拉选择细分类型（含 `chat_general`） |
| 绑定模型 `bind_model_id` | 可选具体模型；或选择「不绑定（全局通用）」，即 NULL |
| 系统提示词内容 `system_content` | 大文本，填写 system 角色提示词 |
| 是否启用 `is_enable` | 开关，禁用后不参与匹配 |
| 排序优先级 `sort` | 数字越大优先级越高 |
| 内部备注 `remark` | 运维备注 |

#### 6.3.3 组合逻辑

```
最终提示词 = 【后台匹配到的系统提示词】 + "\n" + 【用户输入的提示词】
```

**生成任务场景**：前端**不传递、也无法篡改**系统提示词；后端按 `task_type + model_id` 匹配后拼接，并把 `system_prompt_id` 落库。

**会话对话场景**：系统提示词作为 system 角色置于上下文头部，历史消息依次拼接；`ai_chat_message.system_prompt_id` 记录模板 ID。

> 兜底原则：未匹配到任何启用模板时，业务照常执行，仅使用用户提示词，不阻断任务。普通用户不可读取系统提示词原文。

### 6.4 AI 生成工作台（普通用户前端）

> 前端**只有两个 Tab**：【生成图片】、【生成视频】。用户视角不出现 `txt2img`、`img2img`、`vid2vid` 等任何细分术语。
>
> **单次生成数量**：MVP 固定生成 **1 张图片 / 1 个视频**；接口保留 `n` 字段（默认 1，MVP 只接受 1），为 V1.0 批量生成预留。
> **上传方式**：素材一律通过 `multipart/form-data` 提交到后端，由后端流式写入对象存储，**不启用客户端直传**。

#### 6.4.1 「生成图片」Tab

| 页面元素 | 说明 |
| --- | --- |
| 模型下拉 | 动态拉取 `model_type=image` 且启用的模型，按 sort 排序；悬浮提示展示支持分辨率与参考单价 |
| 正向提示词 | 文本输入，上限 2000 字符 |
| 反向提示词 | 可选 |
| 素材上传 | **可选，0~1 张参考图片**（JPG / JPEG / PNG / WebP，单张 ≤ 10MB，经后端中转上传） |
| 重绘强度 | `denoising_strength`，**仅上传图片后展示**，未上传时隐藏 |
| 分辨率 | 下拉，选项随选中模型动态过滤 |
| 预估积分 | 后端计算返回展示 |
| 生成按钮 | 提交任务 |

**行为判定**：不上传图片 → 后端 `txt2img`；上传图片 → 后端 `img2img`。
**校验**：图片 Tab 禁止上传视频文件，后端做文件类型二次校验并拦截。

#### 6.4.2 「生成视频」Tab

| 页面元素 | 说明 |
| --- | --- |
| 模型下拉 | 动态拉取 `model_type=video` 且启用的模型 |
| 正向 / 反向提示词 | 文本输入 |
| 素材上传 | **可选，0~1 个素材（图片或视频）**；视频限 MP4 / MOV，单个 ≤ 200MB，经后端中转上传 |
| 视频子模式单选 | **仅上传视频文件后出现**：○ 参考该视频做风格复刻 ○ 编辑修改这个视频画面 |
| 参数 | 分辨率、画面比例、视频时长；选项随选中模型动态过滤 |
| 预估积分 | 后端计算返回展示 |
| 生成按钮 | 提交任务 |

**行为判定**：无素材 → `txt2vid`；上传图片 → `img2vid`；上传视频 + 复刻 → `vid2vid`；上传视频 + 编辑 → `vid_edit`。

> 视频生成耗时较长，前端展示「排队中」/「生成中」状态提示，轮询任务状态接口。

#### 6.4.3 统一对外生成接口

前端提交 `gen_type`（`image_gen` / `video_gen`），**不传递内部 task_type**，由后端推断。

### 6.5 会话多轮对话模块

#### 6.5.1 会话侧边栏

- 新建会话（创建空会话，**不绑定模型**）；
- 会话列表（标题 + 更新时间）；
- 修改会话标题；
- 逻辑删除会话。

#### 6.5.2 对话主窗口

1. 选中会话后加载并渲染全部历史消息，每条 AI 消息回显该轮使用的模型名称；
2. **每一轮发送消息前有独立的模型下拉选择器**，允许同一会话内第 1 轮用模型 A、第 2 轮切模型 B、第 3 轮切回模型 A；
3. 输入文本，支持附带图片 / 视频素材；
4. **生成任务的触发方式（显式触发，MVP 约定）**：会话输入框旁提供「生成图片」「生成视频」两个按钮，用户点击后进入生成参数面板（选模型、填参数、传素材），提交后**完全复用** `ai_generate_task` 与同一套队列；该轮消息的 `related_task_id` 记录对应 `task_id`，AI 回复展示 `task_id` 并提供「查看任务」跳转。**MVP 不做基于模型意图的自动识别**（该能力列入 V1.0，届时数据表与接口无需改动）；
5. 失败消息展示错误原因，TraceID 可复制。

#### 6.5.3 核心规则

| 规则 | 说明 |
| --- | --- |
| 模型归属 | `model_id` 属于**消息**，不属于会话 |
| 模型校验 | 每轮发送时后端校验 model_id 存在且 `is_enable=1`；禁用模型不可用于对话 |
| 上下文 | 后端按 `context_window_size` 截断后传给模型；前端展示完整历史 |
| 任务复用 | 会话内生成图片 / 视频完全复用 `ai_generate_task` 与 Celery 队列 |
| 权限隔离 | 用户只能访问自己的会话与消息，禁止越权 |

### 6.6 任务管理模块

**普通用户「我的生成任务」列表**

| 列表字段 | 说明 |
| --- | --- |
| task_id | 任务唯一 ID |
| 任务名称 | 友好中文展示：「图片生成」/「视频生成」 |
| 使用模型 | 按 model_id 关联回显模型名称 |
| 状态 | 排队中 / 生成中 / 已完成 / 已失败 / 已取消（后端返回 6 个状态码；UI 将 `pending` 与 `queued` 合并显示为「排队中」） |
| 预估积分 | 该任务预估消耗 |
| 创建时间 | — |
| 操作 | 预览、下载、复制 TraceID、**取消任务**（仅 `pending` / `queued` 状态可取消） |

> **MVP 不提供任务记录删除能力**：用户侧无法删除任务记录，列表仅支持分页浏览。原规划的逻辑删除功能在两份文档的任务表设计中都未落地字段，已确认移出 MVP 范围（V1.0 再评估）。

**管理员后台任务详情**：额外可见真实细分 `task_type`、`system_prompt_id`、`model_id`、`adapter_key`、`trace_id`，用于运维排查。

### 6.7 管理员权限说明

MVP 采用简易管理员机制：**`sys_user.is_admin = true` 标识管理员**，管理员**复用手机号 + 验证码登录体系**（不新建独立管理员表、不做独立登录入口），登录后由后端 `require_admin` 依赖校验；**仅需保证普通用户无法访问 `/api/v1/admin/**` 接口**（非管理员访问返回 403）。管理员账号由运维在数据库中直接标记。完整的 RBAC 角色权限体系列入 V1.0。

> **管理后台交付形态**：后端提供完整管理 API；前端交付**一个最小可用管理页面**（模型列表/编辑/启停、提示词列表/编辑/启停），不做完整后台工程。

---

## 7 API 接口总览

### 7.1 公共约定

**请求头**

```
Authorization: Bearer {jwt_token}
X-Trace-Id: {32 位十六进制全局追踪ID}
Content-Type: application/json      （上传素材时使用 multipart/form-data）
```

**统一响应结构**

```json
{
  "code": 0,
  "msg": "success",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "data": {}
}
```

`code = 0` 表示成功，非 0 为业务错误码；**每次响应体均携带 trace_id（32 位十六进制）**，并回写响应头 `X-Trace-Id`。后端同时**优先识别** W3C 标准头 `traceparent`，前端 MVP 只需发送 `X-Trace-Id`。

### 7.2 用户模块

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/user/register` | POST | 注册：手机号 + 验证码 + 协议勾选 |
| `/api/v1/user/login` | POST | 登录：返回 JWT Token |
| `/api/v1/user/logout` | POST | 退出登录 |

### 7.3 普通用户 - 模型查询

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/model/image/list` | GET | 获取启用的图片模型列表 |
| `/api/v1/model/video/list` | GET | 获取启用的视频模型列表 |

响应示例：

```json
{
  "code": 0,
  "msg": "success",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "data": [
    {
      "model_id": 1,
      "model_name": "智能图片 G2 臻享版",
      "sort": 1,
      "support_resolution": ["1K", "2K", "4K"],
      "price_tip": "1K:1积分，2K:1.5积分"
    }
  ]
}
```

### 7.4 普通用户 - 统一生成任务接口

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/generate/task` | POST | 统一图片 / 视频生成提交接口（`multipart/form-data` 上传素材，**素材经后端中转写入对象存储，不启用客户端直传**） |

请求体（JSON 部分）：

```json
{
  "gen_type": "image_gen",
  "model_id": 1,
  "prompt": "高清电商商品白底摄影图，白色背景",
  "negative_prompt": "水印,模糊,畸形",
  "resolution": "2K",
  "aspect_ratio": "16:9",
  "duration": 4,
  "n": 1,
  "denoising_strength": 0.7,
  "video_sub_mode": "copy_style",
  "extra": {}
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `gen_type` | 是 | `image_gen` / `video_gen`，前端只传大类 |
| `model_id` | 是 | 选中的模型 ID |
| `prompt` | 是 | 用户提示词（不包含系统提示词） |
| `negative_prompt` | 否 | 反向提示词 |
| `resolution` | 是 | 分辨率档位，需在该模型支持范围内 |
| `aspect_ratio` | 视频必填 | 画面比例，如 16:9 |
| `duration` | 视频必填 | 时长（秒），需在该模型支持范围内 |
| `denoising_strength` | 否 | 仅 `img2img` 生效，其他情况后端忽略 |
| `video_sub_mode` | 条件 | 仅 `video_gen` 且上传视频时有效：`copy_style` 复刻 / `edit` 编辑修改 |
| `n` | 否 | 生成数量，**MVP 固定为 1**（后端只接受 1，其他值返回参数错误）；V1.0 支持批量生成 |
| `extra` | 否 | 扩展 JSON，为后续参数预留 |

响应示例：

```json
{
  "code": 0,
  "msg": "success",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "data": {
    "task_id": "9b2d4e6f-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
    "status": "pending",
    "expect_credit": 1.0
  }
}
```

### 7.5 任务查询

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/task/list` | GET | 分页获取当前用户任务列表（`page` 默认 1、`size` 默认 20、上限 100） |
| `/api/v1/task/{task_id}` | GET | 获取单条任务详情（含 `trace_id`、`retry_count`、`error_code`） |
| `/api/v1/task/{task_id}/cancel` | POST | **取消任务**（仅 `pending` / `queued` 状态可取消，取消后置 `canceled`） |

### 7.6 会话与消息

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/chat/session/create` | POST | 新建会话，返回 session_id |
| `/api/v1/chat/session/list` | GET | 获取当前用户会话列表 |
| `/api/v1/chat/session/{session_id}` | GET | 会话详情 |
| `/api/v1/chat/session/{session_id}` | PUT | 修改会话标题 |
| `/api/v1/chat/session/{session_id}` | DELETE | 逻辑删除会话 |
| `/api/v1/chat/message/list` | GET | 获取会话消息历史（query: session_id） |
| `/api/v1/chat/message/send` | POST | **发送一轮消息（核心接口，每轮携带 model_id）** |

`POST /api/v1/chat/message/send` 请求示例：

```json
{
  "session_id": "uuid-session-001",
  "model_id": 2,
  "content_text": "帮我生成一张电商商品白底图",
  "asset_urls": [],
  "extra": {}
}
```

响应示例：

```json
{
  "code": 0,
  "msg": "success",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "data": {
    "user_msg_id": "msg-uuid-01",
    "assistant_msg_id": "msg-uuid-02",
    "related_task_id": "task-uuid-xxx",
    "expect_credit": 1.0
  }
}
```

### 7.7 管理员后台接口

> 需管理员鉴权，普通用户禁止访问。

**模型管理**

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/admin/model/list` | GET | 全部模型列表（含禁用） |
| `/api/v1/admin/model/create` | POST | 新增模型配置 |
| `/api/v1/admin/model/{model_id}` | PUT | 编辑模型配置 |
| `/api/v1/admin/model/{model_id}/status` | PUT | 启用 / 禁用 |
| `/api/v1/admin/model/{model_id}` | GET | 模型详情 |

**系统提示词管理**

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/admin/system-prompt/list` | GET | 全部提示词模板（含禁用） |
| `/api/v1/admin/system-prompt/create` | POST | 新增模板 |
| `/api/v1/admin/system-prompt/{prompt_id}` | PUT | 编辑模板 |
| `/api/v1/admin/system-prompt/{prompt_id}/status` | PUT | 启用 / 禁用 |
| `/api/v1/admin/system-prompt/{prompt_id}` | GET | 模板详情 |

---

## 8 业务规则

### 8.1 计费骨架规则

1. 依据 `model_id` + 分辨率 / 时长，读取 `price_config_json` 计算**预估积分**；
2. 预估积分写入 `ai_generate_task.expect_credit`（或消息表 `expect_credit`），同时写 `ai_credit_log`；
3. **不修改 `sys_user.credit_balance`，不实现支付充值**；
4. V1.0 再开启余额校验与真实扣费。

### 8.2 素材与存储规则

1. 用户上传素材为**临时素材**，设置自动过期清理（建议 7 天）；
2. **素材上传一律经后端中转**（`multipart/form-data` → 后端流式写入对象存储），**不启用客户端直传**；接收过程中累计字节超限立即中断并回收已写入对象；
3. AI 生成产物跟随任务记录持久化；MVP 不实现完整素材资产库；
4. 所有资源以**签名 URL** 对外提供（读取侧），防止未授权访问；
5. 上传文件需校验后缀、MIME 类型与大小上限（图片 ≤ 10MB、视频 ≤ 200MB），**拦截可执行文件**。

### 8.3 参数校验规则

1. 前端下拉仅为 UI 辅助过滤，**后端必须二次校验**：模型存在且启用、分辨率 / 时长在模型能力范围内、文件类型与大小合法；
2. 非法参数直接返回业务错误，不进入队列、不调用第三方模型。

### 8.4 合规规则

1. 用户提示词执行基础敏感词拦截，命中则**直接拒绝提交（返回业务错误），不创建任务、不入队、不调用第三方模型**；
2. 用户操作、任务记录、链路日志持久化留存，用于审计追溯；
3. 注册必须勾选用户协议、隐私政策与生成式 AI 使用声明。

### 8.5 权限与隔离规则

1. 全部业务接口登录鉴权，管理员接口额外校验管理员身份；
2. 用户只能访问自己的任务、会话与消息，禁止越权访问；
3. 传给模型的上下文只取自该用户该会话的历史消息。

### 8.6 配置快照规则

后台修改模型配置、系统提示词配置后：

- **已入队 / 执行中的任务**：沿用提交时刻的配置，不受影响；
- **新提交的任务**：使用最新配置。

### 8.7 任务状态与重试规则

**状态定义（6 态，与后端返回一致）**

| 状态码 | 含义 | 是否终态 | 前端展示 |
| --- | --- | --- | --- |
| `pending` | 已创建，尚未入队 | 否 | 排队中 |
| `queued` | 已成功投递到消息队列 | 否 | 排队中 |
| `running` | Worker 正在执行（**含自动重试期间**） | 否 | 生成中 |
| `success` | 生成成功，产物已写入对象存储 | 是 | 已完成 |
| `failed` | 重试耗尽或遇到终态错误 | 是 | 已失败 |
| `canceled` | 用户主动取消 | 是 | 已取消 |

**重试规则**

1. **可重试错误**（连接超时、第三方 5xx、限流 429、对象存储短暂不可用）：延迟重投，延迟序列 **30 秒 / 2 分钟 / 10 分钟**，最多 3 次；
2. 重试期间状态**保持 `running`**，前端界面**不展示重试次数**，用户只会看到「生成中」；
3. 超过 3 次仍失败：任务置 `failed` 并进入死信队列，等待人工排查；
4. **终态错误**（参数非法、模型已禁用、适配器未实现、内容审核拒绝）：**直接 `failed`，不重试**；
5. 最坏情况下（3 次重试全部失败），从提交到最终失败约需 **12.5 分钟**（含模型调用耗时）；
6. 重试计数记录在 `ai_generate_task.retry_count`，失败原因记录在 `error_code` 与 `error_msg`。

---

## 9 非功能需求

### 9.1 性能需求

1. 图片任务通过异步队列削峰，分钟级完成；
2. 视频任务属长耗时任务，允许分钟级处理，前端轮询状态；
3. MVP 支撑**单日千级生成任务**，满足业务验证目标。

### 9.2 安全需求

1. JWT 鉴权覆盖全部业务接口，管理员接口二次校验；
2. 用户级数据隔离；
3. 第三方 API 密钥**禁止明文存数据库**，`config_json` 只保存环境变量 key；
4. 文件上传类型与大小校验；对象存储签名 URL 访问。

### 9.3 可扩展性需求（架构硬性要求）

1. **模型全部后台配置化**，业务代码禁止硬编码模型名称、价格、能力参数；
2. 模型网关采用适配器模式，新增模型只新增适配器类；
3. 所有请求体预留 `extra: {}` 扩展字段，新增参数不破坏旧接口；
4. `task_type` 的扩展路径已明确：新增类型需**同步扩展三处** —— 数据库 `CHECK` 约束（见 5.2 DDL 要点）、适配器方法、消息队列绑定；后续商品套图、抠图、换装等任务按此路径接入；
5. 数据库预留 V1.0 全部业务字段与表结构；
6. 链路日志中记录 `model_id`、`adapter_key`、`system_prompt_id`，便于定位具体模型与提示词问题。

### 9.4 兼容性

| 项 | 要求 |
| --- | --- |
| 浏览器 | 优先兼容 Chrome、Edge 桌面端；MVP 不重点适配移动端 |
| 输入格式 | 图片 JPG / JPEG / PNG / WebP（单张 ≤ 10MB）；视频 MP4 / MOV（单个 ≤ 200MB） |
| 输出格式 | 图片 JPG / PNG / WebP；视频 MP4 |

---

## 10 MVP 范围边界

### ✅ MVP 需要实现

1. 用户手机号注册、登录、JWT 鉴权，协议勾选；
2. 管理员账号标识（`sys_user.is_admin`）与后台鉴权；管理员后台模型配置管理（CRUD、启用 / 禁用、能力与计价配置）；
3. 前端仅「生成图片」「生成视频」两大入口，后端自动推断细分任务类型；
4. 图片生成：文生图、图 + 提示词生成图片；
5. 视频生成：文生视频、视频生成视频、视频修改生成、图片生成视频；
6. 后台系统提示词模板维护，业务自动匹配并记录 `system_prompt_id`；
7. 会话多轮对话：同一会话内每轮消息独立切换模型，消息可触发生成任务；
8. Celery + RabbitMQ 异步任务队列、6 态任务状态管理、分级延迟重试（3 次）、任务取消（仅排队中）、结果预览与下载；
9. TraceID 全链路追踪，日志埋点，页面可复制 TraceID；
10. 对象存储处理素材与产物，临时素材自动过期；
11. 计费骨架：预估积分计算与日志记录，不实现真实支付扣费；
12. 数据库完整表结构，预留 V1.0 扩展字段。

### ❌ MVP 不实现（预留字段，V1.0 迭代）

1. 电商专用工具：商品套图、A+ 内容、详情长图、抠图、AI 换装；
2. 无限画布模板市场、模板解锁、一键同款；
3. 完整素材资产库与存储空间管理；
4. 微信 / 支付宝充值、卡密兑换、积分商城；
5. 会员体系、OPC 服务商版本；
6. 客服工单系统、AI 课程、创作者生态；
7. 企业营业执照人工准入审核；
8. 管理后台完整 RBAC 权限体系；
9. 会话流式输出、会话导出与分享；
10. 系统提示词变量渲染、版本管理与回滚、A/B 测试；
11. 多素材同时上传（MVP 单次最多 1 份参考素材）；
12. **任务记录删除**（用户侧删除任务记录，MVP 不提供）；
13. **客户端预签名直传上传**（MVP 一律走后端中转，视上传带宽情况在 V1.0 评估）；
14. **会话内基于模型意图自动识别并触发生成**（MVP 用显式按钮触发）；
15. 批量生成（单次固定 1 张 / 1 个，接口预留 `n` 字段）。

---

## 11 测试重点场景

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| T01 | 后台新增模型并启用 | 前端下拉立即出现该模型 |
| T02 | 后台禁用某模型 | 前端下拉不再出现；历史任务仍可关联该 model_id 追溯 |
| T03 | 选择模型后查看分辨率 / 时长选项 | 下拉仅展示该模型支持档位 |
| T04 | 绕过前端提交模型不支持的分辨率 / 时长 | 后端校验拦截，返回参数错误，不进入队列 |
| T05 | 「生成图片」不上传素材提交 | 后端 `task_type=txt2img`，命中 txt2img 系统提示词 |
| T06 | 「生成图片」上传参考图提交 | 后端 `task_type=img2img`，`denoising_strength` 生效，命中 img2img 系统提示词 |
| T07 | 「生成图片」上传视频文件 | 后端拦截，返回文件类型错误 |
| T08 | 「生成视频」上传视频并选择「复刻」 | 后端 `task_type=vid2vid` |
| T09 | 「生成视频」上传视频并选择「编辑修改」 | 后端 `task_type=vid_edit` |
| T10 | 某 task_type 全部模板被禁用后提交任务 | 任务正常执行，不附加系统提示词，不阻断 |
| T11 | 后台修改配置后，观察已排队任务与新任务 | 老任务沿用旧配置；新任务使用新配置 |
| T12 | 同一会话第 1 轮用模型 A，第 2 轮用模型 B | 消息表两条记录 `model_id` 不同，上下文完整携带 |
| T13 | 会话中对已禁用模型发送消息 | 后端返回参数错误，不调用模型 |
| T14 | 会话消息触发生成图片 | `ai_chat_message.related_task_id` 正确关联，任务列表可见该任务 |
| T15 | 删除会话 | 会话逻辑删除成功，底层生成任务记录保留（审计用途） |
| T16 | 链路追踪校验 | 请求、任务表、消息表、日志均可用 trace_id 串联 |
| T17 | 模型调用失败 / 超时（可重试错误） | 自动重试 3 次（30s / 2m / 10m），期间状态为 `running`、前端显示「生成中」；3 次仍失败才置 `failed`，记录 `error_code`、`error_msg`、`retry_count` 与 trace_id，页面可复制 TraceID |
| T18 | 提示词命中敏感词 | 直接拦截，不调用第三方模型 |
| T19 | 越权访问 | 用户 A 无法访问用户 B 的任务、会话与消息 |
| T20 | 替换模型验证 | 仅后台新增配置 + 适配器，**不改前端业务代码**即可切换底层生成模型 |
| T21 | 不可重试的终态错误（模型被禁用、参数非法、审核拒绝） | 直接置 `failed`，不进入重试 |
| T22 | 取消排队中的任务 | 状态置 `canceled`，Worker 不再执行；对已 `running` 的任务发起取消被拒绝 |
| T23 | 非管理员访问 `/api/v1/admin/**` | 返回 403，不返回任何后台数据 |
| T24 | 上传 200MB 视频 / 上传超过 200MB 的文件 | 前者正常受理，后者在接收过程中被中断并返回参数错误 |
| T25 | 校验 6 状态与前端展示映射 | 后端返回 6 个状态码；前端把 `pending` / `queued` 都显示为「排队中」 |
| T26 | 会话内点击「生成图片」按钮提交 | 生成任务正常创建，该轮消息 `related_task_id` 正确关联 |

---

## 12 交付里程碑

| 阶段 | 周期 | 交付内容 |
| --- | --- | --- |
| 阶段一：项目底座与账号体系 | 2 周 | FastAPI 工程脚手架；PostgreSQL 建表与 `update_time` 触发器；RabbitMQ 拓扑与 Celery 接线；链路追踪中间件与日志规范；用户注册登录与管理员标识；模型网关适配器基础框架；模型管理后台 CRUD；系统提示词管理 CRUD |
| 阶段二：图片生成链路 | 2 周 | 图片模型适配器对接；统一生成接口；前端「生成图片」页与动态模型下拉组件；异步任务队列；任务管理与预览下载 |
| 阶段三：视频生成链路 | 3 周 | 四类视频生成能力；视频模型配置；前端「生成视频」页；任务轮询与状态展示 |
| 阶段四：会话多轮对话 | 1 周 | 会话与消息服务；每轮独立模型选择；会话内触发生成任务；上下文截断控制 |
| 阶段五：联调与测试 | 1 周 | 端到端联调；第 11 章重点场景验证；链路追踪验证；异常与合规拦截验证 |

**合计预估：9 周**完成 MVP 交付，形成可持续承接 V1.0 迭代的工程底座。

---

## 13 附录：模型网关适配器设计

### 13.1 设计思想

1. 采用**适配器模式**隔离各第三方模型厂商 API 差异；
2. 上层业务只传递 `model_id`，网关读取数据库配置获取 `adapter_key`；
3. 适配器注册表维护 `adapter_key → 适配器实现类` 映射；
4. 新增第三方模型：只新增适配器实现类 + 后台配置一条记录，**业务接口与前端页面零改动**。

### 13.2 适配器参考实现（Python 伪代码）

```python
from abc import ABC, abstractmethod


class BaseModelAdapter(ABC):
    """模型适配器抽象基类"""

    def __init__(self, config: dict):
        self.config = config

    # ---------- 图片生成能力 ----------
    @abstractmethod
    def txt2img(self, params: dict, trace_id: str) -> dict:
        """文生图"""

    @abstractmethod
    def img2img(self, params: dict, trace_id: str) -> dict:
        """图 + 提示词生成图片"""

    # ---------- 视频生成能力 ----------
    @abstractmethod
    def txt2vid(self, params: dict, trace_id: str) -> dict:
        """文生视频"""

    @abstractmethod
    def img2vid(self, params: dict, trace_id: str) -> dict:
        """图片生成视频"""

    @abstractmethod
    def vid2vid(self, params: dict, trace_id: str) -> dict:
        """视频生成视频"""

    @abstractmethod
    def vid_edit(self, params: dict, trace_id: str) -> dict:
        """视频修改重绘"""

    # ---------- 对话能力 ----------
    @abstractmethod
    def chat_completion(self, messages: list, params: dict, trace_id: str) -> dict:
        """
        :param messages: 组装后的上下文消息列表 [{"role": "user", "content": "...", "assets": [...]}]
        :param params:   请求参数，含 system_prompt、system_prompt_id
        :param trace_id: 链路追踪 ID
        :return: {"content_text": ..., "asset_urls": [...], "task_id": ...}
        """


class WanXiangAdapter(BaseModelAdapter):
    """示例：某图片模型厂商适配器"""

    def txt2img(self, params: dict, trace_id: str) -> dict:
        # 1. 从 self.config 读取 API 地址、超时等
        # 2. 读取环境变量获取密钥（禁止明文落库）
        # 3. 组装厂商私有参数并请求
        # 4. 打印日志：trace_id / model_id / adapter_key / system_prompt_id
        ...


class MiniMaxVideoAdapter(BaseModelAdapter):
    """示例：某视频模型厂商适配器"""

    def txt2vid(self, params: dict, trace_id: str) -> dict:
        ...


# 适配器注册表：key 与 ai_model.adapter_key 一一对应
ADAPTER_REGISTRY = {
    "wanxiang3.0": WanXiangAdapter,
    "minimax_video": MiniMaxVideoAdapter,
}


class ModelGatewayService:
    """模型网关：业务层唯一入口，业务只传 model_id"""

    def get_adapter(self, model_id: int) -> BaseModelAdapter:
        model_conf = db.query_ai_model(model_id)

        if not model_conf or not model_conf.is_enable:
            raise BusinessError("模型不存在或已禁用")

        adapter_cls = ADAPTER_REGISTRY.get(model_conf.adapter_key)
        if not adapter_cls:
            raise BusinessError(f"适配器未实现：{model_conf.adapter_key}")

        return adapter_cls(config=model_conf.config_json)

    def dispatch(self, model_id: int, task_type: str, params: dict, trace_id: str) -> dict:
        """按 task_type 分发到适配器对应能力方法（内部自带 model_id 与 task_type 双重校验）"""
        adapter = self.get_adapter(model_id)
        method = getattr(adapter, task_type, None)
        if not callable(method):
            raise BusinessError(f"模型不支持该能力：{task_type}")
        return method(params=params, trace_id=trace_id)
```

### 13.3 模型调用链路日志字段约定

```
timestamp | trace_id | span_id | task_id | user_id | model_id | adapter_key | system_prompt_id | duration_ms | level | message
```

关键埋点阶段：

1. 请求接收与参数校验；
2. 系统提示词匹配结果；
3. 任务入队；
4. 模型网关发起第三方调用（记录 adapter_key）；
5. 第三方模型返回（记录耗时与状态码）；
6. 产物写入对象存储；
7. 任务状态回写成功 / 失败。

---

**文档结束**

> 后续可继续输出的配套材料：
> 1. OpenAPI（YAML）完整接口文档；
> 2. 前端页面交互原型说明；
> 3. 部署架构与环境变量清单（含密钥管理方案）。
