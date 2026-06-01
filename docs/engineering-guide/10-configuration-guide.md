# 配置指南

## 配置架构

```
config.yaml (运行参数)           .env (密钥)
     │                                │
     └──────────────┬─────────────────┘
                    ▼
           Settings dataclass
           agent_os/config.py

加载优先级:
  1. config.yaml 中的值
  2. 环境变量（仅密钥）
  3. Settings dataclass 默认值
```

## config.yaml 完整参考

路径：项目根目录 `config.yaml`。

### Model 配置

```yaml
provider: deepseek                    # deepseek | dashscope
model: deepseek-v4-flash              # 模型名称
reasoning_effort: high                # high | max
model_timeout_seconds: 200            # 单次请求超时
enable_explicit_cache: false          # DashScope 显式缓存
```

`provider` 自动推导 base_url 和 API key：
- `deepseek` → `api.deepseek.com` + `DEEPSEEK_API_KEY`
- `dashscope` → `dashscope.aliyuncs.com/compatible-mode/v1` + `OPENAI_API_KEY`

### ReAct 循环

```yaml
max_iterations: 64                    # 最大循环次数
sub_agent_max_iterations: 32          # 子 agent 最大循环
blind_search_guardrail_rounds: 9      # 强制 research_state 前连续搜索次数
domain_router_model: deepseek-v4-flash # 域名路由模型
```

### 上下文与压缩

```yaml
context_token_threshold: 600000       # 触发压缩的 token 阈值
preserve_recent_tokens: 8000          # 压缩保留的最近 token 数
max_context_messages: 8               # 上下文摄入消息数
max_context_items: 12                 # 上下文摄入检索条目数
```

### 工具控制

```yaml
disabled_tools: []                    # 禁用的工具列表
filter_tools: []                      # 需要结果过滤的工具

tool_timeouts:
  bash_default: 60
  law_retrieve: 30
  case_retrieve: 30
  web_search: 20
  web_read: 20

tool_output_limits:
  bash_stdout_max_chars: 100000
  bash_stderr_max_chars: 20000
  result_filter_threshold: 5000
```

### 工作区模板

```yaml
workspace:
  folders:
    - uploads
    - research
    - drafts
    - raw_search
    - logs
  files: {}                           # 额外初始文件
```

### 文档解析（MinerU）

```yaml
mineru_base_url: https://mineru.net/api/v1/agent
mineru_v4_base_url: https://mineru.net/api/v4
mineru_premium_model_version: vlm
mineru_timeout_seconds: 20
mineru_poll_interval_seconds: 3
mineru_poll_timeout_seconds: 180
```

### 调度器

```yaml
scheduler_interval_seconds: 30        # 提醒检查间隔
log_level: WARNING
```

## .env 完整参考

```bash
# === API Keys ===
DEEPSEEK_API_KEY=sk-xxx              # DeepSeek 原生 API
OPENAI_API_KEY=sk-xxx                # DashScope 兼容 API（回退/可选）
TAVILY_API_KEY=tvly-xxx              # 网络搜索
JINA_API_KEY=jina_xxx                # 网页读取
SERPER_API_KEY=...                    # Serper 搜索回退

# === 文档解析 ===
MINERU_API_TOKEN=mineru_xxx          # MinerU v4 Premium

# === 通知 ===
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_SECRET=xxx                    # 飞书签名密钥
```

## 自定义 Provider

通过 `provider` 字段和对应的 `API_KEY` 环境变量可支持任意 OpenAI 兼容 API：

| Provider | base_url | 环境变量 |
|----------|---------|---------|
| DeepSeek 原生 | `api.deepseek.com` | `DEEPSEEK_API_KEY` |
| DashScope 百炼 | `dashscope.aliyuncs.com/compatible-mode/v1` | `OPENAI_API_KEY` |
| 自定义 | 通过 `base_url` 参数 | 通过 `api_key` 参数 |

## 运行时配置覆盖

```python
# AgentOS 构造时覆盖
os = AgentOS(
    data_dir="./my_data",
    model="gpt-4",
    enabled_tools=["web_search", "file_read", "file_write"],
    disabled_tools=["bash"],
)
```

## Proxy 配置

AgentOS 自动保护 API 调用不被 proxy 劫持：

```python
# config.py 自动将 API 域名加入 NO_PROXY
# 不需要手动配置
_no_proxy += "api.deepseek.com,dashscope.aliyuncs.com,cdn-mineru.openxlab.org.cn"
```
