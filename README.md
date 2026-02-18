# 카카오톡 내 메시지 삭제 매크로

## 간편화 포인트

- 이제 `삭제 hover 좌표`를 여러 개 입력할 필요 없음
- `삭제 hover` 기준 좌표 1개만 입력
- 답장/이미지/일반 메시지 차이는 스크립트가 Y 오프셋 자동 탐색으로 처리

## 동작 흐름

1. 우클릭
2. 기준 hover 좌표 + 여러 오프셋 후보를 자동 시도
3. `모두에게서 삭제` 클릭 성공 추정 시 스크롤
4. 반복

## 설치

```powershell
pip install -r requirements.txt
```

## 실행

```powershell
python kakao_delete_macro.py
```

## 좌표 입력 (매 실행 2개)

1. 내 말풍선 우클릭 기준 좌표
2. `삭제` hover 기준 좌표 (아무 유형 1개만)

## 단축키

- 시작/일시정지: `F8`
- 종료: `Esc`
- 비상정지: 마우스를 화면 좌상단으로 이동

## 튜닝 포인트

`kakao_delete_macro.py` 상단 상수:

- `DELETE_HOVER_Y_OFFSETS`  : 유형 차이 보정 핵심
- `DELETE_HOVER_WAIT_SEC`   : 너무 빨리 눌릴 때 증가
- `SUBMENU_X_OFFSET_PX`     : "모두에게서 삭제" X 위치 보정
- `SUBMENU_Y_OFFSET_PX`     : "모두에게서 삭제" Y 위치 보정
- `SCROLL_AMOUNT`           : 스크롤 속도
