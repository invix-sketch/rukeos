#!/usr/bin/python3
"""rukeOS Settings, top-bar Wi-Fi indicator, and clock quick panel."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import threading

os.environ.setdefault("NO_AT_BRIDGE", "1")
os.environ.setdefault("GTK_A11Y", "none")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

# Tokyo Night + Judah's icon-pack purple
BG, BG2, SURF, FG, MUTED = "#1a1b26", "#16161e", "#24283b", "#c0caf5", "#565f89"
PURPLE, PURPLE_DK = "#7b4fd6", "#6a35d0"
BLUE, GREEN, RED, YELLOW, CYAN = "#7aa2f7", "#9ece6a", "#f7768e", "#e0af68", "#7dcfff"

ACCENTS = [
    ("Tokyo Night blue", BLUE),
    ("rukeOS purple", PURPLE),
    ("Purple", "#bb9af7"),
    ("Cyan", CYAN),
    ("Green", GREEN),
    ("Yellow", YELLOW),
    ("Red", RED),
]

DARK_PALETTE = {
    "#1a1b26": "#1a1b26",
    "#16161e": "#16161e",
    "#1f2335": "#1f2335",
    "#24283b": "#24283b",
    "#c0caf5": "#c0caf5",
    "#a9b1d6": "#a9b1d6",
    "#565f89": "#565f89",
}
# Tokyo Night Day-ish, used only when the user picks Light
LIGHT_PALETTE = {
    "#1a1b26": "#e1e2e7",
    "#16161e": "#d0d5e3",
    "#1f2335": "#f0f1f5",
    "#24283b": "#ffffff",
    "#c0caf5": "#1a1b26",
    "#a9b1d6": "#3760bf",
    "#565f89": "#6172b0",
}

SHARE = "/usr/share/rukeos"
ICON_DIR = os.environ.get("RUKE_ICON_DIR", SHARE + "/icons")
WALLPAPER_DEFAULT = "/usr/share/backgrounds/rukeos.png"
UPDATE_LOG = "/var/log/ruke-update.log"
VERSION_FILE = "/etc/rukeos/version"
CSS = """
window, .background { background-color: #1a1b26; color: #c0caf5; font-family: Inter, sans-serif; }
headerbar { background-color: #16161e; color: #c0caf5; box-shadow: none;
  border-bottom: 1px solid rgba(123,79,214,0.28); min-height: 40px; }
headerbar button { color: #c0caf5; border-radius: 8px; }
.sidebar { background-color: #16161e; padding: 10px 8px; }
.sidebar button { border-radius: 8px; padding: 9px 12px; color: #c0caf5;
  background: none; border: none; box-shadow: none; }
.sidebar button:hover { background-color: rgba(123,79,214,0.16); }
.sidebar button.selected { background-color: #7b4fd6; color: #ffffff; }
.card { background-color: #24283b; border-radius: 12px; padding: 16px; }
button.suggested-action, button.accent {
  background-image: none; background-color: #7b4fd6; color: #ffffff;
  border-radius: 8px; border: none; padding: 8px 16px; font-weight: 600; }
button.suggested-action:hover, button.accent:hover { background-color: #8b63e0; }
button.suggested-action:disabled { opacity: 0.55; }
button.flat { background: none; border: none; box-shadow: none; color: #c0caf5; border-radius: 8px; }
button.danger { background-image: none; background-color: #f7768e; color: #16161e;
  border-radius: 8px; border: none; padding: 8px 14px; }
progressbar trough { min-height: 8px; border-radius: 8px; background-color: #16161e; border: none; }
progressbar progress { min-height: 8px; border-radius: 8px; background-color: #7b4fd6; }
entry { background-color: #16161e; color: #c0caf5; border: 1px solid rgba(123,79,214,0.30);
  border-radius: 8px; min-height: 28px; padding: 0 10px; }
entry:focus { border-color: #7b4fd6; }
scale highlight { background-color: #7b4fd6; }
scale trough { background-color: #16161e; border-radius: 8px; min-height: 6px; }
switch slider { background-color: #c0caf5; }
switch { background-color: #414868; }
switch:checked { background-color: #7b4fd6; }
label.muted { color: #565f89; }
label.error { color: #f7768e; }
label.ok { color: #9ece6a; }
label.warn { color: #e0af68; }
.wifi-row { border-radius: 8px; padding: 6px 8px; }
.wifi-row:hover { background-color: rgba(123,79,214,0.12); }
.wifi-row.active { background-color: rgba(123,79,214,0.28); }
#quickpanel { background-color: #1a1b26; }
#quickpanel-frame { background-color: #1a1b26; border-radius: 14px;
  border: 1px solid rgba(123,79,214,0.40); padding: 4px; }
button.action-btn, button.action-btn:disabled {
  background-image: none;
  background-color: #24283b;
  background: #24283b;
  color: #c0caf5;
  border: none;
  border-image: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 10px;
  padding: 8px 4px 6px 4px;
  min-width: 56px; }
button.action-btn:hover, button.action-btn:focus, button.action-btn:active,
button.action-btn:checked, button.action-btn:selected {
  background-image: none;
  background-color: #2f3549;
  background: #2f3549;
  color: #c0caf5;
  box-shadow: none; }
button.action-btn.power-btn:hover, button.action-btn.power-btn:active {
  background-image: none;
  background-color: #f7768e;
  background: #f7768e;
  color: #16161e; }
button.action-btn label { color: #c0caf5; background: none; }
button.action-btn.power-btn:hover label, button.action-btn.power-btn:active label { color: #16161e; }
label.signal { font-family: "JetBrains Mono", monospace; }
.swatch { border-radius: 16px; border: 2px solid transparent; min-width: 28px; min-height: 28px; padding: 0; }
.swatch.selected { border-color: #ffffff; }
"""

PROGRESS_PATTERNS = [
    (re.compile(r"ruke-update itself was updated", re.I), 12, "Updating the updater..."),
    (re.compile(r"Downloading rukeOS", re.I), 18, "Downloading update files..."),
    (re.compile(r"Refreshing package lists", re.I), 32, "Refreshing package lists..."),
    (re.compile(r"Upgrading system packages", re.I), 48, "Upgrading system packages..."),
    (re.compile(r"Installing rukeOS apps", re.I), 66, "Installing apps..."),
    (re.compile(r"Applying rukeOS files", re.I), 82, "Applying rukeOS files..."),
    (re.compile(r"Migration ", re.I), 90, "Running migrations..."),
    (re.compile(r"Update finished", re.I), 100, "Update finished"),
]
ERROR_PATTERNS = [
    (re.compile(r"Can't reach the update server", re.I),
     "Can't reach the update server. Connect to Wi-Fi first."),
    (re.compile(r"Saving between boots is OFF", re.I),
     "Turn on Saving between boots first (menu > Saving between boots), then try again."),
    (re.compile(r"apk update failed", re.I),
     "Couldn't refresh packages. Check your internet connection."),
    (re.compile(r"Download failed", re.I),
     "Download failed. Check your internet connection and try again."),
    (re.compile(r"already running", re.I),
     "An update is already running."),
    (re.compile(r"a password is required|no tty present|not allowed to", re.I),
     "Need permission to update. Try again, or run ruke-update from a terminal."),
]
def config_home():
    return os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))


def appearance_path():
    return os.path.join(config_home(), "rukeos", "appearance.conf")


def load_appearance():
    d = {
        "wallpaper": WALLPAPER_DEFAULT,
        "accent": BLUE,
        "theme": "dark",
        "font_size": "10",
        "night_light": "0",
    }
    path = appearance_path()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def save_appearance(d):
    path = appearance_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for k in ("wallpaper", "accent", "theme", "font_size", "night_light"):
            f.write("%s=%s\n" % (k, d.get(k, "")))


def os_version():
    path = os.environ.get("RUKE_VERSION_FILE", VERSION_FILE)
    for p in (path, "/etc/os-release"):
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            continue
        if p.endswith("os-release"):
            m = re.search(r'^VERSION_ID=["\']?([^"\'\n]+)', text, re.M)
            if m:
                return m.group(1).strip()
            continue
        v = text.replace("\r", "").strip()
        if v:
            return v
    return "unknown"


def icon_pixbuf(name, size=24):
    for p in (
        os.path.join(ICON_DIR, "%s.png" % name),
        os.path.join(ICON_DIR, "%s.svg" % name),
        "/usr/share/icons/hicolor/48x48/apps/ruke-settings.png" if name == "settings" else "",
    ):
        if p and os.path.isfile(p):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_size(p, size, size)
            except Exception:
                continue
    return None


def icon_image(name, size=24):
    pb = icon_pixbuf(name, size)
    if pb:
        return Gtk.Image.new_from_pixbuf(pb)
    return Gtk.Image.new_from_icon_name("preferences-system", Gtk.IconSize.BUTTON)


def apply_css(widget=None):
    try:
        p = Gtk.CssProvider()
        p.load_from_data(CSS.encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, p, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
        elif widget:
            widget.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    except Exception:
        pass


def run_cmd(cmd, timeout=25, input_text=None):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            input=input_text,
            text=True,
        )
        return p.returncode, (p.stdout or "")
    except subprocess.TimeoutExpired:
        return 124, "Timed out"
    except FileNotFoundError:
        return 127, "command not found: %s" % cmd[0]
    except Exception as e:
        return 1, str(e)


def tool(env_name, default):
    return os.environ.get(env_name, default)


def update_exe():
    return tool("RUKE_UPDATE", "ruke-update")


def update_argv(args, need_root=False):
    exe = update_exe()
    cmd = [exe] + list(args)
    if not need_root:
        return cmd
    if os.environ.get("RUKE_UPDATE") or os.geteuid() == 0:
        return cmd
    return ["sudo", "-n"] + cmd


def _home():
    return os.path.expanduser("~")


def _set_ini(path, mapping):
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ["[Settings]\n"]
    else:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if not any(l.strip() == "[Settings]" for l in lines):
            lines.insert(0, "[Settings]\n")
    for key, value in mapping.items():
        pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
        text = "".join(lines)
        if pat.search(text):
            text = pat.sub("%s=%s" % (key, value), text)
            lines = text.splitlines(True)
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append("%s=%s\n" % (key, value))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _rewrite_css_palette(path, theme, accent, old_accent=None):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    orig = text
    text = re.sub(r"(@define-color accent_(?:bg_)?color )#[0-9A-Fa-f]{6}", r"\1" + accent, text)
    replacements = []
    for dark_hex, light_hex in LIGHT_PALETTE.items():
        src = light_hex if theme == "dark" else dark_hex
        dst = dark_hex if theme == "dark" else light_hex
        if src.lower() != dst.lower() and src.lower() != accent.lower():
            replacements.append((src, dst))
    for src, dst in replacements:
        text = re.sub(re.escape(src), dst, text, flags=re.I)
    if old_accent and old_accent.lower() != accent.lower():
        text = re.sub(re.escape(old_accent), accent, text, flags=re.I)
    if text != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def _rewrite_jgmenu(path, theme, accent, font_size):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    orig = text
    fg = "#1a1b26" if theme == "light" else FG
    bg = "#ffffff" if theme == "light" else SURF
    muted = "#6172b0" if theme == "light" else MUTED
    sel_fg = "#ffffff" if theme == "light" else BG2
    icon = "Papirus" if theme == "light" else "Papirus-Dark"
    text = re.sub(r"^font = .*", "font = Inter %s" % font_size, text, flags=re.M)
    text = re.sub(r"^icon_theme = .*", "icon_theme = %s" % icon, text, flags=re.M)
    text = re.sub(r"^color_menu_bg = .*", "color_menu_bg = %s 97" % bg, text, flags=re.M)
    text = re.sub(r"^color_menu_border = .*", "color_menu_border = %s 35" % accent, text, flags=re.M)
    text = re.sub(r"^color_norm_fg = .*", "color_norm_fg = %s 100" % fg, text, flags=re.M)
    text = re.sub(r"^color_sel_bg = .*", "color_sel_bg = %s 100" % accent, text, flags=re.M)
    text = re.sub(r"^color_sel_fg = .*", "color_sel_fg = %s 100" % sel_fg, text, flags=re.M)
    text = re.sub(r"^color_sel_border = .*", "color_sel_border = %s 0" % accent, text, flags=re.M)
    text = re.sub(r"^color_sep_fg = .*", "color_sep_fg = %s 100" % muted, text, flags=re.M)
    text = re.sub(r"^color_title_fg = .*", "color_title_fg = %s 100" % muted, text, flags=re.M)
    if text != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def set_night_light(on):
    if not os.environ.get("DISPLAY"):
        return
    rc, out = run_cmd(["xrandr", "--query"], timeout=5)
    if rc != 0:
        return
    outputs = re.findall(r"^(\S+) connected", out, re.M)
    gamma = "1.0:0.85:0.65" if on else "1:1:1"
    for o in outputs:
        run_cmd(["xrandr", "--output", o, "--gamma", gamma], timeout=5)


def set_wallpaper(path):
    if path and os.path.isfile(path) and shutil.which("feh"):
        run_cmd(["feh", "--no-fehbg", "--bg-fill", path], timeout=8)


def apply_appearance(d, session_only=False):
    wallpaper = d.get("wallpaper") or WALLPAPER_DEFAULT
    if not os.path.isfile(wallpaper):
        wallpaper = WALLPAPER_DEFAULT
    set_wallpaper(wallpaper)
    set_night_light(d.get("night_light") == "1")
    if session_only:
        return
    home = _home()
    accent = d.get("accent") or BLUE
    theme = d.get("theme") or "dark"
    font_size = str(d.get("font_size") or "10")
    dark = theme != "light"
    gtk_theme = "adw-gtk3-dark" if dark else "adw-gtk3"
    icons = "Papirus-Dark" if dark else "Papirus"
    ini = {
        "gtk-theme-name": gtk_theme,
        "gtk-application-prefer-dark-theme": "1" if dark else "0",
        "gtk-icon-theme-name": icons,
        "gtk-font-name": "Inter %s" % font_size,
    }
    _set_ini(os.path.join(home, ".config/gtk-3.0/settings.ini"), ini)
    ini4 = dict(ini)
    ini4.pop("gtk-application-prefer-dark-theme", None)
    _set_ini(os.path.join(home, ".config/gtk-4.0/settings.ini"), ini4)
    old_accent = BLUE
    css3 = os.path.join(home, ".config/gtk-3.0/gtk.css")
    if os.path.isfile(css3):
        with open(css3, encoding="utf-8") as f:
            m = re.search(r"@define-color accent_color (#([0-9A-Fa-f]{6}))", f.read())
        if m:
            old_accent = m.group(1)
    for css in (css3, os.path.join(home, ".config/gtk-4.0/gtk.css")):
        _rewrite_css_palette(css, theme, accent, old_accent)
    _rewrite_jgmenu(os.path.join(home, ".config/jgmenu/jgmenurc"), theme, accent, font_size)
    if shutil.which("gsettings"):
        scheme = "prefer-dark" if dark else "prefer-light"
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme], timeout=4)
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk_theme], timeout=4)
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icons], timeout=4)
        run_cmd(["gsettings", "set", "org.gnome.desktop.interface", "font-name", "Inter %s" % font_size], timeout=4)
def nmcli(args, timeout=20):
    return run_cmd([tool("RUKE_NMCLI", "nmcli")] + list(args), timeout=timeout)


def wifi_radio():
    rc, out = nmcli(["-t", "radio", "wifi"], timeout=5)
    return rc == 0 and "enabled" in (out.strip().split("\n") or [""])[0]


def set_wifi_radio(on):
    return nmcli(["radio", "wifi", "on" if on else "off"], timeout=8)


def airplane_on():
    rc, out = nmcli(["-t", "radio", "all"], timeout=5)
    if rc != 0:
        return False
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if not lines:
        return False
    return all(l.endswith("disabled") or l == "disabled" for l in lines)


def set_airplane(on):
    nmcli(["radio", "all", "off" if on else "on"], timeout=8)
    if on:
        set_bluetooth(False)
    elif has_bluetooth():
        set_bluetooth(True)


def device_status():
    """Return (state, connection_name, kind) where kind is wifi/ethernet/none."""
    rc, out = nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"], timeout=5)
    wifi = ("disconnected", "", "none")
    if rc != 0:
        return wifi
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        dev, typ, state, conn = parts[0], parts[1], parts[2], ":".join(parts[3:])
        if typ == "ethernet" and state == "connected":
            return (state, conn or dev, "ethernet")
        if typ == "wifi":
            wifi = (state, conn if conn != "--" else "", "wifi")
    return wifi


def wifi_signal():
    rc, out = nmcli(["-t", "-f", "IN-USE,SSID,SIGNAL", "dev", "wifi"], timeout=8)
    if rc != 0:
        return None, ""
    for line in out.splitlines():
        if line.startswith("*"):
            bits = re.split(r"(?<!\\):", line)
            if len(bits) >= 3:
                ssid = bits[1].replace("\\:", ":")
                try:
                    return int(bits[2] or 0), ssid
                except ValueError:
                    return None, ssid
    return None, ""

def wifi_list(rescan=False):
    args = ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"]
    args += ["--rescan", "yes" if rescan else "auto"]
    rc, out = nmcli(args, timeout=25)
    nets, seen = [], set()
    if rc != 0:
        return nets, out.strip()
    for line in out.splitlines():
        bits = re.split(r"(?<!\\):", line)
        if len(bits) < 4:
            if len(bits) == 3:
                bits.append("")
            else:
                continue
        ssid = bits[1].replace("\\:", ":").strip()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            sig = int(bits[2] or 0)
        except ValueError:
            sig = 0
        sec = bits[3].replace("\\:", ":").strip()
        nets.append({"ssid": ssid, "signal": sig, "security": sec, "active": bits[0] == "*"})
    nets.sort(key=lambda n: (not n["active"], -n["signal"]))
    return nets, ""


def wifi_connect(ssid, password=None):
    args = ["dev", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    return nmcli(args, timeout=40)


def has_bluetooth():
    return bool(shutil.which("bluetoothctl") or os.environ.get("RUKE_BLUETOOTHCTL"))


def bluetooth_on():
    exe = tool("RUKE_BLUETOOTHCTL", "bluetoothctl")
    rc, out = run_cmd([exe, "show"], timeout=5)
    return rc == 0 and re.search(r"Powered:\s*yes", out, re.I) is not None


def set_bluetooth(on):
    exe = tool("RUKE_BLUETOOTHCTL", "bluetoothctl")
    if not shutil.which(exe) and not os.environ.get("RUKE_BLUETOOTHCTL"):
        return 127, "no bluetooth"
    return run_cmd([exe, "power", "on" if on else "off"], timeout=6)


def backlight_root():
    root = os.environ.get("RUKE_BACKLIGHT_ROOT", "/sys/class/backlight")
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isfile(os.path.join(d, "brightness")) and os.path.isfile(os.path.join(d, "max_brightness")):
            return d
    return None


def read_brightness():
    d = backlight_root()
    if not d:
        return None, None
    try:
        cur = int(open(os.path.join(d, "brightness")).read().strip())
        mx = int(open(os.path.join(d, "max_brightness")).read().strip()) or 1
        return cur, mx
    except Exception:
        return None, None


def set_brightness(value):
    d = backlight_root()
    if not d:
        return False
    path = os.path.join(d, "brightness")
    text = str(int(value))
    try:
        with open(path, "w") as f:
            f.write(text)
        return True
    except OSError:
        rc, _ = run_cmd(
            ["sh", "-c", 'printf %s "$1" | sudo -n tee "$2" >/dev/null', "sh", text, path],
            timeout=4,
        )
        return rc == 0


def battery_info():
    root = os.environ.get("RUKE_POWER_ROOT", "/sys/class/power_supply")
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        typ = ""
        try:
            typ = open(os.path.join(d, "type")).read().strip()
        except OSError:
            pass
        if typ and typ.lower() != "battery" and not name.upper().startswith("BAT"):
            continue
        cap_p = os.path.join(d, "capacity")
        if not os.path.isfile(cap_p):
            continue
        try:
            cap = open(cap_p).read().strip()
            status = "Unknown"
            sp = os.path.join(d, "status")
            if os.path.isfile(sp):
                status = open(sp).read().strip()
            return cap, status
        except OSError:
            continue
    return None


def amixer_cmd(args, timeout=5):
    return run_cmd([tool("RUKE_AMIXER", "amixer")] + list(args), timeout=timeout)


_mixer_control = None


def mixer_control():
    global _mixer_control
    if _mixer_control:
        return _mixer_control
    for name in ("Master", "PCM", "Speaker", "Headphone"):
        rc, out = amixer_cmd(["sget", name])
        if rc == 0 and ("Playback" in out or "Limits" in out or "[" in out):
            _mixer_control = name
            return name
    rc, out = amixer_cmd(["scontrols"])
    m = re.search(r"Simple mixer control '([^']+)'", out or "")
    _mixer_control = m.group(1) if m else "Master"
    return _mixer_control


def volume_get():
    rc, out = amixer_cmd(["sget", mixer_control()])
    if rc != 0:
        return 50, False
    muted = bool(re.search(r"\[off\]", out))
    percents = [int(x) for x in re.findall(r"\[(\d+)%\]", out)]
    vol = percents[0] if percents else 0
    return vol, muted


def volume_set(pct):
    pct = max(0, min(100, int(pct)))
    amixer_cmd(["sset", mixer_control(), "%s%%" % pct, "unmute"])


def volume_toggle_mute():
    amixer_cmd(["sset", mixer_control(), "toggle"])


def wifi_state_summary():
    """For the tray: status, signal 0-100 or None, label."""
    if airplane_on():
        return "airplane", None, "Airplane mode"
    if not wifi_radio():
        state, conn, kind = device_status()
        if kind == "ethernet" and state == "connected":
            return "ethernet", 100, conn or "Wired"
        return "off", None, "Wi-Fi off"
    state, conn, kind = device_status()
    if kind == "ethernet" and state == "connected":
        return "ethernet", 100, conn or "Wired"
    if state == "connected":
        sig, ssid = wifi_signal()
        return "connected", sig if sig is not None else 70, ssid or conn or "Connected"
    if state in ("connecting", "preparing", "configuring", "need-auth"):
        return "connecting", 0, "Connecting…"
    return "disconnected", None, "Wi-Fi disconnected"


def classify_update_line(line):
    for pat, msg in ERROR_PATTERNS:
        if pat.search(line):
            return ("error", None, msg)
    for pat, frac, msg in PROGRESS_PATTERNS:
        if pat.search(line):
            return ("progress", frac, msg)
    return (None, None, None)


def card():
    f = Gtk.Frame()
    f.set_shadow_type(Gtk.ShadowType.NONE)
    f.get_style_context().add_class("card")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_margin_top(14)
    box.set_margin_bottom(14)
    f.add(box)
    return f, box


def muted(text, wrap=True):
    l = Gtk.Label(label=text, xalign=0)
    l.get_style_context().add_class("muted")
    l.set_line_wrap(wrap)
    l.set_max_width_chars(52)
    return l


def heading(text):
    l = Gtk.Label(label=text, xalign=0)
    l.set_markup("<b>%s</b>" % GLib.markup_escape_text(text))
    return l


def screenshot_window(win, path):
    win.show_all()
    if hasattr(win, "reselect_page"):
        win.reselect_page()
    win.present()
    while Gtk.events_pending():
        Gtk.main_iteration()

    def _cap(_=None):
        try:
            gdk_win = win.get_window()
            if gdk_win is None:
                return False
            w = gdk_win.get_width()
            h = gdk_win.get_height()
            pb = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
            if pb:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                pb.savev(path, "png", [], [])
        finally:
            Gtk.main_quit()
        return False

    GLib.timeout_add(500, _cap)


def maybe_screenshot(win, path):
    if path:
        screenshot_window(win, path)


def load_css_and_display():
    apply_css()
class SettingsWindow(Gtk.Window):
    def __init__(self, page="updates", demo=None, screenshot=None):
        Gtk.Window.__init__(self, title="Settings")
        self.set_wmclass("RukeSettings", "RukeSettings")
        try:
            GLib.set_prgname("RukeSettings")
        except Exception:
            pass
        self.set_default_size(760, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", Gtk.main_quit)
        pb = icon_pixbuf("settings", 48)
        if pb:
            self.set_icon(pb)
        self.demo = demo
        self._busy = False
        self._pulse_id = None
        self.appearance = load_appearance()

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(outer)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        side.get_style_context().add_class("sidebar")
        side.set_size_request(180, -1)
        icon = icon_image("settings", 36)
        icon.set_margin_top(8)
        icon.set_margin_bottom(4)
        side.pack_start(icon, False, False, 0)
        title = Gtk.Label(label="Settings")
        title.set_markup("<b>Settings</b>")
        title.set_margin_bottom(10)
        side.pack_start(title, False, False, 0)
        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.nav = {}
        for key, label in (("updates", "Updates"), ("customization", "Customization"), ("help", "Help")):
            b = Gtk.Button(label=label)
            b.set_relief(Gtk.ReliefStyle.NONE)
            child = b.get_child()
            if child is not None:
                child.set_halign(Gtk.Align.START)
            b.connect("clicked", self._goto, key)
            self.nav[key] = b
            side.pack_start(b, False, False, 0)
        outer.pack_start(side, False, False, 0)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        pad = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pad.set_margin_start(18)
        pad.set_margin_end(18)
        pad.set_margin_top(16)
        pad.set_margin_bottom(16)
        pad.pack_start(self.stack, True, True, 0)
        sc.add(pad)
        outer.pack_start(sc, True, True, 0)

        self.stack.add_titled(self._build_updates(), "updates", "Updates")
        self.stack.add_titled(self._build_customization(), "customization", "Customization")
        self.stack.add_titled(self._build_help(), "help", "Help")
        self._page = page if page in self.nav else "updates"
        self._goto(None, self._page)
        if demo:
            GLib.idle_add(self._apply_demo, demo)
        if screenshot:
            maybe_screenshot(self, screenshot)
        else:
            self.show_all()
            self.reselect_page()
            self.present()

    def reselect_page(self):
        self._goto(None, getattr(self, "_page", "updates"))

    def _goto(self, _btn, key):
        self._page = key
        self.stack.set_visible_child_name(key)
        for k, b in self.nav.items():
            ctx = b.get_style_context()
            if k == key:
                ctx.add_class("selected")
            else:
                ctx.remove_class("selected")

    def _build_updates(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.pack_start(heading("Updates"), False, False, 0)
        box.pack_start(muted("Check for a new rukeOS in the background. No terminal window is opened."), False, False, 0)
        fr, inner = card()
        ver = Gtk.Label(xalign=0)
        ver.set_markup("This computer is on <b>rukeOS %s</b>" % GLib.markup_escape_text(os_version()))
        inner.pack_start(ver, False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(label="Ready to check for updates.", xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_hexpand(True)
        row.pack_start(self.spinner, False, False, 0)
        row.pack_start(self.status, True, True, 0)
        inner.pack_start(row, False, False, 0)
        self.bar = Gtk.ProgressBar()
        self.bar.set_fraction(0)
        self.bar.set_show_text(False)
        inner.pack_start(self.bar, False, False, 4)
        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.check_btn = Gtk.Button(label="Check for updates")
        self.check_btn.get_style_context().add_class("suggested-action")
        self.check_btn.connect("clicked", self._on_check)
        btnrow.pack_start(self.check_btn, False, False, 0)
        self.restart_btn = Gtk.Button(label="Restart desktop")
        self.restart_btn.set_visible(False)
        self.restart_btn.set_no_show_all(True)
        self.restart_btn.connect("clicked", lambda *_: run_cmd(["jwm", "-restart"], timeout=5) and None)
        btnrow.pack_start(self.restart_btn, False, False, 0)
        inner.pack_start(btnrow, False, False, 0)
        box.pack_start(fr, False, False, 0)
        return box

    def _set_status(self, text, kind=None, fraction=None, pulse=False, spin=False):
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        for c in ("error", "ok", "warn", "muted"):
            ctx.remove_class(c)
        if kind:
            ctx.add_class(kind)
        if spin:
            self.spinner.start()
        else:
            self.spinner.stop()
        if self._pulse_id:
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None
        if pulse:
            self.bar.set_fraction(0)

            def _p():
                self.bar.pulse()
                return True

            self._pulse_id = GLib.timeout_add(120, _p)
        elif fraction is not None:
            self.bar.set_fraction(max(0.0, min(1.0, fraction / 100.0 if fraction > 1 else fraction)))

    def _on_check(self, *_):
        if self._busy:
            return
        self._busy = True
        self.check_btn.set_sensitive(False)
        self.restart_btn.hide()
        self._set_status("Checking for updates...", spin=True, pulse=True)

        def work():
            rc, out = run_cmd(update_argv(["--check"], need_root=False), timeout=40)
            GLib.idle_add(self._after_check, rc, out)

        threading.Thread(target=work, daemon=True).start()

    def _after_check(self, rc, out):
        if rc == 0:
            self._busy = False
            self.check_btn.set_sensitive(True)
            self._set_status("Up to date  ·  rukeOS %s" % os_version(), kind="ok", fraction=100)
            return False
        if rc == 10:
            self._set_status("Updating...", spin=True, pulse=True)
            self._start_apply()
            return False
        self._busy = False
        self.check_btn.set_sensitive(True)
        msg = "Couldn't check for updates."
        for pat, human in ERROR_PATTERNS:
            if pat.search(out or ""):
                msg = human
                break
        else:
            if out.strip():
                for line in (out or "").splitlines():
                    line = line.strip()
                    if line and not line.startswith("==>"):
                        msg = line[:200]
                        break
        self._set_status(msg, kind="error", fraction=0)
        return False

    def _start_apply(self):
        def work():
            cmd = update_argv(["--yes"], need_root=True)
            try:
                p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
                buf = []
                for line in p.stdout:
                    buf.append(line)
                    GLib.idle_add(self._on_update_line, line)
                rc = p.wait()
                GLib.idle_add(self._on_update_done, rc, "".join(buf))
            except Exception as e:
                GLib.idle_add(self._on_update_done, 1, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_update_line(self, line):
        kind, frac, msg = classify_update_line(line)
        if kind == "error":
            self._set_status(msg, kind="error", fraction=0, spin=True, pulse=True)
        elif kind == "progress":
            self._set_status(msg if frac < 100 else "Updating...", spin=True, fraction=frac, pulse=False)
            if frac is not None:
                self.bar.set_fraction(frac / 100.0)
        return False

    def _on_update_done(self, rc, out):
        self._busy = False
        self.check_btn.set_sensitive(True)
        err = None
        for pat, human in ERROR_PATTERNS:
            if pat.search(out or ""):
                err = human
                break
        if rc != 0 and not err:
            err = "Update failed. See /var/log/ruke-update.log"
        if err:
            self._set_status(err, kind="error", fraction=0)
            return False
        if "Restart the desktop" in (out or ""):
            self._set_status("Updated, restart to finish", kind="ok", fraction=100)
            self.restart_btn.show()
        elif "Update finished" in (out or ""):
            self._set_status("Update finished  ·  rukeOS %s" % os_version(), kind="ok", fraction=100)
        else:
            self._set_status("Up to date  ·  rukeOS %s" % os_version(), kind="ok", fraction=100)
        return False

    def _apply_demo(self, demo):
        if demo == "checking":
            self.check_btn.set_sensitive(False)
            self._set_status("Checking for updates...", spin=True, pulse=True)
        elif demo == "updating":
            self.check_btn.set_sensitive(False)
            self._set_status("Upgrading system packages...", spin=True, fraction=48)
            self.bar.set_fraction(0.48)
        elif demo == "uptodate":
            self._set_status("Up to date  ·  rukeOS %s" % os_version(), kind="ok", fraction=100)
        elif demo == "done":
            self._set_status("Updated, restart to finish", kind="ok", fraction=100)
            self.restart_btn.show()
        elif demo == "error":
            self._set_status("Can't reach the update server. Connect to Wi-Fi first.", kind="error", fraction=0)
        return False

    def _build_customization(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.pack_start(heading("Customization"), False, False, 0)
        box.pack_start(muted("These changes apply to your desktop theme. Some apps pick them up after you restart the desktop."), False, False, 0)

        fr, inner = card()
        inner.pack_start(heading("Wallpaper"), False, False, 0)
        self.wall_lbl = Gtk.Label(xalign=0)
        self._refresh_wall_label()
        self.wall_lbl.get_style_context().add_class("muted")
        self.wall_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        inner.pack_start(self.wall_lbl, False, False, 0)
        brow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b1 = Gtk.Button(label="Choose image…")
        b1.connect("clicked", self._choose_wallpaper)
        b2 = Gtk.Button(label="Use rukeOS default")
        b2.connect("clicked", self._default_wallpaper)
        brow.pack_start(b1, False, False, 0)
        brow.pack_start(b2, False, False, 0)
        inner.pack_start(brow, False, False, 0)
        box.pack_start(fr, False, False, 0)

        fr, inner = card()
        inner.pack_start(heading("Accent color"), False, False, 0)
        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._swatches = {}
        for name, color in ACCENTS:
            btn = Gtk.Button()
            btn.set_tooltip_text(name + "  " + color)
            btn.get_style_context().add_class("swatch")
            css = Gtk.CssProvider()
            css.load_from_data(("button { background-image: none; background-color: %s; min-width: 28px; min-height: 28px; border-radius: 16px; }" % color).encode())
            btn.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            btn.connect("clicked", self._pick_accent, color)
            self._swatches[color.lower()] = btn
            swatches.pack_start(btn, False, False, 0)
        inner.pack_start(swatches, False, False, 0)
        self._mark_swatch()
        box.pack_start(fr, False, False, 0)

        fr, inner = card()
        inner.pack_start(heading("Appearance"), False, False, 0)
        trow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.dark_r = Gtk.RadioButton.new_with_label(None, "Dark")
        self.light_r = Gtk.RadioButton.new_with_label_from_widget(self.dark_r, "Light")
        if self.appearance.get("theme") == "light":
            self.light_r.set_active(True)
        else:
            self.dark_r.set_active(True)
        self.dark_r.connect("toggled", self._theme_toggled)
        trow.pack_start(self.dark_r, False, False, 0)
        trow.pack_start(self.light_r, False, False, 0)
        inner.pack_start(trow, False, False, 0)
        frow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        frow.pack_start(Gtk.Label(label="Font size", xalign=0), False, False, 0)
        adj = Gtk.Adjustment(value=int(self.appearance.get("font_size") or 10), lower=8, upper=16, step_increment=1)
        self.font_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        self.font_spin.connect("value-changed", self._font_changed)
        frow.pack_start(self.font_spin, False, False, 0)
        inner.pack_start(frow, False, False, 0)
        box.pack_start(fr, False, False, 0)
        return box

    def _refresh_wall_label(self):
        p = self.appearance.get("wallpaper") or WALLPAPER_DEFAULT
        self.wall_lbl.set_text(p)

    def _commit_appearance(self):
        save_appearance(self.appearance)
        apply_appearance(self.appearance)

    def _choose_wallpaper(self, *_):
        dlg = Gtk.FileChooserDialog(
            title="Choose wallpaper",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name("Images")
        for pat in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"):
            filt.add_pattern(pat)
        dlg.add_filter(filt)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            if path:
                self.appearance["wallpaper"] = path
                self._refresh_wall_label()
                self._commit_appearance()
        dlg.destroy()

    def _default_wallpaper(self, *_):
        self.appearance["wallpaper"] = WALLPAPER_DEFAULT
        self._refresh_wall_label()
        self._commit_appearance()

    def _mark_swatch(self):
        cur = (self.appearance.get("accent") or BLUE).lower()
        for color, btn in self._swatches.items():
            ctx = btn.get_style_context()
            if color == cur:
                ctx.add_class("selected")
            else:
                ctx.remove_class("selected")

    def _pick_accent(self, _btn, color):
        self.appearance["accent"] = color
        self._mark_swatch()
        self._commit_appearance()

    def _theme_toggled(self, *_):
        self.appearance["theme"] = "light" if self.light_r.get_active() else "dark"
        self._commit_appearance()

    def _font_changed(self, *_):
        self.appearance["font_size"] = str(int(self.font_spin.get_value()))
        self._commit_appearance()

    def _build_help(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.pack_start(heading("Help"), False, False, 0)

        def section(title, body):
            fr, inner = card()
            inner.pack_start(heading(title), False, False, 0)
            lbl = Gtk.Label(xalign=0)
            lbl.set_markup(body)
            lbl.set_line_wrap(True)
            lbl.set_max_width_chars(60)
            inner.pack_start(lbl, False, False, 0)
            box.pack_start(fr, False, False, 0)

        section(
            "Saving between boots",
            "Turn this on so your files, apps and settings stay after a reboot.\n"
            "Open the menu → <b>Saving between boots</b>, follow the steps, then reboot.\n"
            "If it says 0 MB free, run this in a terminal once, then reboot:\n"
            "<tt>wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/fix-saving.sh | sudo sh</tt>",
        )
        section(
            "Wi-Fi",
            "Click the clock (or the Wi-Fi icon next to it) to open the quick panel and join a network.\n"
            "Or open the menu → <b>Wi-Fi and Network</b> (or run <tt>nmtui</tt> in a terminal) → "
            "Activate a connection → your network. A phone USB tether or an Ethernet cable also works.",
        )
        section(
            "Keyboard shortcuts",
            "<b>Alt</b>+<b>Tab</b>  switch windows\n"
            "<b>Alt</b>+<b>F4</b>  close the window\n"
            "<b>Super</b>+<b>Enter</b>  or  <b>Ctrl</b>+<b>Alt</b>+<b>T</b>  terminal\n"
            "<b>Super</b>+<b>E</b>  files\n"
            "<b>Super</b>+<b>Space</b>  application menu\n"
            "<b>Super</b>+<b>Up</b>  maximize    <b>Super</b>+<b>Down</b>  minimize",
        )
        ver = os_version()
        section(
            "About rukeOS",
            "rukeOS %s  ·  a lightweight Alpine Linux desktop\n"
            "Updates come from the rukeOS update repo when you use <b>Check for updates</b>.\n"
            "Log: <tt>/var/log/ruke-update.log</tt>" % GLib.markup_escape_text(ver),
        )
        return box
class QuickPanel(Gtk.Window):
    def __init__(self, screenshot=None):
        Gtk.Window.__init__(self, title="Quick settings")
        try:
            GLib.set_prgname("RukeQuickPanel")
        except Exception:
            pass
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(340, 1)
        self._focus_timeout = None
        self._building = True
        self._ssid_for_password = None
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._on_key)

        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        frame.set_name("quickpanel-frame")
        self.add(frame)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_name("quickpanel")
        root.set_margin_start(12)
        root.set_margin_end(12)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        frame.pack_start(root, True, True, 0)

        head = Gtk.Label(xalign=0)
        head.set_markup("<b>Quick settings</b>")
        root.pack_start(head, False, False, 0)

        self.wifi_switch = Gtk.Switch()
        wifi_row, _ = self._row("network", "Wi-Fi", self.wifi_switch)
        root.pack_start(wifi_row, False, False, 0)
        self.wifi_sub = Gtk.Label(xalign=0)
        self.wifi_sub.get_style_context().add_class("muted")
        self.wifi_sub.set_ellipsize(Pango.EllipsizeMode.END)
        self.wifi_sub.set_margin_start(40)
        root.pack_start(self.wifi_sub, False, False, 0)
        self.wifi_switch.connect("notify::active", self._wifi_toggled)
        self.net_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_min_content_height(40)
        sc.set_max_content_height(160)
        sc.set_propagate_natural_height(True)
        sc.add(self.net_box)
        root.pack_start(sc, False, False, 0)
        self.pw_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pw_box.set_no_show_all(True)
        self.pw_hint = Gtk.Label(xalign=0)
        self.pw_hint.get_style_context().add_class("muted")
        self.pw_entry = Gtk.Entry()
        self.pw_entry.set_visibility(False)
        self.pw_entry.set_placeholder_text("Password")
        self.pw_entry.connect("activate", self._do_connect)
        pw_btn = Gtk.Button(label="Connect")
        pw_btn.get_style_context().add_class("suggested-action")
        pw_btn.connect("clicked", self._do_connect)
        self.pw_box.pack_start(self.pw_hint, False, False, 0)
        self.pw_box.pack_start(self.pw_entry, False, False, 0)
        self.pw_box.pack_start(pw_btn, False, False, 0)
        root.pack_start(self.pw_box, False, False, 0)

        self.bt_row, self.bt_switch = None, None
        if has_bluetooth():
            self.bt_switch = Gtk.Switch()
            self.bt_row, _ = self._row("bluetooth", "Bluetooth", self.bt_switch)
            self.bt_switch.connect("notify::active", self._bt_toggled)
            root.pack_start(self.bt_row, False, False, 0)

        def _lead(widget):
            box = Gtk.Box()
            box.set_size_request(24, 24)
            box.set_valign(Gtk.Align.CENTER)
            box.set_halign(Gtk.Align.CENTER)
            widget.set_halign(Gtk.Align.CENTER)
            box.pack_start(widget, True, True, 0)
            return box

        def _trail(widget=None):
            box = Gtk.Box()
            box.set_size_request(56, -1)
            box.set_valign(Gtk.Align.CENTER)
            if widget is not None:
                box.pack_start(widget, True, True, 0)
            return box

        vrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vrow.pack_start(_lead(icon_image("volume", 22)), False, False, 0)
        self.vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol.set_draw_value(False)
        self.vol.set_hexpand(True)
        self.vol.set_valign(Gtk.Align.CENTER)
        self.vol.connect("value-changed", self._vol_changed)
        self.mute_btn = Gtk.Button(label="Mute")
        self.mute_btn.get_style_context().add_class("flat")
        self.mute_btn.set_halign(Gtk.Align.END)
        self.mute_btn.connect("clicked", self._toggle_mute)
        vrow.pack_start(self.vol, True, True, 0)
        vrow.pack_start(_trail(self.mute_btn), False, False, 0)
        root.pack_start(vrow, False, False, 0)

        self.bri_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sun = Gtk.Label(label="☀")
        sun.set_xalign(0.5)
        self.bri_row.pack_start(_lead(sun), False, False, 0)
        self.bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.bri.set_draw_value(False)
        self.bri.set_hexpand(True)
        self.bri.set_valign(Gtk.Align.CENTER)
        self.bri.connect("value-changed", self._bri_changed)
        self.bri_row.pack_start(self.bri, True, True, 0)
        self.bri_row.pack_start(_trail(), False, False, 0)
        root.pack_start(self.bri_row, False, False, 0)

        self.night_switch = Gtk.Switch()
        nrow, _ = self._row(None, "Night light", self.night_switch, icon_label="☾")
        self.night_switch.connect("notify::active", self._night_toggled)
        root.pack_start(nrow, False, False, 0)
        self.air_switch = Gtk.Switch()
        arow, _ = self._row(None, "Airplane mode", self.air_switch, icon_label="✈")
        self.air_switch.connect("notify::active", self._air_toggled)
        root.pack_start(arow, False, False, 0)

        self.bat_lbl = Gtk.Label(xalign=0)
        self.bat_lbl.set_no_show_all(True)
        root.pack_start(self.bat_lbl, False, False, 0)

        actions = Gtk.Grid()
        actions.set_column_spacing(6)
        actions.set_row_spacing(6)
        actions.set_column_homogeneous(True)
        items = [
            ("settings", "Settings", self._open_settings),
            ("lock", "Lock", self._lock),
            ("user", "Log out", self._logout),
            ("updater", "Restart", self._reboot),
            ("power", "Power off", self._poweroff),
        ]
        action_css = Gtk.CssProvider()
        action_css.load_from_data(b"""
            button {
              background-image: none; background-color: #24283b; background: #24283b;
              color: #c0caf5; border: none; border-image: none; box-shadow: none;
              text-shadow: none; outline: none; border-radius: 10px;
              padding: 8px 4px 6px 4px; min-width: 56px; }
            button:hover, button:focus, button:active {
              background-image: none; background-color: #2f3549; background: #2f3549;
              color: #c0caf5; box-shadow: none; }
            button.power-btn:hover, button.power-btn:active {
              background-image: none; background-color: #f7768e; background: #f7768e;
              color: #16161e; }
            button label { color: #c0caf5; background: none; }
            button.power-btn:hover label, button.power-btn:active label { color: #16161e; }
        """)
        for i, (ic, lab, cb) in enumerate(items):
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            ctx = b.get_style_context()
            ctx.add_class("action-btn")
            if ic == "power":
                ctx.add_class("power-btn")
            ctx.add_provider(action_css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.pack_start(icon_image(ic, 24), False, False, 0)
            l = Gtk.Label(label=lab)
            l.set_xalign(0.5)
            col.pack_start(l, False, False, 0)
            col.set_halign(Gtk.Align.CENTER)
            b.add(col)
            b.connect("clicked", cb)
            actions.attach(b, i % 5, i // 5, 1, 1)
        root.pack_start(actions, False, False, 4)

        self._refresh_all()
        self._building = False
        self._place_top_right()
        threading.Thread(target=self._load_networks, args=(False,), daemon=True).start()
        maybe_screenshot(self, screenshot)
        if not screenshot:
            GLib.timeout_add(80, self._grab_focus)

    def _row(self, icon, label, switch, icon_label=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if icon:
            row.pack_start(icon_image(icon, 22), False, False, 0)
        elif icon_label:
            row.pack_start(Gtk.Label(label=icon_label), False, False, 0)
        lab = Gtk.Label(label=label, xalign=0)
        lab.set_hexpand(True)
        row.pack_start(lab, True, True, 0)
        row.pack_end(switch, False, False, 0)
        return row, switch

    def _place_top_right(self):
        self.show_all()
        if battery_info() is None:
            self.bat_lbl.hide()
        if read_brightness()[0] is None:
            self.bri_row.hide()
        screen = self.get_screen()
        try:
            mon = screen.get_monitor_geometry(
                screen.get_primary_monitor() if hasattr(screen, "get_primary_monitor") else 0
            )
            sw, mx, my = mon.width, mon.x, mon.y
        except Exception:
            sw, mx, my = screen.get_width(), 0, 0
        w, h = self.get_size()
        self.move(mx + sw - w - 10, my + 36)
        self.present()

    def _grab_focus(self):
        try:
            self.present()
            if self.get_window():
                self.get_window().focus(Gdk.CURRENT_TIME)
        except Exception:
            pass
        return False

    def _on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def _on_focus_out(self, *_):
        if self._focus_timeout:
            GLib.source_remove(self._focus_timeout)

        def _close():
            self._focus_timeout = None
            if not self.get_visible():
                return False
            if self.has_toplevel_focus():
                return False
            self.destroy()
            return False

        self._focus_timeout = GLib.timeout_add(180, _close)
        return False

    def _block_switch(self, switch, handler, value):
        if switch is None:
            return
        try:
            switch.handler_block_by_func(handler)
        except TypeError:
            pass
        switch.set_active(bool(value))
        try:
            switch.handler_unblock_by_func(handler)
        except TypeError:
            pass

    def _refresh_all(self):
        st, sig, label = wifi_state_summary()
        self._block_switch(self.wifi_switch, self._wifi_toggled, wifi_radio() and st != "airplane")
        extra = (("  ·  %s%%" % sig) if sig is not None and st == "connected" else "")
        self.wifi_sub.set_text(label + extra)
        if self.bt_switch:
            self._block_switch(self.bt_switch, self._bt_toggled, bluetooth_on())
        vol, muted_v = volume_get()
        self.vol.handler_block_by_func(self._vol_changed)
        self.vol.set_value(vol)
        self.vol.handler_unblock_by_func(self._vol_changed)
        self.mute_btn.set_label("Unmute" if muted_v else "Mute")
        cur, mx = read_brightness()
        if cur is None:
            self.bri_row.hide()
        else:
            self.bri.handler_block_by_func(self._bri_changed)
            self.bri.set_range(1, 100)
            self.bri.set_value(max(1, int(round(100.0 * cur / float(mx or 1)))))
            self.bri.handler_unblock_by_func(self._bri_changed)
            self.bri_row.show()
        ap = load_appearance()
        self._block_switch(self.night_switch, self._night_toggled, ap.get("night_light") == "1")
        self._block_switch(self.air_switch, self._air_toggled, st == "airplane" or airplane_on())
        bat = battery_info()
        if bat:
            cap, status = bat
            self.bat_lbl.set_text("Battery  %s%%  ·  %s" % (cap, status))
            self.bat_lbl.show()
        else:
            self.bat_lbl.hide()

    def _load_networks(self, rescan):
        nets, err = wifi_list(rescan=rescan)
        GLib.idle_add(self._fill_networks, nets, err)

    def _fill_networks(self, nets, err):
        for ch in list(self.net_box.get_children()):
            self.net_box.remove(ch)
        if err and not nets:
            self.net_box.pack_start(muted("Couldn't list networks."), False, False, 0)
            self.net_box.show_all()
            return False
        if not wifi_radio() or airplane_on():
            self.net_box.show_all()
            return False
        if not nets:
            self.net_box.pack_start(muted("No networks found."), False, False, 0)
        for n in nets[:12]:
            row = Gtk.EventBox()
            row.get_style_context().add_class("wifi-row")
            if n["active"]:
                row.get_style_context().add_class("active")
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            level = max(1, min(4, 1 + n["signal"] // 25))
            bars = "▂▄▆█"[:level] + " " * (4 - level)
            sig = Gtk.Label(label=bars)
            sig.get_style_context().add_class("signal")
            sig.set_width_chars(4)
            sig.set_xalign(0)
            sig.set_halign(Gtk.Align.START)
            sig_box = Gtk.Box()
            sig_box.set_size_request(36, -1)
            sig_box.pack_start(sig, False, False, 0)
            hb.pack_start(sig_box, False, False, 0)
            name = Gtk.Label(label=n["ssid"], xalign=0)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            name.set_hexpand(True)
            hb.pack_start(name, True, True, 0)
            if n["security"] and n["security"] not in ("--", "", "none", "None"):
                hb.pack_start(Gtk.Label(label="🔒"), False, False, 0)
            if n["active"]:
                hb.pack_start(Gtk.Label(label="✓"), False, False, 0)
            row.add(hb)
            row.connect("button-press-event", self._net_clicked, n)
            self.net_box.pack_start(row, False, False, 0)
        self.net_box.show_all()
        return False

    def _net_clicked(self, _w, _ev, n):
        if n.get("active"):
            return False
        sec = (n.get("security") or "").strip()
        needs_pw = sec and sec not in ("--", "", "none", "None")
        if needs_pw:
            self._ssid_for_password = n["ssid"]
            self.pw_hint.set_text("Password for “%s”" % n["ssid"])
            self.pw_entry.set_text("")
            self.pw_box.show_all()
            self.pw_entry.grab_focus()
        else:
            self._ssid_for_password = n["ssid"]
            self._do_connect()
        return False

    def _do_connect(self, *_):
        ssid = self._ssid_for_password
        if not ssid:
            return
        password = self.pw_entry.get_text() if self.pw_box.get_visible() else None
        self.wifi_sub.set_text("Connecting to %s…" % ssid)

        def work():
            rc, out = wifi_connect(ssid, password or None)

            def done():
                if rc == 0:
                    self.pw_box.hide()
                    self._refresh_all()
                    threading.Thread(target=self._load_networks, args=(False,), daemon=True).start()
                else:
                    msg = "Couldn't connect."
                    low = (out or "").lower()
                    if "password" in low or "802-11-wireless-security" in low:
                        msg = "Wrong password, try again."
                    elif out.strip():
                        msg = out.strip().splitlines()[-1][:160]
                    self.wifi_sub.set_text(msg)
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

    def _wifi_toggled(self, switch, *_):
        if self._building:
            return
        on = switch.get_active()

        def work():
            set_wifi_radio(on)
            GLib.idle_add(self._refresh_all)
            if on:
                threading.Thread(target=self._load_networks, args=(True,), daemon=True).start()

        threading.Thread(target=work, daemon=True).start()

    def _bt_toggled(self, switch, *_):
        if self._building:
            return
        on = switch.get_active()
        threading.Thread(target=lambda: set_bluetooth(on), daemon=True).start()

    def _vol_changed(self, scale):
        if self._building:
            return
        volume_set(scale.get_value())
        self.mute_btn.set_label("Mute")

    def _toggle_mute(self, *_):
        volume_toggle_mute()
        _v, muted_v = volume_get()
        self.mute_btn.set_label("Unmute" if muted_v else "Mute")

    def _bri_changed(self, scale):
        if self._building:
            return
        cur, mx = read_brightness()
        if mx:
            set_brightness(max(1, int(round(mx * scale.get_value() / 100.0))))

    def _night_toggled(self, switch, *_):
        if self._building:
            return
        d = load_appearance()
        d["night_light"] = "1" if switch.get_active() else "0"
        save_appearance(d)
        set_night_light(switch.get_active())

    def _air_toggled(self, switch, *_):
        if self._building:
            return
        on = switch.get_active()

        def work():
            set_airplane(on)
            GLib.idle_add(self._refresh_all)
            if not on:
                threading.Thread(target=self._load_networks, args=(True,), daemon=True).start()

        threading.Thread(target=work, daemon=True).start()

    def _open_settings(self, *_):
        self.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        subprocess.Popen(
            ["ruke-settings"],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _lock(self, *_):
        self.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if shutil.which("slock"):
            subprocess.Popen(["slock"], start_new_session=True)
        else:
            run_cmd(["xset", "dpms", "force", "off"], timeout=3)

    def _logout(self, *_):
        self.destroy()
        run_cmd(["jwm", "-exit"], timeout=5)

    def _confirm(self, title, body, action):
        parent_pos = self.get_position()
        self.hide()
        dlg = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=title,
        )
        dlg.format_secondary_text(body)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button(title, Gtk.ResponseType.OK)
        dlg.set_keep_above(True)
        if parent_pos:
            dlg.move(parent_pos[0], parent_pos[1] + 40)
        r = dlg.run()
        dlg.destroy()
        if r == Gtk.ResponseType.OK:
            action()
        Gtk.main_quit()

    def _reboot(self, *_):
        self._confirm(
            "Restart",
            "Restart this computer now?",
            lambda: subprocess.Popen(["sudo", "-n", "reboot"], start_new_session=True),
        )

    def _poweroff(self, *_):
        self._confirm(
            "Power off",
            "Power off this computer now?",
            lambda: subprocess.Popen(["sudo", "-n", "poweroff"], start_new_session=True),
        )
class StatusTray(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="RukeStatus")
        try:
            GLib.set_prgname("RukeStatus")
            Gdk.set_program_class("RukeStatus")
        except Exception:
            pass
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_default_size(28, 28)
        self.status, self.signal, self.label = "disconnected", None, "Wi-Fi"
        self.da = Gtk.DrawingArea()
        self.da.set_size_request(28, 28)
        self.da.connect("draw", self._draw)
        ev = Gtk.EventBox()
        ev.add(self.da)
        ev.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        ev.connect("button-press-event", self._clicked)
        ev.set_tooltip_text("Wi-Fi")
        self.tip = ev
        self.add(ev)
        self.connect("destroy", Gtk.main_quit)
        self.refresh()
        GLib.timeout_add_seconds(15, self.refresh)
        self.show_all()

    def refresh(self):
        def work():
            st, sig, label = wifi_state_summary()

            def apply():
                self.status, self.signal, self.label = st, sig, label
                self.tip.set_tooltip_text(label)
                self.da.queue_draw()
                return False

            GLib.idle_add(apply)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _clicked(self, *_):
        exe = shutil.which("ruke-quickpanel") or sys.argv[0]
        if exe == sys.argv[0]:
            subprocess.Popen(
                [sys.executable, sys.argv[0], "--quickpanel"],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [exe],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True

    def _draw(self, _w, cr):
        w, h = 28, 28
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        st, sig = self.status, self.signal
        if st in ("off", "airplane"):
            color = (0.337, 0.373, 0.537, 1)
            level = 0
            slash = True
        elif st == "ethernet":
            color = (0.482, 0.310, 0.839, 1)
            level = 4
            slash = False
        elif st == "connected":
            color = (0.753, 0.792, 0.961, 1)
            if sig is None:
                level = 3
            elif sig >= 75:
                level = 4
            elif sig >= 50:
                level = 3
            elif sig >= 25:
                level = 2
            else:
                level = 1
            slash = False
        elif st == "connecting":
            color = (0.482, 0.310, 0.839, 1)
            level = 2
            slash = False
        else:
            color = (0.337, 0.373, 0.537, 1)
            level = 1
            slash = False
        cx, cy = w / 2.0, h / 2.0 + 4
        cr.set_line_width(2.0)
        cr.set_line_cap(1)
        for radius, need in ((5.5, 1), (9.0, 2), (12.5, 3)):
            if level >= need or st == "ethernet":
                cr.set_source_rgba(*color)
            else:
                cr.set_source_rgba(0.337, 0.373, 0.537, 0.45)
            cr.new_path()
            cr.arc(cx, cy, radius, 3.665, 5.760)
            cr.stroke()
        cr.set_source_rgba(*color)
        cr.arc(cx, cy - 1, 1.4, 0, 6.283)
        cr.fill()
        if st == "ethernet":
            cr.rectangle(cx - 4, h - 5, 8, 2)
            cr.fill()
        if slash:
            cr.set_source_rgba(0.969, 0.463, 0.557, 0.95)
            cr.set_line_width(1.8)
            cr.move_to(7, 21)
            cr.line_to(21, 7)
            cr.stroke()
        return False


VIDEO_PATTERNS = (
    "*.mp4", "*.mkv", "*.webm", "*.avi", "*.mov", "*.ogv", "*.m4v",
    "*.wmv", "*.flv", "*.mpeg", "*.mpg", "*.ts", "*.m2ts", "*.3gp",
)
AUDIO_PATTERNS = (
    "*.mp3", "*.flac", "*.ogg", "*.oga", "*.opus", "*.wav", "*.m4a",
    "*.aac", "*.wma", "*.aiff", "*.ape", "*.mka",
)


def play_with_mpv(files):
    if not files:
        return 1
    mpv = shutil.which("mpv") or "mpv"
    # never leave a terminal up; mpv is its own window
    cmd = [mpv, "--player-operation-mode=pseudo-gui"] + list(files)
    try:
        subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL)
        return 0
    except FileNotFoundError:
        dlg = Gtk.MessageDialog(
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="mpv is not installed",
        )
        dlg.format_secondary_text("Install it with Updates, or run:  sudo apk add mpv")
        dlg.run()
        dlg.destroy()
        return 1


def media_picker(kind, files=None):
    """Open a file picker (Video or Music) then play the choice in mpv. If files are given, skip the picker."""
    given = [f for f in (files or []) if f and os.path.exists(f)]
    if given:
        return play_with_mpv(given)
    apply_css()
    home = os.path.expanduser("~")
    if kind == "music":
        title = "Open music"
        folder = os.path.join(home, "Music")
        filt_name = "Audio"
        pats = AUDIO_PATTERNS
        icon = "music"
    else:
        title = "Open video"
        folder = os.path.join(home, "Videos")
        filt_name = "Video"
        pats = VIDEO_PATTERNS
        icon = "video"
    os.makedirs(folder, exist_ok=True)
    dlg = Gtk.FileChooserDialog(title=title, action=Gtk.FileChooserAction.OPEN)
    dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Play", Gtk.ResponseType.OK)
    dlg.set_select_multiple(True)
    dlg.set_default_size(640, 420)
    pb = icon_pixbuf(icon, 48)
    if pb:
        dlg.set_icon(pb)
    if os.path.isdir(folder):
        dlg.set_current_folder(folder)
    filt = Gtk.FileFilter()
    filt.set_name(filt_name)
    for pat in pats:
        filt.add_pattern(pat)
    dlg.add_filter(filt)
    allf = Gtk.FileFilter()
    allf.set_name("All files")
    allf.add_pattern("*")
    dlg.add_filter(allf)
    resp = dlg.run()
    chosen = dlg.get_filenames() if resp == Gtk.ResponseType.OK else []
    dlg.destroy()
    while Gtk.events_pending():
        Gtk.main_iteration()
    if not chosen:
        return 0
    return play_with_mpv(chosen)


def toggle_instance(name):
    """If a process with this lock is running, signal it to exit and return True (toggled off)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    path = os.path.join(runtime, name + ".pid")
    if os.path.isfile(path):
        try:
            pid = int(open(path).read().strip())
            if pid > 0 and pid != os.getpid():
                os.kill(pid, signal.SIGTERM)
                try:
                    os.remove(path)
                except OSError:
                    pass
                return True
        except (ValueError, OSError, ProcessLookupError):
            try:
                os.remove(path)
            except OSError:
                pass
    return False


def write_pid(name):
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    os.makedirs(runtime, exist_ok=True)
    path = os.path.join(runtime, name + ".pid")
    with open(path, "w") as f:
        f.write(str(os.getpid()))
    return path


def main(argv=None):
    p = argparse.ArgumentParser(prog="ruke-settings", description="rukeOS Settings")
    p.add_argument("--page", choices=("updates", "customization", "help"), default="updates")
    p.add_argument("--quickpanel", action="store_true", help="open the clock quick panel")
    p.add_argument("--tray", action="store_true", help="Wi-Fi indicator for the top bar")
    p.add_argument("--apply-appearance", action="store_true", help="rewrite theme files from saved settings")
    p.add_argument("--apply-session", action="store_true", help="restore wallpaper and night light")
    p.add_argument("--play", choices=("video", "music"), help="open a Video or Music file picker, then play in mpv")
    p.add_argument("--screenshot", metavar="PATH", help="write a PNG of the window and exit")
    p.add_argument("--demo-updates", choices=("checking", "updating", "uptodate", "done", "error"))
    p.add_argument("files", nargs="*", help="media files (used with --play, or MIME open)")
    args = p.parse_args(argv)

    if args.apply_session:
        apply_appearance(load_appearance(), session_only=True)
        return 0
    if args.apply_appearance:
        apply_appearance(load_appearance(), session_only=False)
        return 0
    if args.play:
        return media_picker(args.play, args.files)

    load_css_and_display()

    if args.tray:
        StatusTray()
        Gtk.main()
        return 0

    if args.quickpanel:
        if not args.screenshot and toggle_instance("ruke-quickpanel"):
            return 0
        pid_path = write_pid("ruke-quickpanel")

        def _cleanup(*_):
            try:
                os.remove(pid_path)
            except OSError:
                pass
            Gtk.main_quit()

        signal.signal(signal.SIGTERM, _cleanup)
        signal.signal(signal.SIGINT, _cleanup)
        QuickPanel(screenshot=args.screenshot)
        try:
            Gtk.main()
        finally:
            try:
                os.remove(pid_path)
            except OSError:
                pass
        return 0

    SettingsWindow(page=args.page, demo=args.demo_updates, screenshot=args.screenshot)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
