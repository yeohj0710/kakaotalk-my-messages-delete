# KakaoTalk Delete Macro

목표:
- 좌표 입력은 최소화(매 실행 2개만)
- 일반/답장/이미지 메뉴 차이를 자동 탐색으로 흡수
- 실패 시 안전하게 자동 일시정지

## Install

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python kakao_delete_macro.py
```

## Per-run Input (2 points only)

1. 내 말풍선 우측의 안전한 우클릭 기준 좌표
2. 컨텍스트 메뉴에서 `Delete` hover 기준 좌표 1개

나머지는 스크립트가 자동으로 시도:
- 여러 `HOVER_Y_OFFSETS`
- 여러 `SUBMENU_OFFSETS`
- 두 단계 hover 대기시간(`DELETE_HOVER_WAIT_SEC`, `DELETE_HOVER_WAIT_FALLBACK_SEC`)

## Hotkeys

- `F8`: start / pause
- `Esc`: quit
- emergency: mouse to top-left corner

## Safety / Robustness

- 삭제 성공을 화면 변화량으로 검증 (`detect_deleted`)
- 일시적 UI 변화 오탐 방지용 재확인(지속 변화 체크)
- 실패 시 디버그 로그 출력 후 자동 일시정지 (`PAUSE_ON_DELETE_FAIL = True`)
- 성공한 조합(hover/submenu/wait)을 다음 사이클 우선 사용 (adaptive)

## Main Tuning Constants

`kakao_delete_macro.py` 상단:
- `HOVER_Y_OFFSETS`
- `SUBMENU_OFFSETS`
- `DELETE_HOVER_WAIT_SEC`
- `DELETE_HOVER_WAIT_FALLBACK_SEC`
- `DELETE_CHANGE_THRESHOLD`
- `MAX_ATTEMPTS_PER_CYCLE`
- `SCROLL_AMOUNT`
