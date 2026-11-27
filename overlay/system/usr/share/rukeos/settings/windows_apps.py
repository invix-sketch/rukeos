#!/usr/bin/env python3
"""Search the winget-pkgs catalog and install classic Windows installers under Wine."""
from __future__ import print_function
try:
    import apk_job
except ImportError:
    apk_job = None

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

GITHUB = "https://api.github.com"
RAW = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master"
UA = "rukeOS-windows-apps/0.4.4"
CACHE_DIR_NAME = "windows-apps"
WINEPREFIX_NAME = "wine"
SKIP_TYPES = ("msix", "appx", "msixbundle", "appxbundle", "msstore", "store")

# Small built-in index so a first search works without GitHub code-search auth.
# Values are winget PackageIdentifier (Publisher.Name).
KNOWN = {
    "7-zip": "7zip.7zip",
    "7zip": "7zip.7zip",
    "vlc": "VideoLAN.VLC",
    "notepad++": "Notepad++.Notepad++",
    "notepadpp": "Notepad++.Notepad++",
    "firefox": "Mozilla.Firefox",
    "chrome": "Google.Chrome",
    "git": "Git.Git",
    "putty": "PuTTY.PuTTY",
    "winscp": "WinSCP.WinSCP",
    "sumatrapdf": "SumatraPDF.SumatraPDF",
    "sumatra": "SumatraPDF.SumatraPDF",
    "irfanview": "IrfanSkiljan.IrfanView",
    "audacity": "Audacity.Audacity",
    "gimp": "GIMP.GIMP",
    "inkscape": "Inkscape.Inkscape",
    "everything": "voidtools.Everything",
    "sharex": "ShareX.ShareX",
    "cpu-z": "CPUID.CPU-Z",
    "cpuz": "CPUID.CPU-Z",
    "winrar": "RARLab.WinRAR",
    "python": "Python.Python.3.12",
    "vscode": "Microsoft.VisualStudioCode",
    "visual studio code": "Microsoft.VisualStudioCode",
    "libreoffice": "TheDocumentFoundation.LibreOffice",
}

def _home():
    return os.environ.get("HOME") or os.path.expanduser("~")


def cache_dir():
    d = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(_home(), ".cache")), "rukeos", CACHE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def state_path():
    d = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(_home(), ".config")), "rukeos")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "windows-apps.json")


def load_state():
    path = state_path()
    if not os.path.isfile(path):
        return {"installed": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"installed": []}
    if not isinstance(data, dict):
        return {"installed": []}
    data.setdefault("installed", [])
    return data


def save_state(data):
    path = state_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def wineprefix():
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(_home(), ".local/share")), "rukeos", WINEPREFIX_NAME)


def machine():
    return (os.uname().machine or "").lower()


def wine_supported():
    return machine() in ("x86_64", "amd64")


def wine_bin():
    return shutil.which("wine")


def arch_message():
    return (
        "Windows apps need an x86_64 computer so Wine can run .exe installers. "
        "This computer is %s, so they cannot be installed here." % (machine() or "unknown")
    )


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=20, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json, application/json, */*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            data = r.read()
            if binary:
                return 200, data
            return 200, data.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read()
        if binary:
            return e.code, body
        return e.code, body.decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def parse_simple_yaml(text):
    """Tiny subset parser for winget installer/locale manifests (enough for our fields)."""
    root = {}
    stack = [(root, -1)]
    pending_key = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        s = raw.strip()
        while stack and indent <= stack[-1][1] and not (s.startswith("- ") and indent == stack[-1][1]):
            # stay on list parent when the next item is another '-'
            if s.startswith("- ") and stack[-1][0].__class__ is list and indent >= stack[-2][1]:
                break
            if len(stack) == 1:
                break
            if indent <= stack[-1][1]:
                stack.pop()
            else:
                break
        cur, _ = stack[-1]
        if s.startswith("- "):
            item = {}
            rest = s[2:]
            if not isinstance(cur, list):
                # shouldn't happen often
                if pending_key and isinstance(stack[-1][0], dict):
                    pass
            if isinstance(cur, list):
                if ":" in rest and not rest.startswith("http"):
                    k, _, v = rest.partition(":")
                    item[k.strip()] = _scalar(v.strip())
                elif rest:
                    item = _scalar(rest)
                cur.append(item)
                if isinstance(item, dict):
                    stack.append((item, indent))
            continue
        if ":" in s:
            k, _, v = s.partition(":")
            k, v = k.strip(), v.strip()
            if v == "":
                nxt = {}
                # decide list vs dict later; default dict, convert if we see '-'
                cur[k] = nxt
                pending_key = k
                stack.append((nxt, indent))
            else:
                cur[k] = _scalar(v)
                pending_key = None
    return root


def _promote_lists(obj, text):
    """Re-parse lists properly: the tiny parser may leave Installers as a dict. Use a line scan for Installers."""
    return obj


def parse_installers(text):
    """Return (header dict, list of installer dicts) from an installer YAML."""
    header = {}
    installers = []
    current = None
    in_installers = False
    in_switches = False
    switches = None
    base_indent = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        s = raw.strip()
        if s.startswith("Installers:"):
            in_installers = True
            in_switches = False
            continue
        if not in_installers:
            if s.startswith("InstallerSwitches:"):
                continue
            if ":" in s and not s.startswith("- "):
                k, _, v = s.partition(":")
                if v.strip():
                    header[k.strip()] = _scalar(v.strip())
            continue
        # left the Installers block
        if indent == 0 and not s.startswith("- ") and s.endswith(":") and not s.startswith("Installers"):
            break
        if s.startswith("- "):
            current = {}
            installers.append(current)
            in_switches = False
            rest = s[2:]
            if ":" in rest:
                k, _, v = rest.partition(":")
                current[k.strip()] = _scalar(v.strip())
            continue
        if current is None:
            continue
        if s.startswith("InstallerSwitches:"):
            switches = {}
            current["InstallerSwitches"] = switches
            in_switches = True
            continue
        if in_switches:
            if indent <= 4 and ":" in s and not s.startswith("Silent") and not s.startswith("Custom") and not s.startswith("Interactive"):
                # likely left switches
                in_switches = False
            else:
                if ":" in s:
                    k, _, v = s.partition(":")
                    switches[k.strip()] = _scalar(v.strip())
                continue
        if ":" in s:
            k, _, v = s.partition(":")
            current[k.strip()] = _scalar(v.strip())
    return header, installers


def _scalar(v):
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


def package_to_path(pkg_id):
    """VideoLAN.VLC -> manifests/v/VideoLAN/VLC"""
    parts = [p for p in (pkg_id or "").split(".") if p]
    if len(parts) < 2:
        return None
    publisher, name = parts[0], "/".join(parts[1:])
    return "manifests/%s/%s/%s" % (publisher[0].lower(), publisher, name)


def list_versions(pkg_id):
    rel = package_to_path(pkg_id)
    if not rel:
        return []
    code, body = http_get("%s/repos/microsoft/winget-pkgs/contents/%s" % (GITHUB, rel), timeout=20)
    if code != 200:
        return []
    try:
        items = json.loads(body)
    except ValueError:
        return []
    versions = [i["name"] for i in items if i.get("type") == "dir"]
    versions.sort(key=_ver_key, reverse=True)
    return versions


def _ver_key(s):
    nums = [int(x) if x.isdigit() else 0 for x in re.split(r"[^0-9]+", s) if x != ""]
    return nums or [0]


def fetch_installer_manifest(pkg_id, version=None):
    rel = package_to_path(pkg_id)
    if not rel:
        return None, "That package id does not look valid."
    if not version:
        versions = list_versions(pkg_id)
        if not versions:
            return None, "Couldn't find that package in the winget catalog."
        version = versions[0]
    # filename is usually PackageId.last + .installer.yaml, or the last segment
    last = pkg_id.split(".")[-1]
    candidates = [
        "%s/%s/%s.installer.yaml" % (rel, version, pkg_id),
        "%s/%s/%s.installer.yaml" % (rel, version, last),
    ]
    # list the version dir if needed
    code, body = http_get("%s/repos/microsoft/winget-pkgs/contents/%s/%s" % (GITHUB, rel, urllib.parse.quote(version)), timeout=20)
    files = []
    if code == 200:
        try:
            files = [i["name"] for i in json.loads(body) if i.get("name")]
        except ValueError:
            files = []
    for name in files:
        if name.endswith(".installer.yaml"):
            candidates.insert(0, "%s/%s/%s" % (rel, version, name))
    text = None
    used = None
    for c in candidates:
        code, body = http_get("%s/%s" % (RAW, c), timeout=20)
        if code == 200 and "InstallerUrl" in body:
            text, used = body, c
            break
    if not text:
        return None, "Couldn't read the installer manifest."
    header, installers = parse_installers(text)
    header["PackageIdentifier"] = header.get("PackageIdentifier") or pkg_id
    header["PackageVersion"] = header.get("PackageVersion") or version
    locale_name = None
    for name in files:
        if name.endswith(".locale.en-US.yaml") or name.endswith(".yaml") and ".locale." in name:
            code, body = http_get("%s/%s/%s/%s" % (RAW, rel, version, name), timeout=15)
            if code == 200:
                m = re.search(r"^PackageName:\s*(.+)$", body, re.M)
                if m:
                    locale_name = _scalar(m.group(1))
                    break
    return {
        "id": header["PackageIdentifier"],
        "version": header["PackageVersion"],
        "name": locale_name or header.get("PackageName") or pkg_id,
        "installers": installers,
        "manifest": used,
    }, None


def pick_installer(installers):
    """Prefer x64 exe/msi. Skip Microsoft Store / MSIX packages."""
    usable = []
    for ins in installers:
        typ = (ins.get("InstallerType") or ins.get("NestedInstallerType") or "").lower()
        if typ in SKIP_TYPES or typ.startswith("msix") or typ.startswith("appx"):
            continue
        url = ins.get("InstallerUrl") or ""
        low = url.lower()
        if any(low.endswith(ext) for ext in (".msix", ".msixbundle", ".appx", ".appxbundle")):
            continue
        if "microsoft.com/store" in low or typ == "msstore":
            continue
        if not url:
            continue
        if typ not in ("exe", "msi", "inno", "nullsoft", "wix", "burn", "zip", ""):
            # still allow if it looks like exe/msi
            if not any(low.endswith(ext) for ext in (".exe", ".msi")):
                continue
        usable.append(ins)
    def score(ins):
        arch = (ins.get("Architecture") or "").lower()
        typ = (ins.get("InstallerType") or "").lower()
        a = 0
        if arch in ("x64", "amd64"):
            a += 4
        elif arch in ("neutral", "x86"):
            a += 2
        if typ in ("exe", "inno", "nullsoft", "burn"):
            a += 2
        elif typ in ("msi", "wix"):
            a += 1
        return a
    usable.sort(key=score, reverse=True)
    return usable[0] if usable else None


def silent_args(ins):
    sw = ins.get("InstallerSwitches") or {}
    typ = (ins.get("InstallerType") or "").lower()
    silent = sw.get("Silent") or sw.get("SilentWithProgress") or sw.get("Custom") or ""
    if silent:
        return silent
    url = (ins.get("InstallerUrl") or "").lower()
    if typ in ("msi", "wix") or url.endswith(".msi"):
        return "/qn"
    if typ in ("inno",):
        return "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
    if typ in ("nullsoft",):
        return "/S"
    return "/S"


def search(query, limit=12):
    q = (query or "").strip()
    if not q:
        return [], None
    results = []
    seen = set()
    # 1) built-in names / exact package id
    low = q.lower()
    hits = []
    if "." in q and " " not in q:
        hits.append(q)
    for name, pkg in KNOWN.items():
        if low in name or low in pkg.lower():
            hits.append(pkg)
    for pkg in hits:
        if pkg in seen:
            continue
        seen.add(pkg)
        info, err = fetch_installer_manifest(pkg)
        if info:
            results.append(info)
        if len(results) >= limit:
            return results, None
    # 2) GitHub code search (may be rate-limited / require auth)
    if len(results) < 3:
        qenc = urllib.parse.quote("%s repo:microsoft/winget-pkgs filename:.installer.yaml" % q)
        code, body = http_get("%s/search/code?q=%s" % (GITHUB, qenc), timeout=20)
        if code == 200:
            try:
                items = json.loads(body).get("items") or []
            except ValueError:
                items = []
            for it in items:
                path = it.get("path") or ""
                # manifests/v/VideoLAN/VLC/3.0.20/VideoLAN.VLC.installer.yaml
                m = re.match(r"manifests/./([^/]+)/(.+)/[^/]+/([^/]+)\.installer\.yaml$", path)
                if not m:
                    continue
                pkg = m.group(3)
                if pkg in seen:
                    continue
                seen.add(pkg)
                info, err = fetch_installer_manifest(pkg)
                if info:
                    results.append(info)
                if len(results) >= limit:
                    break
    if not results:
        # last chance: treat "Publisher.Name" fetch error as the message
        if "." in q and " " not in q:
            _, err = fetch_installer_manifest(q)
            return [], err or "No classic Windows installers found."
        return [], "No classic Windows installers found. Try a name like VLC or a winget id like VideoLAN.VLC."
    return results, None


def wine_ok():
    return bool(wine_bin())


def install_wine():
    if not wine_supported():
        return 1, arch_message()
    if wine_ok():
        return 0, "Wine is already installed."
    try:
        if apk_job is not None:
            rc, out = apk_job.run_apk(["add", "wine"], timeout=600)
        else:
            sudo = shutil.which("sudo") or "sudo"
            p = subprocess.run(
                [sudo, "apk", "add", "--no-progress", "wine"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=600,
            )
            rc, out = p.returncode, (p.stdout or "")
        if rc != 0:
            return rc, (out or "").strip() or "Couldn't install Wine."
        if not wine_ok():
            return 1, "apk finished but the wine command is still missing."
        return 0, "Wine is installed."
    except subprocess.TimeoutExpired:
        return 124, "Installing Wine timed out."
    except OSError as e:
        return 1, str(e)


def download_and_verify(url, sha256, dest):
    expected = (sha256 or "").strip().lower()
    if not expected or len(expected) != 64:
        return None, "The manifest is missing a SHA256 checksum, so the download was not started."
    code, data = http_get(url, timeout=180, binary=True)
    if code != 200 or not data:
        return None, "Couldn't download the installer."
    got = hashlib.sha256(data).hexdigest()
    if got != expected:
        return None, "The installer checksum did not match (wanted %s, got %s). Installation was cancelled." % (expected, got)
    with open(dest, "wb") as f:
        f.write(data)
    return dest, None


def _wine_env():
    env = os.environ.copy()
    env["WINEPREFIX"] = wineprefix()
    env["WINEDEBUG"] = "-all"
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d"
    env["DISPLAY"] = os.environ.get("DISPLAY", "")
    os.makedirs(env["WINEPREFIX"], exist_ok=True)
    return env


def run_installer(path, ins):
    typ = (ins.get("InstallerType") or "").lower()
    url = (ins.get("InstallerUrl") or "").lower()
    args = silent_args(ins)
    env = _wine_env()
    wine = wine_bin()
    if typ in ("msi", "wix") or path.lower().endswith(".msi"):
        cmd = [wine, "msiexec", "/i", path] + (args.split() if args else ["/qn"])
    else:
        cmd = [wine, path] + (args.split() if args else [])
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, timeout=1800)
        return p.returncode, p.stdout or ""
    except subprocess.TimeoutExpired:
        return 124, "The installer timed out."
    except OSError as e:
        return 1, str(e)


def _lnk_files(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip windows system noise
        low = dirpath.lower()
        if any(s in low for s in ("/windows/", "/installer", "internet explorer", "accessories", "administrative tools", "system tools", "windows powershell")):
            continue
        for name in filenames:
            if name.lower().endswith(".lnk"):
                found.append(os.path.join(dirpath, name))
    return found


def make_launchers(info):
    """Create .desktop files (and a menu snippet) for Start Menu shortcuts added by the installer."""
    prefix = wineprefix()
    before_log = []  # we just scan current start menu
    start_roots = []
    for base in (
        os.path.join(prefix, "drive_c", "ProgramData", "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(prefix, "drive_c", "users"),
    ):
        if os.path.isdir(base) and base.endswith("users"):
            for user in os.listdir(base):
                p = os.path.join(base, user, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs")
                if os.path.isdir(p):
                    start_roots.append(p)
                desk = os.path.join(base, user, "Desktop")
                if os.path.isdir(desk):
                    start_roots.append(desk)
        elif os.path.isdir(base):
            start_roots.append(base)
    lnks = []
    for root in start_roots:
        lnks.extend(_lnk_files(root))
    # prefer lnks whose names look like the package
    needle = (info.get("name") or info.get("id") or "").split(".")[-1].lower()
    ranked = sorted(lnks, key=lambda p: (0 if needle and needle in os.path.basename(p).lower() else 1, len(p)))
    if not ranked:
        # generic launcher into the wine prefix explorer
        ranked = []
    created = []
    apps_dir = os.path.join(_home(), ".local", "share", "applications")
    desk_dir = os.path.join(_home(), "Desktop")
    os.makedirs(apps_dir, exist_ok=True)
    os.makedirs(desk_dir, exist_ok=True)
    targets = ranked[:4] if ranked else [None]
    wine = wine_bin() or "wine"
    prefix = wineprefix()
    for i, lnk in enumerate(targets):
        title = info.get("name") or info.get("id")
        if lnk:
            title = os.path.splitext(os.path.basename(lnk))[0]
            exec_line = 'env WINEPREFIX=%s WINEDEBUG=-all %s start /unix %s' % (
                _quote(prefix), _quote(wine), _quote(lnk)
            )
        else:
            exec_line = 'env WINEPREFIX=%s WINEDEBUG=-all %s explorer' % (_quote(prefix), _quote(wine))
        fname = "ruke-windows-%s%s.desktop" % (re.sub(r"[^A-Za-z0-9]+", "-", info.get("id") or title).strip("-"), "" if i == 0 else "-%d" % i)
        body = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=%s\n"
            "Comment=Windows app (Wine) — %s\n"
            "Exec=%s\n"
            "Icon=ruke-app-menu\n"
            "Terminal=false\n"
            "Categories=Wine;Application;\n"
            % (title, info.get("id") or "", exec_line)
        )
        for dest_dir, mode in ((apps_dir, 0o644), (desk_dir, 0o755)):
            dest = os.path.join(dest_dir, fname)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(body)
            os.chmod(dest, mode)
            created.append(dest)
    _write_menu_entries(info, targets, wine, prefix)
    return created


def _quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def _write_menu_entries(info, lnks, wine, prefix):
    menu = os.path.join(_home(), ".config", "jgmenu", "windows-apps.csv")
    os.makedirs(os.path.dirname(menu), exist_ok=True)
    existing = ""
    if os.path.isfile(menu):
        with open(menu, encoding="utf-8") as f:
            existing = f.read()
    icon = "/usr/share/icons/hicolor/24x24/apps/ruke-app-menu.png"
    lines = existing.splitlines()
    # drop header we will rewrite
    body = [l for l in lines if not l.startswith("^sep") and l.strip()]
    added = False
    for i, lnk in enumerate(lnks or [None]):
        title = info.get("name") or info.get("id")
        if lnk:
            title = os.path.splitext(os.path.basename(lnk))[0]
            cmd = "env WINEPREFIX=%s WINEDEBUG=-all %s start /unix %s" % (prefix, wine, lnk)
        else:
            cmd = "env WINEPREFIX=%s WINEDEBUG=-all %s explorer" % (prefix, wine)
        entry = "%s,%s,%s" % (title.replace(",", " "), cmd, icon)
        # replace by title
        body = [l for l in body if not l.startswith(title + ",")]
        body.append(entry)
        added = True
    text = "^sep(Windows apps)\n" + "\n".join(body) + ("\n" if body else "")
    with open(menu, "w", encoding="utf-8") as f:
        f.write(text)
    _ensure_menu_include()


def _ensure_menu_include():
    menu = os.path.join(_home(), ".config", "jgmenu", "menu.csv")
    inc = "^include(%s)" % os.path.join(_home(), ".config", "jgmenu", "windows-apps.csv")
    if not os.path.isfile(menu):
        return
    with open(menu, encoding="utf-8") as f:
        text = f.read()
    if "windows-apps.csv" in text:
        return
    # insert before System section if present, else before the last sep
    if "^sep(System)" in text:
        text = text.replace("^sep(System)", inc + "\n^sep(System)", 1)
    else:
        text = text.rstrip() + "\n" + inc + "\n"
    with open(menu, "w", encoding="utf-8") as f:
        f.write(text)


def install_package(info, progress=None):
    """Download, verify, run the installer, write launchers. progress(msg) optional."""
    def say(msg):
        if progress:
            progress(msg)
    if not wine_supported():
        return False, arch_message()
    if not wine_ok():
        return False, "Wine is not installed yet."
    ins = pick_installer(info.get("installers") or [])
    if not ins:
        return False, "That package only has Microsoft Store or MSIX installers, which rukeOS cannot install."
    url = ins.get("InstallerUrl")
    sha = ins.get("InstallerSha256") or ""
    ext = ".msi" if (ins.get("InstallerType") or "").lower() in ("msi", "wix") or (url or "").lower().endswith(".msi") else ".exe"
    dest = os.path.join(cache_dir(), re.sub(r"[^A-Za-z0-9._-]+", "-", info.get("id") or "app") + ext)
    say("Downloading %s…" % (info.get("name") or info.get("id")))
    path, err = download_and_verify(url, sha, dest)
    if err:
        return False, err
    say("Running the installer in Wine…")
    rc, out = run_installer(path, ins)
    try:
        os.remove(path)
    except OSError:
        pass
    if rc not in (0, None):
        tail = "\n".join((out or "").strip().splitlines()[-8:])
        return False, "The installer exited with an error." + (("\n" + tail) if tail else "")
    created = make_launchers(info)
    st = load_state()
    st["installed"] = [x for x in st.get("installed") or [] if x.get("id") != info.get("id")]
    st["installed"].append({"id": info.get("id"), "name": info.get("name"), "version": info.get("version"), "launchers": created, "time": int(time.time())})
    save_state(st)
    say("Installed.")
    return True, "Installed. A launcher was added to the desktop and the application menu."
