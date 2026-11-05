#!/usr/bin/env python3
"""Generate the image's third-party notices from what is actually installed.

Run as the last build step of docker/Dockerfile.user. Writes

    <out>/THIRD_PARTY_NOTICES.md    one inventory of every Debian, Conda and
                                    Python package in the image, with its
                                    declared license
    <out>/licenses/python/<dist>/   the license files each Python distribution
                                    ships in its .dist-info, collected in one
                                    place (GPL/LGPL require the text to travel
                                    with the binaries)

Debian packages already carry their license texts at
/usr/share/doc/<pkg>/copyright, and Conda packages under
<env>/info/licenses or <env>/share/licenses; the notice points there instead of
copying hundreds of files a second time.

Generated rather than hand-maintained on purpose: a hand-written list goes
stale the first time conda_environment.yaml or requirements-ubuntu.txt moves,
and a stale notice is worse than none for a redistributed image.

Pure standard library, so it runs on the env's interpreter without touching
the environment it is describing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata as md
import json
import re
import shutil
import subprocess
from pathlib import Path

COPYLEFT = re.compile(r"\b(A?GPL|LGPL|GNU (Library|Lesser|Affero)?\s*General Public|MPL|EPL|CDDL)", re.I)
PROPRIETARY = re.compile(r"proprietary|nvidia software license|LicenseRef-NVIDIA", re.I)
# Our own packages, which are not third-party and are covered by the product license.
FIRST_PARTY = re.compile(r"^(lerobot|xense|taccap|xensevr)", re.I)
LICENSE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS|COPYRIGHT)", re.I)


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def python_license(meta) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (meta.get("License") or "").strip()
    # Some projects paste the whole license text into the field.
    if lic and len(lic) < 80 and "\n" not in lic and lic.upper() != "UNKNOWN":
        return lic
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::") and c.split("::")[-1].strip() != "OSI Approved"
    ]
    if classifiers:
        return "; ".join(classifiers)
    return lic.splitlines()[0][:80] if lic else ""


def python_rows(out: Path) -> list[dict]:
    rows, dest_root = [], out / "licenses" / "python"
    for dist in sorted(md.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
        meta = dist.metadata
        name = meta["Name"]
        if not name:
            continue
        copied = []
        for f in dist.files or []:
            # Only the dist's own metadata dir: a bare "licenses" path match also
            # caught code, e.g. packaging's vendored licenses/__init__.py.
            if not f.parts or not f.parts[0].endswith(".dist-info") or f.suffix in {".py", ".pyc"}:
                continue
            if LICENSE_FILE.search(f.name) or "licenses" in f.parts[1:-1]:
                src = Path(str(dist.locate_file(f)))
                if src.is_file():
                    dst = dest_root / name / f.name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                    copied.append(f.name)
        home = meta.get("Home-page") or ""
        for url in meta.get_all("Project-URL") or []:
            label, _, link = url.partition(",")
            if not home or label.strip().lower() in {"source", "repository", "source code"}:
                home = link.strip()
        if not home:
            # No URL in the metadata (pyyaml-include is one): PyPI still serves
            # the exact sdist, which is what a source offer has to point at.
            home = f"https://pypi.org/project/{name}/{dist.version}/"
        rows.append(
            {
                "name": name,
                "version": dist.version,
                "license": python_license(meta),
                "source": home,
                "texts": f"licenses/python/{name}/" if copied else "",
            }
        )
    return rows


def conda_rows(prefix: Path) -> list[dict]:
    rows = []
    for f in sorted((prefix / "conda-meta").glob("*.json")):
        d = json.loads(f.read_text())
        rows.append(
            {
                "name": d.get("name", ""),
                "version": d.get("version", ""),
                "license": d.get("license") or "",
                "source": d.get("channel", ""),
            }
        )
    return rows


def deb_rows() -> list[dict]:
    try:
        out = subprocess.run(
            ["/usr/bin/dpkg-query", "-W", "-f=${Package}\t${Version}\t${Homepage}\n"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in sorted(out.splitlines()):
        pkg, ver, home = (line.split("\t") + ["", ""])[:3]
        copyright_file = Path("/usr/share/doc") / pkg / "copyright"
        licenses = ""
        if copyright_file.is_file():
            found = re.findall(r"^License:\s*(\S.*)$", copyright_file.read_text(errors="replace"), re.M)
            licenses = "; ".join(dict.fromkeys(x.strip() for x in found))[:120]
        rows.append({"name": pkg, "version": ver, "license": licenses, "source": home})
    return rows


def table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(t for _, t in cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(_cell(r.get(k, "")) for k, _ in cols) + " |\n" for r in rows)


def flagged(rows: list[dict], pattern: re.Pattern) -> list[dict]:
    return [r for r in rows if pattern.search(r["license"]) and not FIRST_PARTY.match(r["name"])]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--conda-prefix", type=Path, required=True)
    ap.add_argument("--image-version", default="", help="defaults to [project].version in --project-root")
    ap.add_argument("--project-root", type=Path, default=Path("/opt/lerobot"))
    args = ap.parse_args()
    if not args.image_version:
        pyproject = args.project_root / "pyproject.toml"
        if pyproject.is_file():
            import tomllib

            args.image_version = tomllib.loads(pyproject.read_text()).get("project", {}).get("version", "")
    args.out.mkdir(parents=True, exist_ok=True)

    py, conda, deb = python_rows(args.out), conda_rows(args.conda_prefix), deb_rows()
    copyleft = flagged(py, COPYLEFT) + flagged(conda, COPYLEFT)
    proprietary = flagged(py, PROPRIETARY) + flagged(conda, PROPRIETARY)
    unknown = [r for r in py if not r["license"] and not FIRST_PARTY.match(r["name"])]

    header = (Path(__file__).parent / "THIRD_PARTY_NOTICES.header.md").read_text()
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    body = [
        header.replace("{{IMAGE_VERSION}}", args.image_version or "unversioned").replace("{{DATE}}", stamp),
        "\n## Summary\n",
        f"- Debian packages: {len(deb)} (license texts: `/usr/share/doc/<package>/copyright`)",
        f"- Conda packages: {len(conda)} (license texts: `{args.conda_prefix}/info/licenses`, `{args.conda_prefix}/share/licenses`)",
        f"- Python distributions: {len(py)} (license texts collected under `licenses/python/`)",
        "\n## Copyleft components (GPL / LGPL / MPL and similar)\n",
        "These are distributed unmodified. Their license texts are included as listed, "
        "and their corresponding source is available as described in *Source code offer* above.\n",
        table(
            copyleft,
            [("name", "Component"), ("version", "Version"), ("license", "License"), ("source", "Upstream source")],
        )
        if copyleft
        else "_None detected._\n",
        "\n## Components under proprietary redistributable licenses\n",
        "NVIDIA CUDA/cuDNN runtime libraries are included as runtime dependencies of PyTorch and are "
        "redistributed under the NVIDIA Software License Agreement / CUDA Toolkit EULA, which "
        "permits redistribution of these runtime components with an application.\n",
        table(proprietary, [("name", "Component"), ("version", "Version"), ("license", "License")])
        if proprietary
        else "_None detected._\n",
    ]
    if unknown:
        body += [
            "\n## Python distributions without license metadata\n",
            "Review manually; see the upstream source for the license.\n",
            table(unknown, [("name", "Component"), ("version", "Version"), ("source", "Upstream source")]),
        ]
    body += [
        "\n## Python distributions\n",
        table(
            py,
            [
                ("name", "Component"),
                ("version", "Version"),
                ("license", "License"),
                ("texts", "License texts"),
                ("source", "Upstream source"),
            ],
        ),
        "\n## Conda packages\n",
        table(conda, [("name", "Package"), ("version", "Version"), ("license", "License"), ("source", "Channel")]),
        "\n## Debian packages\n",
        table(
            deb,
            [
                ("name", "Package"),
                ("version", "Version"),
                ("license", "License (from copyright file)"),
                ("source", "Homepage"),
            ],
        ),
    ]
    (args.out / "THIRD_PARTY_NOTICES.md").write_text("\n".join(body))
    print(
        f"[notices] {len(deb)} deb, {len(conda)} conda, {len(py)} python; "
        f"{len(copyleft)} copyleft, {len(proprietary)} proprietary, {len(unknown)} without license -> {args.out}"
    )


if __name__ == "__main__":
    main()
