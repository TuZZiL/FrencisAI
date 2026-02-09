"""Interactive setup wizard for nanobot configuration.

Guides users through provider selection, model choice, and channel setup
via a friendly terminal UI. Saves results to ~/.nanobot/config.json.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from nanobot import __logo__
from nanobot.config.loader import load_config, save_config, get_config_path
from nanobot.config.schema import Config
from nanobot.utils.helpers import get_workspace_path

console = Console()


# ============================================================================
# Provider definitions
# ============================================================================

PROVIDERS = [
    {
        "key": "openrouter",
        "name": "OpenRouter",
        "desc": "100+ models with one API key",
        "needs_key": True,
        "key_hint": "Get key at: https://openrouter.ai/keys",
        "key_env": "apiKey",
        "models": [
            "anthropic/claude-opus-4-5",
            "anthropic/claude-sonnet-4-5",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-chat",
        ],
    },
    {
        "key": "anthropic",
        "name": "Anthropic",
        "desc": "Claude models direct",
        "needs_key": True,
        "key_hint": "Get key at: https://console.anthropic.com/settings/keys",
        "key_env": "apiKey",
        "models": [
            "anthropic/claude-opus-4-5",
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-haiku-3.5",
        ],
    },
    {
        "key": "openai",
        "name": "OpenAI",
        "desc": "GPT models direct",
        "needs_key": True,
        "key_hint": "Get key at: https://platform.openai.com/api-keys",
        "key_env": "apiKey",
        "models": ["openai/gpt-4o", "openai/gpt-4o-mini"],
    },
    {
        "key": "gemini",
        "name": "Google Gemini",
        "desc": "Gemini models via API key",
        "needs_key": True,
        "key_hint": "Get key at: https://aistudio.google.com/apikey",
        "key_env": "apiKey",
        "models": ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"],
    },
    {
        "key": "deepseek",
        "name": "DeepSeek",
        "desc": "DeepSeek models",
        "needs_key": True,
        "key_hint": "Get key at: https://platform.deepseek.com/api_keys",
        "key_env": "apiKey",
        "models": ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
    },
    {
        "key": "antigravity",
        "name": "Antigravity",
        "desc": "Free with Google account (Gemini 3, Claude)",
        "needs_key": False,
        "models": [
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-opus-4-5-thinking",
            "anthropic/gemini-3-pro-high",
            "anthropic/gemini-3-flash",
        ],
    },
    {
        "key": "groq",
        "name": "Groq",
        "desc": "Ultra-fast inference",
        "needs_key": True,
        "key_hint": "Get key at: https://console.groq.com/keys",
        "key_env": "apiKey",
        "models": ["groq/llama-3.3-70b", "groq/mixtral-8x7b-32768"],
    },
    {
        "key": "vllm",
        "name": "Custom endpoint",
        "desc": "vLLM, Ollama, or any OpenAI-compatible server",
        "needs_key": False,
        "needs_base": True,
        "models": [],
    },
]


# ============================================================================
# Helper functions
# ============================================================================


def _pick(prompt: str, options: list[str], *, allow_empty: bool = False) -> int | None:
    """Show numbered list, return selected index (0-based) or None if skipped."""
    for i, opt in enumerate(options, 1):
        console.print(f"  [cyan][{i}][/cyan] {opt}")

    if allow_empty:
        console.print(f"  [dim][Enter] Skip[/dim]")

    while True:
        raw = Prompt.ask(prompt, default="" if allow_empty else None)
        if allow_empty and raw.strip() == "":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        console.print(f"[red]Enter a number 1-{len(options)}[/red]")


def _pick_multi(prompt: str, options: list[str]) -> list[int]:
    """Show numbered list, return list of selected indices. Empty = none."""
    for i, opt in enumerate(options, 1):
        console.print(f"  [cyan][{i}][/cyan] {opt}")
    console.print(f"  [dim][Enter] Skip[/dim]")

    raw = Prompt.ask(prompt, default="")
    if not raw.strip():
        return []

    selected = []
    for part in raw.replace(",", " ").split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(options):
                selected.append(idx)
        except ValueError:
            pass
    return selected


def _ask(prompt: str, *, default: str = "", password: bool = False, required: bool = False) -> str:
    """Ask for a string value."""
    while True:
        val = Prompt.ask(prompt, default=default, password=password)
        if required and not val.strip():
            console.print("[red]This field is required[/red]")
            continue
        return val.strip()


def _ask_list(prompt: str) -> list[str]:
    """Ask for comma-separated list. Returns empty list if skipped."""
    raw = Prompt.ask(prompt, default="")
    if not raw.strip():
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


# ============================================================================
# Step 1: Provider
# ============================================================================


def step_provider() -> dict:
    """Choose LLM provider. Returns provider dict from PROVIDERS list."""
    console.print("\n[bold]Step 1 — Choose LLM Provider[/bold]\n")

    options = [f"{p['name']:20s} {p['desc']}" for p in PROVIDERS]
    idx = _pick("Your choice", options)
    provider = PROVIDERS[idx]
    console.print(f"\n  Selected: [green]{provider['name']}[/green]\n")
    return provider


# ============================================================================
# Step 2: Configure provider
# ============================================================================


def step_configure_provider(provider: dict, config: Config) -> Config:
    """Configure the selected provider. Returns updated config."""
    console.print(f"[bold]Step 2 — Configure {provider['name']}[/bold]\n")

    key = provider["key"]

    if key == "antigravity":
        return _configure_antigravity(config)
    elif key == "vllm":
        return _configure_vllm(config)
    else:
        return _configure_api_key_provider(provider, config)


def _configure_api_key_provider(provider: dict, config: Config) -> Config:
    """Configure a standard API-key provider."""
    key = provider["key"]
    hint = provider.get("key_hint", "")
    if hint:
        console.print(f"  [dim]{hint}[/dim]\n")

    api_key = _ask("  API Key", password=True, required=True)

    # Optional custom endpoint
    api_base = ""
    if Confirm.ask("  Custom API endpoint?", default=False):
        api_base = _ask("  API Base URL", required=True)

    # Update config
    prov_config = getattr(config.providers, key)
    prov_config.api_key = api_key
    if api_base:
        prov_config.api_base = api_base

    console.print(f"  [green]\u2713[/green] {provider['name']} configured\n")
    return config


def _configure_antigravity(config: Config) -> Config:
    """Install and configure Antigravity proxy."""
    from nanobot.cli.antigravity import (
        install_proxy, run_auth, _is_proxy_running, start_proxy, ANTIGRAVITY_API_BASE,
    )

    # Install proxy
    if not install_proxy():
        console.print("[red]Cannot continue without proxy.[/red]")
        raise typer.Exit(1)

    # Auth
    if not run_auth():
        console.print("[red]Authentication failed.[/red]")
        raise typer.Exit(1)

    # Start proxy
    if not _is_proxy_running():
        start_proxy()

    # Update config — point anthropic provider to local proxy
    config.providers.anthropic.api_key = "antigravity"
    config.providers.anthropic.api_base = ANTIGRAVITY_API_BASE

    console.print(f"  [green]\u2713[/green] Antigravity configured\n")
    return config


def _configure_vllm(config: Config) -> Config:
    """Configure custom/vLLM endpoint."""
    api_base = _ask("  Endpoint URL (e.g. http://localhost:8000/v1)", required=True)
    api_key = _ask("  API Key (if needed, empty for none)", default="dummy")

    config.providers.vllm.api_base = api_base
    config.providers.vllm.api_key = api_key or "dummy"

    console.print(f"  [green]\u2713[/green] Custom endpoint configured\n")
    return config


# ============================================================================
# Step 3: Model
# ============================================================================


def step_model(provider: dict, config: Config) -> Config:
    """Choose default model. Returns updated config."""
    console.print("[bold]Step 3 — Choose Default Model[/bold]\n")

    models = provider["models"]
    if not models:
        # vLLM / custom — ask for model name
        model = _ask("  Model name (e.g. my-model)", required=True)
        config.agents.defaults.model = model
        return config

    idx = _pick("Your choice", models)
    config.agents.defaults.model = models[idx]
    console.print(f"\n  Selected: [green]{models[idx]}[/green]\n")
    return config


# ============================================================================
# Step 4: Channels
# ============================================================================


CHANNELS = ["Telegram", "Discord", "WhatsApp", "Feishu"]


# ============================================================================
# Persona presets
# ============================================================================

PERSONAS = [
    {
        "name": "Professional Assistant",
        "desc": "Formal, precise, business-oriented",
        "soul": """# Soul

I am nanobot, a professional AI assistant.

## Personality

- Formal and precise in communication
- Structured and well-organized responses
- Business-oriented, focused on results

## Communication Style

- Use clear, professional language
- Structure responses with headers and lists when appropriate
- Be concise but thorough
- Avoid slang, emojis, and informal expressions

## Values

- Accuracy and reliability above all
- Respect for the user's time
- Transparency in reasoning
""",
    },
    {
        "name": "Friendly Companion",
        "desc": "Casual, warm, conversational",
        "soul": """# Soul

I am nanobot, a friendly AI companion.

## Personality

- Warm and approachable
- Casual and conversational tone
- Encouraging and supportive

## Communication Style

- Use simple, everyday language
- Be personable and engaging
- Add light humor when appropriate
- Use emojis occasionally to convey warmth

## Values

- Making the user feel comfortable
- Patience and understanding
- Honest but kind feedback
""",
    },
    {
        "name": "Tech Expert",
        "desc": "Technical, concise, developer-focused",
        "soul": """# Soul

I am nanobot, a technical AI assistant.

## Personality

- Direct and to the point
- Technically precise
- Pragmatic problem-solver

## Communication Style

- Use technical terminology when appropriate
- Provide code examples and commands
- Keep explanations brief unless asked for detail
- Focus on actionable solutions

## Values

- Correctness and precision
- Efficiency in communication
- Practical solutions over theoretical ones
""",
    },
    {
        "name": "Creative Writer",
        "desc": "Expressive, imaginative, storytelling",
        "soul": """# Soul

I am nanobot, a creative AI assistant.

## Personality

- Imaginative and expressive
- Enthusiastic about ideas
- Thoughtful and reflective

## Communication Style

- Use vivid and engaging language
- Explore ideas from multiple angles
- Be descriptive and paint pictures with words
- Encourage creative thinking

## Values

- Originality and fresh perspectives
- Open-mindedness to all ideas
- Balance between creativity and usefulness
""",
    },
]


def step_channels(config: Config) -> Config:
    """Configure chat channels. Returns updated config."""
    console.print("[bold]Step 4 — Chat Channels[/bold]\n")
    console.print("  [dim]Select channels to enable (e.g. 1,3 or Enter to skip)[/dim]\n")

    selected = _pick_multi("Channels", CHANNELS)

    if not selected:
        console.print("  [dim]No channels selected, skipping.[/dim]\n")
        return config

    for idx in selected:
        name = CHANNELS[idx]
        console.print(f"\n  [bold]--- {name} ---[/bold]")

        if name == "Telegram":
            config = _configure_telegram(config)
        elif name == "Discord":
            config = _configure_discord(config)
        elif name == "WhatsApp":
            config = _configure_whatsapp(config)
        elif name == "Feishu":
            config = _configure_feishu(config)

    console.print()
    return config


def _configure_telegram(config: Config) -> Config:
    """Configure Telegram channel."""
    console.print("  [dim]Get token from @BotFather in Telegram[/dim]")
    token = _ask("  Bot token", required=True)
    allow = _ask_list("  Allowed user IDs (comma-separated, Enter = all)")
    proxy = _ask("  Proxy URL if Telegram is blocked in your network (Enter = none)")

    config.channels.telegram.enabled = True
    config.channels.telegram.token = token
    config.channels.telegram.allow_from = allow
    if proxy:
        config.channels.telegram.proxy = proxy

    console.print(f"  [green]\u2713[/green] Telegram configured")
    return config


def _configure_discord(config: Config) -> Config:
    """Configure Discord channel."""
    console.print("  [dim]Get token from Discord Developer Portal > Bot[/dim]")
    token = _ask("  Bot token", required=True)
    allow = _ask_list("  Allowed user IDs (comma-separated, Enter = all)")

    config.channels.discord.enabled = True
    config.channels.discord.token = token
    config.channels.discord.allow_from = allow

    console.print(f"  [green]\u2713[/green] Discord configured")
    return config


def _configure_whatsapp(config: Config) -> Config:
    """Configure WhatsApp channel."""
    console.print("  [dim]WhatsApp uses a local bridge. After setup run: nanobot channels login[/dim]")
    bridge_url = _ask("  Bridge URL", default="ws://localhost:3001")
    allow = _ask_list("  Allowed phone numbers (comma-separated, Enter = all)")

    config.channels.whatsapp.enabled = True
    config.channels.whatsapp.bridge_url = bridge_url
    config.channels.whatsapp.allow_from = allow

    console.print(f"  [green]\u2713[/green] WhatsApp configured")
    return config


def _configure_feishu(config: Config) -> Config:
    """Configure Feishu/Lark channel."""
    console.print("  [dim]Get credentials from Feishu Open Platform > App[/dim]")
    app_id = _ask("  App ID", required=True)
    app_secret = _ask("  App Secret", password=True, required=True)
    allow = _ask_list("  Allowed user IDs (comma-separated, Enter = all)")

    config.channels.feishu.enabled = True
    config.channels.feishu.app_id = app_id
    config.channels.feishu.app_secret = app_secret
    config.channels.feishu.allow_from = allow

    console.print(f"  [green]\u2713[/green] Feishu configured")
    return config


# ============================================================================
# Step 5: Persona
# ============================================================================


def step_persona() -> str | None:
    """Choose bot personality. Returns SOUL.md content or None to use default."""
    console.print("[bold]Step 5 — Bot Personality[/bold]\n")
    console.print("  [dim]Choose how your bot communicates (or skip for default)[/dim]\n")

    options = [f"{p['name']:25s} {p['desc']}" for p in PERSONAS]
    options.append("Custom                    Write your own description")

    idx = _pick("Your choice", options, allow_empty=True)

    if idx is None:
        console.print("  [dim]Using default personality.[/dim]\n")
        return None

    # Custom option (last in list)
    if idx == len(PERSONAS):
        console.print("\n  Describe the bot's personality and communication style.")
        console.print("  [dim]Example: Friendly, speaks Ukrainian, uses humor, gives short answers[/dim]\n")
        desc = _ask("  Description", required=True)
        soul = f"""# Soul

I am nanobot, a personal AI assistant.

## Personality & Communication Style

{desc}

## Values

- Accuracy and helpfulness
- Respect for the user
- Consistency in character
"""
        console.print(f"  [green]\u2713[/green] Custom personality set\n")
        return soul

    persona = PERSONAS[idx]
    console.print(f"\n  Selected: [green]{persona['name']}[/green]\n")
    return persona["soul"]


# ============================================================================
# Summary & Save
# ============================================================================


def step_summary(config: Config, provider: dict, persona_name: str = "Default") -> bool:
    """Show summary and ask for confirmation. Returns True if user confirms."""
    table = Table(title="Configuration Summary", show_header=False, border_style="dim")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Provider", provider["name"])
    table.add_row("Model", config.agents.defaults.model)
    table.add_row("Personality", persona_name)

    # Channels
    enabled = []
    if config.channels.telegram.enabled:
        enabled.append("Telegram")
    if config.channels.discord.enabled:
        enabled.append("Discord")
    if config.channels.whatsapp.enabled:
        enabled.append("WhatsApp")
    if config.channels.feishu.enabled:
        enabled.append("Feishu")
    table.add_row("Channels", ", ".join(enabled) if enabled else "[dim]none[/dim]")

    table.add_row("Config path", str(get_config_path()))

    console.print()
    console.print(table)
    console.print()

    return Confirm.ask("Save configuration?", default=True)


# ============================================================================
# Main wizard entry point
# ============================================================================


def run_wizard():
    """Run the full interactive setup wizard."""
    console.print(Panel(
        f"{__logo__}  [bold]nanobot — Interactive Setup[/bold]\n\n"
        "[dim]This wizard will guide you through the initial configuration.\n"
        "You can re-run it anytime with: [cyan]nanobot setup[/cyan][/dim]",
        border_style="blue",
    ))

    # Load existing config (to preserve settings not covered by wizard)
    config_path = get_config_path()
    if config_path.exists():
        config = load_config()
        console.print(f"[dim]Existing config found at {config_path}, will update it.[/dim]")
    else:
        config = Config()

    # Step 1: Provider
    provider = step_provider()

    # Step 2: Configure provider
    config = step_configure_provider(provider, config)

    # Step 3: Model
    config = step_model(provider, config)

    # Step 4: Channels
    config = step_channels(config)

    # Step 5: Persona
    soul_content = step_persona()

    # Determine persona name for summary
    if soul_content is None:
        persona_name = "Default"
    else:
        # Match against presets or mark as custom
        persona_name = "Custom"
        for p in PERSONAS:
            if p["soul"] == soul_content:
                persona_name = p["name"]
                break

    # Summary & save
    if step_summary(config, provider, persona_name):
        # Ensure workspace exists
        workspace = get_workspace_path()

        save_config(config)
        console.print(f"\n[green]\u2713[/green] Config saved to [cyan]{get_config_path()}[/cyan]")
        console.print(f"[green]\u2713[/green] Workspace at [cyan]{workspace}[/cyan]")

        # Create workspace template files if missing
        from nanobot.cli.commands import _create_workspace_templates
        _create_workspace_templates(workspace, soul_content=soul_content)

        # Post-setup hints
        console.print(f"\n{__logo__}  [bold]nanobot is ready![/bold]\n")

        if provider["key"] == "antigravity":
            console.print("Before each session, start the proxy:")
            console.print("  [cyan]nanobot antigravity start[/cyan]\n")

        console.print("Quick start:")
        console.print("  [cyan]nanobot agent -m \"Hello!\"[/cyan]       — single message")
        console.print("  [cyan]nanobot agent[/cyan]                    — interactive chat")
        console.print("  [cyan]nanobot gateway[/cyan]                  — start full server")

        if config.channels.whatsapp.enabled:
            console.print("\nWhatsApp requires device linking:")
            console.print("  [cyan]nanobot channels login[/cyan]")
    else:
        console.print("[yellow]Setup cancelled.[/yellow]")
