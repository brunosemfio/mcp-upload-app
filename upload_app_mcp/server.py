from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Literal

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

TestTrack = Literal["internal", "alpha", "beta"]

mcp = FastMCP(
    name="upload-app",
    instructions=(
        "Uploads an already built .aab to a Google Play test track or an .ipa to TestFlight, "
        "then promotes it to production. The app project builds the file; these tools only take "
        "its path. promote_android and release_ios publish only with confirm=true; without it "
        "they show what would happen."
    ),
)


def run_lane(platform: str, lane: str, **options: object) -> str:
    result = subprocess.run(
        ["fastlane", platform, lane, *(f"{k}:{v}" for k, v in options.items())],
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


@mcp.tool(description="Upload an .aab to a Google Play test track.")
def upload_android(aab_path: str, package_name: str, track: TestTrack = "internal") -> str:
    return run_lane("android", "upload", aab=aab_path, package_name=package_name, track=track)


@mcp.tool(
    description=(
        "Promote a version code from a Google Play test track to production. A rollout below 1 "
        "starts a staged rollout. Without confirm=true it only validates with Google Play and "
        "publishes nothing."
    )
)
def promote_android(
    package_name: str,
    version_code: int,
    rollout: float = 1.0,
    from_track: TestTrack = "internal",
    confirm: bool = False,
) -> str:
    if not 0 < rollout <= 1:
        raise ValueError("rollout must be greater than 0 and at most 1")
    options = dict(
        package_name=package_name,
        version_code=version_code,
        rollout=rollout,
        from_track=from_track,
    )
    if confirm:
        return run_lane("android", "promote", **options)
    output = run_lane("android", "promote", validate_only="true", **options)
    return f"Validated with Google Play, nothing published. Call again with confirm=true.\n{output}"


@mcp.tool(description="Upload an .ipa to TestFlight without waiting for Apple's processing.")
def upload_ios(ipa_path: str) -> str:
    return run_lane("ios", "upload", ipa=ipa_path)


@mcp.tool(
    description=(
        "Attach a TestFlight build to an App Store version, creating the version if needed, and "
        "submit it for review. Without confirm=true it only describes what it would do."
    )
)
def release_ios(
    app_identifier: str, app_version: str, build_number: str, confirm: bool = False
) -> str:
    if not confirm:
        return (
            f"Would attach build {build_number} to version {app_version} of {app_identifier} "
            "and submit it for review. Call again with confirm=true."
        )
    return run_lane(
        "ios",
        "release",
        app_identifier=app_identifier,
        app_version=app_version,
        build_number=build_number,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
