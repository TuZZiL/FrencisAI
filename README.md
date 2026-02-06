<div align="center">
  <h1>FrencisAI</h1>
  <p>Personal AI assistant with semantic memory</p>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

**FrencisAI** is a personal AI assistant based on [nanobot](https://github.com/HKUDS/nanobot), extended with local RAG memory and other improvements.

## Key Features

- **Semantic Memory (RAG)** — past conversations are indexed locally via ChromaDB and retrieved by meaning, not just date. The agent remembers what matters.
- **Multi-channel** — Telegram, Discord, WhatsApp, Feishu
- **Multi-provider** — OpenRouter, Anthropic, OpenAI, DeepSeek, Gemini, Groq, vLLM (local)
- **Tools** — file ops, shell, web search/fetch, memory search, subagents, cron scheduling
- **Skills** — extensible skill system (GitHub, weather, tmux, etc.)
- **Lightweight** — ~3,500 lines of core agent code

## How Memory Works

FrencisAI has a two-tier memory system:

| Layer | Storage | Retrieval |
|-------|---------|-----------|
| **Long-term** (`MEMORY.md`) | Key facts, preferences, decisions | Always included in full |
| **Daily notes** (`YYYY-MM-DD.md`) | Conversations, events, tasks | Today — in full; past — via semantic search (top-5 relevant chunks) |

When you ask a question, the agent automatically searches past notes for relevant context. The agent can also explicitly search memory via the `memory_search` tool.

**ChromaDB is optional.** Without it, behavior is identical to the original nanobot (today's notes + MEMORY.md in full). Install it for RAG:

```bash
pip install chromadb
```

Vector database is stored at `~/.nanobot/data/chroma/` and indexed automatically on first run.

## Install

```bash
git clone https://github.com/TuZZiL/FrencisAI.git
cd FrencisAI
pip install -e .

# Optional: enable semantic memory
pip install chromadb
```

## Quick Start

> [!TIP]
> Set your API key in `~/.nanobot/config.json`.
> Get API keys: [OpenRouter](https://openrouter.ai/keys) (LLM) · [Brave Search](https://brave.com/search/api/) (optional, for web search)

**1. Initialize**

```bash
nanobot onboard
```

**2. Configure** (`~/.nanobot/config.json`)

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA-xxx"
      }
    }
  }
}
```

**3. Chat**

```bash
nanobot agent -m "What is 2+2?"
```

## Local Models (vLLM)

Run with your own local models using vLLM or any OpenAI-compatible server.

**1. Start your vLLM server**

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. Configure** (`~/.nanobot/config.json`)

```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

**3. Chat**

```bash
nanobot agent -m "Hello from my local LLM!"
```

> [!TIP]
> The `apiKey` can be any non-empty string for local servers that don't require authentication.

## Chat Apps

Talk to your assistant through Telegram, Discord, WhatsApp, or Feishu.

| Channel | Setup |
|---------|-------|
| **Telegram** | Easy (just a token) |
| **Discord** | Easy (bot token + intents) |
| **WhatsApp** | Medium (scan QR) |
| **Feishu** | Medium (app credentials) |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

**1. Create a bot**
- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

**2. Configure**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> Get your user ID from `@userinfobot` on Telegram.

**3. Run**

```bash
nanobot gateway
```

</details>

<details>
<summary><b>Discord</b></summary>

**1. Create a bot**
- Go to https://discord.com/developers/applications
- Create an application → Bot → Add Bot
- Copy the bot token

**2. Enable intents**
- In the Bot settings, enable **MESSAGE CONTENT INTENT**

**3. Get your User ID**
- Discord Settings → Advanced → enable **Developer Mode**
- Right-click your avatar → **Copy User ID**

**4. Configure**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

**5. Invite the bot**
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- Open the generated invite URL and add the bot to your server

**6. Run**

```bash
nanobot gateway
```

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires **Node.js ≥18**.

**1. Link device**

```bash
nanobot channels login
# Scan QR with WhatsApp → Settings → Linked Devices
```

**2. Configure**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. Run** (two terminals)

```bash
# Terminal 1
nanobot channels login

# Terminal 2
nanobot gateway
```

</details>

<details>
<summary><b>Feishu</b></summary>

Uses **WebSocket** long connection — no public IP required.

```bash
pip install nanobot-ai[feishu]
```

**1. Create a Feishu bot**
- Visit [Feishu Open Platform](https://open.feishu.cn/app)
- Create a new app → Enable **Bot** capability
- **Permissions**: Add `im:message` (send messages)
- **Events**: Add `im.message.receive_v1` (receive messages)
  - Select **Long Connection** mode
- Get **App ID** and **App Secret** from "Credentials & Basic Info"
- Publish the app

**2. Configure**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": []
    }
  }
}
```

**3. Run**

```bash
nanobot gateway
```

</details>

## Configuration

Config file: `~/.nanobot/config.json`

### Providers

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `openrouter` | LLM (recommended, access to all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM (Claude direct) | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM (GPT direct) | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | LLM (DeepSeek direct) | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM + Voice transcription (Whisper) | [console.groq.com](https://console.groq.com) |
| `gemini` | LLM (Gemini direct) | [aistudio.google.com](https://aistudio.google.com) |

### Security

| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | When `true`, restricts all agent tools to the workspace directory |
| `channels.*.allowFrom` | `[]` (allow all) | Whitelist of user IDs |

## CLI Reference

| Command | Description |
|---------|-------------|
| `nanobot onboard` | Initialize config & workspace |
| `nanobot agent -m "..."` | Chat with the agent |
| `nanobot agent` | Interactive chat mode |
| `nanobot gateway` | Start the gateway |
| `nanobot status` | Show status |
| `nanobot channels login` | Link WhatsApp (scan QR) |
| `nanobot channels status` | Show channel status |

<details>
<summary><b>Scheduled Tasks (Cron)</b></summary>

```bash
# Add a job
nanobot cron add --name "daily" --message "Good morning!" --cron "0 9 * * *"
nanobot cron add --name "hourly" --message "Check status" --every 3600

# List jobs
nanobot cron list

# Remove a job
nanobot cron remove <job_id>
```

</details>

## Docker

```bash
docker build -t frencis .

docker run -v ~/.nanobot:/root/.nanobot --rm frencis onboard
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 frencis gateway
docker run -v ~/.nanobot:/root/.nanobot --rm frencis agent -m "Hello!"
```

## Project Structure

```
nanobot/
├── agent/              # Core agent logic
│   ├── loop.py         #   Agent loop (LLM <-> tool execution)
│   ├── context.py      #   Prompt builder
│   ├── memory.py       #   Persistent memory + RAG integration
│   ├── vectorstore.py  #   ChromaDB vector store wrapper
│   ├── skills.py       #   Skills loader
│   ├── subagent.py     #   Background task execution
│   └── tools/          #   Built-in tools (incl. memory_search)
├── skills/             # Bundled skills (github, weather, tmux...)
├── channels/           # Telegram, Discord, WhatsApp, Feishu
├── bus/                # Message routing
├── cron/               # Scheduled tasks
├── heartbeat/          # Proactive wake-up
├── providers/          # LLM providers
├── session/            # Conversation sessions
├── config/             # Configuration
└── cli/                # Commands
```

## Credits

Based on [nanobot](https://github.com/HKUDS/nanobot) by HKUDS.

<p align="center">
  <sub>FrencisAI is for educational, research, and technical exchange purposes only</sub>
</p>
