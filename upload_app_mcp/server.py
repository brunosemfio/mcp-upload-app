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

SCREENSHOT_LAYOUT = """\
# Screenshot folder layout

Save the screenshots of each store in its own folder, with one subfolder per language. Each
store uploads the images in file name order, so prefix them with 01-, 02-, 03-.

## App Store (upload_screenshots_ios)

    folder/
      pt-BR/
        01-home.png      1320x2868, iPhone 6.9"
        02-search.png    1320x2868
        03-ipad-home.png 2064x2752, iPad 13"

- The images go straight in the language folder. fastlane detects the device from the image
  size, so each image must have the exact size of an App Store screenshot type.
- Language folders use App Store Connect locale codes, such as pt-BR, en-US and es-MX. A folder
  for a language the version does not have adds that language to the version.
- Up to 10 images per device and language, PNG or JPEG.
- For each language in the folder, every existing screenshot of that language is deleted
  first, on every device. Languages not in the folder stay as they are.

## Google Play (upload_screenshots_android)

    folder/
      pt-BR/
        images/
          phoneScreenshots/
            01-home.png
            02-search.png
          tenInchScreenshots/
            01-home.png

- The device folder is required, because Google Play does not detect the device from the
  image size: phoneScreenshots, sevenInchScreenshots, tenInchScreenshots, tvScreenshots or
  wearScreenshots.
- Language folders use Google Play language codes, such as pt-BR, en-US and es-419 for Latin
  American Spanish.
- 2 to 8 images per device and language, PNG or JPEG.
- Only the device folders that have images replace the existing screenshots. The store
  listing changes for everyone after Google Play reviews it, independent of any release.
"""

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")

mcp = FastMCP(
    name="upload-app",
    instructions=(
        "Uploads an already built .aab to a Google Play test track or an .ipa to TestFlight, "
        "then promotes it to production. The app project builds the file; these tools only take "
        "its path. Use status_android and status_ios to see what is in each track, whether an "
        "iOS build finished processing and the current rollout. The screenshot tools take a "
        "folder laid out as the resource upload-app://screenshots/layout describes. "
        "promote_android, update_rollout_android, release_ios, update_review_info_ios, "
        "update_age_rating_ios and the screenshot tools publish only with confirm=true; without "
        "it they show what would happen."
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


def absolute(path: str) -> str:
    return str(Path(path).expanduser().absolute())


def count_screenshots(folder: str, pattern: str) -> dict[str, int]:
    root = Path(folder).expanduser()
    counts = {}
    for language in sorted(root.iterdir()) if root.is_dir() else []:
        images = [f for f in language.glob(pattern) if f.suffix.lower() in IMAGE_SUFFIXES]
        if images:
            counts[language.name] = len(images)
    if not counts:
        raise ValueError(f"No screenshots found in {folder}.\n\n{SCREENSHOT_LAYOUT}")
    return counts


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
    return run_lane(
        "android", "upload", aab=absolute(aab_path), package_name=package_name, track=track
    )


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
    return run_lane("ios", "upload", ipa=absolute(ipa_path))


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


@mcp.resource(
    "upload-app://screenshots/layout",
    name="screenshots-layout",
    description="Folder layout the screenshot tools expect for the App Store and Google Play.",
    mime_type="text/markdown",
)
def screenshots_layout() -> str:
    return SCREENSHOT_LAYOUT


@mcp.tool(
    description=(
        "Replace the App Store screenshots of an app version with the images in folder, one "
        "subfolder per App Store Connect locale with the images straight inside, as the resource "
        "upload-app://screenshots/layout describes. Creates the version if needed. Without "
        "confirm=true it only lists the images it found."
    )
)
def upload_screenshots_ios(
    app_identifier: str, app_version: str, folder: str, confirm: bool = False
) -> str:
    counts = count_screenshots(folder, "*")
    if not confirm:
        found = ", ".join(f"{language}: {count}" for language, count in counts.items())
        return (
            f"Would replace the screenshots of version {app_version} of {app_identifier} in "
            f"these languages, on every device: {found}. Call again with confirm=true."
        )
    return run_lane(
        "ios",
        "screenshots",
        app_identifier=app_identifier,
        app_version=app_version,
        folder=absolute(folder),
    )


@mcp.tool(
    description=(
        "Set the App Review sign-in information of an App Store version: the demo account user "
        "and password, with optional notes for the reviewer. Contact details stay as they are. "
        "Creates the version if needed. Without confirm=true it only describes what it would do."
    )
)
def update_review_info_ios(
    app_identifier: str,
    app_version: str,
    demo_user: str,
    demo_password: str,
    notes: str | None = None,
    confirm: bool = False,
) -> str:
    if not demo_user.strip() or not demo_password.strip():
        raise ValueError("demo_user and demo_password must not be empty")
    if not confirm:
        with_notes = " and the given notes" if notes else ""
        return (
            f"Would set the App Review sign-in of version {app_version} of {app_identifier} to "
            f"user {demo_user}{with_notes}. Call again with confirm=true."
        )
    return run_lane(
        "ios",
        "review_info",
        app_identifier=app_identifier,
        app_version=app_version,
        demo_user=demo_user,
        demo_password=demo_password,
        notes=notes,
    )


@mcp.tool(
    description=(
        "Answer the App Store age rating questions of the app version in preparation with the "
        "answers in a JSON file. The keys are App Store Connect ageRatingDeclaration attribute "
        'names and the values are Apple\'s, such as {"ageRatingOverrideV2": "EIGHTEEN_PLUS", '
        '"matureOrSuggestiveThemes": "FREQUENT", "userGeneratedContent": false}. Questions '
        "missing from the file stay as they are. Run it before release_ios when the release "
        "fails for a missing attribute such as userGeneratedContent. The version must already "
        "exist. Without confirm=true it only lists the answers that would change."
    )
)
def update_age_rating_ios(app_identifier: str, answers_path: str, confirm: bool = False) -> str:
    return run_lane(
        "ios",
        "age_rating",
        app_identifier=app_identifier,
        answers=absolute(answers_path),
        dry_run=None if confirm else "true",
    )


@mcp.tool(
    description=(
        "Replace the Google Play store listing screenshots with the images in "
        "folder/<language>/images/<device>Screenshots/, as the resource "
        "upload-app://screenshots/layout describes. The listing changes for everyone after "
        "Google Play reviews it. Without confirm=true it only validates with Google Play and "
        "publishes nothing."
    )
)
def upload_screenshots_android(package_name: str, folder: str, confirm: bool = False) -> str:
    count_screenshots(folder, "images/*Screenshots/*")
    return validate_or_publish(
        "screenshots", confirm, package_name=package_name, folder=absolute(folder)
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
