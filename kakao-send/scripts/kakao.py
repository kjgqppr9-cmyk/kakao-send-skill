# -*- coding: utf-8 -*-
"""카카오톡 PC 보내기 도구 (Windows 전용).

창 찾기·검색·읽기·글 보내기의 Win32 조작은 kronenz/kakaotalk-mcp (MIT) 의 방식을 참고해 옮겼다.
여기에 더한 것: 검색 결과·대화방 화면 캡처(사람이 맞는지 눈으로 확인), 방 제목 정확 일치 검사,
파일 첨부(CF_HDROP), --yes 없이는 절대 보내지 않는 안전장치. 여러 방 한꺼번에 보내기는 넣지 않는다.

사용 (PowerShell):
  python kakao.py status
  python kakao.py search "이름"                  # 검색 결과 화면 캡처 → 후보 확인용
  python kakao.py open "이름" [--pick N]         # N번째 검색 결과 열기 (기본 1)
  python kakao.py peek "방 제목" [--lines 40]     # 최근 대화 글 + 방 화면 캡처
  python kakao.py send-text "방 제목" --text-file 글.txt [--yes]
  python kakao.py send-file "방 제목" "C:\\경로\\파일.pdf" [--yes]
출력은 모두 JSON 한 줄(UTF-8).
"""
import argparse, ctypes, io, json, os, struct, sys, time
import win32api, win32clipboard, win32con, win32gui, win32process

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
U = ctypes.windll.user32
MAIN_CLASS, MAIN_TITLE = "EVA_Window_Dblclk", "카카오톡"
EDIT_CLASS, LIST_CLASS = "RICHEDIT50W", "EVA_VH_ListControl_Dblclk"
KEYUP, VK_RETURN, VK_CONTROL, VK_DOWN, VK_ESC = 0x0002, 0x0D, 0x11, 0x28, 0x1B
SHOT_DIR = os.path.join(os.environ.get("TEMP", "."), "kakao_send")
os.makedirs(SHOT_DIR, exist_ok=True)


def out(**kw):
    print(json.dumps(kw, ensure_ascii=False)); sys.exit(0 if kw.get("ok", True) else 1)


# ── 창 ─────────────────────────────────────────────
def main_window():
    return win32gui.FindWindow(MAIN_CLASS, MAIN_TITLE) or None


def chat_windows():
    """열린 대화방 창 — 입력창(RICHEDIT50W)이 있는 창만 대화방으로 인정한다(사진 보기 창 등을 방으로 오인하지 않게)."""
    m = main_window(); res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == MAIN_CLASS and h != m:
            t = win32gui.GetWindowText(h)
            if t and t != MAIN_TITLE and child(h, EDIT_CLASS): res.append({"hwnd": h, "title": t})
        return True
    win32gui.EnumWindows(cb, None); return res


def kakao_pid():
    m = main_window()
    return win32process.GetWindowThreadProcessId(m)[1] if m else None


def popups():
    """앞을 막을 수 있는 카카오톡의 다른 창(사진 보기·확인 창 등). 본창·대화방·본창 안에 붙은 띠(광고)는 뺀다.
    9/30: 예전 코드가 대화 목록 가운데를 눌러 사진 말풍선이 열렸고, 그 '사진 보기' 창이 앞을 막아 실패했다."""
    m = main_window(); pid = kakao_pid()
    if not m: return []
    ml, mt, mr, mb = win32gui.GetWindowRect(m)
    rooms = {w["hwnd"] for w in chat_windows()}
    res = []
    def cb(h, _):
        if h == m or h in rooms or not win32gui.IsWindowVisible(h): return True
        if win32process.GetWindowThreadProcessId(h)[1] != pid: return True
        l, t, r, b = win32gui.GetWindowRect(h)
        if r - l < 60 or b - t < 60: return True
        if l >= ml - 2 and t >= mt - 2 and r <= mr + 2 and b <= mb + 2: return True  # 본창 안의 띠
        res.append({"hwnd": h, "class": win32gui.GetClassName(h), "title": win32gui.GetWindowText(h), "size": [r - l, b - t]})
        return True
    win32gui.EnumWindows(cb, None); return res


def stop_if_popups(where):
    ps = popups()
    if ps:
        from PIL import ImageGrab
        shots = []
        for p in ps[:3]:
            f = os.path.join(SHOT_DIR, f"popup_{time.strftime('%H%M%S')}_{p['hwnd']:x}.png")
            try: ImageGrab.grab(bbox=win32gui.GetWindowRect(p["hwnd"]), all_screens=True).save(f); shots.append(f)
            except Exception: pass
        out(ok=False, error=f"카카오톡에 다른 창(사진 보기·확인 창 등)이 떠 있어 {where} 전에 멈췄습니다 — 캡처를 보고 사용자에게 닫아 달라고 하거나, 사진 보기 창이면 닫아도 되는지 묻는다",
            popups=[{k: v for k, v in p.items() if k != "hwnd"} for p in ps], screenshots=shots)


def find_chat(title):
    for w in chat_windows():
        if w["title"] == title: return w["hwnd"]
    return None


def child(parent, cls, name_part=None):
    found = []
    def cb(h, _):
        if win32gui.GetClassName(h) == cls and (name_part is None or name_part in win32gui.GetWindowText(h)):
            found.append(h); return False
        return True
    try: win32gui.EnumChildWindows(parent, cb, None)
    except Exception: pass
    return found[0] if found else None


def front(h):
    U.ShowWindow(h, 9)
    U.keybd_event(0x12, 0, 0, 0); U.keybd_event(0x12, 0, KEYUP, 0)
    U.SetForegroundWindow(h)
    U.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0043); U.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0043)
    for _ in range(10):  # 고정 0.25초 대신: 앞에 오는 즉시 진행(최대 0.5초)
        if U.GetForegroundWindow() == h: time.sleep(0.05); return True
        time.sleep(0.05)
    return False


def ensure_front(h):
    """맨 앞에 온 게 확인될 때만 진행. 아니면 클릭·키 입력 없이 멈춘다(다른 창을 누르는 사고 방지)."""
    if U.GetForegroundWindow() == h: return True  # 이미 맨 앞이면 다시 가져오지 않는다
    for _ in range(3):
        if front(h): return True
        time.sleep(0.3)
    fg = U.GetForegroundWindow()
    out(ok=False, error="카카오톡 창을 맨 앞으로 가져오지 못해 아무것도 누르지 않고 멈췄습니다(화면 잠금·다른 창 확인)",
        foreground=[win32gui.GetClassName(fg), win32gui.GetWindowText(fg)],
        kakao_popups=[{k: v for k, v in p.items() if k != "hwnd"} for p in popups()])


def edit_text(h):
    """다른 프로그램의 입력칸 글자 읽기 (GetWindowText 는 남의 입력칸을 못 읽음 → WM_GETTEXT)."""
    n = U.SendMessageW(h, 0x000E, 0, 0) + 1
    buf = ctypes.create_unicode_buffer(n)
    U.SendMessageW(h, 0x000D, n, buf)
    return buf.value


def key(vk):
    U.keybd_event(vk, 0, 0, 0); time.sleep(0.02); U.keybd_event(vk, 0, KEYUP, 0); time.sleep(0.03)


def ctrl(vk):
    U.keybd_event(VK_CONTROL, 0, 0, 0); time.sleep(0.02); key(vk); U.keybd_event(VK_CONTROL, 0, KEYUP, 0); time.sleep(0.05)


def focus_ctrl(ctl):
    """마우스 클릭 없이 컨트롤에 키보드 초점 주기 — 대화 목록 가운데를 누르면 말풍선의 '열기' 링크 등을 누를 수 있다."""
    my = ctypes.windll.kernel32.GetCurrentThreadId()
    tgt = U.GetWindowThreadProcessId(ctl, None)
    U.AttachThreadInput(my, tgt, True); U.SetFocus(ctl); U.AttachThreadInput(my, tgt, False)
    time.sleep(0.15)


def copy_log(h):
    """대화 기록 전체 복사(Ctrl+A → Ctrl+C). 비면 두 번 더 시도."""
    lst = child(h, LIST_CLASS)
    if not lst: return ""
    for _ in range(3):
        try:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.CloseClipboard()
        except Exception: pass
        focus_ctrl(lst); ctrl(0x41); ctrl(0x43); time.sleep(0.3)
        txt = clip_read()
        if txt.strip(): return txt
        time.sleep(0.4)
    return ""


def click_center(h):
    l, t, r, b = win32gui.GetWindowRect(h)
    U.SetCursorPos((l + r) // 2, (t + b) // 2)
    U.mouse_event(0x0002, 0, 0, 0, 0); U.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(0.1)


def shot(h, name):
    from PIL import ImageGrab
    ensure_front(h); time.sleep(0.3)
    rect = win32gui.GetWindowRect(h)
    p = os.path.join(SHOT_DIR, f"{name}_{time.strftime('%H%M%S')}.png")
    ImageGrab.grab(bbox=rect, all_screens=True).save(p)
    return p


# ── 클립보드 ────────────────────────────────────────
def clip_text(t):
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(t, win32clipboard.CF_UNICODETEXT); win32clipboard.CloseClipboard()


def clip_read():
    for _ in range(8):
        try:
            win32clipboard.OpenClipboard()
            try: return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or ""
            finally: win32clipboard.CloseClipboard()
        except Exception: time.sleep(0.1)
    return ""


def clip_files(paths):
    # DROPFILES 구조체(20바이트) + 유니코드 경로 목록(각각 \0, 끝에 \0 하나 더)
    body = ("\0".join(paths) + "\0\0").encode("utf-16-le")
    data = struct.pack("<IiiII", 20, 0, 0, 0, 1) + body
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_HDROP, data); win32clipboard.CloseClipboard()


# ── 명령 ───────────────────────────────────────────
def cmd_status(a):
    m = main_window()
    out(ok=bool(m), running=bool(m), open_rooms=[w["title"] for w in chat_windows()],
        note=None if m else "카카오톡 PC가 꺼져 있거나 로그인 전입니다")


def _search(name):
    m = main_window()
    if not m: out(ok=False, error="카카오톡 PC가 꺼져 있습니다")
    stop_if_popups("검색")
    ensure_front(m)
    view = child(m, "EVA_Window", "ChatRoomListView")
    if not view or not win32gui.IsWindowVisible(view):
        out(ok=False, error="채팅 탭이 아닙니다 — 카카오톡에서 '채팅' 탭을 열어 두세요")
    # 검색이 열려 있으면 닫고, 위쪽 '채팅 | 오픈채팅' 중 '채팅'을 눌러 일반 대화방에서 찾는다
    key(VK_ESC); time.sleep(0.2)
    vl, vt, vr, vb = win32gui.GetWindowRect(view)
    U.SetCursorPos(vl + 36, vt + 24); U.mouse_event(0x0002, 0, 0, 0, 0); U.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.3)
    ctrl(0x46)  # Ctrl+F
    time.sleep(0.35)
    edit = child(view, "Edit")
    if not edit: out(ok=False, error="검색창을 찾지 못했습니다")
    win32api.SendMessage(edit, 0x00B1, 0, -1); win32api.SendMessage(edit, 0x0303, 0, 0)
    for ch in name:
        win32api.SendMessage(edit, 0x0102, ord(ch), 0); time.sleep(0.02)
    time.sleep(1.0)
    return m


def cmd_search(a):
    m = _search(a.name)
    p = shot(m, "search")
    out(ok=True, searched=a.name, screenshot=p,
        next="캡처를 보고 후보 수·마지막 대화 시각을 확인한 뒤 open --pick N")


def cmd_open(a):
    before = {w["hwnd"] for w in chat_windows()}
    m = _search(a.name)
    ensure_front(m)   # 10/1: 검색 뒤 카톡이 뒤로 밀리면 Enter 가 다른 창으로 가서 방이 안 열렸다
    for _ in range(max(0, a.pick - 1)):
        key(VK_DOWN); time.sleep(0.1)
    key(VK_RETURN)
    # 고정 1초 대신: 새 대화방 창이 뜨는 즉시 진행(최대 3초). 이미 열려 있던 방이면 3초 뒤 제목으로 찾는다
    new = wait_for(lambda: [w for w in chat_windows() if w["hwnd"] not in before], 3, 0.1) or []
    rooms = new or [w for w in chat_windows() if a.name in w["title"]]
    if not rooms: out(ok=False, error="대화방이 열리지 않았습니다", screenshot=shot(m, "open_fail"))
    out(ok=True, opened=rooms[0]["title"], exact=(rooms[0]["title"] == a.name))


def cmd_peek(a):
    stop_if_popups("대화 확인")
    h = find_chat(a.title)
    if not h: out(ok=False, error=f"'{a.title}' 대화방 창이 열려 있지 않습니다", open_rooms=[w["title"] for w in chat_windows()])
    ensure_front(h)
    txt = copy_log(h)
    lines = [l for l in txt.replace("\r", "").split("\n") if l.strip()]
    out(ok=True, title=a.title, recent=lines[-a.lines:], total_lines=len(lines), screenshot=shot(h, "room"))


def _focus_edit(h):
    edit = child(h, EDIT_CLASS)
    if not edit: out(ok=False, error="입력창을 찾지 못했습니다")
    ensure_front(h)
    # 입력창은 클릭한다 — SetFocus 만으로는 초점이 대화 목록에 남아 붙여넣기가 안 됐다(9/30 실측).
    # 입력창(글쓰기 칸)에는 말풍선이 없어 눌러도 안전. 대화 목록은 절대 클릭하지 않는다(사진 보기 창이 열림).
    click_center(edit)
    return edit


def _check_room(title):
    stop_if_popups("보내기")
    h = find_chat(title)
    if not h:
        out(ok=False, error=f"'{title}' 제목과 정확히 같은 대화방 창이 없습니다", open_rooms=[w["title"] for w in chat_windows()])
    return h


IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic"}

# 보내는 모든 메시지 끝에 붙는 안내 문구. 파일만 보낼 때는 이 문구를 글로 뒤따라 보낸다.
# AI 가 대신 보냈다는 것을 받는 사람이 알 수 있게 붙여 두기를 권한다. 원하는 말로 바꿔도 된다.
SIGN = "-AI 비서가 대신 보낸 메시지입니다. 실수가 있을 수 있으니 양해 부탁드립니다."


# (선택) 짧은 문구를 쓸 방 — 방 제목과 정확히 같을 때만. 예: SHORT_SIGN_ROOMS = {"우리 동아리 공지방"}
SIGN_SHORT = "-AI 비서가 대신 올렸습니다"
SHORT_SIGN_ROOMS = set()


def sign_for(room=None):
    return SIGN_SHORT if room in SHORT_SIGN_ROOMS else SIGN


def with_sign(text, room=None):
    sign = sign_for(room)
    return text if sign in text else text.rstrip() + "\n\n" + sign


def log_lines(h):
    """대화방 기록 전체를 복사해 줄 목록으로 (Ctrl+A → Ctrl+C)."""
    ensure_front(h)
    return [l for l in copy_log(h).replace("\r", "").split("\n") if l.strip()]


def cmd_send_text(a):
    text = io.open(a.text_file, encoding="utf-8").read().rstrip("\n") if a.text_file else a.text
    if not text: out(ok=False, error="보낼 글이 비었습니다")
    text = with_sign(text, a.title)
    h = _check_room(a.title)
    if not a.yes:
        out(ok=True, dry_run=True, room=a.title, text=text, note="--yes 를 붙여야 실제로 보냅니다")
    ok = paste_send(h, a.title, text)
    out(ok=ok, sent=ok, room=a.title, chars=len(text),
        note=None if ok else "대화 기록에서 방금 글을 찾지 못했습니다 — 화면 확인 필요")


def paste_send(h, title, text):
    """글을 붙여 넣고 Enter → 대화 기록에서 첫 줄이 새로 올라왔는지 확인해 True/False."""
    _focus_edit(h)
    if win32gui.GetWindowText(U.GetForegroundWindow()) != title:
        out(ok=False, error="앞에 있는 창이 받는 방이 아니라서 멈췄습니다")
    clip_text(text); time.sleep(0.05); ctrl(0x56); time.sleep(0.15); key(VK_RETURN)
    time.sleep(0.8)
    first = text.strip().split("\n")[0].strip()
    tail = "\n".join(copy_log(h).replace("\r", "").split("\n")[-(text.count("\n") + 4):])
    return first[:30] in tail


def wait_for(pred, timeout, step=0.05):
    """조건이 참이 되는 즉시 돌려준다(고정 대기 대신). 시간 안에 안 되면 None."""
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v: return v
        time.sleep(step)
    return None


def attach_one(h, title, p, pid):
    """파일 1개: 파일 아이콘 → '열기' 창에 경로 → 열기 → '파일 전송' 확인 창의 전송 버튼. 기록 확인은 하지 않는다(마지막에 한 번)."""
    ensure_front(h)
    if win32gui.GetWindowText(U.GetForegroundWindow()) != title:
        out(ok=False, error="앞에 있는 창이 받는 방이 아니라서 멈췄습니다")
    # 입력창 아래 아이콘 줄의 세 번째(파일) 아이콘 — 창 왼쪽 아래 기준 (88, -24). Ctrl+T·클립보드 파일 붙여넣기는 안 됨(9/30 실측)
    l, t, r, b = win32gui.GetWindowRect(h)
    U.SetCursorPos(l + 88, b - 24); U.mouse_event(0x0002, 0, 0, 0, 0); U.mouse_event(0x0004, 0, 0, 0, 0)

    def fg_dialog():
        fg = U.GetForegroundWindow()
        return fg if fg and fg != h and win32gui.GetClassName(fg) == "#32770" else None
    dlg = wait_for(fg_dialog, 6)
    if not dlg:
        out(ok=False, error="파일 선택 창이 열리지 않았습니다",
            foreground=[win32gui.GetClassName(U.GetForegroundWindow()), win32gui.GetWindowText(U.GetForegroundWindow())])

    # 파일 이름 칸 = 컨트롤 1148 (ComboBoxEx32 > ComboBox > Edit). 창이 막 뜨면 초기화되며 지워지므로
    # 넣고 → 읽어서 확인 → 0.3초 뒤 한 번 더 읽어 그대로면 진행 (예전: 고정 1초 + 0.4초)
    def put_path():
        cbx = win32gui.GetDlgItem(dlg, 1148)
        fe = child(cbx, "Edit") if cbx else None
        if not fe: return None
        if edit_text(fe) != p:
            win32api.SendMessage(fe, win32con.WM_SETTEXT, 0, p); time.sleep(0.1)
        if edit_text(fe) != p: return None
        time.sleep(0.3)
        return fe if edit_text(fe) == p else None
    fe = wait_for(put_path, 5, 0.15)
    if not fe:
        win32api.PostMessage(win32gui.GetDlgItem(dlg, 2), win32con.BM_CLICK, 0, 0)  # 취소
        out(ok=False, error="파일 선택 창에 경로를 넣지 못해 취소했습니다")
    win32api.PostMessage(win32gui.GetDlgItem(dlg, 1), win32con.BM_CLICK, 0, 0)  # '열기'

    # '파일 전송 — N개 전송' 확인 창(제목 없는 EVA_Window_Dblclk). Enter 는 안 먹음 → 아래쪽 가운데 전송 버튼 클릭
    def fg_confirm():
        fg = U.GetForegroundWindow()
        return fg if (fg and fg not in (h, dlg) and win32gui.GetClassName(fg) == MAIN_CLASS
                      and win32gui.GetWindowText(fg) == "" and win32process.GetWindowThreadProcessId(fg)[1] == pid) else None
    conf = wait_for(fg_confirm, 6)
    if not conf:
        out(ok=False, error="'파일 전송' 확인 창이 뜨지 않았습니다 — 보내지 않았을 수 있음", screenshot=shot(h, "file_fail"))
    time.sleep(0.25)  # 버튼이 그려질 시간
    cl, ct, cr, cb_ = win32gui.GetWindowRect(conf)
    U.SetCursorPos((cl + cr) // 2, cb_ - 42); U.mouse_event(0x0002, 0, 0, 0, 0); U.mouse_event(0x0004, 0, 0, 0, 0)
    closed = wait_for(lambda: not win32gui.IsWindowVisible(conf), 5)  # 예전: 고정 2초
    return {"file": os.path.basename(p), "confirm_closed": bool(closed)}


def cmd_send(a):
    """파일(여러 개 가능) → 글(끝에 안내 문구) 을 한 번에 보내고, 마지막에 기록을 한 번 읽어 모두 확인한다.
    사진은 1:1 방에서 '다음 글을 보낸 뒤에야' 기록에 잡히므로(9/30 실측), 글까지 보낸 뒤 확인하면 기다림이 거의 없다.
    글이 없으면 안내 문구만 글로 보낸다(안내 문구는 항상)."""
    t0 = time.time(); tm = {}
    paths = [os.path.abspath(p) for p in (a.paths or [])]
    miss = [p for p in paths if not os.path.isfile(p)]
    if miss: out(ok=False, error="파일이 없습니다", missing=miss)
    body = ""
    if getattr(a, "text_file", None): body = io.open(a.text_file, encoding="utf-8").read().rstrip("\n")
    elif getattr(a, "text", None): body = a.text
    text = with_sign(body, a.title) if body.strip() else sign_for(a.title)
    if not paths and not body.strip(): out(ok=False, error="보낼 글도 파일도 없습니다")
    h = _check_room(a.title)
    if not a.yes:
        out(ok=True, dry_run=True, room=a.title, files=paths, text=text, note="--yes 를 붙여야 실제로 보냅니다(파일 먼저, 이어서 글)")
    pid = win32process.GetWindowThreadProcessId(h)[1]
    ensure_front(h)
    before = len(log_lines(h)); tm["준비"] = round(time.time() - t0, 1)
    steps = [attach_one(h, a.title, p, pid) for p in paths]; tm["파일"] = round(time.time() - t0, 1)
    _focus_edit(h)
    if win32gui.GetWindowText(U.GetForegroundWindow()) != a.title:
        out(ok=False, error="앞에 있는 창이 받는 방이 아니라서 멈췄습니다(파일은 보냈을 수 있음)", steps=steps)
    clip_text(text); time.sleep(0.05); ctrl(0x56); time.sleep(0.1); key(VK_RETURN); tm["글"] = round(time.time() - t0, 1)

    first = text.strip().split("\n")[0].strip()[:30]
    def check():
        new = log_lines(h)[before:]
        photos = sum(1 for l in new if l.rstrip().endswith("] 사진") or l.strip() == "사진")
        got = []
        for p in paths:
            nm = os.path.basename(p)
            if os.path.splitext(nm)[1].lower() in IMG_EXT:
                if photos > 0: photos -= 1; got.append(nm)
            elif any(f"파일: {nm}" in l for l in new): got.append(nm)
        text_ok = any(first in l for l in new)
        return (got, text_ok) if (len(got) == len(paths) and text_ok) else None
    res = wait_for(check, 12, 0.6)
    if not res:  # 마지막으로 한 번 더 읽어 무엇이 빠졌는지
        new = log_lines(h)[before:]
        res = ([os.path.basename(p) for p in paths if any(os.path.basename(p) in l for l in new)], any(first in l for l in new))
        ok = False
    else:
        ok = True
    tm["확인"] = round(time.time() - t0, 1)
    out(ok=ok, sent=ok, room=a.title, verified_files=res[0], text_sent=res[1], steps=steps, seconds=tm,
        screenshot=None if ok else shot(h, "send_check"),
        note=None if ok else "기록에서 일부를 확인 못 함 — screenshot 을 Read 로 보고 말풍선이 있으면 전송된 것. 없으면 사용자에게 알린다")


def cmd_send_file(a):
    a.text = None; a.text_file = None
    cmd_send(a)


def cmd_send_text_fast(a):
    a.paths = []
    cmd_send(a)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    s = sp.add_parser("search"); s.add_argument("name")
    s = sp.add_parser("open"); s.add_argument("name"); s.add_argument("--pick", type=int, default=1)
    s = sp.add_parser("peek"); s.add_argument("title"); s.add_argument("--lines", type=int, default=40)
    s = sp.add_parser("send-text"); s.add_argument("title"); s.add_argument("--text"); s.add_argument("--text-file"); s.add_argument("--yes", action="store_true")
    s = sp.add_parser("send-file"); s.add_argument("title"); s.add_argument("paths", nargs="+"); s.add_argument("--yes", action="store_true")
    s.add_argument("--sign-follows", action="store_true", help="(옛 옵션, 무시됨 — send 명령이 알아서 한 번만 붙인다)")
    s = sp.add_parser("send", help="파일(선택) + 글(선택)을 한 번에 — 권장")
    s.add_argument("title"); s.add_argument("paths", nargs="*"); s.add_argument("--text"); s.add_argument("--text-file")
    s.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    {"status": cmd_status, "search": cmd_search, "open": cmd_open, "peek": cmd_peek,
     "send-text": cmd_send_text_fast, "send-file": cmd_send_file, "send": cmd_send}[a.cmd](a)


if __name__ == "__main__":
    main()
