"""Reproducibility metadata.

Every real-data number in this repository is a function of the OpenCV SIFT
implementation, and of the seed, and of the exact inputs. A result that does
not record those is not reproducible, only asserted. This module captures them.

``dirty`` is recorded rather than hidden. A result produced from a working
tree with uncommitted changes is still a result; what would be wrong is
reporting it as though the commit identified it.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = ["Provenance", "capture_provenance", "file_digest", "git_state"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def file_digest(path: str | Path, *, algorithm: str = "sha256",
                chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file, streamed so that multi-gigabyte products are fine."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _run_git(*args: str, cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ("git", *args), cwd=str(cwd), capture_output=True, text=True,
            timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_state(repo_root: Path | None = None) -> dict[str, Any]:
    """Commit, branch and dirtiness, or an explicit unavailability record."""
    root = repo_root or _REPO_ROOT
    commit = _run_git("rev-parse", "HEAD", cwd=root)
    if commit is None:
        return {
            "available": False,
            "reason": "git metadata unavailable (not a repository, or git absent)",
        }
    status = _run_git("status", "--porcelain", cwd=root)
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    tracked_dirty = [
        line for line in (status or "").splitlines() if not line.startswith("??")
    ]
    return {
        "available": True,
        "commit": commit,
        "branch": branch,
        "dirty": bool(tracked_dirty),
        "dirty_paths": [line[3:] for line in tracked_dirty[:20]],
        "untracked_present": any(
            line.startswith("??") for line in (status or "").splitlines()
        ),
    }


def _library_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for name, attr in (
        ("numpy", "__version__"),
        ("scipy", "__version__"),
        ("cv2", "__version__"),
        ("torch", "__version__"),
        ("kornia", "__version__"),
    ):
        try:
            module = __import__(name)
        except Exception:  # noqa: BLE001 - absence is the answer we want
            versions[name] = None
        else:
            versions[name] = str(getattr(module, attr, "unknown"))
    return versions


@dataclass(frozen=True)
class Provenance:
    """Everything needed to say where a number came from."""

    captured_utc: str
    git: Mapping[str, Any]
    libraries: Mapping[str, str | None]
    platform_str: str
    executable: str
    seed: int | None = None
    #: Path to digest, for inputs whose bytes matter.
    input_digests: Mapping[str, str] = field(default_factory=dict)
    #: Inputs that were named but could not be digested, and why.
    input_problems: Mapping[str, str] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def reproducible(self) -> bool:
        """Whether this record identifies its code state unambiguously."""
        return bool(self.git.get("available")) and not self.git.get("dirty", True)

    def caveats(self) -> tuple[str, ...]:
        """Reasons a re-run might not reproduce this exactly."""
        out: list[str] = []
        if not self.git.get("available"):
            out.append("code state unknown: git metadata unavailable")
        elif self.git.get("dirty"):
            out.append(
                "working tree had uncommitted tracked changes; the commit does "
                "not identify the code that produced this"
            )
        if self.libraries.get("cv2") is None:
            out.append("OpenCV absent: classical engines cannot have run")
        if self.libraries.get("kornia") is None:
            out.append(
                "kornia absent: DISK and LightGlue results cannot be reproduced "
                "on this machine"
            )
        if self.seed is None:
            out.append("no seed recorded; a stochastic stage may not repeat")
        if self.input_problems:
            out.append(
                f"{len(self.input_problems)} input(s) could not be digested"
            )
        return tuple(out)

    def as_dict(self) -> dict[str, Any]:
        return {
            "captured_utc": self.captured_utc,
            "git": dict(self.git),
            "libraries": dict(self.libraries),
            "platform": self.platform_str,
            "executable": self.executable,
            "seed": self.seed,
            "input_digests": dict(self.input_digests),
            "input_problems": dict(self.input_problems),
            "reproducible": self.reproducible,
            "caveats": list(self.caveats()),
            "extra": dict(self.extra),
        }


def capture_provenance(
    *,
    seed: int | None = None,
    inputs: Iterable[str | Path] = (),
    repo_root: Path | None = None,
    extra: Mapping[str, Any] | None = None,
    digest_inputs: bool = True,
) -> Provenance:
    """Capture the current environment and the digests of named inputs.

    ``digest_inputs`` may be disabled when inputs are very large and their
    identity is already established elsewhere; the paths are still recorded,
    with the reason digesting was skipped, so the omission is visible.
    """
    digests: dict[str, str] = {}
    problems: dict[str, str] = {}
    for item in inputs:
        p = Path(item)
        key = str(p)
        if not p.exists():
            problems[key] = "file does not exist"
            continue
        if p.is_dir():
            problems[key] = "path is a directory, not a file"
            continue
        if not digest_inputs:
            problems[key] = "digest skipped by caller (digest_inputs=False)"
            continue
        try:
            digests[key] = file_digest(p)
        except OSError as exc:
            problems[key] = f"unreadable: {exc}"

    return Provenance(
        captured_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        git=git_state(repo_root),
        libraries=_library_versions(),
        platform_str=platform.platform(),
        executable=sys.executable,
        seed=seed,
        input_digests=digests,
        input_problems=problems,
        extra=dict(extra or {}),
    )
