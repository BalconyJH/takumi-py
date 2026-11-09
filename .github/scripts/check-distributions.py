from __future__ import annotations

import argparse
from base64 import urlsafe_b64encode
import csv
from email import policy
from email.message import Message
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
from typing import NoReturn
import zipfile

PROJECT_NAME = "takumi-py"
PACKAGE_NAME = "takumi_py"
EXPECTED_LICENSES = {
    "LICENSE",
    "LICENSES/Geist-OFL-1.1.txt",
    "LICENSES/MathJax-Apache-2.0.txt",
    "LICENSES/mhchemparser-Apache-2.0.txt",
    "THIRD_PARTY_NOTICES.md",
    "takumilib/LICENSE-MIT",
    "takumilib/takumi-core/LICENSE-CHROMIUM",
    "takumilib/takumi-core/LICENSE-EMOJI-SEGMENTER",
    "takumilib/takumi-core/LICENSE-ICU",
}
EXPECTED_PLATFORMS = {
    "linux-aarch64",
    "linux-x86_64",
    "macos-aarch64",
    "macos-x86_64",
    "musllinux-aarch64",
    "musllinux-x86_64",
    "windows-arm64",
    "windows-x64",
}
SDIST_FONTS = {
    "takumilib/assets/fonts/geist/geist-latin-wght-300-800.ttf",
    "takumilib/assets/fonts/geist/geist-latin-wght-300-800.woff2",
}
MATH_BUNDLE = "mathjax.bundle.js"
MATH_MANIFEST = "manifest.json"
MATH_RUNTIME_PACKAGE = "mini-racer"
MATH_RUNTIME_VERSION = "0.14.1"
MATHJAX_VERSION = "4.1.3"
MATH_ALLOWED_PLATFORMS = EXPECTED_PLATFORMS | {"macos-arm64"}
MATH_PACKAGE_VERSIONS = {
    "@mathjax/src": MATHJAX_VERSION,
    "@mathjax/mathjax-newcm-font": MATHJAX_VERSION,
    "@mathjax/mathjax-mhchem-font-extension": MATHJAX_VERSION,
    "mhchemparser": "4.2.1",
}
MATH_PACKAGE_LICENSES = dict.fromkeys(MATH_PACKAGE_VERSIONS, "Apache-2.0")
MATH_BUILD_FIELDS = {
    "bun_version",
    "command",
    "target",
    "format",
    "entry",
}
MATH_SDIST_BUILD_FILES = {
    "README.md",
    "build.mjs",
    "bun.lock",
    "mathjax-entry.mjs",
    "package.json",
}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def parse_metadata(data: bytes) -> Message:
    return BytesParser(policy=policy.default).parsebytes(data)


def check_metadata(metadata: Message, version: str, source: Path) -> None:
    expected = {
        "Name": PROJECT_NAME,
        "Version": version,
        "Requires-Python": ">=3.11",
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

    extras = {extra.lower() for extra in metadata.get_all("Provides-Extra", [])}
    if "math" not in extras:
        fail(f"{source}: expected a math optional dependency")

    requirements = metadata.get_all("Requires-Dist", [])
    math_requirements = [
        requirement
        for requirement in requirements
        if _requirement_name(requirement) == MATH_RUNTIME_PACKAGE
    ]
    if len(math_requirements) != 1:
        fail(
            f"{source}: expected exactly one {MATH_RUNTIME_PACKAGE} requirement, "
            f"got {math_requirements}"
        )
    requirement = math_requirements[0]
    if not re.search(
        r"""(?ix)
        ^\s*mini[-_.]racer\s*==\s*0\.14\.1
        \s*;\s*[^;]*\bextra\s*==\s*["']math["']
        """,
        requirement,
    ):
        fail(
            f"{source}: {MATH_RUNTIME_PACKAGE}=={MATH_RUNTIME_VERSION} must be "
            f"restricted to the math extra, got {requirement!r}"
        )


def _requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    return "" if match is None else match[1].replace("_", "-").lower()


def check_math_assets(
    assets: dict[str, bytes],
    *,
    source: Path,
    archive_path: str,
) -> None:
    expected = {MATH_BUNDLE, MATH_MANIFEST}
    if set(assets) != expected:
        fail(
            f"{source}: expected math assets {sorted(expected)} in {archive_path}, "
            f"got {sorted(assets)}"
        )

    try:
        manifest = json.loads(assets[MATH_MANIFEST])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"{source}: invalid math manifest JSON: {error}")
    if not isinstance(manifest, dict):
        fail(f"{source}: math manifest root must be an object")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        fail(f"{source}: expected math manifest schema_version 1")

    bundle_metadata = manifest.get("bundle")
    if not isinstance(bundle_metadata, dict):
        fail(f"{source}: math manifest bundle must be an object")
    if bundle_metadata.get("file") != MATH_BUNDLE:
        fail(f"{source}: math manifest bundle.file must be {MATH_BUNDLE!r}")

    bundle = assets[MATH_BUNDLE]
    if type(bundle_metadata.get("bytes")) is not int or bundle_metadata["bytes"] != len(
        bundle
    ):
        fail(
            f"{source}: math manifest bundle.bytes {bundle_metadata.get('bytes')!r} "
            f"does not match {len(bundle)} installed bytes"
        )
    expected_sha256 = hashlib.sha256(bundle).hexdigest()
    if bundle_metadata.get("sha256") != expected_sha256:
        fail(
            f"{source}: math manifest bundle.sha256 does not match the installed "
            f"bundle ({expected_sha256})"
        )
    for key in ("gzip_bytes", "brotli_bytes"):
        value = bundle_metadata.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            fail(f"{source}: math manifest bundle.{key} must be a positive integer")

    build = manifest.get("build")
    if not isinstance(build, dict):
        fail(f"{source}: math manifest build must be an object")
    for field in sorted(MATH_BUILD_FIELDS):
        value = build.get(field)
        if not isinstance(value, str) or not value:
            fail(f"{source}: math manifest build.{field} must be a non-empty string")

    packages = manifest.get("packages")
    if not isinstance(packages, list):
        fail(f"{source}: math manifest packages must be an array")
    package_versions: dict[str, str] = {}
    package_licenses: dict[str, str] = {}
    for package in packages:
        if not isinstance(package, dict):
            fail(f"{source}: every math manifest package must be an object")
        name = package.get("name")
        package_version = package.get("version")
        license_name = package.get("license")
        if not all(
            isinstance(value, str) and value
            for value in (name, package_version, license_name)
        ):
            fail(
                f"{source}: math manifest packages need non-empty name, version, "
                "and license strings"
            )
        if name in package_versions:
            fail(f"{source}: duplicate math package {name!r}")
        package_versions[name] = package_version
        package_licenses[name] = license_name
    if package_versions != MATH_PACKAGE_VERSIONS:
        fail(
            f"{source}: expected math packages {MATH_PACKAGE_VERSIONS}, "
            f"got {package_versions}"
        )
    if package_licenses != MATH_PACKAGE_LICENSES:
        fail(
            f"{source}: expected math package licenses {MATH_PACKAGE_LICENSES}, "
            f"got {package_licenses}"
        )

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        fail(f"{source}: math manifest runtime must be an object")
    if runtime.get("package") != MATH_RUNTIME_PACKAGE:
        fail(
            f"{source}: expected math runtime package {MATH_RUNTIME_PACKAGE!r}, "
            f"got {runtime.get('package')!r}"
        )
    if runtime.get("version") != MATH_RUNTIME_VERSION:
        fail(
            f"{source}: expected math runtime version {MATH_RUNTIME_VERSION!r}, "
            f"got {runtime.get('version')!r}"
        )
    tested_platforms = runtime.get("tested_platforms")
    if not isinstance(tested_platforms, list) or any(
        not isinstance(platform, str) for platform in tested_platforms
    ):
        fail(f"{source}: math manifest runtime.tested_platforms must be a string array")
    if len(set(tested_platforms)) != len(tested_platforms):
        fail(f"{source}: math manifest runtime.tested_platforms contains duplicates")
    if not tested_platforms:
        fail(f"{source}: math manifest must list at least one tested platform")
    unexpected_platforms = set(tested_platforms) - MATH_ALLOWED_PLATFORMS
    if unexpected_platforms:
        fail(
            f"{source}: math manifest claims unsupported platforms "
            f"{sorted(unexpected_platforms)}"
        )

    licenses = manifest.get("licenses")
    if (
        not isinstance(licenses, list)
        or not licenses
        or any(
            not isinstance(license_name, str) or not license_name
            for license_name in licenses
        )
    ):
        fail(f"{source}: math manifest licenses must be a non-empty string array")
    if len(set(licenses)) != len(licenses):
        fail(f"{source}: math manifest licenses contains duplicates")


def check_math_build_sources(
    names: set[str],
    *,
    source: Path,
    expected_root: str,
) -> None:
    prefix = f"{expected_root}/tools/mathjax/"
    packaged = {name for name in names if name.startswith(prefix)}
    expected = {f"{prefix}{name}" for name in MATH_SDIST_BUILD_FILES}
    if packaged != expected:
        fail(
            f"{source}: expected only reproducible MathJax build sources "
            f"{sorted(expected)}, got {sorted(packaged)}"
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
        math_asset_path = f"{expected_root}/python/{PACKAGE_NAME}/math/assets"
        math_names = {
            name
            for name in names
            if name.startswith(f"{math_asset_path}/") and not name.endswith("/")
        }
        expected_math_names = {
            f"{math_asset_path}/{asset}" for asset in (MATH_BUNDLE, MATH_MANIFEST)
        }
        if math_names != expected_math_names:
            fail(
                f"{path}: expected math assets {sorted(expected_math_names)}, "
                f"got {sorted(math_names)}"
            )
        assets = {}
        for name in math_names:
            asset = archive.extractfile(name)
            if asset is None:
                fail(f"{path}: missing math asset {name}")
            assets[Path(name).name] = asset.read()
        check_math_assets(
            assets,
            source=path,
            archive_path=math_asset_path,
        )
        check_math_build_sources(names, source=path, expected_root=expected_root)

    expected_members = {
        f"{expected_root}/{license_path}" for license_path in EXPECTED_LICENSES
    }
    expected_members.update(f"{expected_root}/{font}" for font in SDIST_FONTS)
    missing = expected_members - names
    if missing:
        fail(f"{path}: missing expected files {sorted(missing)}")

    asset_prefix = f"{expected_root}/takumilib/assets/"
    packaged_assets = {name for name in names if name.startswith(asset_prefix)}
    expected_assets = {f"{expected_root}/{font}" for font in SDIST_FONTS}
    if packaged_assets != expected_assets:
        fail(
            f"{path}: expected only the embedded default font asset, "
            f"got {sorted(packaged_assets)}"
        )


def wheel_platform(tag: str, *, allow_native: bool = False) -> str:
    if "manylinux2014_x86_64" in tag or "manylinux_2_17_x86_64" in tag:
        return "linux-x86_64"
    if "manylinux2014_aarch64" in tag or "manylinux_2_17_aarch64" in tag:
        return "linux-aarch64"
    if "musllinux_1_2_x86_64" in tag:
        return "musllinux-x86_64"
    if "musllinux_1_2_aarch64" in tag:
        return "musllinux-aarch64"
    if "macosx_11_0_arm64" in tag:
        return "macos-aarch64"
    if re.search(r"macosx_\d+_\d+_x86_64", tag):
        return "macos-x86_64"
    if "win_amd64" in tag:
        return "windows-x64"
    if "win_arm64" in tag:
        return "windows-arm64"
    if allow_native:
        _, separator, platform_tag = tag.removesuffix(".whl").rpartition("cp311-abi3-")
        if separator and platform_tag:
            return f"native:{platform_tag}"
    fail(f"unsupported wheel platform tag: {tag}")


def check_wheel(path: Path, version: str, *, allow_native: bool = False) -> str:
    expected_prefix = f"{PACKAGE_NAME}-{version}-cp311-abi3-"
    if not path.name.startswith(expected_prefix):
        fail(f"{path}: wheel filename must start with {expected_prefix}")

    filename_platform = wheel_platform(path.name, allow_native=allow_native)
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

        math_asset_path = f"{PACKAGE_NAME}/math/assets"
        math_names = {
            name for name in archived_files if name.startswith(f"{math_asset_path}/")
        }
        expected_math_names = {
            f"{math_asset_path}/{asset}" for asset in (MATH_BUNDLE, MATH_MANIFEST)
        }
        if math_names != expected_math_names:
            fail(
                f"{path}: expected math assets {sorted(expected_math_names)}, "
                f"got {sorted(math_names)}"
            )
        check_math_assets(
            {Path(name).name: archive.read(name) for name in math_names},
            source=path,
            archive_path=math_asset_path,
        )

    if wheel_metadata["Wheel-Version"] != "1.0":
        fail(f"{path}: expected Wheel-Version 1.0")
    if wheel_metadata["Root-Is-Purelib"] != "false":
        fail(f"{path}: native wheel must set Root-Is-Purelib: false")
    tags = wheel_metadata.get_all("Tag", [])
    if not tags or any(not tag.startswith("cp311-abi3-") for tag in tags):
        fail(f"{path}: expected only cp311-abi3 wheel tags, got {tags}")
    tag_platforms = {wheel_platform(tag, allow_native=allow_native) for tag in tags}
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
    parser.add_argument("--allow-native-wheel-tag", action="store_true")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    if args.complete and args.allow_native_wheel_tag:
        fail("--allow-native-wheel-tag cannot be used with --complete")

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
    platforms = {
        check_wheel(
            wheel,
            args.version,
            allow_native=args.allow_native_wheel_tag,
        )
        for wheel in wheels
    }

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
