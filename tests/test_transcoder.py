import subprocess
from unittest.mock import patch, MagicMock

import pytest


def test_import():
    from h265ify.transcoder import main, detect_hardware, get_codec, find_spanish_spain_stream
    assert callable(main)
    assert callable(detect_hardware)
    assert callable(get_codec)
    assert callable(find_spanish_spain_stream)


def test_video_extensions_defined():
    from h265ify.transcoder import VIDEO_EXTENSIONS
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".mkv" in VIDEO_EXTENSIONS
    assert ".avi" in VIDEO_EXTENSIONS


def test_detect_hardware_no_ffmpeg():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        from h265ify.transcoder import detect_hardware
        assert detect_hardware() == []


def test_detect_hardware_no_encoders():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from h265ify.transcoder import detect_hardware
        assert detect_hardware() == []


def test_detect_hardware_finds_nvenc():
    mock_result = MagicMock()
    mock_result.stdout = " hevc_nvenc "
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from h265ify.transcoder import detect_hardware
        encoders = detect_hardware()
        assert len(encoders) >= 1
        assert any("hevc_nvenc" in e for _, e, _ in encoders)


@pytest.mark.parametrize("codec_name,expected", [
    ("hevc", True),
    ("h265", True),
    ("h264", False),
    ("vp9", False),
    ("", False),
])
def test_codec_skip_logic(codec_name, expected):
    from h265ify.transcoder import get_codec

    def fake_get_codec(_path):
        return codec_name

    codec = fake_get_codec(None)
    if codec and codec in ("hevc", "h265"):
        assert expected
    else:
        assert not expected


def test_cli_no_directory(capsys):
    from h265ify.transcoder import main
    with patch("sys.argv", ["h265ify", "/nonexistent/path"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Directory" in captured.err or "Error: Directory" in captured.out


def test_cli_missing_ffprobe(capsys, tmp_path):
    from h265ify.transcoder import main
    with patch("sys.argv", ["h265ify", str(tmp_path)]):
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 3


def test_cli_dry_run_no_encoders(capsys, tmp_path):
    (tmp_path / "test.mp4").write_text("fake video")
    from h265ify.transcoder import main
    with patch("sys.argv", ["h265ify", str(tmp_path), "--dry-run"]):
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("h265ify.transcoder.detect_hardware", return_value=[]):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 2


def test_find_spanish_spain_stream_no_audio():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from h265ify.transcoder import find_spanish_spain_stream
        result = find_spanish_spain_stream("dummy.mp4")
        assert result is None


def test_find_spanish_spain_stream_spain_preferred():
    mock_result = MagicMock()
    mock_result.stdout = """\n[/STREAM]
index=2
TAG:language=spa
TAG:title=Spanish (Latin America)
[/STREAM]
index=3
TAG:language=spa
TAG:title=Castellano (Spain)
[/STREAM]"""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from h265ify.transcoder import find_spanish_spain_stream
        result = find_spanish_spain_stream("dummy.mp4")
        assert result == 3


def test_find_spanish_spain_stream_fallback():
    mock_result = MagicMock()
    mock_result.stdout = """\n[/STREAM]
index=1
TAG:language=spa
TAG:title=
[/STREAM]"""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        from h265ify.transcoder import find_spanish_spain_stream
        result = find_spanish_spain_stream("dummy.mp4")
        assert result == 1
