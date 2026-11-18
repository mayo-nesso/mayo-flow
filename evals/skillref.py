"""Extract a skill directory as of a git ref."""
import io
import shutil
import subprocess
import tarfile
from pathlib import Path

WORKING_TREE = "working-tree"


def extract_skill(repo, skill, ref, dest):
    """Put `<skill>/` as of `ref` under `dest`; return `dest/<skill>`.

    `working-tree` copies the current files instead of reading git.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / skill
    if ref == WORKING_TREE:
        if not (Path(repo) / skill).is_dir():
            raise ValueError(f"no skill directory {skill!r} in {repo}")
        shutil.copytree(Path(repo) / skill, out)
        return out
    r = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar",
                        f"{ref}:{skill}"], capture_output=True)
    if r.returncode != 0:
        raise ValueError(f"cannot extract {skill!r} at {ref!r}: "
                         + r.stderr.decode().strip())
    out.mkdir()
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        tar.extractall(out, filter="data")
    return out
