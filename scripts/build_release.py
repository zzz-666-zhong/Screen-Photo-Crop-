"""Build a clean GitHub-ready ZIP from release-files.txt (standard library only)."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


def release_files(root: Path) -> list[Path]:
    """Accept only explicitly listed regular files contained in the source tree."""
    root = root.resolve()
    names = [line.strip() for line in (root / "release-files.txt").read_text(
        encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not names or len(names) != len(set(names)):
        raise ValueError("Release manifest is empty or contains duplicate paths.")
    result = []
    for name in names:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise ValueError(f"Unsafe release path: {name}")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError(f"Missing or external release file: {name}")
        if path.stat().st_size >= 100 * 1024 * 1024:
            raise ValueError(f"File exceeds the regular GitHub repository limit: {name}")
        result.append(path)
    return sorted(result)


def application_metadata(root: Path) -> tuple[str, list[str]]:
    """Read constants without importing OpenCV or executing the application."""
    constants = {}
    for node in ast.parse((root / "screen_crop.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"__version__", "FEATURE_NAMES"}:
                    constants[target.id] = ast.literal_eval(node.value)
    version = constants["__version__"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Application version must use major.minor.patch.")
    return version, constants["FEATURE_NAMES"]


def validate_links(root: Path, files: list[Path]) -> None:
    allowed = {p.resolve() for p in files}
    for path in files:
        if path.suffix != ".md":
            continue
        for link in re.findall(r"\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in link or link.startswith(("#", "mailto:")):
                continue
            target = (path.parent / link.split("#", 1)[0]).resolve()
            if target not in allowed:
                raise ValueError(f"Link targets an unpublished file: {path.relative_to(root)} -> {link}")


def build(root: Path, output: Path, overwrite: bool = False) -> Path:
    root, output = root.resolve(), output.resolve()
    files = release_files(root)
    version, features = application_metadata(root)
    model = json.loads((root / "screen_crop_model.json").read_text(encoding="utf-8"))
    if model["features"] != features:
        raise ValueError("Model metadata feature order does not match the application.")
    if model.get('reflection'):
        specialist=model['reflection']
        weights=root/'screen_crop_reflection.xml.gz'
        if specialist['features'] != features or weights not in files:
            raise ValueError('Release is missing a compatible reflection model.')
        if hashlib.sha256(weights.read_bytes()).hexdigest() != specialist['weight_sha256']:
            raise ValueError('Reflection weights do not match their metadata fingerprint.')
    review_dir=root/'extreme_review_model'
    review_metadata=review_dir/'screen_crop_model.json'
    review_weights=review_dir/'screen_crop_forest.xml.gz'
    if review_metadata not in files or review_weights not in files:
        raise ValueError('Release is missing the review specialist model.')
    review_model=json.loads(review_metadata.read_text(encoding='utf-8'))
    if review_model['features'] != features or hashlib.sha256(review_weights.read_bytes()).hexdigest() != review_model['weight_sha256']:
        raise ValueError('Review specialist features or weight fingerprint do not match.')
    validate_links(root, files)
    basename = f"screen-photo-crop-v{version}"
    destination = output / f"{basename}.zip"
    checksum = output / f"{basename}.zip.sha256"
    if not overwrite and (destination.exists() or checksum.exists()):
        raise FileExistsError(f"Release already exists: {destination.name}; use --overwrite.")
    # Never replace any source file, even if a custom manifest is used.
    if destination in files or checksum in files:
        raise ValueError("Release outputs must not replace source files.")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        records = {}
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                payload = path.read_bytes()
                records[relative] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                info = zipfile.ZipInfo(f"{basename}/{relative}", date_time=(2026, 10, 11, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                # The forest is already gzip-compressed.
                info.compress_type = zipfile.ZIP_STORED if path.suffix == ".gz" else zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)
            info = zipfile.ZipInfo(f"{basename}/release-manifest.json", date_time=(2026, 10, 11, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json.dumps({"version": version, "files": records}, indent=2,
                                             ensure_ascii=False).encode("utf-8") + b"\n")
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(destination)
        checksum.write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="Release output directory")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing release archive")
    args = parser.parse_args()
    try:
        path = build(ROOT, args.output, args.overwrite)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Release build failed: {exc}\n")
    print(f"Built {path.name} ({path.stat().st_size / 1024**2:.1f} MiB)")
    print("The archive contains only files in release-files.txt plus release-manifest.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
