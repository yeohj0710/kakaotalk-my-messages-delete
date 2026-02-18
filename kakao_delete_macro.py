#!/usr/bin/env python3
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import keyboard
import pyautogui

try:
    from PIL import Image, ImageChops, ImageStat
    PIL_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - import guard for runtime
    Image = Any  # type: ignore[misc,assignment]
    ImageChops = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]
    PIL_IMPORT_ERROR = exc


CAPTURE_KEYS = {"space", "enter"}

# ----- Tuning -----
SCROLL_AMOUNT = 20

MOVE_DURATION_SEC = 0.03
MENU_WAIT_SEC = 0.10
DELETE_HOVER_WAIT_SEC = 0.40
DELETE_HOVER_WAIT_FALLBACK_SEC = 0.55
SUBMENU_STABILIZE_WAIT_SEC = 0.07
AFTER_DELETE_CLICK_WAIT_SEC = 0.22

# submenu click candidate offsets from "delete hover" point
SUBMENU_OFFSETS: list[tuple[int, int]] = [
    (112, 2),
    (112, 6),
    (112, -2),
    (106, 2),
    (118, 2),
]

# message-type variation candidates (general/reply/image) by Y offset
HOVER_Y_OFFSETS = [0, -24, 24, -48, 48, -72, 72, -96, 96, -120, 120]

RETRIES_PER_COMBO = 1
MAX_ATTEMPTS_PER_CYCLE = 18
RETRY_GAP_SEC = 0.08

FOCUS_LEFT_OFFSET_PX = 40
FOCUS_Y_OFFSET_PX = 0
FOCUS_CLICK_WAIT_SEC = 0.06
INTERVAL_SEC = 0.22

# deletion detection (region difference based)
PROBE_BOX_WIDTH = 240
PROBE_BOX_HEIGHT = 160
PROBE_CENTER_X_OFFSET = -90
PROBE_CENTER_Y_OFFSET = 0

DELETE_CHANGE_THRESHOLD = 5.5
DELETE_DETECT_TIMEOUT_SEC = 1.00
DELETE_DETECT_INTERVAL_SEC = 0.10
DELETE_PERSISTENCE_CHECK_SEC = 0.12
DELETE_CONFIRM_RATIO = 0.65

PAUSE_ON_DELETE_FAIL = True

START_PAUSE_KEY = "f8"
QUIT_KEY = "esc"


@dataclass
class Point:
    x: int
    y: int


@dataclass
class MacroConfig:
    target: Point
    delete_hover_base: Point


@dataclass
class AdaptiveState:
    hover_idx: int = 0
    submenu_idx: int = 0
    wait_idx: int = 0


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def hotkey_to_label(key: str) -> str:
    return key.upper() if len(key) <= 3 else key


def wait_capture_key() -> None:
    while True:
        event = keyboard.read_event(suppress=False)
        if event.event_type != keyboard.KEY_DOWN:
            continue

        key = (event.name or "").lower()
        if key in CAPTURE_KEYS:
            return
        if key == QUIT_KEY:
            raise KeyboardInterrupt


def capture_point(title: str) -> Point:
    print(f"\n{title}")
    print(f"[Space/Enter]=capture / [{hotkey_to_label(QUIT_KEY)}]=cancel")
    wait_capture_key()

    x, y = pyautogui.position()
    print(f"captured: ({x}, {y})")
    time.sleep(0.2)
    return Point(x=x, y=y)


def move_and_click(point: Point, button: str = "left") -> None:
    pyautogui.moveTo(point.x, point.y, duration=MOVE_DURATION_SEC)
    pyautogui.click(button=button)


def open_context_menu(target: Point) -> None:
    move_and_click(target, button="right")
    time.sleep(MENU_WAIT_SEC)


def focus_point_from_target(target: Point) -> Point:
    screen_w, screen_h = pyautogui.size()
    x = clamp(target.x - FOCUS_LEFT_OFFSET_PX, 0, screen_w - 1)
    y = clamp(target.y + FOCUS_Y_OFFSET_PX, 0, screen_h - 1)
    return Point(x=x, y=y)


def focus_chat_area(target: Point) -> None:
    move_and_click(focus_point_from_target(target), button="left")
    time.sleep(FOCUS_CLICK_WAIT_SEC)


def hover_point(base: Point, y_offset: int) -> Point:
    screen_w, screen_h = pyautogui.size()
    return Point(
        x=clamp(base.x, 0, screen_w - 1),
        y=clamp(base.y + y_offset, 0, screen_h - 1),
    )


def submenu_click_point(hover: Point, submenu_offset: tuple[int, int]) -> Point:
    screen_w, screen_h = pyautogui.size()
    x_off, y_off = submenu_offset
    return Point(
        x=clamp(hover.x + x_off, 0, screen_w - 1),
        y=clamp(hover.y + y_off, 0, screen_h - 1),
    )


def probe_region(target: Point) -> tuple[int, int, int, int]:
    screen_w, screen_h = pyautogui.size()
    width = min(PROBE_BOX_WIDTH, screen_w)
    height = min(PROBE_BOX_HEIGHT, screen_h)

    center_x = clamp(target.x + PROBE_CENTER_X_OFFSET, 0, screen_w - 1)
    center_y = clamp(target.y + PROBE_CENTER_Y_OFFSET, 0, screen_h - 1)

    left = clamp(center_x - (width // 2), 0, screen_w - width)
    top = clamp(center_y - (height // 2), 0, screen_h - height)
    return left, top, width, height


def capture_probe_gray(target: Point) -> Image.Image:
    left, top, width, height = probe_region(target)
    return pyautogui.screenshot(region=(left, top, width, height)).convert("L")


def change_score(before: Image.Image, after: Image.Image) -> float:
    diff = ImageChops.difference(before, after)
    stat = ImageStat.Stat(diff)
    return float(stat.mean[0])


def detect_deleted(before_probe: Image.Image, target: Point) -> tuple[bool, float]:
    deadline = time.time() + DELETE_DETECT_TIMEOUT_SEC
    best_score = 0.0

    while True:
        after_probe = capture_probe_gray(target)
        score = change_score(before_probe, after_probe)
        best_score = max(best_score, score)

        if score >= DELETE_CHANGE_THRESHOLD:
            time.sleep(DELETE_PERSISTENCE_CHECK_SEC)
            confirm_probe = capture_probe_gray(target)
            confirm_score = change_score(before_probe, confirm_probe)
            best_score = max(best_score, confirm_score)
            if confirm_score >= DELETE_CHANGE_THRESHOLD * DELETE_CONFIRM_RATIO:
                return True, best_score

        if time.time() >= deadline:
            return False, best_score
        time.sleep(DELETE_DETECT_INTERVAL_SEC)


def build_order(total: int, preferred_idx: int) -> list[int]:
    if total <= 0:
        return []
    preferred = clamp(preferred_idx, 0, total - 1)
    return sorted(range(total), key=lambda i: (0 if i == preferred else 1, abs(i - preferred), i))


def try_delete_once(
    target: Point,
    base_hover: Point,
    hover_y_offset: int,
    submenu_offset: tuple[int, int],
    hover_wait: float,
) -> None:
    open_context_menu(target)

    hover = hover_point(base_hover, hover_y_offset)
    pyautogui.moveTo(hover.x, hover.y, duration=MOVE_DURATION_SEC)
    time.sleep(hover_wait)

    submenu = submenu_click_point(hover, submenu_offset)
    pyautogui.moveTo(submenu.x, submenu.y, duration=MOVE_DURATION_SEC)
    time.sleep(SUBMENU_STABILIZE_WAIT_SEC)
    pyautogui.click(button="left")
    time.sleep(AFTER_DELETE_CLICK_WAIT_SEC)

    # close residual context UI and return wheel focus to chat area
    focus_chat_area(target)


def run_cycle(config: MacroConfig, adaptive: AdaptiveState) -> tuple[bool, str]:
    wait_candidates = [DELETE_HOVER_WAIT_SEC, DELETE_HOVER_WAIT_FALLBACK_SEC]

    hover_order = build_order(len(HOVER_Y_OFFSETS), adaptive.hover_idx)
    submenu_order = build_order(len(SUBMENU_OFFSETS), adaptive.submenu_idx)
    wait_order = build_order(len(wait_candidates), adaptive.wait_idx)

    logs: list[str] = []
    attempts = 0

    for w_idx in wait_order:
        hover_wait = wait_candidates[w_idx]

        for h_idx in hover_order:
            y_offset = HOVER_Y_OFFSETS[h_idx]

            for s_idx in submenu_order:
                submenu_offset = SUBMENU_OFFSETS[s_idx]

                for retry in range(1, RETRIES_PER_COMBO + 1):
                    attempts += 1
                    before_probe = capture_probe_gray(config.target)

                    try:
                        try_delete_once(
                            target=config.target,
                            base_hover=config.delete_hover_base,
                            hover_y_offset=y_offset,
                            submenu_offset=submenu_offset,
                            hover_wait=hover_wait,
                        )
                        success, score = detect_deleted(before_probe, config.target)
                        logs.append(
                            "w="
                            f"{hover_wait:.2f},y={y_offset},s={submenu_offset},r={retry},score={score:.2f}"
                        )
                    except Exception as exc:
                        logs.append(
                            "w="
                            f"{hover_wait:.2f},y={y_offset},s={submenu_offset},r={retry},err={exc}"
                        )
                        success = False
                        try:
                            focus_chat_area(config.target)
                        except Exception:
                            pass

                    if success:
                        adaptive.wait_idx = w_idx
                        adaptive.hover_idx = h_idx
                        adaptive.submenu_idx = s_idx
                        return True, "; ".join(logs)

                    if attempts >= MAX_ATTEMPTS_PER_CYCLE:
                        return False, "; ".join(logs)

                    time.sleep(RETRY_GAP_SEC)

    return False, "; ".join(logs)


def calibrate_every_run() -> MacroConfig:
    print("\n=== Coordinate Setup (every run) ===")
    print("Keep KakaoTalk chat window open and fixed.")
    print("This version needs only 2 points.")

    target = capture_point("1/2: right-click safe point near your own bubble")

    print("\nOpen menu once automatically to capture delete-hover base point...")
    time.sleep(0.2)
    open_context_menu(target)

    delete_hover_base = capture_point("2/2: hover point on 'Delete' menu item")
    return MacroConfig(target=target, delete_hover_base=delete_hover_base)


def run_macro(config: MacroConfig) -> None:
    state = {"running": False, "quit": False}
    adaptive = AdaptiveState()
    cycle_count = 0

    def toggle_running() -> None:
        state["running"] = not state["running"]
        print("\nRUN" if state["running"] else "\nPAUSE")

    def request_quit() -> None:
        state["quit"] = True
        state["running"] = False
        print("\nSTOP requested")

    keyboard.add_hotkey(START_PAUSE_KEY, toggle_running)
    keyboard.add_hotkey(QUIT_KEY, request_quit)

    print("\n=== Macro Ready ===")
    print(f"[{hotkey_to_label(START_PAUSE_KEY)}]=start/pause, [{hotkey_to_label(QUIT_KEY)}]=quit")
    print("Emergency stop: move mouse to top-left corner.")

    try:
        while not state["quit"]:
            if not state["running"]:
                time.sleep(0.05)
                continue

            try:
                deleted, debug_log = run_cycle(config, adaptive)
                if not deleted:
                    print("\nDelete not confirmed.")
                    print(f"Debug: {debug_log[-450:]}")
                    if PAUSE_ON_DELETE_FAIL:
                        print("Paused automatically. Adjust constants and press F8.")
                        state["running"] = False
                        continue

                pyautogui.scroll(SCROLL_AMOUNT)
                time.sleep(INTERVAL_SEC)

                cycle_count += 1
                print(f"\rcycles: {cycle_count}", end="", flush=True)
            except pyautogui.FailSafeException:
                print("\nFail-safe triggered. Paused.")
                state["running"] = False
            except Exception as exc:
                print(f"\nCycle error: {exc}")
                state["running"] = False
    finally:
        keyboard.clear_all_hotkeys()
        print("\nMacro ended.")


def main() -> int:
    if PIL_IMPORT_ERROR is not None:
        print("Pillow import failed. Run: pip install -r requirements.txt")
        print(f"detail: {PIL_IMPORT_ERROR}")
        return 1

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.0

    try:
        config = calibrate_every_run()
        run_macro(config)
        return 0
    except KeyboardInterrupt:
        print("\nCanceled by user.")
        return 1
    except Exception as exc:
        print(f"\nFatal error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
