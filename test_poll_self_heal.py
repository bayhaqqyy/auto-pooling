from pathlib import Path
import importlib.util


SPEC = importlib.util.spec_from_file_location(
    "poll_danantara", "/home/rafli/auto-pooling/poll_danantara.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_get_next_screenshot_number_continues_existing_sequence(tmp_path: Path):
    (tmp_path / "rafli_14_07_2026_1.png").write_text("x")
    (tmp_path / "rafli_14_07_2026_2.png").write_text("x")
    (tmp_path / "random.txt").write_text("x")

    assert module.get_next_screenshot_number(str(tmp_path)) == 3
    assert module.build_screenshot_path(3, str(tmp_path)).endswith("rafli_14_07_2026_3.png")


def test_get_next_screenshot_number_starts_at_one_when_empty(tmp_path: Path):
    assert module.get_next_screenshot_number(str(tmp_path)) == 1


def test_should_retry_status_only_for_self_heal_failures():
    assert module.should_retry_status("failed") is True
    assert module.should_retry_status("timeout") is True
    assert module.should_retry_status("crashed") is True
    assert module.should_retry_status("success") is False
    assert module.should_retry_status("skipped") is False
