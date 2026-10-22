# 커서·키보드를 쓰지 않고(창 메시지만으로) 카톡을 조작한다 
#   open : 검색 첫 결과를 신호로 더블클릭      send : 파일 묶음 → 업로드 끝 확인 → 글
import sys, os, time, uuid
sys.path.insert(0, os.path.dirname(__file__))
import kakao as K
import win32gui, win32api, win32con, win32process

EMPTY = ("", "메시지 입력")          # 입력창이 빈 상태(자리표시 글 포함)


def post_click(h, x, y):
    """클라이언트 좌표 (x, y) 에 클릭 신호. 커서는 움직이지 않는다."""
    lp = (y << 16) | (x & 0xFFFF)
    win32api.PostMessage(h, win32con.WM_MOUSEMOVE, 0, lp)
    win32api.PostMessage(h, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp); time.sleep(0.05)
    win32api.PostMessage(h, win32con.WM_LBUTTONUP, 0, lp)


def bg_open(name):
    m = K.main_window()
    if not m: return {"ok": False, "error": "카카오톡 PC가 꺼져 있습니다"}
    view = K.child(m, "EVA_Window", "ChatRoomListView")
    edit = K.child(view, "Edit") if view else None
    if not edit:
        return {"ok": False, "error": "검색창 없음(검색을 연 적이 없으면 Edit 이 안 생김 — kakao.py search 를 한 번)"}
    before = {w["hwnd"] for w in K.chat_windows()}
    win32api.SendMessage(edit, win32con.WM_SETTEXT, 0, "")
    for ch in name:
        win32api.SendMessage(edit, win32con.WM_CHAR, ord(ch), 0); time.sleep(0.02)
    time.sleep(1.0)
    lst = K.child(view, "EVA_VH_ListControl_Dblclk", "SearchListCtrl")
    if not lst or not win32gui.IsWindowVisible(lst):
        return {"ok": False, "error": "검색 결과 목록이 보이지 않습니다"}
    lp = (33 << 16) | 150                       # 첫 결과 줄(목록 기준 x150, y33). Enter 신호는 안 먹음(10/1 실측)
    win32api.PostMessage(lst, win32con.WM_LBUTTONDOWN, 1, lp); win32api.PostMessage(lst, win32con.WM_LBUTTONUP, 0, lp)
    win32api.PostMessage(lst, win32con.WM_LBUTTONDBLCLK, 1, lp); win32api.PostMessage(lst, win32con.WM_LBUTTONUP, 0, lp)
    new = K.wait_for(lambda: [w for w in K.chat_windows() if w["hwnd"] not in before], 3, 0.1) or []
    return {"ok": bool(new), "opened": new[0]["title"] if new else None}


def owned_by(w, h, pid):
    """카톡 프로세스의 창이고, 소유자를 따라 올라가면 받는 방(h)에 닿는가 — 다른 방·다른 앱의 창을 건드리지 않게"""
    if win32process.GetWindowThreadProcessId(w)[1] != pid: return False
    o = w
    for _ in range(4):
        o = win32gui.GetWindow(o, win32con.GW_OWNER)
        if not o: return False
        if o == h: return True
    return False


def bg_attach_many(h, paths, pid):
    """파일 여러 개를 '열기' 창에서 한 번에 골라 'N개 전송' 확인 창의 버튼까지 — 커서를 쓰지 않는다.
    '열기' 창은 카톡이 띄우는 모달 창이라 1~2초 맨 앞에 나온다(피할 수 없음)."""
    folder = os.path.dirname(paths[0])
    if any(os.path.dirname(p) != folder for p in paths):
        return {"ok": False, "error": "한 번에 보낼 파일은 같은 폴더에 있어야 합니다"}
    _, _, cw, ch = win32gui.GetClientRect(h)
    before = set()
    win32gui.EnumWindows(lambda w, _: before.add(w), None)

    def new_wins(pred):
        found = []
        def cb(w, _):
            if w not in before and win32gui.IsWindowVisible(w) and pred(w): found.append(w)
        win32gui.EnumWindows(cb, None)
        return found

    post_click(h, 88, ch - 24)                  # 파일 아이콘 (클라이언트 기준 왼쪽 88, 아래 24)
    def dialog():
        f = new_wins(lambda w: win32gui.GetClassName(w) == "#32770" and owned_by(w, h, pid))
        return f[0] if len(f) == 1 else None
    dlg = K.wait_for(dialog, 6)
    if not dlg:
        stray = new_wins(lambda w: win32gui.GetClassName(w) == "#32770")
        return {"ok": False, "error": "받는 방의 파일 선택 창을 하나로 특정하지 못했습니다", "stray_dialogs": len(stray)}

    def fe():
        cbx = win32gui.GetDlgItem(dlg, 1148); return K.child(cbx, "Edit") if cbx else None
    def put(text):
        e = fe()
        if not e: return False
        if K.edit_text(e) != text:
            win32api.SendMessage(e, win32con.WM_SETTEXT, 0, text); time.sleep(0.1)
        if K.edit_text(e) != text: return False
        time.sleep(0.3); return K.edit_text(e) == text
    def cancel(msg):
        win32api.PostMessage(win32gui.GetDlgItem(dlg, 2), win32con.BM_CLICK, 0, 0)
        return {"ok": False, "error": msg}
    if not K.wait_for(lambda: put(folder), 5, 0.15): return cancel("폴더 경로를 넣지 못해 취소")
    win32api.PostMessage(win32gui.GetDlgItem(dlg, 1), win32con.BM_CLICK, 0, 0)   # 폴더로 이동
    time.sleep(0.8)
    multi = " ".join('"%s"' % os.path.basename(p) for p in paths) if len(paths) > 1 else os.path.basename(paths[0])
    if not K.wait_for(lambda: put(multi), 5, 0.15): return cancel("파일 이름을 넣지 못해 취소")
    win32api.PostMessage(win32gui.GetDlgItem(dlg, 1), win32con.BM_CLICK, 0, 0)   # 열기

    def confirm():
        f = new_wins(lambda w: w != h and win32gui.GetClassName(w) == K.MAIN_CLASS
                     and win32gui.GetWindowText(w) == "" and owned_by(w, h, pid))
        return f[0] if len(f) == 1 else None
    conf = K.wait_for(confirm, 8)
    if not conf: return {"ok": False, "error": "받는 방의 '파일 전송' 확인 창을 하나로 특정하지 못했습니다 — 보내지 않았음"}
    time.sleep(0.4)
    _, _, ccw, cch = win32gui.GetClientRect(conf)
    post_click(conf, ccw // 2, cch - 42)        # 'N개 전송' 버튼
    closed = K.wait_for(lambda: not win32gui.IsWindowVisible(conf), 6)
    return {"ok": bool(closed), "files": [os.path.basename(p) for p in paths], "confirm_closed": bool(closed),
            "error": None if closed else "'N개 전송' 버튼을 눌렀지만 확인 창이 닫히지 않았습니다"}


def bg_text(h, text):
    """입력창에 EM_REPLACESEL 로 넣어야 '전송' 버튼이 켜진다(WM_SETTEXT 는 버튼이 꺼진 채). 버튼을 창 메시지로 누른다."""
    e = K.child(h, K.EDIT_CLASS)
    if not e: return {"ok": False, "error": "입력창 없음"}
    draft = K.edit_text(e)
    if draft not in EMPTY:
        return {"ok": False, "error": "입력창에 쓰던 글(초안)이 있어 지우지 않고 멈췄습니다", "draft": draft[:40]}
    win32api.SendMessage(e, win32con.EM_SETSEL, 0, -1)
    win32api.SendMessage(e, win32con.EM_REPLACESEL, 1, text); time.sleep(0.4)
    norm = lambda x: x.replace("\r\n", "\n").replace("\r", "\n").strip()
    if norm(K.edit_text(e)) != norm(text):
        win32api.SendMessage(e, win32con.WM_SETTEXT, 0, "")
        return {"ok": False, "error": "입력창에 글이 그대로 들어가지 않아 지우고 멈췄습니다"}
    _, _, cw, ch = win32gui.GetClientRect(h)
    post_click(h, cw - 37, ch - 23)             # '전송' 버튼 (클라이언트 기준 오른쪽 37, 아래 23)
    ok = K.wait_for(lambda: K.edit_text(e) in EMPTY, 3)
    return {"ok": bool(ok), "error": None if ok else "전송 버튼을 눌렀지만 입력창이 비지 않았습니다"}


def bg_shot(h, name):
    """창을 앞으로 띄우지 않고 캡처(PrintWindow, PW_RENDERFULLCONTENT)"""
    import ctypes, win32ui
    from PIL import Image
    l, t, r, b = win32gui.GetWindowRect(h); w, hh = r - l, b - t
    hdc = win32gui.GetWindowDC(h); src = mem = bmp = old = None
    try:
        src = win32ui.CreateDCFromHandle(hdc); mem = src.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap(); bmp.CreateCompatibleBitmap(src, w, hh); old = mem.SelectObject(bmp)
        if not ctypes.windll.user32.PrintWindow(h, mem.GetSafeHdc(), 2):
            raise RuntimeError("PrintWindow 실패(창이 최소화됐거나 그려지지 않음)")
        info = bmp.GetInfo(); data = bmp.GetBitmapBits(True)
        im = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), data, "raw", "BGRX", 0, 1)
    finally:
        if mem is not None and old is not None: mem.SelectObject(old)
        if bmp is not None: win32gui.DeleteObject(bmp.GetHandle())
        if mem is not None: mem.DeleteDC()
        if src is not None: src.DeleteDC()
        win32gui.ReleaseDC(h, hdc)
    p = os.path.join(K.SHOT_DIR, f"{name}_{time.strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.png")
    im.save(p)
    return p


def list_sig(h):
    """대화 목록 부분(입력창 위)의 모양 지문 — 새 말풍선·업로드 진행이 끝났는지 보려고"""
    import hashlib
    from PIL import Image
    p = bg_shot(h, "_sig")
    try:
        im = Image.open(p); w, hh = im.size
        return hashlib.md5(im.crop((0, 120, w, hh - 140)).resize((95, 216)).tobytes()).hexdigest()
    finally:
        try: os.remove(p)
        except Exception: pass


def wait_landed(h, sig0, max_wait=90):
    """보낸 뒤 목록이 바뀌고(새 말풍선), 2초 동안 더 안 바뀌면(업로드 끝) True. 시간 안에 못 보면 False.
    한계: 화면 지문이라 그 사이 상대 답장·스크롤이 끼면 늦어지거나 틀릴 수 있다 → 마지막 캡처를 눈으로 확인한다."""
    t0 = time.time(); changed = False; last = sig0; stable_since = None
    while time.time() - t0 < max_wait:
        time.sleep(0.5); s = list_sig(h)
        if s != last: changed = True; last = s; stable_since = time.time(); continue
        if changed and stable_since and time.time() - stable_since >= 2.0: return True
    return False


def cmd_bgsend(argv):
    import argparse, io, shutil, tempfile
    ap = argparse.ArgumentParser(prog="kakao_bg.py send")
    ap.add_argument("title"); ap.add_argument("paths", nargs="*")
    ap.add_argument("--text"); ap.add_argument("--text-file"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--no-sign", action="store_true", help="사용자가 그 건만 안내 문구를 빼라고 했을 때만")
    a = ap.parse_args(argv)
    paths = [os.path.abspath(p) for p in a.paths]
    miss = [p for p in paths if not os.path.isfile(p)]
    if miss: K.out(ok=False, error="파일이 없습니다", missing=miss)
    names = [os.path.basename(p) for p in paths]
    if len(set(n.lower() for n in names)) != len(names): K.out(ok=False, error="파일 이름이 겹칩니다")
    body = io.open(a.text_file, encoding="utf-8").read().rstrip("\n") if a.text_file else (a.text or "")
    if a.no_sign and not body.strip(): K.out(ok=False, error="--no-sign 은 보낼 글이 있을 때만 씁니다")
    text = body if a.no_sign else (K.with_sign(body, a.title) if body.strip() else K.sign_for(a.title))
    K.stop_if_popups("보내기")
    same = [w["hwnd"] for w in K.chat_windows() if w["title"] == a.title]
    if len(same) != 1:
        K.out(ok=False, error=f"'{a.title}' 제목의 대화방 창이 {len(same)}개 — 정확히 하나일 때만 보냅니다(먼저 open, 같은 제목 방은 닫기)",
              open_rooms=[w["title"] for w in K.chat_windows()])
    h = same[0]
    if not a.yes:
        K.out(ok=True, dry_run=True, room=a.title, files=paths, text=text, note="--yes 를 붙여야 보냅니다(파일 묶음 → 업로드 끝 확인 → 글)")
    pid = win32process.GetWindowThreadProcessId(h)[1]

    def still_room():   # 창이 그대로인가(닫히고 핸들이 재사용되지 않았나)
        return (win32gui.IsWindow(h) and win32gui.GetWindowText(h) == a.title and win32gui.GetClassName(h) == K.MAIN_CLASS
                and win32process.GetWindowThreadProcessId(h)[1] == pid and bool(K.child(h, K.EDIT_CLASS)))

    if K.edit_text(K.child(h, K.EDIT_CLASS)) not in EMPTY:
        K.out(ok=False, error="입력창에 쓰던 글(초안)이 있어 아무것도 보내지 않았습니다")
    cur0 = win32gui.GetCursorPos(); t0 = time.time(); tm = {}
    res = {"ok": True}
    if paths:
        # 한 번에 고르려면 같은 폴더여야 한다 → 실행마다 새 임시 폴더에 복사
        batch = tempfile.mkdtemp(prefix="batch_", dir=K.SHOT_DIR)
        staged = []
        for p in paths:
            q = os.path.join(batch, os.path.basename(p)); shutil.copyfile(p, q); staged.append(q)
        if not still_room(): K.out(ok=False, error="받는 방 창이 바뀌어 아무것도 보내지 않았습니다")
        sig0 = list_sig(h)
        res = bg_attach_many(h, staged, pid); tm["파일"] = round(time.time() - t0, 1)
        if not res.get("ok"): K.out(ok=False, error=res.get("error"), step="파일", screenshot=bg_shot(h, "bg_fail"))
        landed = wait_landed(h, sig0); tm["업로드"] = round(time.time() - t0, 1)
        res["landed"] = landed
        if not landed:
            K.out(ok=False, error="파일 업로드가 끝난 것을 확인하지 못해 글은 보내지 않았습니다", files=res.get("files"),
                  screenshot=bg_shot(h, "bg_upload"), note="캡처로 파일이 올라갔는지 확인한 뒤, 글만 따로 보낼 것")
        shutil.rmtree(batch, ignore_errors=True)
    if not still_room(): K.out(ok=False, error="받는 방 창이 바뀌어 글은 보내지 않았습니다", files=res.get("files"))
    tr = bg_text(h, text); tm["글"] = round(time.time() - t0, 1)
    time.sleep(1.0)
    K.out(ok=bool(tr.get("ok")) and res.get("ok", True), room=a.title, files=res.get("files", []), upload_landed=res.get("landed"),
          text_sent=tr.get("ok"), text_error=tr.get("error"), seconds=tm, cursor_moved=(win32gui.GetCursorPos() != cur0),
          screenshot=bg_shot(h, "bg_sent"),
          note="ok 는 '조작이 끝났다'는 뜻 — 파일 개수·순서는 screenshot 을 Read 로 열어 눈으로 확인해야 확정")


def cmd_bgopen(argv):
    r = bg_open(argv[0])
    if not r["ok"]:
        K.out(ok=False, error=r.get("error") or "창 메시지로 방을 열지 못함 — kakao.py open 으로(키보드 사용) 다시")
    if len(argv) > 1 and r["opened"] != argv[1]:
        K.out(ok=False, error=f"열린 방 '{r['opened']}' 이 기대한 '{argv[1]}' 과 달라 멈췄습니다(보내지 않음)")
    K.out(ok=True, opened=r["opened"])


if __name__ == "__main__":
    cmd, rest = sys.argv[1], sys.argv[2:]
    {"send": cmd_bgsend, "open": cmd_bgopen}[cmd](rest)
