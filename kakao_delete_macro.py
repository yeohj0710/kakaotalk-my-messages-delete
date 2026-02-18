#!/usr/bin/env python3
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import keyboard
import pyautogui
from PIL import Image, ImageChops, ImageStat


CAPTURE_KEYS = {"space", "enter"}

# ====== 사용자 설정 상수 ======
SCROLL_AMOUNT = 24  # 양수=위로 스크롤, 음수=아래로 스크롤

MOVE_DURATION_SEC = 0.03
MENU_WAIT_SEC = 0.08
DELETE_HOVER_WAIT_SEC = 0.34
SUBMENU_STABILIZE_WAIT_SEC = 0.06
AFTER_DELETE_CLICK_WAIT_SEC = 0.20

# "삭제 hover" 기준으로 "모두에게서 삭제" 클릭 오프셋
SUBMENU_X_OFFSET_PX = 112
SUBMENU_Y_OFFSET_PX = 2

# 메시지 유형별 메뉴 차이를 흡수하는 자동 탐색 오프셋(픽셀)
# 일반/답장/이미지 차이를 세로 방향으로 순차 탐색
DELETE_HOVER_Y_OFFSETS = [0, -28, 28, -56, 56, -84, 84, -112, 112]
RETRIES_PER_OFFSET = 2
RETRY_GAP_SEC = 0.08

# 채팅창 포커스 복귀 클릭 오프셋
FOCUS_LEFT_OFFSET_PX = 40
FOCUS_Y_OFFSET_PX = 0
FOCUS_CLICK_WAIT_SEC = 0.06
INTERVAL_SEC = 0.22

# 삭제 성공 판정(화면 변화량 기반)
PROBE_BOX_WIDTH = 220
PROBE_BOX_HEIGHT = 140
DELETE_CHANGE_THRESHOLD = 5.0
DELETE_DETECT_TIMEOUT_SEC = 0.90
DELETE_DETECT_INTERVAL_SEC = 0.10

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


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def wait_capture_action(allow_skip: bool = False) -> str:
    while True:
        event = keyboard.read_event(suppress=False)
        if event.event_type != keyboard.KEY_DOWN:
            continue

        key = (event.name or "").lower()
        if key in CAPTURE_KEYS:
            return "capture"
        if allow_skip and key == "s":
            return "skip"
        if key == QUIT_KEY:
            raise KeyboardInterrupt


def capture_point(
    title: str,
    allow_skip: bool = False,
    skip_point: Optional[Point] = None,
) -> Point:
    print(f"\n{title}")
    if allow_skip:
        print("[Space/Enter]=캡처 / [S]=이전 좌표 재사용 / [Esc]=취소")
    else:
        print("[Space/Enter]=캡처 / [Esc]=취소")

    action = wait_capture_action(allow_skip=allow_skip)
    if action == "skip":
        if skip_point is None:
            raise RuntimeError("재사용할 이전 좌표가 없습니다.")
        print(f"이전 좌표 사용: ({skip_point.x}, {skip_point.y})")
        return skip_point

    x, y = pyautogui.position()
    print(f"좌표 저장: ({x}, {y})")
    time.sleep(0.2)
    return Point(x=x, y=y)


def open_context_menu(target: Point) -> None:
    pyautogui.moveTo(target.x, target.y, duration=MOVE_DURATION_SEC)
    pyautogui.click(button="right")
    time.sleep(MENU_WAIT_SEC)


def focus_point_from_target(target: Point) -> Point:
    screen_w, screen_h = pyautogui.size()
    x = clamp(target.x - FOCUS_LEFT_OFFSET_PX, 0, screen_w - 1)
    y = clamp(target.y + FOCUS_Y_OFFSET_PX, 0, screen_h - 1)
    return Point(x=x, y=y)


def focus_chat_area(target: Point) -> None:
    p = focus_point_from_target(target)
    pyautogui.moveTo(p.x, p.y, duration=MOVE_DURATION_SEC)
    pyautogui.click(button="left")
    time.sleep(FOCUS_CLICK_WAIT_SEC)


def submenu_click_point_from_hover(hover: Point) -> Point:
    screen_w, screen_h = pyautogui.size()
    x = clamp(hover.x + SUBMENU_X_OFFSET_PX, 0, screen_w - 1)
    y = clamp(hover.y + SUBMENU_Y_OFFSET_PX, 0, screen_h - 1)
    return Point(x=x, y=y)


def hover_with_y_offset(base: Point, y_offset: int) -> Point:
    screen_w, screen_h = pyautogui.size()
    x = clamp(base.x, 0, screen_w - 1)
    y = clamp(base.y + y_offset, 0, screen_h - 1)
    return Point(x=x, y=y)


def probe_region_from_target(target: Point) -> tuple[int, int, int, int]:
    screen_w, screen_h = pyautogui.size()
    width = min(PROBE_BOX_WIDTH, screen_w)
    height = min(PROBE_BOX_HEIGHT, screen_h)
    left = clamp(target.x - (width // 2), 0, screen_w - width)
    top = clamp(target.y - (height // 2), 0, screen_h - height)
    return left, top, width, height


def capture_probe_gray(target: Point) -> Image.Image:
    left, top, width, height = probe_region_from_target(target)
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
            return True, best_score
        if time.time() >= deadline:
            return False, best_score
        time.sleep(DELETE_DETECT_INTERVAL_SEC)


def try_delete_with_hover(target: Point, hover: Point) -> None:
    open_context_menu(target)

    pyautogui.moveTo(hover.x, hover.y, duration=MOVE_DURATION_SEC)
    time.sleep(DELETE_HOVER_WAIT_SEC)

    submenu_click = submenu_click_point_from_hover(hover)
    pyautogui.moveTo(submenu_click.x, submenu_click.y, duration=MOVE_DURATION_SEC)
    time.sleep(SUBMENU_STABILIZE_WAIT_SEC)
    pyautogui.click(button="left")
    time.sleep(AFTER_DELETE_CLICK_WAIT_SEC)


def calibrate_every_run() -> MacroConfig:
    print("\n=== 좌표 입력 (매번 실행 시 재입력) ===")
    print("카카오톡 채팅창을 열어두세요.")
    print("이번 버전은 '삭제 hover' 좌표 1개만 입력하면 자동 오프셋 탐색합니다.")

    target = capture_point("1/2 내 말풍선 오른쪽 아래 안전한 우클릭 지점")

    print("\n우클릭 메뉴를 자동으로 띄웁니다.")
    time.sleep(0.2)
    open_context_menu(target)

    delete_hover_base = capture_point(
        "2/2 '삭제' hover 기준 좌표 (아무 유형 1개만 잡아도 됨)"
    )

    return MacroConfig(target=target, delete_hover_base=delete_hover_base)


def offset_order(preferred_idx: int) -> list[int]:
    total = len(DELETE_HOVER_Y_OFFSETS)
    preferred = clamp(preferred_idx, 0, total - 1)
    order = [preferred]
    for i in range(total):
        if i != preferred:
            order.append(i)
    return order


def run_cycle(config: MacroConfig, preferred_offset_idx: int) -> tuple[bool, int, str]:
    logs: list[str] = []

    for idx in offset_order(preferred_offset_idx):
        y_offset = DELETE_HOVER_Y_OFFSETS[idx]
        hover = hover_with_y_offset(config.delete_hover_base, y_offset)

        for retry in range(1, RETRIES_PER_OFFSET + 1):
            before_probe = capture_probe_gray(config.target)
            try_delete_with_hover(config.target, hover)
            focus_chat_area(config.target)
            success, score = detect_deleted(before_probe, config.target)
            logs.append(f"o{y_offset}/r{retry}:{score:.2f}")
            if success:
                return True, idx, ", ".join(logs)
            time.sleep(RETRY_GAP_SEC)

    return False, preferred_offset_idx, ", ".join(logs)


def post_delete_scroll() -> None:
    pyautogui.scroll(SCROLL_AMOUNT)
    time.sleep(INTERVAL_SEC)


def run_macro(config: MacroConfig) -> None:
    state = {"running": False, "quit": False}
    cycle_count = 0
    preferred_offset_idx = 0

    def toggle_running() -> None:
        state["running"] = not state["running"]
        print("\n실행 시작" if state["running"] else "\n일시정지")

    def stop_macro() -> None:
        state["quit"] = True
        state["running"] = False
        print("\n종료 요청됨")

    keyboard.add_hotkey(START_PAUSE_KEY, toggle_running)
    keyboard.add_hotkey(QUIT_KEY, stop_macro)

    print("\n=== 매크로 준비 완료 ===")
    print(f"[{START_PAUSE_KEY.upper()}] 시작/일시정지 | [{QUIT_KEY.upper()}] 종료")
    print("비상정지: 마우스를 화면 좌상단으로 이동 (PyAutoGUI fail-safe)")
    print("카카오톡 창에 포커스를 두고 시작하세요.")

    try:
        while not state["quit"]:
            if not state["running"]:
                time.sleep(0.05)
                continue

            try:
                deleted, used_offset_idx, debug_log = run_cycle(
                    config=config,
                    preferred_offset_idx=preferred_offset_idx,
                )
                if not deleted:
                    print(f"\n삭제 실패 추정. 시도 로그: {debug_log}")
                    if PAUSE_ON_DELETE_FAIL:
                        print("자동 일시정지됨. 상단 상수 조정 후 F8로 재시작하세요.")
                        state["running"] = False
                        continue
                else:
                    preferred_offset_idx = used_offset_idx

                post_delete_scroll()
                cycle_count += 1
                print(f"\r반복 횟수: {cycle_count}", end="", flush=True)
            except pyautogui.FailSafeException:
                print("\n비상정지 감지됨. 일시정지합니다.")
                state["running"] = False
            except Exception as exc:
                print(f"\n반복 중 오류: {exc}")
                state["running"] = False
    finally:
        keyboard.clear_all_hotkeys()
        print("\n매크로 종료")


def main() -> int:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.0

    try:
        config = calibrate_every_run()
        run_macro(config)
        return 0
    except KeyboardInterrupt:
        print("\n사용자 취소")
        return 1
    except Exception as exc:
        print(f"\n치명적 오류: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
