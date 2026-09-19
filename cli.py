"""Command-line interface for the Agent Worker Team."""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.request import Request, urlopen

from config.settings import GROQ_KEYS, GROQ_MODEL, MAX_DEPTH, MAX_REVIEW_ROUNDS, MAX_TASKS
from core.agent import Agent
from core.message_bus import MessageBus
from core.network import AgentNetwork
from core.orchestrator import Orchestrator
from providers.groq import GroqProvider
from tools.security_headers import SecurityHeaderScanner
from tools.system import ToolRegistry, ToolRequest


AGENT_CONFIGS = (
    ("agent_01", ("research", "analysis", "web")),
    ("agent_02", ("python", "programming", "debugging")),
    ("agent_03", ("security", "testing", "analysis")),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="awt", description="Agent Worker Team tools")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("tui", help="Open the interactive terminal UI.")

    scan_parser = subparsers.add_parser("scan-headers", help="Inspect HTTP security headers.")
    scan_parser.add_argument("url", nargs="?", help="URL to inspect")
    scan_parser.add_argument("--header", action="append", default=[], metavar="NAME=VALUE")
    scan_parser.add_argument("--json", action="store_true", help="Print JSON output")

    run_parser = subparsers.add_parser("run", help="Run a task through the agent network.")
    run_parser.add_argument("task", help="Task description")
    run_parser.add_argument("--timeout", type=float, default=900, help="Maximum run time in seconds")
    return parser


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        name, separator, header_value = value.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Invalid header {value!r}; expected NAME=VALUE")
        headers[name.strip()] = header_value.strip()
    return headers


def fetch_headers(url: str) -> Mapping[str, str]:
    request = Request(url, headers={"User-Agent": "awt-security-scanner/1.0"})
    with urlopen(request, timeout=15) as response:
        return dict(response.headers.items())


def scan_headers_command(args: argparse.Namespace) -> int:
    if args.url and args.header:
        raise ValueError("Use either URL or --header, not both")
    if not args.url and not args.header:
        raise ValueError("Provide a URL or at least one --header NAME=VALUE")

    headers = fetch_headers(args.url) if args.url else parse_headers(args.header)
    findings = [finding.as_dict() for finding in SecurityHeaderScanner().scan(headers)]
    if args.json:
        print(json.dumps(findings, indent=2))
        return 1 if findings else 0
    if not findings:
        print("No security header findings.")
        return 0
    for finding in findings:
        print(f"[{finding['severity'].upper()}] {finding['header']}: {finding['message']}")
        print(f"  Recommendation: {finding['recommendation']}")
    return 1


def build_system() -> tuple[Orchestrator, list[Agent]]:
    if not GROQ_KEYS:
        raise RuntimeError("No GROQ_API_KEY_1..9 values found in the environment.")

    bus = MessageBus()
    network = AgentNetwork()
    orchestrator = Orchestrator(
        bus=bus,
        network=network,
        max_tasks=MAX_TASKS,
        max_depth=MAX_DEPTH,
        max_review_rounds=MAX_REVIEW_ROUNDS,
        tool_registry=ToolRegistry(Path.cwd()),
        approval_handler=approve_tool_request,
    )
    agents: list[Agent] = []
    for index, (agent_id, capabilities) in enumerate(AGENT_CONFIGS):
        if index >= len(GROQ_KEYS):
            break
        agent = Agent(
            agent_id=agent_id,
            provider=GroqProvider(GROQ_KEYS[index], GROQ_MODEL, f"groq_{index + 1}"),
            capabilities=list(capabilities),
            bus=bus,
            network=network,
            orchestrator=orchestrator,
        )
        agents.append(agent)
        network.register(agent)
        bus.register_agent(agent.agent_id)
    if not agents:
        raise RuntimeError("No agents available.")
    return orchestrator, agents


async def run_task(task_description: str, timeout: float) -> int:
    orchestrator, agents = build_system()
    workers = [asyncio.create_task(agent.run()) for agent in agents]
    root = orchestrator.create_root_task(task_description)
    try:
        await orchestrator.start(root)
        await asyncio.wait_for(_wait_for_completion(orchestrator), timeout=timeout)
    finally:
        for agent in agents:
            agent.stop()
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    orchestrator.print_tree()
    if root.result:
        print("\nFINAL RESULT\n" + str(root.result))
    return 0 if root.status.value == "COMPLETED" else 1


async def _wait_for_completion(orchestrator: Orchestrator) -> None:
    while not orchestrator.completed:
        await asyncio.sleep(0.25)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    print("=" * 68)
    print("        A W T   /   A G E N T   W O R K E R   T E A M")
    print("=" * 68)


def run_tui() -> int:
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.styles import Style
    except ImportError:
        return run_legacy_tui()

    commands = {
        "/agents": "Switch agent",
        "/config": "View runtime configuration",
        "/debug": "View task/debug info",
        "/exit": "Exit the app",
        "/help": "Show help",
        "/scan": "Scan HTTP security headers",
        "/tools": "View system tools and permissions",
    }

    class CommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            word = document.get_word_before_cursor(WORD=True)
            if not word.startswith("/"):
                return
            for command, description in commands.items():
                if command.startswith(word):
                    yield Completion(
                        command,
                        start_position=-len(word),
                        display=command,
                        display_meta=description,
                    )

    def bottom_toolbar():
        return HTML(
            f" <b>Workspace</b> {Path.cwd()}  "
            f"<b>Model</b> {GROQ_MODEL}  "
            f"<b>Agents</b> {len(GROQ_KEYS)} ready"
        )

    style = Style.from_dict(
        {
            "prompt": "#61afef bold",
            "bottom-toolbar": "bg:#1f2329 #9da5b4",
            "bottom-toolbar.text": "#9da5b4",
            "completion-menu.completion": "bg:#202020 #c8ccd4",
            "completion-menu.completion.current": "bg:#ffb38a #171717",
            "completion-menu.meta.completion": "#777777",
            "completion-menu.meta.completion.current": "#444444",
        }
    )

    clear_screen()
    print("=" * 72)
    print("                 A W T   /   A G E N T   W O R K E R   T E A M")
    print("=" * 72)
    print("\nAsk anything. AWT plans, delegates, executes, reviews, and reports.")
    print("Type / for commands. Use Up/Down and Tab to select a command.\n")

    session = PromptSession(
        completer=CommandCompleter(),
        complete_while_typing=True,
        complete_in_thread=False,
        bottom_toolbar=bottom_toolbar,
        style=style,
    )

    while True:
        try:
            prompt = session.prompt(
                HTML("<prompt>></prompt> "),
                refresh_interval=0.5,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        try:
            if prompt.startswith("/"):
                if handle_tui_command(prompt) == 0:
                    return 0
            else:
                tui_run_task(prompt)
        except (OSError, TimeoutError, ValueError, RuntimeError) as error:
            print(f"\nError: {error}")


def run_legacy_tui() -> int:
    clear_screen()
    print_banner()
    print(f"\nWorkspace  {Path.cwd()}")
    print(f"Model      {GROQ_MODEL}")
    print(f"Agents     {len(GROQ_KEYS)} provider key(s) configured")
    print("\nAsk anything. AWT will plan, delegate, execute, review, and report.")
    print("Type /help for commands. Ctrl+C or /exit closes the workspace.")

    while True:
        try:
            prompt = read_tui_input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        try:
            if prompt.startswith("/"):
                if handle_tui_command(prompt) == 0:
                    return 0
            else:
                tui_run_task(prompt)
        except (OSError, TimeoutError, ValueError, RuntimeError) as error:
            print(f"\nError: {error}")


def handle_tui_command(command: str) -> int:
    name, _, argument = command.partition(" ")
    name = name.lower()
    argument = argument.strip()
    if name in {"/exit", "/quit"}:
        return 0
    if name == "/help":
        print_tui_help()
    elif name == "/agents":
        tui_show_agents()
    elif name == "/config":
        tui_show_configuration()
    elif name == "/tools":
        tui_show_tools()
    elif name == "/scan":
        tui_scan_headers(argument)
    else:
        print(f"Unknown command: {name}. Type /help for available commands.")
    return 1


def read_tui_input(prompt: str) -> str:
    if os.name != "nt" or not sys.stdin.isatty():
        return input(prompt)

    import msvcrt

    sys.stdout.write(prompt)
    sys.stdout.flush()
    buffer: list[str] = []
    palette_visible = False

    while True:
        key = msvcrt.getwch()
        if key in {"\r", "\n"}:
            if palette_visible:
                redraw_tui_input(prompt, buffer)
            print()
            return "".join(buffer)
        if key == "\x03":
            raise KeyboardInterrupt
        if key == "\x08":
            if buffer:
                buffer.pop()
                palette_visible = False
                redraw_tui_input(prompt, buffer)
                sys.stdout.flush()
            continue
        if key in {"\x00", "\xe0"}:
            msvcrt.getwch()
            continue

        if palette_visible:
            palette_visible = False
            redraw_tui_input(prompt, buffer)
        buffer.append(key)
        sys.stdout.write(key)
        sys.stdout.flush()
        if key == "/" and len(buffer) == 1:
            print_command_palette()
            palette_visible = True


def print_command_palette() -> None:
    sys.stdout.write(
        "  [ /agents | /config | /tools | /scan | /help | /exit ]"
    )
    sys.stdout.flush()


def redraw_tui_input(prompt: str, buffer: list[str]) -> None:
    sys.stdout.write("\r" + (" " * 120) + "\r" + prompt + "".join(buffer))
    sys.stdout.flush()


def print_tui_help() -> None:
    print("""
Project prompts:
  Type a normal sentence to start a multi-agent engineering task.
  Example: Build a Python HTTP security header scanner with tests.

Commands:
  /agents              Show available capabilities
  /config              Show runtime limits and provider status
    /tools               Show available system tools and permissions
  /scan [URL]          Scan HTTP security headers
  /help                Show this help
  /exit                Close AWT
""")


def tui_show_agents() -> None:
    print("\nAvailable agents")
    for index, (agent_id, capabilities) in enumerate(AGENT_CONFIGS):
        available = index < len(GROQ_KEYS)
        status = "ready" if available else "no provider key"
        print(f"  {agent_id:<10} [{status:<16}] {', '.join(capabilities)}")


def tui_show_tools() -> None:
    print("\nSystem tools")
    for tool in ToolRegistry(Path.cwd()).describe():
        approval = "approval required" if tool["requires_approval"] else "read-only"
        print(f"  {tool['name']:<14} [{approval}] {tool['description']}")


def approve_tool_request(request: ToolRequest) -> bool:
    print("\n" + "!" * 68)
    print(f"TOOL APPROVAL REQUIRED: {request.agent_id} requests {request.name}")
    print(json.dumps(request.arguments, indent=2, ensure_ascii=False))
    print("This action may modify files or execute a process in the workspace.")
    answer = input("Approve this action? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def tui_scan_headers(url: str = "") -> None:
    if not url:
        url = input("URL (blank for manual headers): ").strip()
    headers = fetch_headers(url) if url else parse_tui_headers()
    findings = [finding.as_dict() for finding in SecurityHeaderScanner().scan(headers)]
    print()
    if not findings:
        print("No security header findings.")
        return
    for finding in findings:
        print(f"[{finding['severity'].upper()}] {finding['header']}")
        print(f"  {finding['message']}")
        print(f"  Fix: {finding['recommendation']}\n")


def parse_tui_headers() -> dict[str, str]:
    print("Enter NAME=VALUE headers. Submit an empty line when finished.")
    values: list[str] = []
    while True:
        value = input("Header: ").strip()
        if not value:
            return parse_headers(values)
        values.append(value)


def tui_run_task(task: str) -> None:
    print("\nStarting project task. The team will work through the orchestrator.\n")
    exit_code = asyncio.run(run_task(task, 900))
    print(f"\nTask finished with exit code {exit_code}.")


def tui_show_configuration() -> None:
    print("\nRuntime configuration")
    print(f"Model: {GROQ_MODEL}")
    print(f"Configured provider keys: {len(GROQ_KEYS)}")
    print(f"Task limit: {MAX_TASKS}")
    print(f"Depth limit: {MAX_DEPTH}")
    print(f"Review rounds: {MAX_REVIEW_ROUNDS}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command is None or args.command == "tui":
            return run_tui()
        if args.command == "scan-headers":
            return scan_headers_command(args)
        return asyncio.run(run_task(args.task, args.timeout))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())