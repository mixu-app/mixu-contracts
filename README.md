# mixu-contracts

谜序（Mixu）的**契约仓库**：叙事图数据格式、HTTP 接口约定、错误码信封。客户端、
服务端、抽取 worker 都从这里取类型定义，**不允许各自发明字段**。

公开仓库。这里只有结构化契约与示例，没有业务逻辑、没有模型路由、没有价格目录。

## 内容

```text
config/           # 权威基础 URI 配置（schema $id 与 OpenAPI servers）
schemas/graph/    # 叙事图 / 图包格式，schema 版本 1（draft）
schemas/api/      # 错误信封与错误码注册表
api/openapi.yaml  # /v1 草案骨架（proposal，不是已发布契约）
examples/         # 示例载荷，必须能通过 schema 校验
tools/            # 无网络即可运行的校验与同步脚本
```

## 设计要点（与产品文档对应）

- **两个时间轴**：`story_time`（故事世界内）与 `first_reveal`（读者何时能知道）分开。
  见 `mixu-docs`（内部私有仓库）。
- **声称不等于事实**：`attribution.kind` 与 `epistemic_status` 必填，后来才被推翻的信息
  用 `assertion-transition` **追加**，不覆盖历史。
- **身份合并是有揭示边界的**：`identity-link.first_reveal` 之前，投影必须把两个 persona
  当两个实体渲染。
- **定位符不是页码**：`locator` 用 Readium 风格 href + progression；页码会随字号和屏宽变化。
- **摘录受版权约束**：`excerpt_policy` 默认 `LOCATOR_ONLY`；`AUTHORIZED_BY_USER` 也不等于
  可以公开再分发。

## 版本规则

四个版本号互相独立，不得互相替代：

| 版本 | 位置 | 含义 |
|---|---|---|
| graph schema version | `graph-pack-manifest.schema.json` | 数据结构版本，破坏性变更必须升主版本 |
| graph version | 同上 | 某个 edition 的图内容版本（`1.2.0`） |
| API version | `api/openapi.yaml` 的 `/v1` | HTTP 表面版本 |
| client app version | `mixu-client` | 客户端发布版本，与上面三者无关 |

破坏性 schema 变更需要：新主版本、`mixu-docs` 迁移说明、`mixu-fixtures` 更新、消费方评审。

## 校验

```sh
just check         # markdownlint + 全部契约校验
just validate      # 仅契约：schema 合法、$ref 可解析、示例合规、OpenAPI 指针可解析
just sync-uris     # 从 config/ 同步 schema $id 与 OpenAPI servers URL
```

`just validate` 不需要网络，也不下载 schema：它在本仓库内建立 `$id` 注册表。
校验脚本必须能**失败**：把 OpenAPI 的任意 `$ref` 改错一个字符，`just validate` 必须非零退出。

## 依赖

`python3` + `jsonschema` + `pyyaml`（本地已装则直接可用；缺则
`pacman -S python-jsonschema python-yaml` 或用 uv 建 venv）。

## English

Public contract repository for Mixu: narrative graph pack schemas, the draft
`/v1` HTTP surface, and the shared error envelope. Schemas are the single
source of truth for field names, enums and error codes; consumers pin an exact
commit and never redefine a field.

## 许可证

[Apache-2.0](LICENSE)。示例数据仅用于测试，不包含任何受版权保护的书籍文本。
