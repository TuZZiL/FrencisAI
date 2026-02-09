"""Claude Code CLI tool — lets the agent delegate coding tasks to Claude Code."""

import asyncio
import shutil
import sys
from typing import Any

from nanobot.agent.tools.base import Tool

_IS_WIN = sys.platform == "win32"
DEFAULT_TIMEOUT = 300  # 5 minutes


def is_claude_available() -> bool:
    """Check if claude CLI is in PATH."""
    return shutil.which("claude") is not None


class ClaudeCodeTool(Tool):
    """Run Claude Code in non-interactive print mode."""

    def __init__(self, working_dir: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self._working_dir = working_dir
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def description(self) -> str:
        return (
            "Delegate a complex coding task to Claude Code CLI. "
            "Use for: code generation, refactoring, debugging, code review, "
            "searching the codebase, or any task that benefits from deep code understanding. "
            "Claude Code can read/write files and run shell commands in the working directory. "
            "Returns Claude Code's full response."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Detailed task description for Claude Code. "
                        "Be specific: mention file paths, expected behavior, context."
                    ),
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for Claude Code (default: bot workspace)",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, prompt: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self._working_dir

        cmd = [
            "claude",
            "-p",
            prompt,
            "--dangerously-skip-permissions",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Claude Code timed out after {self._timeout} seconds"

            output = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
            errors = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

            if process.returncode != 0 and not output:
                return f"Error (exit {process.returncode}): {errors or 'unknown error'}"

            # Truncate very long output
            max_len = 15000
            if len(output) > max_len:
                output = output[:max_len] + f"\n... (truncated, {len(output) - max_len} more chars)"

            if errors:
                output += f"\n\nSTDERR:\n{errors[:2000]}"

            return output or "(no output)"

        except FileNotFoundError:
            return "Error: claude CLI not found in PATH"
        except Exception as e:
            return f"Error running Claude Code: {e}"
