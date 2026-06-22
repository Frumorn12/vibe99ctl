from __future__ import annotations

from typer.testing import CliRunner

from vibe99 import __version__
from vibe99.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_command_groups():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("rgb", "screen", "clock", "protocol", "doctor", "info"):
        assert group in result.stdout


def test_rgb_set_dry_run(fake_hid_enumeration):
    fake_hid_enumeration([])  # no hardware -> dry-run still works
    result = runner.invoke(app, ["rgb", "set", "#ff0000"])
    assert result.exit_code == 0
    # The result line and the per-packet hex dump are written to stdout.
    assert "rgb set" in result.output.lower()
    assert "->" in result.output


def test_rgb_set_invalid_color():
    result = runner.invoke(app, ["rgb", "set", "notacolor"])
    assert result.exit_code != 0


def test_screen_upload_image_dry_run(fake_hid_enumeration, tmp_path):
    from PIL import Image
    fake_hid_enumeration([])
    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), (255, 0, 0)).save(img_path)
    result = runner.invoke(app, ["screen", "upload-image", str(img_path)])
    assert result.exit_code == 0
    assert "screen upload-image" in result.output.lower()


def test_clock_sync_dry_run(fake_hid_enumeration):
    fake_hid_enumeration([])
    result = runner.invoke(app, ["clock", "sync"])
    assert result.exit_code == 0
    assert "clock sync" in result.stdout.lower()


def test_protocol_checksum():
    result = runner.invoke(app, ["protocol", "checksum", "01 02 03"])
    assert result.exit_code == 0
    assert "sum8" in result.stdout
    assert "0x06" in result.stdout


def test_list_devices_recognises_real_vibe99(fake_hid_enumeration):
    fake_hid_enumeration(
        [
            {
                "path": b"/dev/hidraw3",
                "vendor_id": 0x05AC,
                "product_id": 0x024F,
                "usage_page": 0xFF13,
                "usage": 1,
                "interface_number": 3,
                "manufacturer_string": "SONiX",
                "product_string": "SONiX Mechlands Vibe99",
                "serial_number": "X",
            }
        ]
    )
    result = runner.invoke(app, ["list-devices"])
    assert result.exit_code == 0
    assert "05ac:024f" in result.output
    assert "confirmed" in result.output


def test_doctor_runs(fake_hid_enumeration):
    fake_hid_enumeration([])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout.lower()
