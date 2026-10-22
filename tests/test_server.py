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


def test_promote_android_passes_release_notes_with_locale(lanes):
    _tool("promote_android")(
        "com.example.app", 42, release_notes="Correções: login", locale="es-419"
    )
    assert lanes[0][0][-2:] == ["release_notes:Correções: login", "locale:es-419"]


def test_update_rollout_android_validates_by_default(lanes):
    result = _tool("update_rollout_android")("com.example.app", 42, rollout=0.5)
    assert "nothing published" in result
    assert lanes[0][0][2:] == [
        "rollout",
        "validate_only:true",
        "package_name:com.example.app",
        "version_code:42",
        "rollout:0.5",
    ]


def test_update_rollout_android_halts(lanes):
    _tool("update_rollout_android")("com.example.app", 42, halt=True, confirm=True)
    assert lanes[0][0][2:] == [
        "rollout",
        "package_name:com.example.app",
        "version_code:42",
        "halt:true",
    ]


@pytest.mark.parametrize("kwargs", [{}, {"rollout": 0.5, "halt": True}])
def test_update_rollout_android_needs_rollout_or_halt(lanes, kwargs):
    with pytest.raises(ValueError, match="either rollout or halt"):
        _tool("update_rollout_android")("com.example.app", 42, **kwargs)
    assert lanes == []


def test_update_rollout_android_rejects_rollout_out_of_range(lanes):
    with pytest.raises(ValueError, match="rollout"):
        _tool("update_rollout_android")("com.example.app", 42, rollout=2)
    assert lanes == []


def test_status_tools(lanes):
    _tool("status_android")("com.example.app")
    _tool("status_ios")("com.example.app")
    assert [cmd for cmd, _ in lanes] == [
        ["fastlane", "android", "status", "package_name:com.example.app"],
        ["fastlane", "ios", "status", "app_identifier:com.example.app"],
    ]


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


def test_release_ios_passes_release_notes(lanes):
    preview = _tool("release_ios")("com.example.app", "1.2.0", "15", release_notes="Novidades")
    assert "What's New" in preview
    _tool("release_ios")("com.example.app", "1.2.0", "15", release_notes="Novidades", confirm=True)
    assert lanes[0][0][-1] == "release_notes:Novidades"


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


def test_upload_android_accepts_custom_track(lanes):
    _tool("upload_android")("/tmp/app.aab", "com.example.app", track="Guia Go Beta Testes")
    assert lanes[0][0][-1] == "track:Guia Go Beta Testes"


def test_production_is_not_a_test_track(lanes):
    with pytest.raises(ValueError, match="test track"):
        _tool("upload_android")("/tmp/app.aab", "com.example.app", track="production")
    with pytest.raises(ValueError, match="test track"):
        _tool("promote_android")("com.example.app", 42, from_track="production")
    assert lanes == []
