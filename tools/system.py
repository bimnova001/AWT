"""Permission-aware local tools for agent tasks."""

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
from typing import Any, Callable


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]
    agent_id: str
    task_id: str


@dataclass(frozen=True)
class ToolResult:
    tool: str
    approved: bool
    output: str
    error: str | None = None


class ToolRegistry:
    """Execute built-in tools inside a bounded workspace."""

    def __init__(self, workspace: Path | str, allow_full_shell: bool = False):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.allow_full_shell = allow_full_shell

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list_files",
                "description": "List files below a workspace-relative directory.",
                "requires_approval": False,
                "arguments": {"path": "string, default '.'"},
            },
            {
                "name": "read_file",
                "description": "Read a UTF-8 text file inside the workspace.",
                "requires_approval": False,
                "arguments": {"path": "workspace-relative string"},
            },
            {
                "name": "write_file",
                "description": "Create or replace a UTF-8 text file inside the workspace.",
                "requires_approval": True,
                "arguments": {"path": "string", "content": "string"},
            },
            {
                "name": "run_shell",
                "description": (
                    "Run a user-approved CMD/shell command in the workspace. "
                    "Permission mode controls whether approval is required."
                ),
                "requires_approval": True,
                "arguments": {"command": "string", "timeout": "number, default 30"},
            },
        ]

    def execute(self, request: ToolRequest) -> ToolResult:
        allowed = {item["name"] for item in self.describe()}
        if request.name not in allowed:
            return ToolResult(
                request.name,
                False,
                "",
                f"Tool is not available: {request.name}",
            )
        try:
            output = getattr(self, f"_tool_{request.name}")(**request.arguments)
            return ToolResult(request.name, True, output)
        except (OSError, TypeError, ValueError, subprocess.SubprocessError) as error:
            return ToolResult(request.name, True, "", str(error))
        except AttributeError:
            return ToolResult(request.name, True, "", f"Unknown tool: {request.name}")

    def requires_approval(self, name: str) -> bool:
        tool = next((item for item in self.describe() if item["name"] == name), None)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        return bool(tool["requires_approval"])

    def _safe_path(self, value: str) -> Path:
        candidate = (self.workspace / value).resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ValueError("Path escapes the configured workspace")
        return candidate

    def _tool_list_files(self, path: str = ".") -> str:
        directory = self._safe_path(path)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {path}")
        return "\n".join(
            str(item.relative_to(self.workspace))
            for item in sorted(directory.rglob("*"))
            if item.is_file() and ".git" not in item.parts
        )

    def _tool_read_file(self, path: str) -> str:
        file_path = self._safe_path(path)
        if not file_path.is_file():
            raise ValueError(f"File not found: {path}")
        return file_path.read_text(encoding="utf-8")

    def _tool_write_file(self, path: str, content: str) -> str:
        file_path = self._safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {file_path.relative_to(self.workspace)} ({len(content)} bytes)."

    def _tool_run_shell(self, command: str, timeout: float = 30) -> str:
        if self.allow_full_shell:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=min(float(timeout), 120),
                check=False,
                shell=True,
            )
            output = (completed.stdout + completed.stderr).strip()
            return f"exit_code={completed.returncode}\n{output}".strip()

        parts = shlex.split(command, posix=False)
        if not parts or parts[0].lower() not in {"python", "python.exe", "pytest", "git"}:
            raise ValueError("Command is not allowlisted; use python, pytest, or git")
        if parts[0].lower().startswith("git") and parts[1:2] not in [["status"], ["diff"]]:
            raise ValueError("Only git status and git diff are allowed")
        completed = subprocess.run(
            parts,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=min(float(timeout), 120),
            check=False,
        )
        output = (completed.stdout + completed.stderr).strip()
        return f"exit_code={completed.returncode}\n{output}".strip()


ApprovalHandler = Callable[[ToolRequest], bool]