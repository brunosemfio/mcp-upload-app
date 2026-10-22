from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).parent
FASTLANE_ENV = {
    **os.environ,
    "LC_ALL": "en_US.UTF-8",
    "LANG": "en_US.UTF-8",
    "FASTLANE_DISABLE_COLORS": "1",
    "FASTLANE_SKIP_UPDATE_CHECK": "1",
    "FASTLANE_OPT_OUT_USAGE": "1",
    "FASTLANE_SKIP_DOCS": "1",
}

mcp = FastMCP(
    name="upload-app",
    instructions=(
        "Uploads an already built .aab to a Google Play test track or an .ipa to TestFlight, "
        "then promotes it to production. The app project builds the file; these tools only take "
        "its path. Use status_android and status_ios to see what is in each track, whether an "
        "iOS build finished processing and the current rollout. promote_android, "
        "update_rollout_android and release_ios publish only with confirm=true; without it they "
        "show what would happen."
    ),
)


def run_lane(platform: str, lane: str, **options: object) -> str:
    args = [f"{k}:{v}" for k, v in options.items() if v is not None]
    result = subprocess.run(
        ["fastlane", platform, lane, *args],
        cwd=ROOT,
        env=FASTLANE_ENV,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=1800,
    )
    tail = "\n".join(result.stdout.splitlines()[-40:])
    if result.returncode != 0:
        raise RuntimeError(tail)
    return tail


def validate_or_publish(lane: str, confirm: bool, **options: object) -> str:
    if confirm:
        return run_lane("android", lane, **options)
    output = run_lane("android", lane, validate_only="true", **options)
    return f"Validated with Google Play, nothing published. Call again with confirm=true.\n{output}"


def check_test_track(track: str) -> None:
    if track == "production":
        raise ValueError("track must be a test track; use promote_android for production")


def check_rollout(rollout: float) -> None:
    if not 0 < rollout <= 1:
        raise ValueError("rollout must be greater than 0 and at most 1")


@mcp.tool(
    description=(
        "Upload an .aab to a Google Play test track: internal, alpha, beta or the name of a "
        "custom closed track."
    )
)
def upload_android(aab_path: str, package_name: str, track: str = "internal") -> str:
    check_test_track(track)
    return run_lane("android", "upload", aab=aab_path, package_name=package_name, track=track)


@mcp.tool(
    description=(
        "Promote a version code from a Google Play test track to production. A rollout below 1 "
        "starts a staged rollout. release_notes sets the release notes in the given Play "
        "language code. Without confirm=true it only validates with Google Play and publishes "
        "nothing."
    )
)
def promote_android(
    package_name: str,
    version_code: int,
    rollout: float = 1.0,
    from_track: str = "internal",
    release_notes: str | None = None,
    locale: str = "pt-BR",
    confirm: bool = False,
) -> str:
    check_test_track(from_track)
    check_rollout(rollout)
    return validate_or_publish(
        "promote",
        confirm,
        package_name=package_name,
        version_code=version_code,
        rollout=rollout,
        from_track=from_track,
        release_notes=release_notes,
        locale=locale if release_notes else None,
    )


@mcp.tool(
    description=(
        "Change a Google Play production release: a new rollout fraction, 1 to complete it, or "
        "halt=true to stop it. Without confirm=true it only validates with Google Play and "
        "publishes nothing."
    )
)
def update_rollout_android(
    package_name: str,
    version_code: int,
    rollout: float | None = None,
    halt: bool = False,
    confirm: bool = False,
) -> str:
    if halt == (rollout is not None):
        raise ValueError("pass either rollout or halt=true")
    if rollout is not None:
        check_rollout(rollout)
    return validate_or_publish(
        "rollout",
        confirm,
        package_name=package_name,
        version_code=version_code,
        rollout=rollout,
        halt="true" if halt else None,
    )


@mcp.tool(
    description=(
        "List the Google Play releases of every track with version codes, status and rollout "
        "fraction."
    )
)
def status_android(package_name: str) -> str:
    return run_lane("android", "status", package_name=package_name)


@mcp.tool(description="Upload an .ipa to TestFlight without waiting for Apple's processing.")
def upload_ios(ipa_path: str) -> str:
    return run_lane("ios", "upload", ipa=ipa_path)


@mcp.tool(
    description=(
        "Attach a TestFlight build to an App Store version, creating the version if needed, and "
        "submit it for review. release_notes sets What's New in every language of the live "
        "version. Without confirm=true it only describes what it would do."
    )
)
def release_ios(
    app_identifier: str,
    app_version: str,
    build_number: str,
    release_notes: str | None = None,
    confirm: bool = False,
) -> str:
    if not confirm:
        notes = " with the given What's New" if release_notes else ""
        return (
            f"Would attach build {build_number} to version {app_version} of {app_identifier} "
            f"and submit it for review{notes}. Call again with confirm=true."
        )
    return run_lane(
        "ios",
        "release",
        app_identifier=app_identifier,
        app_version=app_version,
        build_number=build_number,
        release_notes=release_notes,
    )


@mcp.tool(
    description=(
        "Show the latest App Store versions with their state and the latest builds with their "
        "processing state. A build can be submitted only after it is VALID."
    )
)
def status_ios(app_identifier: str) -> str:
    return run_lane("ios", "status", app_identifier=app_identifier)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
