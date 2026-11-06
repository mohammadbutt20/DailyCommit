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

# Memory check when a run times out (so a memory bomb that the kernel is slow to OOM-kill shows
# as MLE, not TLE). A sampler thread reads the container's cgroup memory while a test has been
# silent for over a quarter of its budget; the watchdog only looks at the latest sample, so the
# check never delays a kill. One stats call is ~20 ms; each is capped by its own client timeout.
# (Most bombs never get here: the data limit in languages.py makes huge allocations fail fast.)
STATS_TIMEOUT_S = 0.5
STATS_INTERVAL_S = 0.1
STATS_MAX_AGE_S = 0.35  # older samples are ignored: no fresh data means TLE
MEMORY_EXHAUSTED_FRACTION = 0.9


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
    memory_exhausted: bool = False  # timed out while at its memory limit (see memory_exhausted)
    stderr: str = ""


# Called once per stdout line. Returns True if the line is real progress (resets the idle timer).
LineHandler = Callable[[str], bool]


class SandboxBackend(Protocol):
    def run(self, req: RunRequest, on_line: LineHandler) -> RunOutcome: ...


def memory_exhausted(stats: object) -> bool:
    """Whether a Docker stats payload shows the container at its memory limit: working memory
    (usage minus reclaimable inactive page cache) at 90% of the limit or more. Anything
    missing or malformed means no (the caller then reports TLE)."""
    try:
        mem = stats["memory_stats"]  # type: ignore[index]
        usage, limit = int(mem["usage"]), int(mem["limit"])
        extra = mem.get("stats") or {}
        cache = int(extra.get("inactive_file", extra.get("total_inactive_file", 0)))
    except (KeyError, TypeError, ValueError):
        return False
    return limit > 0 and usage - cache >= MEMORY_EXHAUSTED_FRACTION * limit


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
        # Separate low-level client so a slow stats call can't hold up anything else.
        self.stats_api = docker.from_env(timeout=STATS_TIMEOUT_S).api
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
                # docker-py sets StdinOnce itself when stdin_open=True on a non-detached create,
                # so stdin closes after the tar is sent; it rejects an explicit stdin_once kwarg.
                stdin_open=True,
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

        sample: dict[str, object] = {}  # latest memory reading: {"at": monotonic, "full": bool}

        def sampler() -> None:
            while not finished.wait(STATS_INTERVAL_S):
                with lock:
                    silent = time.monotonic() - state["last"] > state["allow"] / 4
                if not silent:
                    continue
                try:
                    stats = self.stats_api.stats(container.id, stream=False, one_shot=True)
                except Exception:  # timeout, container gone, daemon trouble: no reading
                    continue
                sample.update(at=time.monotonic(), full=memory_exhausted(stats))

        def watchdog() -> None:
            while not finished.wait(0.05):
                now = time.monotonic()
                with lock:
                    idle_over = now - state["last"] > state["allow"]
                if idle_over or now - started > req.deadline_s:
                    # Decide from what's already known; never wait for Docker here.
                    at = sample.get("at")
                    fresh = isinstance(at, float) and now - at <= STATS_MAX_AGE_S
                    outcome.memory_exhausted = bool(fresh and sample.get("full"))
                    outcome.timed_out = True
                    kill()
                    return

        threading.Thread(target=watchdog, daemon=True).start()
        threading.Thread(target=sampler, daemon=True).start()
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
