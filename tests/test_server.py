import subprocess

import pytest

from upload_app_mcp import server


def _tool(name):
    tool = getattr(server, name)
    return getattr(tool, "fn", tool)


@pytest.fixture
def lanes(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    return calls


def test_fastfile_ships_inside_the_package():
    assert (server.ROOT / "fastlane" / "Fastfile").is_file()


def test_upload_android_runs_lane_from_package_dir(lanes):
    assert _tool("upload_android")("/tmp/app.aab", "com.example.app") == "ok"
    cmd, kwargs = lanes[0]
    assert cmd == [
        "fastlane",
        "android",
        "upload",
        "aab:/tmp/app.aab",
        "package_name:com.example.app",
        "track:internal",
    ]
    assert kwargs["cwd"] == server.ROOT
    assert kwargs["stdin"] == subprocess.DEVNULL


def test_promote_android_without_confirm_only_validates(lanes):
    result = _tool("promote_android")("com.example.app", 42, rollout=0.2)
    assert "nothing published" in result
    assert lanes[0][0][2:] == [
        "promote",
        "validate_only:true",
        "package_name:com.example.app",
        "version_code:42",
        "rollout:0.2",
        "from_track:internal",
    ]


def test_promote_android_with_confirm_publishes(lanes):
    _tool("promote_android")("com.example.app", 42, confirm=True)
    assert not any(arg.startswith("validate_only") for arg in lanes[0][0])


@pytest.mark.parametrize("rollout", [0, -0.5, 1.5])
def test_promote_android_rejects_rollout_out_of_range(lanes, rollout):
    with pytest.raises(ValueError, match="rollout"):
        _tool("promote_android")("com.example.app", 42, rollout=rollout, confirm=True)
    assert lanes == []


def test_upload_ios(lanes):
    _tool("upload_ios")("/tmp/app.ipa")
    assert lanes[0][0] == ["fastlane", "ios", "upload", "ipa:/tmp/app.ipa"]


def test_release_ios_without_confirm_runs_nothing(lanes):
    result = _tool("release_ios")("com.example.app", "1.2.0", "15")
    assert "confirm=true" in result
    assert lanes == []


def test_release_ios_with_confirm(lanes):
    _tool("release_ios")("com.example.app", "1.2.0", "15", confirm=True)
    assert lanes[0][0] == [
        "fastlane",
        "ios",
        "release",
        "app_identifier:com.example.app",
        "app_version:1.2.0",
        "build_number:15",
    ]


def test_failed_lane_raises_with_output_tail(monkeypatch):
    output = "\n".join(f"line {i}" for i in range(100))
    monkeypatch.setattr(
        server.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1, stdout=output),
    )
    with pytest.raises(RuntimeError) as error:
        _tool("upload_ios")("/tmp/app.ipa")
    assert str(error.value).splitlines() == [f"line {i}" for i in range(60, 100)]
