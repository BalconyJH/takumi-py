from __future__ import annotations

import argparse
from base64 import urlsafe_b64encode
import csv
from email import policy
from email.message import Message
from email.parser import BytesParser
import hashlib
from pathlib import Path
import sys
import tarfile
from typing import NoReturn
import zipfile

PROJECT_NAME = "takumi-py"
PACKAGE_NAME = "takumi_py"
EXPECTED_LICENSES = {
    "LICENSE",
    "LICENSES/Geist-OFL-1.1.txt",
    "THIRD_PARTY_NOTICES.md",
    "takumilib/LICENSE-MIT",
}
EXPECTED_PLATFORMS = {
    "linux-aarch64",
    "linux-x86_64",
    "macos-aarch64",
    "windows-x64",
}
DEFAULT_FONT = "takumilib/assets/fonts/geist/geist-latin-wght-300-800.woff2"


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def parse_metadata(data: bytes) -> Message:
    return BytesParser(policy=policy.default).parsebytes(data)


def check_metadata(metadata: Message, version: str, source: Path) -> None:
    expected = {
        "Name": PROJECT_NAME,
        "Version": version,
        "Requires-Python": ">=3.10",
        "License-Expression": "GPL-3.0-or-later",
    }
    for field, value in expected.items():
        if metadata[field] != value:
            fail(f"{source}: expected {field}: {value}, got {metadata[field]}")

    license_files = set(metadata.get_all("License-File", []))
    if license_files != EXPECTED_LICENSES:
        fail(
            f"{source}: expected license metadata {sorted(EXPECTED_LICENSES)}, "
            f"got {sorted(license_files)}"
        )


def check_sdist(path: Path, version: str) -> None:
    expected_filename = f"{PACKAGE_NAME}-{version}.tar.gz"
    if path.name != expected_filename:
        fail(f"{path}: expected sdist filename {expected_filename}")

    expected_root = f"{PACKAGE_NAME}-{version}"
    with tarfile.open(path, "r:gz") as archive:
        names = set(archive.getnames())
        metadata_path = f"{expected_root}/PKG-INFO"
        member = archive.extractfile(metadata_path)
        if member is None:
            fail(f"{path}: missing {metadata_path}")
        check_metadata(parse_metadata(member.read()), version, path)

    expected_members = {
        f"{expected_root}/{license_path}" for license_path in EXPECTED_LICENSES
    }
    expected_members.add(f"{expected_root}/{DEFAULT_FONT}")
    missing = expected_members - names
    if missing:
        fail(f"{path}: missing expected files {sorted(missing)}")

    asset_prefix = f"{expected_root}/takumilib/assets/"
    packaged_assets = {name for name in names if name.startswith(asset_prefix)}
    expected_assets = {f"{expected_root}/{DEFAULT_FONT}"}
    if packaged_assets != expected_assets:
        fail(
            f"{path}: expected only the embedded default font asset, "
            f"got {sorted(packaged_assets)}"
        )


def wheel_platform(tag: str) -> str:
    if "manylinux2014_x86_64" in tag or "manylinux_2_17_x86_64" in tag:
        return "linux-x86_64"
    if "manylinux2014_aarch64" in tag or "manylinux_2_17_aarch64" in tag:
        return "linux-aarch64"
    if "macosx_11_0_arm64" in tag:
        return "macos-aarch64"
    if "win_amd64" in tag:
        return "windows-x64"
    fail(f"unsupported wheel platform tag: {tag}")


def check_wheel(path: Path, version: str) -> str:
    expected_prefix = f"{PACKAGE_NAME}-{version}-cp310-abi3-"
    if not path.name.startswith(expected_prefix):
        fail(f"{path}: wheel filename must start with {expected_prefix}")

    filename_platform = wheel_platform(path.name)
    dist_info = f"{PACKAGE_NAME}-{version}.dist-info"
    with zipfile.ZipFile(path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            fail(f"{path}: corrupt wheel member {corrupt_member}")
        names = set(archive.namelist())
        metadata_path = f"{dist_info}/METADATA"
        wheel_path = f"{dist_info}/WHEEL"
        record_path = f"{dist_info}/RECORD"
        try:
            metadata = parse_metadata(archive.read(metadata_path))
            wheel_metadata = parse_metadata(archive.read(wheel_path))
            record_data = archive.read(record_path).decode("utf-8")
        except KeyError:
            fail(f"{path}: missing METADATA, WHEEL, or RECORD")
        check_metadata(metadata, version, path)

        rows = [row for row in csv.reader(record_data.splitlines()) if len(row) == 3]
        record = {row[0]: (row[1], row[2]) for row in rows}
        if len(record) != len(rows):
            fail(f"{path}: wheel RECORD contains duplicate paths")
        archived_files = {name for name in names if not name.endswith("/")}
        if set(record) != archived_files:
            fail(
                f"{path}: wheel RECORD manifest mismatch: "
                f"missing={sorted(archived_files - record.keys())}, "
                f"unexpected={sorted(record.keys() - archived_files)}"
            )
        for name in sorted(archived_files - {record_path}):
            digest, size = record[name]
            data = archive.read(name)
            expected_digest = "sha256=" + urlsafe_b64encode(
                hashlib.sha256(data).digest()
            ).decode().rstrip("=")
            if digest != expected_digest or size != str(len(data)):
                fail(f"{path}: invalid wheel RECORD entry for {name}")
        if record[record_path] != ("", ""):
            fail(f"{path}: wheel RECORD must not hash itself")

    if wheel_metadata["Wheel-Version"] != "1.0":
        fail(f"{path}: expected Wheel-Version 1.0")
    if wheel_metadata["Root-Is-Purelib"] != "false":
        fail(f"{path}: native wheel must set Root-Is-Purelib: false")
    tags = wheel_metadata.get_all("Tag", [])
    if not tags or any(not tag.startswith("cp310-abi3-") for tag in tags):
        fail(f"{path}: expected only cp310-abi3 wheel tags, got {tags}")
    tag_platforms = {wheel_platform(tag) for tag in tags}
    if tag_platforms != {filename_platform}:
        fail(
            f"{path}: filename platform {filename_platform} does not match "
            f"wheel tags {tags}"
        )

    wheel_licenses = {
        name.removeprefix(f"{dist_info}/licenses/")
        for name in names
        if name.startswith(f"{dist_info}/licenses/")
    }
    if wheel_licenses != EXPECTED_LICENSES:
        fail(
            f"{path}: expected wheel licenses {sorted(EXPECTED_LICENSES)}, "
            f"got {sorted(wheel_licenses)}"
        )
    embedded_assets = [
        name for name in names if name.endswith((".woff2", ".ttf", ".ttc"))
    ]
    if embedded_assets:
        fail(
            f"{path}: font assets must be embedded in the extension: {embedded_assets}"
        )
    return filename_platform


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    missing = [path for path in args.paths if not path.is_file()]
    if missing:
        fail(f"distribution files do not exist: {missing}")

    sdists = [path for path in args.paths if path.name.endswith(".tar.gz")]
    wheels = [path for path in args.paths if path.suffix == ".whl"]
    unknown = set(args.paths) - set(sdists) - set(wheels)
    if unknown:
        fail(f"unsupported distribution files: {sorted(unknown)}")
    if len(sdists) > 1:
        fail(f"expected at most one sdist, found {len(sdists)}")

    for sdist in sdists:
        check_sdist(sdist, args.version)
    platforms = {check_wheel(wheel, args.version) for wheel in wheels}

    if args.complete:
        if len(sdists) != 1:
            fail(f"complete release requires one sdist, found {len(sdists)}")
        if len(wheels) != len(EXPECTED_PLATFORMS):
            fail(
                f"complete release requires {len(EXPECTED_PLATFORMS)} wheels, "
                f"found {len(wheels)}"
            )
        if platforms != EXPECTED_PLATFORMS:
            fail(
                f"expected wheel platforms {sorted(EXPECTED_PLATFORMS)}, "
                f"got {sorted(platforms)}"
            )

    for path in sorted(args.paths):
        sys.stdout.write(f"{sha256(path)}  {path}\n")


if __name__ == "__main__":
    main()
