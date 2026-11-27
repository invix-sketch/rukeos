"""Curated Alpine Linux apps for the rukeOS App store."""
from __future__ import annotations

import os
import shutil
import subprocess

try:
    import apk_job
except ImportError:
    apk_job = None

APPS = [
    {
        "id": "gimp",
        "name": "GIMP",
        "summary": "Photo and image editor",
        "category": "Graphics",
        "packages": ["gimp"],
        "icon": "gimp",
        "heavy": True,
    },
    {
        "id": "libreoffice",
        "name": "LibreOffice",
        "summary": "Writer, Calc, and Impress",
        "category": "Office",
        "packages": ["libreoffice"],
        "icon": "libreoffice-writer",
        "heavy": True,
    },
    {
        "id": "geany",
        "name": "Geany",
        "summary": "Lightweight code editor",
        "category": "Code",
        "packages": ["geany"],
        "icon": "geany",
        "heavy": False,
    },
    {
        "id": "aisleriot",
        "name": "Solitaire",
        "summary": "Card games (Aisleriot)",
        "category": "Games",
        "packages": ["aisleriot"],
        "icon": "aisleriot",
        "heavy": False,
    },
    {
        "id": "gnome-mines",
        "name": "Mines",
        "summary": "Minesweeper",
        "category": "Games",
        "packages": ["gnome-mines"],
        "icon": "gnome-mines",
        "heavy": False,
    },
    {
        "id": "supertux",
        "name": "SuperTux",
        "summary": "2D platform game",
        "category": "Games",
        "packages": ["supertux"],
        "icon": "supertux",
        "heavy": True,
    },
    {
        "id": "discord",
        "name": "Discord",
        "summary": "Opens Discord in the browser (no extra package)",
        "category": "Chat",
        "kind": "web",
        "url": "https://discord.com/app",
        "icon": "ruke-browser",
        "heavy": False,
    },
]


def _home():
    return os.environ.get("HOME") or os.path.expanduser("~")


def _run_apk(apk_args, progress=None):
    if apk_job is not None:
        return apk_job.run_apk(apk_args, progress=progress)
    # Fallback if the helper is missing: still try sudo apk once.
    cmd = ["sudo", "-n", "apk", "--no-progress"] + list(apk_args)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        lines.append(line)
        if progress:
            progress(line)
    rc = proc.wait()
    return rc, "\n".join(lines)


def apk_installed(package):
    try:
        return subprocess.call(
            ["apk", "info", "-e", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0
    except OSError:
        return False


def discord_desktop_path():
    return os.path.join(_home(), ".local", "share", "applications", "ruke-discord.desktop")


def discord_installed():
    return os.path.isfile(discord_desktop_path())


def is_installed(app):
    if app.get("kind") == "web":
        return discord_installed()
    pkgs = app.get("packages") or []
    return bool(pkgs) and all(apk_installed(p) for p in pkgs)


def install_discord():
    path = discord_desktop_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    browser = "ruke-browser" if shutil.which("ruke-browser") else "epiphany"
    body = f"""[Desktop Entry]
Type=Application
Name=Discord
Comment=Discord in the rukeOS browser
Exec={browser} https://discord.com/app
Icon=ruke-browser
Terminal=False
Categories=Network;InstantMessaging;
StartupNotify=true
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    os.chmod(path, 0o755)
    desk = os.path.join(_home(), "Desktop")
    os.makedirs(desk, exist_ok=True)
    link = os.path.join(desk, "Discord.desktop")
    if not os.path.exists(link):
        try:
            os.symlink(path, link)
        except OSError:
            with open(link, "w", encoding="utf-8") as f:
                f.write(body)
            os.chmod(link, 0o755)
    return 0, "Discord was added to the menu and the desktop. It opens in the browser."


def remove_discord():
    for path in (
        discord_desktop_path(),
        os.path.join(_home(), "Desktop", "Discord.desktop"),
    ):
        try:
            if os.path.islink(path) or os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
    return 0, "Discord was removed."


def install_app(app, progress=None):
    if app.get("kind") == "web":
        if progress:
            progress("Creating the Discord launcher…")
        return install_discord()
    pkgs = app.get("packages") or []
    if not pkgs:
        return 1, "No package is listed for this app."
    if progress:
        progress("Installing " + ", ".join(pkgs) + "…")
    rc, log = _run_apk(["add"] + pkgs, progress)
    if rc == 0:
        return 0, app["name"] + " is installed. You can open it from the menu."
    tail = "\n".join(log.splitlines()[-8:]) if log else "apk failed"
    return rc, "Could not install " + app["name"] + ".\n" + tail


def remove_app(app, progress=None):
    if app.get("kind") == "web":
        return remove_discord()
    pkgs = app.get("packages") or []
    if not pkgs:
        return 1, "No package is listed for this app."
    if progress:
        progress("Removing " + ", ".join(pkgs) + "…")
    rc, log = _run_apk(["del"] + pkgs, progress)
    if rc == 0:
        return 0, app["name"] + " was removed."
    tail = "\n".join(log.splitlines()[-8:]) if log else "apk failed"
    return rc, "Could not remove " + app["name"] + ".\n" + tail


def app_by_id(app_id):
    for app in APPS:
        if app["id"] == app_id:
            return app
    return None
