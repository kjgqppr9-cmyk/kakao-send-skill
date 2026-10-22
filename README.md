# 카톡 보내기 스킬 (kakao-send) — 클로드 코드용

클로드 코드에게 **"카톡으로 홍길동에게 '내일 회의 3시예요' 보내줘"** 라고 말하면,
내 PC 카카오톡에서 그 사람을 찾아 메시지·파일을 보내 주는 스킬입니다.

> 스몰브랜드설계자 AI 특강 수강생용으로 공개한 버전입니다.
> 카카오 공식 API가 아니라 **PC 카카오톡 창을 프로그램이 직접 조작**하는 방식이라 **Windows 전용**입니다.

## 가장 쉬운 설치 — 클로드 코드에 한 줄

클로드 코드를 열고 아래 문장을 그대로 붙여 넣으세요.

```
https://github.com/kjgqppr9-cmyk/kakao-send-skill 저장소의 kakao-send 폴더를 내 %USERPROFILE%\.claude\skills\ 안에 설치하고, pip install pywin32 pillow 까지 해 줘.
```

## 직접 설치 (3단계)

1. 이 페이지 위쪽 초록색 **Code → Download ZIP** 으로 내려받아 압축을 풉니다.
2. 안의 `kakao-send` 폴더를 통째로 `%USERPROFILE%\.claude\skills\` 안에 복사합니다.
   (탐색기 주소창에 `%USERPROFILE%\.claude\skills` 입력 → 폴더가 없으면 만들기)
3. PowerShell 에서 준비물 설치: `pip install pywin32 pillow` (안 되면 `py -m pip install pywin32 pillow`)

그다음 **PC 카카오톡에 로그인**해 두고, 클로드 코드를 **새로 열어** 말하면 됩니다.
처음에는 **"카톡으로 나와의 채팅에 '테스트' 보내줘"** 로 연습해 보세요.

## 꼭 지킬 것

- 보내기 전에 **받는 사람과 내용을 꼭 확인**하세요. 스킬도 확인 없이 보내지 않게 되어 있습니다.
- 모르는 사람·단체방에 대량으로 보내는 용도로 쓰지 마세요.
- 카톡 버전이나 화면 배율(디스플레이 배율)에 따라 버튼 위치가 달라 안 될 수 있습니다. 자세한 대처는 `kakao-send/SKILL.md` 의 '안 될 때'를 보세요.

## 출처 · 라이선스

창 찾기·검색·글 보내기의 Win32 조작 방식은 [kronenz/kakaotalk-mcp](https://github.com/kronenz/kakaotalk-mcp) (MIT) 를 참고했습니다.
이 저장소도 MIT 라이선스입니다. 사용에 따른 책임은 사용자에게 있습니다.
