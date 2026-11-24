#!/usr/bin/env python3
"""rukeOS keyboard shortcuts: defaults, per-user config, JWM key file."""
from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
import xml.sax.saxutils as saxutils

CONFIG_NAME = "shortcuts.json"
KEYS_NAME = "jwm-keys.xml"

# kind: "exec" uses payload as a command; "jwm" uses a raw JWM action (close, nextstacked, …).
DEFAULTS = [
    {
        "id": "menu",
        "label": "Application menu",
        "keys": "Super+Space",
        "kind": "exec",
        "command": "jgmenu --simple --csv-file={menu}",
    },
    {
        "id": "terminal",
        "label": "Terminal",
        "keys": "Ctrl+Alt+T",
        "kind": "exec",
        "command": "xterm",
    },
    {
        "id": "terminal-super",
        "label": "Terminal (Super+Enter)",
        "keys": "Super+Enter",
        "kind": "exec",
        "command": "xterm",
    },
    {
        "id": "files",
        "label": "Files",
        "keys": "Super+E",
        "kind": "exec",
        "command": "pcmanfm",
    },
    {
        "id": "browser",
        "label": "Browser",
        "keys": "Super+B",
        "kind": "exec",
        "command": "ruke-browser",
    },
    {
        "id": "settings",
        "label": "Settings",
        "keys": "Super+I",
        "kind": "exec",
        "command": "ruke-settings",
    },
    {
        "id": "task-manager",
        "label": "Task manager",
        "keys": "Ctrl+Shift+Esc",
        "kind": "exec",
        "command": "xterm -T Tasks -e htop",
    },
    {
        "id": "lock",
        "label": "Lock screen",
        "keys": "Super+L",
        "kind": "exec",
        "command": "ruke-lock",
    },
    {
        "id": "close",
        "label": "Close window",
        "keys": "Alt+F4",
        "kind": "jwm",
        "command": "close",
    },
    {
        "id": "switch-windows",
        "label": "Switch windows",
        "keys": "Alt+Tab",
        "kind": "jwm",
        "command": "nextstacked",
    },
    {
        "id": "screenshot",
        "label": "Screenshot",
        "keys": "PrtSc",
        "kind": "exec",
        "command": "ruke-screenshot",
    },
    {
        "id": "maximize",
        "label": "Maximize window",
        "keys": "Super+Up",
        "kind": "jwm",
        "command": "maximize",
    },
    {
        "id": "minimize",
        "label": "Minimize window",
        "keys": "Super+Down",
        "kind": "jwm",
        "command": "minimize",
    },
]

_DEFAULT_BY_ID = {d["id"]: d for d in DEFAULTS}

_MOD_TO_JWM = {
    "control": "C",
    "ctrl": "C",
    "shift": "S",
    "alt": "A",
    "mod1": "A",
    "super": "4",
    "meta": "4",
    "win": "4",
    "mod4": "4",
}

_KEY_TO_JWM = {
    "esc": "Escape",
    "escape": "Escape",
    "prtsc": "Print",
    "prtscr": "Print",
    "print": "Print",
    "printscreen": "Print",
    "sysrq": "Sys_Req",
    "space": "space",
    "return": "Return",
    "enter": "Return",
    "tab": "Tab",
    "backspace": "BackSpace",
    "delete": "Delete",
    "del": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "pagedown": "Next",
    "pgup": "Prior",
    "pgdn": "Next",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "plus": "plus",
    "minus": "minus",
}

_JWM_TO_DISPLAY = {
    "Escape": "Esc",
    "Print": "PrtSc",
    "Return": "Enter",
    "space": "Space",
    "Prior": "PageUp",
    "Next": "PageDown",
    "BackSpace": "Backspace",
}

_MOD_ORDER = ("Super", "Ctrl", "Alt", "Shift")


def config_home():
    return os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))


def home_dir():
    return os.environ.get("HOME") or os.path.expanduser("~")


def config_path():
    return os.path.join(config_home(), "rukeos", CONFIG_NAME)


def keys_path():
    return os.path.join(config_home(), "rukeos", KEYS_NAME)


def jwmrc_path():
    return os.path.join(home_dir(), ".jwmrc")


def menu_csv_path():
    return os.path.join(config_home(), "jgmenu", "menu.csv")


def empty_config():
    return {"overrides": {}, "disabled": [], "custom": []}


def load_config():
    path = config_path()
    data = empty_config()
    if not os.path.isfile(path):
        return data
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError, TypeError):
        return data
    if not isinstance(raw, dict):
        return data
    ov = raw.get("overrides") or {}
    if isinstance(ov, dict):
        data["overrides"] = ov
    dis = raw.get("disabled") or []
    if isinstance(dis, list):
        data["disabled"] = [str(x) for x in dis]
    custom = raw.get("custom") or []
    if isinstance(custom, list):
        data["custom"] = [c for c in custom if isinstance(c, dict)]
    return data


def save_config(data):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {
        "overrides": data.get("overrides") or {},
        "disabled": data.get("disabled") or [],
        "custom": data.get("custom") or [],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)
    return path


def expand_command(command):
    command = command or ""
    return command.replace("{menu}", menu_csv_path()).replace("{home}", home_dir())


def split_combo(keys):
    if not keys:
        return [], ""
    parts = [p.strip() for p in str(keys).replace("-", "+").split("+") if p.strip()]
    mods, key = [], ""
    for p in parts:
        low = p.lower().replace("_", "")
        if low in _MOD_TO_JWM:
            name = {
                "C": "Ctrl",
                "S": "Shift",
                "A": "Alt",
                "4": "Super",
            }[_MOD_TO_JWM[low]]
            if name not in mods:
                mods.append(name)
        else:
            key = p
    return mods, key


def normalize_keys(keys):
    mods, key = split_combo(keys)
    if not key:
        return ""
    jwm_key = to_jwm_key(key)
    display_key = _JWM_TO_DISPLAY.get(jwm_key, jwm_key)
    if len(display_key) == 1:
        display_key = display_key.upper()
    ordered = [m for m in _MOD_ORDER if m in mods]
    return "+".join(ordered + [display_key])


def to_jwm_key(key):
    raw = (key or "").strip()
    low = raw.lower().replace("_", "").replace(" ", "")
    if low in _KEY_TO_JWM:
        return _KEY_TO_JWM[low]
    if re.fullmatch(r"f\d{1,2}", low):
        return "F" + low[1:]
    if len(raw) == 1:
        return raw.lower()
    return raw


def to_jwm(keys):
    """Return (mask, key) for a JWM <Key> element, or (None, None) if invalid."""
    mods, key = split_combo(keys)
    if not key:
        return None, None
    mask = ""
    letter = {"Super": "4", "Ctrl": "C", "Alt": "A", "Shift": "S"}
    for m in ("Ctrl", "Shift", "Alt", "Super"):
        if m in mods:
            mask += letter[m]
    return mask, to_jwm_key(key)


def keys_conflict(a, b):
    ja, ka = to_jwm(a)
    jb, kb = to_jwm(b)
    if not ka or not kb:
        return False
    return (ja or "") == (jb or "") and ka.lower() == kb.lower()


def resolved_entries(config=None):
    """List of shortcut dicts as they will be applied (defaults + overrides + custom)."""
    cfg = config if config is not None else load_config()
    disabled = set(cfg.get("disabled") or [])
    overrides = cfg.get("overrides") or {}
    out = []
    for d in DEFAULTS:
        if d["id"] in disabled:
            item = dict(d)
            item["enabled"] = False
            item["builtin"] = True
            item["command"] = expand_command(item.get("command") or "")
            item["keys"] = normalize_keys(item["keys"])
            out.append(item)
            continue
        item = dict(d)
        ov = overrides.get(d["id"]) or {}
        if isinstance(ov, dict):
            if ov.get("keys"):
                item["keys"] = ov["keys"]
            if d["kind"] == "exec" and ov.get("command"):
                item["command"] = ov["command"]
        item["keys"] = normalize_keys(item["keys"])
        item["command"] = expand_command(item.get("command") or "")
        item["enabled"] = True
        item["builtin"] = True
        item["overridden"] = bool(ov)
        out.append(item)
    for c in cfg.get("custom") or []:
        kid = str(c.get("id") or "").strip() or ("c-" + uuid.uuid4().hex[:8])
        keys = normalize_keys(c.get("keys") or "")
        cmd = (c.get("command") or "").strip()
        if not keys or not cmd:
            continue
        out.append({
            "id": kid,
            "label": (c.get("label") or cmd).strip() or "Custom",
            "keys": keys,
            "kind": "exec",
            "command": cmd,
            "enabled": True,
            "builtin": False,
        })
    return out


def find_conflict(keys, entries, skip_id=None):
    keys = normalize_keys(keys)
    for e in entries:
        if skip_id and e["id"] == skip_id:
            continue
        if not e.get("enabled", True):
            continue
        if keys_conflict(keys, e.get("keys")):
            return e
    return None


def write_keys_xml(entries=None, path=None):
    entries = entries if entries is not None else resolved_entries()
    path = path or keys_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        '<?xml version="1.0"?>',
        "<!-- Generated by ruke-shortcuts. Edit in Settings → Keyboard shortcuts. -->",
        "<JWM>",
    ]
    seen = set()
    for e in entries:
        if not e.get("enabled", True):
            continue
        mask, key = to_jwm(e.get("keys"))
        if not key:
            continue
        sig = (mask or "", key.lower())
        if sig in seen:
            continue
        seen.add(sig)
        if e.get("kind") == "jwm":
            action = (e.get("command") or "").strip()
        else:
            cmd = (e.get("command") or "").strip()
            if not cmd:
                continue
            action = "exec:" + cmd
        attr = ""
        if mask:
            attr += ' mask="%s"' % saxutils.escape(mask, {"\"": "&quot;"})
        attr += ' key="%s"' % saxutils.escape(key, {"\"": "&quot;"})
        lines.append("  <Key%s>%s</Key>" % (attr, saxutils.escape(action)))
    lines.append("</JWM>")
    lines.append("")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)
    return path


def patch_jwmrc(path=None, include_path=None):
    """Replace in-file <Key> bindings with an Include of the generated keys file."""
    path = path or jwmrc_path()
    include_path = include_path or keys_path()
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        text = f.read()
    original = text
    text = re.sub(r"\s*<Key\b[^>]*>.*?</Key>", "", text)
    inc = "  <Include>%s</Include>" % saxutils.escape(include_path)
    if "jwm-keys.xml" in text:
        # Keep the existing Include, but make sure the path is current.
        text = re.sub(
            r"[ \t]*<Include>\s*[^<]*jwm-keys\.xml\s*</Include>",
            inc,
            text,
        )
    else:
        if re.search(r"</JWM>\s*$", text):
            text = re.sub(r"\s*</JWM>\s*$", "\n" + inc + "\n</JWM>\n", text)
        else:
            text = text.rstrip() + "\n" + inc + "\n"
    if text != original:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        return True
    return False


def restart_jwm():
    if not os.environ.get("DISPLAY"):
        return False
    try:
        subprocess.run(["jwm", "-restart"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def apply_shortcuts(config=None, restart=False):
    cfg = config if config is not None else load_config()
    entries = resolved_entries(cfg)
    write_keys_xml(entries)
    patch_jwmrc()
    if restart:
        restart_jwm()
    return keys_path()


def ensure_shortcuts():
    """Create the keys file and JWM include if they are missing; never clobber a user keys file."""
    cfg = load_config()
    if not os.path.isfile(config_path()):
        save_config(cfg)
    if not os.path.isfile(keys_path()):
        write_keys_xml(resolved_entries(cfg))
    patch_jwmrc()
    return keys_path()


def new_custom_id():
    return "c-" + uuid.uuid4().hex[:8]


def main(argv=None):
    p = argparse.ArgumentParser(prog="ruke-shortcuts", description="rukeOS keyboard shortcuts")
    p.add_argument("--ensure", action="store_true", help="write defaults if missing; patch JWM include")
    p.add_argument("--apply", action="store_true", help="regenerate JWM keys from the user config")
    p.add_argument("--restart", action="store_true", help="restart JWM after applying")
    args = p.parse_args(argv)
    if args.apply:
        path = apply_shortcuts(restart=args.restart)
        print(path)
        return 0
    # default: --ensure
    path = ensure_shortcuts()
    if args.restart:
        restart_jwm()
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
