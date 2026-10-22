# -*- coding: utf-8 -*-
"""(선택 기능) 자주 보내는 서류를 명령 한 번으로 카톡 방에 보낸다.

  python quick_doc.py "받는 사람(방 제목)" 서류키 [--dry]

처음에는 아래 DOCS 표가 비어 있다. 자주 보내는 서류를 직접 한 줄씩 등록해서 쓴다.

순서: 이미 열린 방이면 그대로 → 아니면 검색 결과 1~4번째를 차례로 열어
      방 제목이 받는 사람 이름과 '정확히' 같은 방을 찾는다(다르면 닫고, 끝내 없으면 멈추고 보고)
      → kakao_bg.py send 로 파일 전송(안내 문구 자동) → 캡처 경로와 걸린 시간 출력
--dry 를 붙이면 미리보기만 하고 보내지 않는다.
"""
import glob, json, os, re, subprocess, sys, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# 서류키 → (폴더, 파일 이름 패턴). 폴더 바로 아래에서 이름 앞 날짜(YYMMDD)가 가장 큰 파일을 고른다.
# 예시(앞의 # 를 지우고 내 폴더·파일 이름에 맞게 고친다):
# DOCS = {
#     "자기소개서": (os.path.join(os.environ["USERPROFILE"], "Documents", "서류"), "*자기소개서*.pdf"),
#     "포트폴리오": (os.path.join(os.environ["USERPROFILE"], "Documents", "서류"), "*포트폴리오*.pdf"),
# }
DOCS = {}

# (선택) 방 제목 → 검색어. 카톡 검색이 단톡방을 먼저 보여 줄 때, 그 방만 나오는 짧은 검색어를 적는다.
# 예: SEARCH = {"홍길동 (동아리)": "홍길동"}
SEARCH = {}
# (선택) 내가 부르는 이름 → 실제 방 제목.  예: ALIASES = {"길동": "홍길동 (동아리)"}
ALIASES = {}


def latest(folder, pattern):
    files = [f for f in glob.glob(os.path.join(folder, pattern)) if os.path.isfile(f)]
    files.sort(key=lambda f: (re.match(r"(\d{6})", os.path.basename(f)) or [None, "0"])[1])
    return files[-1] if files else None


def run(args):
    r = subprocess.run([PY, "-X", "utf8"] + args, capture_output=True, encoding="utf-8", errors="replace")
    line = (r.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        return json.loads(line)
    except Exception:
        return {"ok": False, "error": (r.stdout + r.stderr)[-400:]}


def say(**kw):
    print(json.dumps(kw, ensure_ascii=False))


def main():
    t0 = time.time()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if not DOCS:
        say(ok=False, error="DOCS 표가 비어 있습니다 — quick_doc.py 위쪽 DOCS 에 자주 보내는 서류를 먼저 등록하세요"); return
    if len(args) < 2:
        say(ok=False, error="받는 사람과 서류키가 필요합니다", 가능=list(DOCS)); return
    name = ALIASES.get(args[0], args[0])
    key = args[1]
    if key not in DOCS:
        say(ok=False, error=f"모르는 서류: {key}", 가능=list(DOCS)); return
    doc = latest(*DOCS[key])
    if not doc:
        say(ok=False, error=f"{key} 파일을 찾지 못했습니다"); return

    st = run([os.path.join(HERE, "kakao.py"), "status"])
    if not st.get("running"):
        say(ok=False, error="카카오톡 PC가 꺼져 있습니다"); return
    opened_now = False
    if name not in st.get("open_rooms", []):
        import win32gui, win32con
        query = SEARCH.get(name, name)
        tried = []
        for pick in range(1, 5):
            before = set(run([os.path.join(HERE, "kakao.py"), "status"]).get("open_rooms", []))
            o = run([os.path.join(HERE, "kakao.py"), "open", query, "--pick", str(pick)])
            got = o.get("opened")
            if not o.get("ok") or not got:
                break
            if got == name:
                opened_now = True
                break
            tried.append(got)
            if got not in before:  # 잘못 연 방은 바로 닫는다
                h = win32gui.FindWindow(None, got)
                if h:
                    win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0); time.sleep(0.3)
        if not opened_now:
            say(ok=False, step="받는 사람 확인",
                error=f"'{name}' 과 제목이 정확히 같은 방을 찾지 못해 보내지 않았습니다",
                열어_본_방=tried, hint="카톡 방 제목을 그대로 다시 알려 주세요"); return
    t_open = round(time.time() - t0, 1)

    cmd = [os.path.join(HERE, "kakao_bg.py"), "send", name, doc]
    if not dry:
        cmd.append("--yes")
    s = run(cmd)
    say(ok=bool(s.get("ok")), dry=dry, room=name, file=os.path.basename(doc),
        opened_now=opened_now, sec_open=t_open, sec_total=round(time.time() - t0, 1),
        screenshot=s.get("screenshot"), detail=s)


if __name__ == "__main__":
    main()
