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

.wifi-shell { background-color: #1a1b26; }
.wifi-card { background-color: #24283b; border-radius: 12px; }
button.wifi-item {
  background: transparent; background-image: none; border: none; box-shadow: none;
  border-radius: 10px; padding: 0; min-height: 0; outline: none;
}
button.wifi-item:hover { background: rgba(123,79,214,0.14); background-image: none; }
button.wifi-item:active { background: rgba(123,79,214,0.22); background-image: none; }
button.wifi-item.active { background: rgba(123,79,214,0.30); background-image: none; }
button.wifi-item label { color: #c0caf5; background: none; }
.wifi-pass { background-color: #24283b; border-radius: 12px; border: 1px solid rgba(123,79,214,0.40); }
.wifi-header { color: #c0caf5; }
#taskbar-preview, .taskbar-preview { background-color: #1a1b26; }
.taskbar-top { background-color: #16161e; }
.taskbar-dock { background-color: #16161e; border-radius: 16px; }
button.suggested-action { background: #7B4FD6; background-image: none; color: #ffffff; border: none; border-radius: 8px; min-height: 32px; }
button.suggested-action:hover { background: #6A35D0; background-image: none; }
switch { min-width: 42px; }
switch:checked, switch:checked:hover, switch:checked:backdrop {
  background: #7B4FD6; background-color: #7B4FD6; background-image: none; border-color: #7B4FD6;
}
switch slider { min-width: 18px; min-height: 18px; }
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



def _set_ini_section(path, section, mapping):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        text = ""
    header = "[%s]" % section
    parts = re.split(r"(?=^\[[^\]]+\])", text, flags=re.M)
    found = False
    out = []
    for part in parts:
        if part.lstrip().startswith(header):
            found = True
            body = part
            for key, value in mapping.items():
                pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
                if pat.search(body):
                    body = pat.sub("%s=%s" % (key, value), body)
                else:
                    if body and not body.endswith("\n"):
                        body += "\n"
                    body += "%s=%s\n" % (key, value)
            out.append(body if body.endswith("\n") or body == "" else body + "\n")
        else:
            if part:
                out.append(part if part.endswith("\n") else part + "\n")
    if not found:
        chunk = header + "\n"
        for key, value in mapping.items():
            chunk += "%s=%s\n" % (key, value)
        if out and not "".join(out).endswith("\n"):
            out.append("\n")
        out.append(chunk if chunk.endswith("\n") else chunk + "\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))


def security_path():
    return os.path.join(_home(), ".config/rukeos/security.conf")


def load_security():
    d = {"lock_minutes": "10", "lock_on_sleep": "1"}
    path = security_path()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def save_security(d):
    path = security_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for k in ("lock_minutes", "lock_on_sleep"):
            f.write("%s=%s\n" % (k, d.get(k, "")))


def password_status():
    rc, out = run_cmd(["sudo", "-n", "ruke-passwd", "status"], timeout=6)
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    if rc == 0 and lines and lines[-1] in ("set", "none"):
        return lines[-1]
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if user:
        rc, out = run_cmd(["passwd", "-S", user], timeout=5)
        bits = (out or "").split()
        if len(bits) >= 2 and bits[1] in ("NP", "NK", "Empty"):
            return "none"
        if len(bits) >= 2 and bits[1] in ("P", "PS"):
            return "set"
    return "unknown"


def set_pcmanfm_desktop(wallpaper=None, theme=None, font_size=None):
    dark = (theme or "dark") != "light"
    fs = str(font_size or "10")
    mapping = {
        "wallpaper_mode": "crop",
        "show_wm_menu": "1",
        "desktop_bg": "#e6e7ed" if not dark else "#1a1b26",
        "desktop_fg": "#1a1b26" if not dark else "#c0caf5",
        "desktop_shadow": "#d0d1d8" if not dark else "#16161e",
        "desktop_font": "Inter %s" % fs,
        "show_documents": "0",
        "show_trash": "0",
        "show_mounts": "0",
    }
    if wallpaper:
        mapping["wallpaper"] = wallpaper
    conf = os.path.join(_home(), ".config/pcmanfm/default/pcmanfm.conf")
    _set_ini_section(conf, "desktop", mapping)
    if wallpaper and os.path.isfile(wallpaper) and os.environ.get("DISPLAY") and shutil.which("pcmanfm"):
        run_cmd(["pcmanfm", "--set-wallpaper", wallpaper, "--wallpaper-mode=crop"], timeout=8)


def write_gtk2_rc(theme, icons, font_size):
    path = os.path.join(_home(), ".gtkrc-2.0")
    text = (
        'gtk-theme-name = "%s"\n'
        'gtk-icon-theme-name = "%s"\n'
        'gtk-font-name = "Inter %s"\n'
        'include "/usr/share/themes/%s/gtk-2.0/gtkrc"\n'
        % (theme, icons, font_size, theme)
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def write_xsettingsd(theme, icons, font_size, dark):
    path = os.path.join(_home(), ".config/xsettingsd/xsettingsd.conf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = (
        'Net/ThemeName "%s"\n'
        'Net/IconThemeName "%s"\n'
        'Gtk/CursorThemeName "Adwaita"\n'
        'Gtk/FontName "Inter %s"\n'
        "Gtk/ApplicationPreferDarkTheme %s\n"
        "Xft/Antialias 1\n"
        "Xft/Hinting 1\n"
        'Xft/HintStyle "hintslight"\n'
        'Xft/RGBA "rgb"\n'
        % (theme, icons, font_size, 1 if dark else 0)
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        return
    if not os.environ.get("DISPLAY") or not shutil.which("xsettingsd"):
        return
    rc, _ = run_cmd(["pkill", "-u", str(os.getuid()), "-HUP", "-x", "xsettingsd"], timeout=3)
    if rc != 0:
        subprocess.Popen(
            ["xsettingsd", "-c", path],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def set_wallpaper(path, theme=None, font_size=None):
    if path and os.path.isfile(path) and shutil.which("feh"):
        run_cmd(["feh", "--no-fehbg", "--bg-fill", path], timeout=8)
    set_pcmanfm_desktop(path if path and os.path.isfile(path) else None, theme=theme, font_size=font_size)


def apply_appearance(d, session_only=False):
    wallpaper = d.get("wallpaper") or WALLPAPER_DEFAULT
    if not os.path.isfile(wallpaper):
        wallpaper = WALLPAPER_DEFAULT
    theme = d.get("theme") or "dark"
    font_size = str(d.get("font_size") or "10")
    set_wallpaper(wallpaper, theme=theme, font_size=font_size)
    set_night_light(d.get("night_light") == "1")
    if session_only:
        return
    home = _home()
    accent = d.get("accent") or BLUE
    dark = theme != "light"
    gtk_theme = "rukeOS-dark" if dark else "adw-gtk3"
    icons = "rukeOS"
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
    write_gtk2_rc(gtk_theme, icons, font_size)
    write_xsettingsd(gtk_theme, icons, font_size, dark)


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
    def __init__(self, page="updates", demo=None, screenshot=None, prompt_password=False):
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
        self.prompt_password = prompt_password
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
        for key, label in (("updates", "Updates"), ("customization", "Customization"), ("security", "Security"), ("help", "Help")):
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
        self.stack.add_titled(self._build_security(), "security", "Security")
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
            if prompt_password:
                GLib.idle_add(self._prompt_set_password)

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

    def _build_security(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.pack_start(heading("Security"), False, False, 0)
        box.pack_start(muted("Lock the screen with your password. Super+L, the Lock button, or the menu."), False, False, 0)

        self.sec_banner, banner_inner = card()
        self.sec_banner_lbl = Gtk.Label(xalign=0)
        self.sec_banner_lbl.set_line_wrap(True)
        banner_inner.pack_start(self.sec_banner_lbl, False, False, 0)
        box.pack_start(self.sec_banner, False, False, 0)

        fr, inner = card()
        inner.pack_start(heading("Password"), False, False, 0)
        self.pw_status = Gtk.Label(xalign=0)
        inner.pack_start(self.pw_status, False, False, 0)
        self.pw_current = Gtk.Entry()
        self.pw_current.set_visibility(False)
        self.pw_current.set_placeholder_text("Current password")
        self.pw_current.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw_new = Gtk.Entry()
        self.pw_new.set_visibility(False)
        self.pw_new.set_placeholder_text("New password")
        self.pw_new.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw_confirm = Gtk.Entry()
        self.pw_confirm.set_visibility(False)
        self.pw_confirm.set_placeholder_text("Confirm new password")
        self.pw_confirm.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw_confirm.connect("activate", self._save_password)
        for e in (self.pw_current, self.pw_new, self.pw_confirm):
            inner.pack_start(e, False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save = Gtk.Button(label="Save password")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self._save_password)
        row.pack_start(save, False, False, 0)
        self.pw_msg = Gtk.Label(xalign=0)
        self.pw_msg.get_style_context().add_class("muted")
        row.pack_start(self.pw_msg, True, True, 0)
        inner.pack_start(row, False, False, 0)
        box.pack_start(fr, False, False, 0)

        fr, inner = card()
        inner.pack_start(heading("Auto-lock"), False, False, 0)
        inner.pack_start(muted("Lock automatically after the computer has been idle. Choose Off to disable this."), False, False, 0)
        self.lock_idle = Gtk.ComboBoxText()
        self._idle_values = [("0", "Off"), ("1", "1 minute"), ("2", "2 minutes"),
                             ("5", "5 minutes"), ("10", "10 minutes"), ("15", "15 minutes"),
                             ("30", "30 minutes"), ("60", "60 minutes")]
        for val, lab in self._idle_values:
            self.lock_idle.append(val, lab)
        self.lock_idle.connect("changed", self._security_changed)
        inner.pack_start(self.lock_idle, False, False, 0)
        self.lock_sleep = Gtk.CheckButton(label="Lock when the computer wakes from sleep")
        self.lock_sleep.connect("toggled", self._security_changed)
        inner.pack_start(self.lock_sleep, False, False, 0)
        lock_now = Gtk.Button(label="Lock now")
        lock_now.connect("clicked", self._lock_now)
        lock_now.set_halign(Gtk.Align.START)
        inner.pack_start(lock_now, False, False, 0)
        box.pack_start(fr, False, False, 0)

        note = Gtk.Label(xalign=0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("muted")
        note.set_markup(
            "While the lock screen is up, switching to another console (Ctrl+Alt+F2…) is blocked.\n"
            "After you unlock, other consoles still ask for a password. The live image also has a "
            "<b>root</b> account with a default password — run <tt>sudo passwd root</tt> if others can reach a console."
        )
        box.pack_start(note, False, False, 0)
        self._refresh_security()
        return box

    def _refresh_security(self):
        st = password_status()
        if st == "none":
            self.sec_banner_lbl.set_markup(
                "<b>Set a password</b> so Lock can protect this computer. Until you do, the lock screen will open this page instead."
            )
            self.sec_banner.show()
            self.pw_status.set_text("No password is set.")
            self.pw_current.set_sensitive(False)
            self.pw_current.hide()
        else:
            self.sec_banner.hide()
            self.pw_status.set_text("A password is set. Enter the current one to change it.")
            self.pw_current.set_sensitive(True)
            self.pw_current.show()
        sec = load_security()
        mins = sec.get("lock_minutes") or "10"
        ids = [v for v, _ in self._idle_values]
        if mins not in ids:
            mins = "10"
        try:
            self.lock_idle.handler_block_by_func(self._security_changed)
            self.lock_idle.set_active_id(mins)
            self.lock_idle.handler_unblock_by_func(self._security_changed)
        except TypeError:
            self.lock_idle.set_active_id(mins)
        try:
            self.lock_sleep.handler_block_by_func(self._security_changed)
            self.lock_sleep.set_active(sec.get("lock_on_sleep", "1") == "1")
            self.lock_sleep.handler_unblock_by_func(self._security_changed)
        except TypeError:
            self.lock_sleep.set_active(sec.get("lock_on_sleep", "1") == "1")

    def _prompt_set_password(self):
        if password_status() != "none":
            return False
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Set a password",
        )
        dlg.format_secondary_text(
            "This computer does not have a user password yet. Set one on the Security page so the lock screen can protect it."
        )
        dlg.set_keep_above(True)
        dlg.run()
        dlg.destroy()
        return False

    def _save_password(self, *_):
        new = self.pw_new.get_text() or ""
        confirm = self.pw_confirm.get_text() or ""
        if not new:
            self.pw_msg.set_text("Enter a new password.")
            return
        if new != confirm:
            self.pw_msg.set_text("The two new passwords do not match.")
            return
        st = password_status()
        if st == "none":
            rc, out = run_cmd(["sudo", "-n", "ruke-passwd", "set"], timeout=8, input_text=new + "\n")
        else:
            old = self.pw_current.get_text() or ""
            if not old:
                self.pw_msg.set_text("Enter your current password.")
                return
            rc, out = run_cmd(["sudo", "-n", "ruke-passwd", "change"], timeout=8, input_text=old + "\n" + new + "\n")
        if rc == 0:
            self.pw_current.set_text("")
            self.pw_new.set_text("")
            self.pw_confirm.set_text("")
            self.pw_msg.set_text("Password saved.")
            self._refresh_security()
        else:
            err = (out or "").strip().splitlines()
            self.pw_msg.set_text(err[-1] if err else "Couldn't save the password.")

    def _security_changed(self, *_):
        d = load_security()
        d["lock_minutes"] = self.lock_idle.get_active_id() or "10"
        d["lock_on_sleep"] = "1" if self.lock_sleep.get_active() else "0"
        save_security(d)
        if shutil.which("ruke-autolock"):
            subprocess.Popen(
                ["ruke-autolock"],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _lock_now(self, *_):
        if password_status() == "none":
            self.pw_msg.set_text("Set a password first.")
            self.pw_new.grab_focus()
            return
        exe = shutil.which("ruke-lock") or shutil.which("slock")
        if exe:
            subprocess.Popen(
                [exe],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

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
            "Click the Wi-Fi icon next to the clock (or on the dock) for the Wi-Fi menu.\n"
            "Click the clock for the quick panel (volume, brightness, and the same Wi-Fi list).",
        )
        section(
            "Desktop",
            "Files and shortcuts in <tt>~/Desktop</tt> show as icons on the wallpaper.\n"
            "Right-click the desktop for New folder, New text file, Open terminal here, Add app shortcut, "
            "and the rukeOS application menu. You can also drag a <tt>.desktop</tt> file onto the desktop.",
        )
        section(
            "Lock screen",
            "<b>Super</b>+<b>L</b>, the Lock button in the quick panel, or the menu locks the screen.\n"
            "Set or change your password and auto-lock time in Settings \u2192 <b>Security</b>.\n"
            "While locked, switching consoles (Ctrl+Alt+F2\u2026) is blocked. Other consoles still ask for a "
            "password when unlocked; change the <b>root</b> password too if others can reach a console.",
        )
        section(
            "Keyboard shortcuts",
            "<b>Alt</b>+<b>Tab</b>  switch windows\n"
            "<b>Alt</b>+<b>F4</b>  close the window\n"
            "<b>Super</b>+<b>Enter</b>  or  <b>Ctrl</b>+<b>Alt</b>+<b>T</b>  terminal\n"
            "<b>Super</b>+<b>E</b>  files\n"
            "<b>Super</b>+<b>L</b>  lock the screen\n"
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

def _wifi_secured(n):
    sec = (n.get("security") or "").strip()
    return bool(sec and sec not in ("--", "", "none", "None"))


class SignalBars(Gtk.DrawingArea):
    """Four Tokyo Night signal bars, purple when this row is the connected network."""

    def __init__(self, level=0, active=False):
        Gtk.DrawingArea.__init__(self)
        self.level = max(0, min(4, int(level)))
        self.active = bool(active)
        self.set_size_request(20, 18)
        self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        w, h = 20, 18
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        if self.active:
            on = (0.482, 0.310, 0.839, 1)  # #7B4FD6
        else:
            on = (0.753, 0.792, 0.961, 1)  # #c0caf5
        off = (0.337, 0.373, 0.537, 0.40)
        bar_w, gap = 3.2, 1.8
        heights = (5, 8.5, 12, 16)
        total = 4 * bar_w + 3 * gap
        x0 = (w - total) / 2.0
        for i, bh in enumerate(heights):
            cr.set_source_rgba(*(on if self.level >= i + 1 else off))
            x = x0 + i * (bar_w + gap)
            y = h - bh - 1
            r = 1.1
            cr.new_path()
            cr.arc(x + bar_w - r, y + r, r, -1.5708, 0)
            cr.arc(x + bar_w - r, y + bh - r, r, 0, 1.5708)
            cr.arc(x + r, y + bh - r, r, 1.5708, 3.1416)
            cr.arc(x + r, y + r, r, 3.1416, 4.7124)
            cr.close_path()
            cr.fill()
        return False


class LockMark(Gtk.DrawingArea):
    def __init__(self, active=False):
        Gtk.DrawingArea.__init__(self)
        self.active = bool(active)
        self.set_size_request(14, 16)
        self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        if self.active:
            cr.set_source_rgba(0.482, 0.310, 0.839, 1)
        else:
            cr.set_source_rgba(0.337, 0.373, 0.537, 1)
        # shackle
        cr.set_line_width(1.6)
        cr.arc(7, 6.2, 3.1, 3.1416, 0)
        cr.stroke()
        # body
        cr.rectangle(3.2, 7.2, 7.6, 6.4)
        cr.fill()
        return False


class WifiList(Gtk.Box):
    """Shared network list + in-panel password prompt, used by the Wi-Fi menu and the quick panel."""

    def __init__(self, compact=False):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._on_connected = None
        self._ssid_for_password = None
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_min_content_height(48)
        sc.set_max_content_height(280 if not compact else 180)
        sc.set_propagate_natural_height(True)
        sc.add(self.list_box)
        self.pack_start(sc, True, True, 0)

        self.pw_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.pw_box.get_style_context().add_class("wifi-pass")
        self.pw_box.set_no_show_all(True)
        self.pw_hint = Gtk.Label(xalign=0)
        self.pw_hint.set_line_wrap(True)
        self.pw_entry = Gtk.Entry()
        self.pw_entry.set_visibility(False)
        self.pw_entry.set_placeholder_text("Password")
        self.pw_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw_entry.connect("activate", self._do_connect)
        pw_btn = Gtk.Button(label="Connect")
        pw_btn.get_style_context().add_class("suggested-action")
        pw_btn.connect("clicked", self._do_connect)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_start(12)
        inner.set_margin_end(12)
        inner.set_margin_top(10)
        inner.set_margin_bottom(10)
        inner.pack_start(self.pw_hint, False, False, 0)
        inner.pack_start(self.pw_entry, False, False, 0)
        inner.pack_start(pw_btn, False, False, 0)
        self.pw_box.pack_start(inner, False, False, 0)
        self.pack_start(self.pw_box, False, False, 0)

    def set_status_handler(self, fn):
        self._on_connected = fn

    def refresh(self, rescan=False):
        def work():
            nets, err = wifi_list(rescan=rescan)
            GLib.idle_add(self.set_networks, nets, err)
        threading.Thread(target=work, daemon=True).start()

    def set_networks(self, nets, err):
        for ch in list(self.list_box.get_children()):
            self.list_box.remove(ch)
        if not wifi_radio() or airplane_on():
            self.list_box.pack_start(muted("Wi-Fi is turned off."), False, False, 0)
            self.list_box.show_all()
            return False
        if err and not nets:
            self.list_box.pack_start(muted("Couldn't list networks."), False, False, 0)
            self.list_box.show_all()
            return False
        if not nets:
            self.list_box.pack_start(muted("No networks found."), False, False, 0)
            self.list_box.show_all()
            return False
        # connected first (wifi_list already sorts that way)
        for n in nets[:12]:
            self.list_box.pack_start(self._row(n), False, False, 0)
        self.list_box.show_all()
        return False

    def _row(self, n):
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.get_style_context().add_class("wifi-item")
        if n.get("active"):
            row.get_style_context().add_class("active")
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hb.set_margin_start(8)
        hb.set_margin_end(8)
        hb.set_margin_top(7)
        hb.set_margin_bottom(7)
        level = 0 if n.get("signal") is None else max(1, min(4, 1 + int(n["signal"]) // 25))
        hb.pack_start(SignalBars(level, n.get("active")), False, False, 0)
        name = Gtk.Label(label=n["ssid"], xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        if n.get("active"):
            name.set_markup("<b>%s</b>" % GLib.markup_escape_text(n["ssid"]))
        hb.pack_start(name, True, True, 0)
        if _wifi_secured(n):
            hb.pack_start(LockMark(n.get("active")), False, False, 0)
        if n.get("active"):
            tick = Gtk.Label()
            tick.set_markup('<span foreground="#7B4FD6"><b>✓</b></span>')
            hb.pack_start(tick, False, False, 0)
        row.add(hb)
        row.connect("clicked", self._clicked, n)
        return row

    def show_password(self, ssid):
        self._ssid_for_password = ssid
        self.pw_hint.set_markup("Password for <b>%s</b>" % GLib.markup_escape_text(ssid))
        self.pw_entry.set_text("")
        self.pw_box.set_no_show_all(False)
        self.pw_box.show_all()
        self.pw_entry.grab_focus()
        top = self.get_toplevel()
        if isinstance(top, Gtk.Window):
            top.queue_resize()
            top.resize(max(top.get_size()[0], 340), 1)

    def hide_password(self):
        self.pw_box.hide()
        self.pw_box.set_no_show_all(True)
        self._ssid_for_password = None

    def _clicked(self, _w, n):
        if n.get("active"):
            return
        if _wifi_secured(n):
            self.show_password(n["ssid"])
        else:
            self._ssid_for_password = n["ssid"]
            self._do_connect()

    def _do_connect(self, *_):
        ssid = self._ssid_for_password
        if not ssid:
            return
        password = self.pw_entry.get_text() if self.pw_box.get_visible() else None
        if self._on_connected:
            self._on_connected("Connecting to %s…" % ssid)

        def work():
            rc, out = wifi_connect(ssid, password or None)

            def done():
                if rc == 0:
                    self.hide_password()
                    if self._on_connected:
                        self._on_connected(None)
                    self.refresh(False)
                else:
                    low = (out or "").lower()
                    if "password" in low or "802-11-wireless-security" in low:
                        msg = "Wrong password, try again."
                    elif out.strip():
                        msg = out.strip().splitlines()[-1][:160]
                    else:
                        msg = "Couldn't connect."
                    self.pw_hint.set_text(msg)
                    if self._on_connected:
                        self._on_connected(msg)
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()


class WifiPanel(Gtk.Window):
    """Dedicated Wi-Fi menu opened from the top-bar icon or the dock."""

    def __init__(self, screenshot=None, demo=False):
        Gtk.Window.__init__(self, title="Wi-Fi")
        try:
            GLib.set_prgname("RukeWifi")
        except Exception:
            pass
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(340, -1)
        self._focus_timeout = None
        self._building = True
        self._demo = demo
        if not screenshot:
            self.connect("focus-out-event", self._on_focus_out)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", lambda _w, ev: ev.keyval == Gdk.KEY_Escape and (self.destroy() or True) or False)

        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        frame.set_name("quickpanel-frame")
        self.add(frame)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.get_style_context().add_class("wifi-shell")
        root.set_margin_start(14)
        root.set_margin_end(14)
        root.set_margin_top(14)
        root.set_margin_bottom(14)
        frame.pack_start(root, True, True, 0)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        head.pack_start(icon_image("network", 28), False, False, 0)
        title = Gtk.Label(xalign=0)
        title.set_markup("<b>Wi-Fi</b>")
        title.set_hexpand(True)
        head.pack_start(title, True, True, 0)
        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.connect("notify::active", self._wifi_toggled)
        head.pack_end(self.wifi_switch, False, False, 0)
        root.pack_start(head, False, False, 0)

        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("muted")
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        root.pack_start(self.status, False, False, 0)

        self.wifi_list = WifiList(compact=False)
        self.wifi_list.set_status_handler(self._status_from_list)
        root.pack_start(self.wifi_list, True, True, 0)

        adv = Gtk.Button(label="Advanced network settings")
        adv.get_style_context().add_class("flat")
        adv.set_halign(Gtk.Align.START)
        adv.connect("clicked", self._advanced)
        root.pack_start(adv, False, False, 0)

        self._refresh_header()
        self._building = False
        if screenshot or demo:
            nets, err = wifi_list(rescan=False)
            self.wifi_list.set_networks(nets, err)
        else:
            self.wifi_list.refresh(False)
        if demo:
            self.wifi_list.show_password("Cafe")
        self._place_top_right()
        maybe_screenshot(self, screenshot)
        if not screenshot:
            GLib.timeout_add(80, self._grab_focus)

    def _demo_password(self):
        self.wifi_list.show_password("Cafe")
        return False

    def _refresh_header(self):
        st, sig, label = wifi_state_summary()
        try:
            self.wifi_switch.handler_block_by_func(self._wifi_toggled)
        except TypeError:
            pass
        self.wifi_switch.set_active(wifi_radio() and st != "airplane")
        try:
            self.wifi_switch.handler_unblock_by_func(self._wifi_toggled)
        except TypeError:
            pass
        extra = (("  ·  %s%%" % sig) if sig is not None and st == "connected" else "")
        self.status.set_text(label + extra)

    def _status_from_list(self, msg):
        if msg:
            self.status.set_text(msg)
        else:
            self._refresh_header()

    def _wifi_toggled(self, switch, *_):
        if self._building:
            return
        on = switch.get_active()

        def work():
            set_wifi_radio(on)
            GLib.idle_add(self._refresh_header)
            if on:
                self.wifi_list.refresh(True)

        threading.Thread(target=work, daemon=True).start()

    def _advanced(self, *_):
        self.destroy()
        subprocess.Popen(
            ["xterm", "-T", "Network", "-e", "nmtui"],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
        )

    def _place_top_right(self):
        self.show_all()
        if not getattr(self, "_demo", False):
            self.wifi_list.hide_password()
        screen = self.get_screen()
        try:
            mon = screen.get_monitor_geometry(
                screen.get_primary_monitor() if hasattr(screen, "get_primary_monitor") else 0
            )
            sw, mx, my = mon.width, mon.x, mon.y
        except Exception:
            sw, mx, my = screen.get_width(), 0, 0
        w, _h = self.get_size()
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

    def _on_focus_out(self, *_):
        if self._focus_timeout:
            GLib.source_remove(self._focus_timeout)

        def _close():
            self._focus_timeout = None
            if not self.get_visible() or self.has_toplevel_focus():
                return False
            self.destroy()
            return False

        self._focus_timeout = GLib.timeout_add(180, _close)
        return False


class TaskbarPreview(Gtk.Window):
    """Headless preview of the dock + a sliver of the top bar with the new icon pack."""

    def __init__(self, screenshot=None):
        Gtk.Window.__init__(self, title="rukeOS")
        self.set_default_size(900, 220)
        self.set_decorated(False)
        self.set_name("taskbar-preview")
        self.connect("destroy", Gtk.main_quit)
        bg = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bg.get_style_context().add_class("taskbar-preview")
        self.add(bg)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top.get_style_context().add_class("taskbar-top")
        top.set_size_request(-1, 36)
        logo = Gtk.Label(label="rukeOS")
        logo.set_markup("<b>rukeOS</b>")
        top.pack_start(logo, False, False, 12)
        top.pack_start(Gtk.Label(), True, True, 0)
        clock = Gtk.Label(label="Tue 24 Nov   15:00")
        top.pack_end(clock, False, False, 12)
        top.pack_end(icon_image("network", 20), False, False, 8)
        bg.pack_start(top, False, False, 0)

        bg.pack_start(Gtk.Label(), True, True, 0)

        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dock.set_halign(Gtk.Align.CENTER)
        dock.set_valign(Gtk.Align.END)
        dock.set_margin_bottom(18)
        frame = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        frame.get_style_context().add_class("taskbar-dock")
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_margin_top(12)
        inner.set_margin_bottom(12)
        items = [
            ("terminal", "Terminal"),
            ("files", "Files"),
            ("browser", "Browser"),
            ("text-editor", "Editor"),
            ("video", "Video"),
            ("music", "Music"),
            ("settings", "Settings"),
            ("network", "Wi-Fi"),
            ("volume", "Volume"),
        ]
        for name, label in items:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            col.set_halign(Gtk.Align.CENTER)
            col.pack_start(icon_image(name, 48), False, False, 0)
            l = Gtk.Label(label=label)
            l.get_style_context().add_class("muted")
            col.pack_start(l, False, False, 0)
            inner.pack_start(col, False, False, 0)
        frame.pack_start(inner, False, False, 0)
        dock.pack_start(frame, False, False, 0)
        bg.pack_end(dock, False, False, 0)
        maybe_screenshot(self, screenshot)
        if not screenshot:
            self.show_all()
            self.present()



def _wallpaper_pixbuf(w, h):
    for path in (
        os.environ.get("RUKE_WALLPAPER") or "",
        "/usr/share/backgrounds/rukeos.png",
        "/workspace/judah-os/work/art/wallpaper.png",
        "/workspace/judah-os/work/rootfs/usr/share/backgrounds/rukeos.png",
    ):
        if path and os.path.isfile(path):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w, h, False)
            except Exception:
                continue
    return None


def add_shortcut_dialog():
    """Pick an application and copy its .desktop file to ~/Desktop."""
    desk = os.path.join(_home(), "Desktop")
    os.makedirs(desk, exist_ok=True)
    apps = []
    seen = set()
    for d in ("/usr/share/applications", os.path.join(_home(), ".local/share/applications")):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".desktop"):
                continue
            path = os.path.join(d, fn)
            name, icon, hidden, typ = fn[:-8], "", False, "Application"
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            if "\n[Desktop Entry]" not in "\n" + text:
                continue
            for line in text.splitlines():
                if line.startswith("Name=") and "Name" not in (x.split("=", 1)[0] for x in []):
                    pass
            meta = {}
            for line in text.splitlines():
                if not line or line.startswith("#") or line.startswith("[") or "=" not in line:
                    if line.startswith("[") and line.strip() != "[Desktop Entry]":
                        break
                    continue
                k, v = line.split("=", 1)
                if k in ("Name", "Icon", "Exec", "Type", "NoDisplay", "Hidden", "OnlyShowIn") and k not in meta:
                    meta[k] = v
            if meta.get("Type", "Application") != "Application":
                continue
            if meta.get("NoDisplay", "").lower() == "true" or meta.get("Hidden", "").lower() == "true":
                continue
            label = meta.get("Name") or fn[:-8]
            if label in seen:
                continue
            seen.add(label)
            apps.append((label, meta.get("Icon") or "", path, fn))
    win = Gtk.Window(title="Add app shortcut")
    try:
        GLib.set_prgname("RukeDesktop")
    except Exception:
        pass
    win.set_default_size(420, 480)
    win.set_position(Gtk.WindowPosition.CENTER)
    win.connect("destroy", Gtk.main_quit)
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    root.set_margin_start(14)
    root.set_margin_end(14)
    root.set_margin_top(12)
    root.set_margin_bottom(12)
    win.add(root)
    root.pack_start(heading("Add app shortcut"), False, False, 0)
    root.pack_start(muted("Pick an app to place on the desktop. You can also drag a .desktop file there."), False, False, 0)
    sc = Gtk.ScrolledWindow()
    sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sc.set_vexpand(True)
    lst = Gtk.ListBox()
    lst.set_selection_mode(Gtk.SelectionMode.SINGLE)
    sc.add(lst)
    root.pack_start(sc, True, True, 0)
    rows = []
    for label, icon, path, fn in apps:
        row = Gtk.ListBoxRow()
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hb.set_margin_start(8)
        hb.set_margin_end(8)
        hb.set_margin_top(6)
        hb.set_margin_bottom(6)
        img = icon_image(icon.replace("ruke-", "") if icon.startswith("ruke-") else "app-menu", 24)
        if icon and not icon.startswith("ruke-"):
            try:
                img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            except Exception:
                pass
        hb.pack_start(img, False, False, 0)
        hb.pack_start(Gtk.Label(label=label, xalign=0), True, True, 0)
        row.add(hb)
        row._ruke_src = path
        row._ruke_fn = fn
        lst.add(row)
        rows.append(row)
    status = Gtk.Label(xalign=0)
    status.get_style_context().add_class("muted")
    btn = Gtk.Button(label="Add to desktop")
    btn.get_style_context().add_class("suggested-action")

    def _add(_=None):
        row = lst.get_selected_row()
        if row is None:
            status.set_text("Select an application first.")
            return
        dest = os.path.join(desk, row._ruke_fn)
        base, ext = os.path.splitext(row._ruke_fn)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(desk, "%s %s%s" % (base, n, ext))
            n += 1
        try:
            import shutil as sh
            sh.copy2(row._ruke_src, dest)
            os.chmod(dest, 0o755)
            status.set_text("Added “%s” to the desktop." % os.path.basename(dest))
        except OSError as e:
            status.set_text(str(e))

    btn.connect("clicked", _add)
    lst.connect("row-activated", lambda *_: _add())
    root.pack_start(status, False, False, 0)
    root.pack_start(btn, False, False, 0)
    win.show_all()
    win.present()
    Gtk.main()
    return 0


class DesktopPreview(Gtk.Window):
    def __init__(self, screenshot=None):
        Gtk.Window.__init__(self, title="rukeOS desktop")
        self.set_default_size(1100, 640)
        self.set_decorated(False)
        self.set_name("taskbar-preview")
        self.connect("destroy", Gtk.main_quit)
        overlay = Gtk.Overlay()
        self.add(overlay)
        area = Gtk.DrawingArea()
        area.connect("draw", self._draw_bg)
        overlay.add(area)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        overlay.add_overlay(col)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top.get_style_context().add_class("taskbar-top")
        top.set_size_request(-1, 36)
        logo = Gtk.Label()
        logo.set_markup("<b>rukeOS</b>")
        top.pack_start(logo, False, False, 12)
        top.pack_start(Gtk.Label(), True, True, 0)
        top.pack_end(Gtk.Label(label="Tue 24 Nov   15:20"), False, False, 12)
        top.pack_end(icon_image("network", 20), False, False, 8)
        col.pack_start(top, False, False, 0)

        mid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        mid.set_hexpand(True)
        mid.set_vexpand(True)
        icons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        icons.set_margin_start(28)
        icons.set_margin_top(28)
        icons.set_valign(Gtk.Align.START)
        for name, label in (("files", "Files"), ("terminal", "Terminal"), ("browser", "Browser"), ("settings", "Settings")):
            item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            item.set_halign(Gtk.Align.CENTER)
            item.pack_start(icon_image(name, 48), False, False, 0)
            l = Gtk.Label(label=label)
            l.set_markup('<span foreground="#c0caf5" size="small">%s</span>' % label)
            item.pack_start(l, False, False, 0)
            icons.pack_start(item, False, False, 0)
        mid.pack_start(icons, False, False, 0)

        # fake right-click menu
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        menu.get_style_context().add_class("wifi-pass")
        menu.set_valign(Gtk.Align.START)
        menu.set_halign(Gtk.Align.START)
        menu.set_margin_top(80)
        menu.set_margin_start(40)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner.set_margin_start(8)
        inner.set_margin_end(8)
        inner.set_margin_top(8)
        inner.set_margin_bottom(8)
        for i, lab in enumerate((
            "New folder", "New text file", "Open terminal here", "Add app shortcut...",
            None, "Terminal", "Files", "Browser", "Settings",
            None, "Lock", "Restart desktop", "Power off",
        )):
            if lab is None:
                inner.pack_start(Gtk.Separator(), False, False, 6)
                continue
            l = Gtk.Label(label=lab, xalign=0)
            l.set_margin_start(10)
            l.set_margin_end(24)
            l.set_margin_top(5)
            l.set_margin_bottom(5)
            if i == 0:
                ev = Gtk.EventBox()
                ev.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.482, 0.310, 0.839, 1))
                ev.add(l)
                inner.pack_start(ev, False, False, 0)
            else:
                inner.pack_start(l, False, False, 0)
        menu.pack_start(inner, False, False, 0)
        mid.pack_start(menu, False, False, 0)
        col.pack_start(mid, True, True, 0)

        maybe_screenshot(self, screenshot)
        if not screenshot:
            self.show_all()
            self.present()

    def _draw_bg(self, w, cr):
        alloc = w.get_allocation()
        pb = _wallpaper_pixbuf(max(alloc.width, 1), max(alloc.height, 1))
        if pb:
            Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgb(0.102, 0.106, 0.149)
            cr.paint()
        return False


class LockPreview(Gtk.Window):
    def __init__(self, screenshot=None):
        Gtk.Window.__init__(self, title="rukeOS lock")
        self.set_default_size(1100, 640)
        self.set_decorated(False)
        self.connect("destroy", Gtk.main_quit)
        area = Gtk.DrawingArea()
        area.connect("draw", self._draw)
        self.add(area)
        maybe_screenshot(self, screenshot)
        if not screenshot:
            self.show_all()
            self.present()

    def _draw(self, w, cr):
        alloc = w.get_allocation()
        width, height = max(alloc.width, 1), max(alloc.height, 1)
        pb = _wallpaper_pixbuf(width, height)
        if pb:
            Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
            cr.paint()
            cr.set_source_rgba(0.102, 0.106, 0.149, 0.35)
            cr.paint()
        else:
            cr.set_source_rgb(0.102, 0.106, 0.149)
            cr.paint()
        cx, cy = width / 2.0, height / 2.0 - 20
        radius = 110
        # ring
        cr.set_line_width(8)
        cr.set_source_rgb(0.482, 0.310, 0.839)  # #7B4FD6
        cr.arc(cx, cy, radius, 0, 6.2832)
        cr.stroke()
        cr.set_source_rgba(0.102, 0.106, 0.149, 0.85)
        cr.arc(cx, cy, radius - 8, 0, 6.2832)
        cr.fill()
        # time + date
        cr.set_source_rgb(0.753, 0.792, 0.961)
        cr.select_font_face("Inter", 0, 0)
        cr.set_font_size(48)
        text = "15:20"
        xb, yb, tw, th, xa, ya = cr.text_extents(text)
        cr.move_to(cx - tw / 2.0, cy - 8)
        cr.show_text(text)
        cr.set_font_size(16)
        text = "Tuesday, 24 November"
        xb, yb, tw, th, xa, ya = cr.text_extents(text)
        cr.move_to(cx - tw / 2.0, cy + 22)
        cr.show_text(text)
        cr.set_font_size(18)
        text = "rukeOS  ·  locked"
        xb, yb, tw, th, xa, ya = cr.text_extents(text)
        cr.move_to(cx - tw / 2.0, cy + radius + 36)
        cr.show_text(text)
        return False


class FileManagerPreview(Gtk.Window):
    """Tokyo Night PCManFM stand-in used for preview-files.png (host has no pcmanfm)."""

    def __init__(self, screenshot=None):
        Gtk.Window.__init__(self, title="Files")
        self.set_default_size(900, 560)
        self.set_name("files-preview")
        try:
            GLib.set_prgname("RukeFiles")
        except Exception:
            pass
        pb = icon_pixbuf("files", 48)
        if pb:
            self.set_icon(pb)
        self.connect("destroy", Gtk.main_quit)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.get_style_context().add_class("taskbar-top")
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_size_request(-1, 36)
        for lab in ("◀", "▶", "↑", "🏠"):
            b = Gtk.Button(label=lab)
            b.set_relief(Gtk.ReliefStyle.NONE)
            toolbar.pack_start(b, False, False, 0)
        path = Gtk.Label(label="  /home/judah", xalign=0)
        path.set_hexpand(True)
        toolbar.pack_start(path, True, True, 8)
        outer.pack_start(toolbar, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.pack_start(body, True, True, 0)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        side.get_style_context().add_class("taskbar-top")
        side.set_size_request(180, -1)
        side.set_margin_top(8)
        side.set_margin_start(8)
        for name, lab in (("user", "Home"), ("files", "Desktop"), ("documents", "Documents"),
                          ("downloads", "Downloads"), ("image-viewer", "Pictures"),
                          ("video", "Videos"), ("music", "Music")):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_margin_start(10)
            row.set_margin_end(10)
            row.set_margin_top(4)
            row.set_margin_bottom(4)
            row.pack_start(icon_image(name, 20), False, False, 0)
            l = Gtk.Label(label=lab, xalign=0)
            if lab == "Home":
                l.set_markup("<b>Home</b>")
            row.pack_start(l, True, True, 0)
            side.pack_start(row, False, False, 0)
        body.pack_start(side, False, False, 0)

        view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        view.get_style_context().add_class("taskbar-preview")
        grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        grid.set_margin_start(28)
        grid.set_margin_top(24)
        grid.set_valign(Gtk.Align.START)
        for name, lab in (("files", "Desktop"), ("documents", "Documents"),
                          ("downloads", "Downloads"), ("image-viewer", "Pictures"),
                          ("terminal", "Terminal.desktop"), ("browser", "Browser.desktop")):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            col.set_halign(Gtk.Align.CENTER)
            col.set_size_request(96, -1)
            col.pack_start(icon_image(name, 48), False, False, 0)
            l = Gtk.Label(label=lab)
            l.set_line_wrap(True)
            l.set_justify(Gtk.Justification.CENTER)
            l.set_max_width_chars(12)
            col.pack_start(l, False, False, 0)
            grid.pack_start(col, False, False, 0)
        view.pack_start(grid, True, True, 0)
        body.pack_start(view, True, True, 0)

        status = Gtk.Label(label="6 items", xalign=0)
        status.get_style_context().add_class("muted")
        status.set_margin_start(12)
        status.set_margin_top(4)
        status.set_margin_bottom(4)
        outer.pack_end(status, False, False, 0)
        maybe_screenshot(self, screenshot)
        if not screenshot:
            self.show_all()
            self.present()



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
        self.wifi_list = WifiList(compact=True)
        self.wifi_list.set_status_handler(lambda msg: self.wifi_sub.set_text(msg) if msg else self._refresh_all())
        root.pack_start(self.wifi_list, False, False, 0)

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
        if screenshot:
            nets, err = wifi_list(rescan=False)
            self.wifi_list.set_networks(nets, err)
        else:
            self.wifi_list.refresh(False)
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

    def _wifi_toggled(self, switch, *_):
        if self._building:
            return
        on = switch.get_active()

        def work():
            set_wifi_radio(on)
            GLib.idle_add(self._refresh_all)
            if on:
                self.wifi_list.refresh(True)

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
                self.wifi_list.refresh(True)

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
        exe = shutil.which("ruke-lock") or shutil.which("slock")
        if exe:
            subprocess.Popen(
                [exe],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
        exe = shutil.which("ruke-wifi") or sys.argv[0]
        if exe == sys.argv[0]:
            subprocess.Popen(
                [sys.executable, sys.argv[0], "--wifi"],
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
    p.add_argument("--page", choices=("updates", "customization", "security", "help"), default="updates")
    p.add_argument("--quickpanel", action="store_true", help="open the clock quick panel")
    p.add_argument("--wifi", action="store_true", help="open the Wi-Fi menu")
    p.add_argument("--preview-taskbar", action="store_true", help="render a dock/taskbar preview and exit")
    p.add_argument("--preview-desktop", action="store_true", help="render a desktop-icons preview and exit")
    p.add_argument("--preview-lock", action="store_true", help="render a lock-screen preview and exit")
    p.add_argument("--preview-files", action="store_true", help="render a Files (PCManFM) theme preview and exit")
    p.add_argument("--add-shortcut", action="store_true", help="pick an app and add a shortcut to the desktop")
    p.add_argument("--prompt-password", action="store_true", help="open Security and ask to set a password if none is set")
    p.add_argument("--tray", action="store_true", help="Wi-Fi indicator for the top bar")
    p.add_argument("--apply-appearance", action="store_true", help="rewrite theme files from saved settings")
    p.add_argument("--apply-session", action="store_true", help="restore wallpaper and night light")
    p.add_argument("--play", choices=("video", "music"), help="open a Video or Music file picker, then play in mpv")
    p.add_argument("--screenshot", metavar="PATH", help="write a PNG of the window and exit")
    p.add_argument("--demo-updates", choices=("checking", "updating", "uptodate", "done", "error"))
    p.add_argument("--demo-wifi", action="store_true", help="show the Wi-Fi password prompt in screenshots")
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

    if args.preview_taskbar:
        TaskbarPreview(screenshot=args.screenshot)
        Gtk.main()
        return 0
    if args.preview_desktop:
        DesktopPreview(screenshot=args.screenshot)
        Gtk.main()
        return 0
    if args.preview_lock:
        LockPreview(screenshot=args.screenshot)
        Gtk.main()
        return 0
    if args.preview_files:
        FileManagerPreview(screenshot=args.screenshot)
        Gtk.main()
        return 0
    if args.add_shortcut:
        return add_shortcut_dialog()

    if args.wifi:
        if not args.screenshot and toggle_instance("ruke-wifi"):
            return 0
        pid_path = write_pid("ruke-wifi")

        def _cleanup_wifi(*_):
            try:
                os.remove(pid_path)
            except OSError:
                pass
            Gtk.main_quit()

        signal.signal(signal.SIGTERM, _cleanup_wifi)
        signal.signal(signal.SIGINT, _cleanup_wifi)
        WifiPanel(screenshot=args.screenshot, demo=args.demo_wifi)
        try:
            Gtk.main()
        finally:
            try:
                os.remove(pid_path)
            except OSError:
                pass
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

    SettingsWindow(page=args.page, demo=args.demo_updates, screenshot=args.screenshot, prompt_password=args.prompt_password)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
