# 调度器与中断

`agent_os/scheduler/interrupt_scheduler.py` — 210 行。

## 架构

```
AgentOS
  ├── start()
  │     └── scheduler.start()
  │           └── asyncio.create_task(_loop())
  │
  ├── _loop() (每 30 秒)
  │     ├── poll SessionManager.list_reminders(status="pending")
  │     ├── parse fire_at → compare with now
  │     ├── if expired:
  │     │     ├── mark_reminder_fired()
  │     │     ├── EventBus.publish(INTERRUPT_FIRED)
  │     │     ├── inject_message(session_id, "<scheduled_message>")
  │     │     └── if feishu configured → send card notification
  │     └── sleep(scheduler_interval_seconds)
  │
  └── stop()
        └── scheduler.stop()
              └── cancel task
```

## 中断类型

```python
class InterruptType(Enum):
    TIME_EVENT = "time_event"        # 定时事件
    EXTERNAL_EVENT = "external"      # 外部触发
    REMINDER = "reminder"            # 用户设定的提醒
    DEADLINE = "deadline"            # 截止日期
    FOLLOW_UP = "follow_up"          # 后续跟进
```

## 提醒创建

### 通过 SessionManager

```python
# 存储为 SQLite 记录
session.create_reminder(
    session_id="abc123",
    reminder_type="reminder",
    title="检查被告提交的证据",
    message="被告证据提交截止日期已到",
    fire_at="2026-06-01T09:00:00+08:00",
    priority=1,
)
```

### 通过 Agent 工具

```python
# Agent 可以在对话中创建提醒
reminder_create(
    title="3 天后复查 A 公司工商信息",
    message="A 公司可能有新的工商变更",
    fire_at="2026-05-30T10:00:00",
    priority=2,
)
```

## 触发流程

```python
async def _check_and_fire(self):
    now = datetime.now(timezone.utc)
    reminders = await self.session_manager.list_reminders(status="pending")
    
    for reminder in reminders:
        fire_at = datetime.fromisoformat(reminder["fire_at"])
        if fire_at <= now:
            # 1. 标记已触发
            await self.session_manager.mark_reminder_fired(reminder["id"])
            
            # 2. EventBus 通知
            await self.event_bus.publish_typed(
                EventType.INTERRUPT_FIRED,
                payload=reminder,
                session_id=reminder["session_id"],
            )
            
            # 3. 注入调度消息到 session
            await self.session_manager.add_message(
                reminder["session_id"],
                role="user",
                content=f"<scheduled_message>\n{reminder['message']}\n</scheduled_message>",
                kind="scheduled",
            )
            
            # 4. 飞书通知
            if self.feishu_webhook:
                await self._send_feishu_notification(reminder)
```

## 飞书通知

### 配置

```bash
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_SECRET=xxx  # 可选签名密钥
```

### 卡片格式

```python
card = {
    "config": {"wide_screen_mode": True},
    "header": {
        "title": {"tag": "plain_text", "content": reminder["title"]},
        "template": priority_color,  # red / orange / blue
    },
    "elements": [
        {"tag": "div", "text": {"tag": "lark_md", "content": reminder["message"]}},
        {"tag": "hr"},
        {"tag": "note", "elements": [
            {"tag": "plain_text", "content": f"会话: {reminder['session_id'][:8]}"},
            {"tag": "plain_text", "content": f"触发时间: {reminder['fire_at']}"},
        ]},
    ],
}
```

### 签名

```python
def _sign(secret, timestamp):
    import hashlib, base64, hmac
    string_to_sign = f"{timestamp}\n{secret}"
    sign = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(sign).decode("utf-8")
```

## 运行时中断

除了定时提醒外，AgentOS 支持运行时中断：

### inject_message

```python
# 在 agent 当前迭代结束后，下一次迭代前注入消息
os.inject_message(session_id, "用户新消息")
```

用途：用户或外部系统在 agent 运行时插入信息。

### request_interrupt

```python
# 在当前迭代完成后通知 agent 暂停
os.request_interrupt(session_id)
```

用途：用户希望 agent 暂停当前工作。

### 与提醒的区别

| | 定时提醒 (reminder_create) | 运行时中断 (inject_message) |
|--|---------------------------|---------------------------|
| 触发 | 计划时间到达 | 立即 |
| 存储 | SQLite 持久化 | 内存 |
| 循环 | Scheduler 轮询 | AgentLoop 检查 |
| 用途 | 未来任务安排 | 即时干预 |
