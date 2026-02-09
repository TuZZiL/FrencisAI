"""Antigravity proxy management commands.

Manages antigravity-claude-proxy — a local proxy that exposes
Antigravity (Google IDE) models via Anthropic-compatible API.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Manage Antigravity proxy (Google IDE models)")
console = Console()

_IS_WIN = sys.platform == "win32"

PROXY_PACKAGE = "antigravity-claude-proxy"
PROXY_CMD = "antigravity-claude-proxy"
DEFAULT_PORT = 8080
ANTIGRAVITY_API_BASE = f"http://localhost:{DEFAULT_PORT}"
HEALTH_URL = f"{ANTIGRAVITY_API_BASE}/health"
PID_FILE = Path.home() / ".nanobot" / "antigravity.pid"


def _check_npm() -> bool:
    """Check if npm is available."""
    return shutil.which("npm") is not None


def _is_proxy_installed() -> bool:
    """Check if antigravity-claude-proxy is installed globally."""
    return shutil.which(PROXY_CMD) is not None


def _is_proxy_running() -> bool:
    """Check if proxy is running by hitting health endpoint."""
    try:
        import httpx
        r = httpx.get(HEALTH_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _read_pid() -> int | None:
    """Read PID from pid file."""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
    return None


def _kill_pid(pid: int) -> bool:
    """Kill process by PID (cross-platform)."""
    try:
        if _IS_WIN:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, check=True)
        else:
            import signal
            import os
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def install_proxy() -> bool:
    """Install antigravity-claude-proxy via npm. Returns True on success."""
    if not _check_npm():
        console.print("[red]Node.js/npm not found.[/red]")
        console.print("Install from: https://nodejs.org/")
        return False

    if _is_proxy_installed():
        console.print(f"[green]\u2713[/green] {PROXY_PACKAGE} already installed")
        return True

    console.print(f"Installing {PROXY_PACKAGE}...")
    try:
        subprocess.run(
            ["npm", "install", "-g", f"{PROXY_PACKAGE}@latest"],
            check=True,
            capture_output=True,
            text=True,
            shell=_IS_WIN,
        )
        console.print(f"[green]\u2713[/green] {PROXY_PACKAGE} installed")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Install failed:[/red] {e.stderr[:300]}")
        return False


def run_auth() -> bool:
    """Run OAuth flow — opens browser for Google login. Returns True on success."""
    if not _is_proxy_installed():
        console.print("[red]Proxy not installed. Run setup first.[/red]")
        return False

    console.print("\nOpening browser for Google OAuth...")
    console.print("[dim]Log in with your Google account that has Antigravity access.[/dim]\n")

    try:
        subprocess.run(
            [PROXY_CMD, "accounts", "add"],
            check=True,
            shell=_IS_WIN,
        )
        console.print(f"[green]\u2713[/green] Account added")
        return True
    except subprocess.CalledProcessError:
        console.print("[red]Authentication failed.[/red]")
        return False
    except FileNotFoundError:
        console.print(f"[red]{PROXY_CMD} not found in PATH.[/red]")
        return False


def start_proxy() -> bool:
    """Start proxy in background. Returns True on success."""
    if _is_proxy_running():
        console.print(f"[green]\u2713[/green] Proxy already running on port {DEFAULT_PORT}")
        return True

    if not _is_proxy_installed():
        console.print("[red]Proxy not installed. Run: nanobot antigravity setup[/red]")
        return False

    console.print("Starting antigravity proxy...")

    try:
        # Start as detached background process
        if _IS_WIN:
            proc = subprocess.Popen(
                [PROXY_CMD, "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                shell=True,
            )
        else:
            proc = subprocess.Popen(
                [PROXY_CMD, "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        # Save PID
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))

        # Wait for proxy to become healthy
        for _ in range(15):
            time.sleep(1)
            if _is_proxy_running():
                console.print(f"[green]\u2713[/green] Proxy running on port {DEFAULT_PORT}")
                return True

        console.print("[yellow]Proxy started but health check not responding yet.[/yellow]")
        console.print(f"[dim]Check manually: curl {HEALTH_URL}[/dim]")
        return True
    except FileNotFoundError:
        console.print(f"[red]{PROXY_CMD} not found in PATH.[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Failed to start proxy: {e}[/red]")
        return False


def stop_proxy() -> bool:
    """Stop the proxy. Returns True on success."""
    pid = _read_pid()
    stopped = False

    if pid:
        stopped = _kill_pid(pid)
        if stopped:
            PID_FILE.unlink(missing_ok=True)

    if not stopped and _is_proxy_running():
        # Fallback: try to find and kill by process name
        try:
            if _IS_WIN:
                # Find PID by port, taskkill doesn't support wildcards
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True,
                )
                for line in result.stdout.splitlines():
                    if f":{DEFAULT_PORT}" in line and "LISTENING" in line:
                        parts = line.split()
                        if parts:
                            fallback_pid = int(parts[-1])
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(fallback_pid)],
                                capture_output=True,
                            )
                            stopped = True
                            break
            else:
                subprocess.run(["pkill", "-f", PROXY_CMD], capture_output=True)
                stopped = True
        except Exception:
            pass

    PID_FILE.unlink(missing_ok=True)

    # Verify proxy actually stopped
    if stopped:
        for _ in range(5):
            if not _is_proxy_running():
                return True
            time.sleep(0.5)
        # Process was killed but port still occupied
        return False

    return stopped


# ============================================================================
# CLI Commands
# ============================================================================


@app.command()
def setup():
    """Install proxy and authenticate with Google."""
    console.print("[bold]Antigravity Setup[/bold]\n")

    # Step 1: Install
    if not install_proxy():
        raise typer.Exit(1)

    # Step 2: Auth
    if not run_auth():
        raise typer.Exit(1)

    console.print("\n[green]\u2713 Antigravity ready![/green]")
    console.print("Start proxy: [cyan]nanobot antigravity start[/cyan]")


@app.command()
def start():
    """Start the Antigravity proxy in background."""
    if not start_proxy():
        raise typer.Exit(1)


@app.command()
def stop():
    """Stop the Antigravity proxy."""
    if stop_proxy():
        console.print("[green]\u2713[/green] Proxy stopped")
    else:
        console.print("[yellow]Proxy was not running[/yellow]")


@app.command()
def status():
    """Show Antigravity proxy status."""
    installed = _is_proxy_installed()
    running = _is_proxy_running()

    console.print("[bold]Antigravity Status[/bold]\n")
    console.print(f"Installed: {'[green]\u2713[/green]' if installed else '[red]\u2717[/red]'}")
    console.print(f"Running:   {'[green]\u2713[/green] port ' + str(DEFAULT_PORT) if running else '[dim]stopped[/dim]'}")

    if running:
        try:
            import httpx
            r = httpx.get(f"http://localhost:{DEFAULT_PORT}/account-limits?format=table", timeout=3)
            if r.status_code == 200:
                console.print(f"\n[dim]{r.text[:500]}[/dim]")
        except Exception:
            pass


@app.command("add-account")
def add_account():
    """Add another Google account to the proxy."""
    if not _is_proxy_installed():
        console.print("[red]Proxy not installed. Run: nanobot antigravity setup[/red]")
        raise typer.Exit(1)
    run_auth()
