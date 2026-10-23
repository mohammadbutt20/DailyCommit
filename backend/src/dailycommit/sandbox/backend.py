"""Where untrusted code actually runs. See ARCHITECTURE.md §5 before changing any limit here."""

import io
import socket
import tarfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from dailycommit.config import settings

SANDBOX_LABEL = "dailycommit.sandbox"
MAX_STDOUT_BYTES = 1_000_000
STDERR_TAIL_BYTES = 4_000


class SandboxError(Exception):
    """Infrastructure failure (Docker down, image missing). Not the user's fault."""


@dataclass(frozen=True)
class RunRequest:
    image: str
    files: dict[str, str]  # placed in /work
    argv: list[str]  # run after the files are extracted
    memory_mb: int
    startup_s: float  # allowed silence before the first progress line
    idle_s: float  # allowed silence between progress lines
    deadline_s: float  # hard cap on the whole run


@dataclass
class RunOutcome:
    exit_code: int | None = None
    oom_killed: bool = False
    timed_out: bool = False
    output_exceeded: bool = False
    stderr: str = ""


# Called once per stdout line. Returns True if the line is real progress (resets the idle timer).
LineHandler = Callable[[str], bool]


class SandboxBackend(Protocol):
    def run(self, req: RunRequest, on_line: LineHandler) -> RunOutcome: ...


def _tar(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o444
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class DockerSandbox:
    """One throwaway container per run, driven through the Docker socket.

    Files go in over stdin as a tar stream (a tmpfs can't be filled with `docker cp`), so the
    container needs no host mounts at all.
    """

    def __init__(self, runtime: str | None = None) -> None:
        import docker

        self._docker = docker
        self.client = docker.from_env()
        self.runtime = runtime or settings.sandbox_runtime

    def reap_orphans(self) -> int:
        """Remove sandbox containers left behind by a crashed worker."""
        stale = self.client.containers.list(all=True, filters={"label": SANDBOX_LABEL})
        for c in stale:
            c.remove(force=True)
        return len(stale)

    def run(self, req: RunRequest, on_line: LineHandler) -> RunOutcome:
        types = self._docker.types
        try:
            container = self.client.containers.create(
                req.image,
                command=["sh", "-c", 'tar -x -C /work && exec "$@"', "sh", *req.argv],
                user="65534:65534",
                working_dir="/work",
                network_mode="none",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                read_only=True,
                tmpfs={
                    "/work": "rw,exec,nosuid,size=64m,mode=1777",
                    "/tmp": "rw,noexec,nosuid,size=16m,mode=1777",
                },
                mem_limit=f"{req.memory_mb}m",
                memswap_limit=f"{req.memory_mb}m",
                nano_cpus=1_000_000_000,
                pids_limit=64,
                ulimits=[
                    types.Ulimit(name="nofile", soft=64, hard=64),
                    types.Ulimit(name="fsize", soft=16 * 2**20, hard=16 * 2**20),
                ],
                runtime=self.runtime,
                labels={SANDBOX_LABEL: "1"},
                stdin_open=True,
                stdin_once=True,
                environment={},
            )
        except self._docker.errors.ImageNotFound as e:
            raise SandboxError(f"sandbox image {req.image} missing; run make sandbox-images") from e
        except self._docker.errors.DockerException as e:
            raise SandboxError(str(e)) from e

        outcome = RunOutcome()
        try:
            self._feed_stdin_and_start(container, _tar(req.files))
            self._stream(container, req, on_line, outcome)
            result = container.wait(timeout=10)
            container.reload()
            outcome.exit_code = result.get("StatusCode")
            outcome.oom_killed = bool(container.attrs["State"].get("OOMKilled"))
            stderr = container.logs(stdout=False, stderr=True)
            outcome.stderr = stderr[-STDERR_TAIL_BYTES:].decode(errors="replace")
            return outcome
        except self._docker.errors.DockerException as e:
            raise SandboxError(str(e)) from e
        finally:
            try:
                container.remove(force=True)
            except self._docker.errors.DockerException:
                pass  # the reaper gets it on next worker start

    def _feed_stdin_and_start(self, container, payload: bytes) -> None:
        sock = self.client.api.attach_socket(container.id, params={"stdin": 1, "stream": 1})
        raw = getattr(sock, "_sock", sock)
        container.start()
        raw.sendall(payload)
        try:
            raw.shutdown(socket.SHUT_WR)
        finally:
            raw.close()

    def _stream(self, container, req: RunRequest, on_line: LineHandler, outcome: RunOutcome):
        started = time.monotonic()
        state = {"last": started, "allow": req.startup_s}
        lock = threading.Lock()
        finished = threading.Event()

        def kill() -> None:
            try:
                container.kill()
            except self._docker.errors.DockerException:
                pass

        def watchdog() -> None:
            while not finished.wait(0.05):
                now = time.monotonic()
                with lock:
                    idle_over = now - state["last"] > state["allow"]
                if idle_over or now - started > req.deadline_s:
                    outcome.timed_out = True
                    kill()
                    return

        threading.Thread(target=watchdog, daemon=True).start()
        try:
            total = 0
            pending = b""
            for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=False):
                total += len(chunk)
                if total > MAX_STDOUT_BYTES:
                    outcome.output_exceeded = True
                    kill()
                    break
                pending += chunk
                *lines, pending = pending.split(b"\n")
                for line in lines:
                    if on_line(line.decode(errors="replace")):
                        with lock:
                            state["last"] = time.monotonic()
                            state["allow"] = req.idle_s
            if pending and not outcome.output_exceeded:
                on_line(pending.decode(errors="replace"))
        finally:
            finished.set()
