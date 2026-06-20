"""
MCPClient — bridges the ADK LlmAgent to the local MCP server subprocess.

Instead of importing mcp_server/server.py as a Python module, this class spawns
it as a persistent child process and communicates via JSON-RPC over stdio.
This is the actual MCP protocol boundary: data never leaves the subprocess;
only structured tool call results cross the pipe.

Protocol: one JSON line per request → one JSON line per response.
"""

import json
import os
import subprocess
import sys
import threading
import atexit


_SERVER_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp_server", "server.py",
)


class MCPError(Exception):
    pass


class MCPClient:
    """Manages a single persistent subprocess running mcp_server/server.py.

    The subprocess reads one JSON-RPC request line from stdin and writes one
    JSON response line to stdout, staying alive for the full app lifecycle.

    A threading.Lock serialises concurrent Flask requests through the
    single stdin/stdout pipe, preventing interleaved writes.
    """

    def __init__(self, server_script: str = _SERVER_SCRIPT):
        self._proc = subprocess.Popen(
            [sys.executable, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered so readline() returns immediately
        )
        self._lock = threading.Lock()
        # Register cleanup so the process exits when the app shuts down
        atexit.register(self.close)

    def call(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request to the MCP server and return the result.

        Raises MCPError if the subprocess has died or the server returns a
        top-level protocol error. Inner result errors (e.g. member not found)
        are returned as-is for the LLM to interpret.
        """
        if self._proc.poll() is not None:
            raise MCPError(
                f"MCP server process has exited with code {self._proc.returncode}"
            )

        request_line = json.dumps({"method": method, "params": params}) + "\n"

        with self._lock:
            self._proc.stdin.write(request_line)
            self._proc.stdin.flush()
            response_line = self._proc.stdout.readline()

        if not response_line.strip():
            raise MCPError("MCP server returned an empty response — protocol error")

        response = json.loads(response_line)

        # Top-level "error" means the server itself failed (bad JSON, unhandled
        # exception). This is distinct from a result that contains {"error": ...},
        # which is a valid tool response that the LLM handles gracefully.
        if "error" in response and "result" not in response:
            raise MCPError(f"MCP server error: {response['error']}")

        return response.get("result", {})

    def close(self):
        """Terminate the MCP subprocess cleanly."""
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
