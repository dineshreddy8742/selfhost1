# Dailsmart AI

**语音 AI 平台** — 使用可视化拖拽工作流构建器，构建生产级语音智能体。从零到运行机器人仅需不到 2 分钟。

## 🚀 快速开始

##### 在本地机器上设置 Dailsmart AI

确保你已安装 Docker 和 Docker Compose。然后启动服务：

```bash
docker compose up -d
```

运行后，在浏览器中打开 [http://localhost:3010](http://localhost:3010)。

### 🎙️ 你的第一个语音机器人

1. 在浏览器中打开 [http://localhost:3010](http://localhost:3010)。
2. 选择 **Inbound** 或 **Outbound**，为你的机器人命名并描述使用场景。
3. 点击 **Web Call** 即可直接与机器人通话。

> 🔑 **无需 API 密钥。** Dailsmart AI 可以使用自带的 LLM / TTS / STT 栈运行，你也可以随时连接自己的 LLM、TTS、STT 或电话服务密钥（例如 Twilio、Vonage、Telnyx）。

## 功能特性

### 语音能力
- **电话集成**：支持 Twilio、Vonage、Vobiz、Cloudonix 等电话服务，支持呼叫转移。
- **低延迟**：针对实时处理和低延迟对话流进行了优化。
- **自定义提供商**：轻松更换 STT、LLM 或 TTS 模型。

### 开发者体验
- **零配置**：自动生成本地密钥以便快速原型设计。
- **Docker 优先**：容器化环境保证本地开发与测试的一致性。
- **高可定制性**：基于 FastAPI 的 Python 后端，支持深度自定义对话状态。
