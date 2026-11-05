from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "nautilus-copy-path" / "config.json"

DEFAULT_CONFIG = {
    "notifications": True,
    "show_submenu": True,
    "default_format": "absolute",
}


def load_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_CONFIG, **data}
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def get_git_relative_path(path_str: str) -> str | None:
    p = Path(path_str).resolve()
    target_dir = p if p.is_dir() else p.parent
    try:
        root = subprocess.check_output(
            ["git", "-C", str(target_dir), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return str(p.relative_to(root))
    except Exception:
        return None


def format_single_path(path: str, style: str) -> str | None:
    p = Path(path)
    if style == "absolute":
        return str(p.resolve())
    if style == "tilde":
        home = str(Path.home())
        resolved = str(p.resolve())
        return resolved.replace(home, "~", 1) if resolved.startswith(home) else resolved
    if style == "git":
        return get_git_relative_path(path)
    if style == "shell":
        return shlex.quote(str(p.resolve()))
    if style == "basename":
        return p.name
    if style == "uri":
        return p.resolve().as_uri()
    if style == "markdown":
        return f"[{p.name}]({p.resolve().as_uri()})"
    return str(p.resolve())


def format_multiple_paths(paths: list[str], style: str) -> str:
    if style == "shell_spaced":
        return " ".join(shlex.quote(str(Path(p).resolve())) for p in paths)
    if style == "json":
        return json.dumps([str(Path(p).resolve()) for p in paths], indent=2)
    formatted = [format_single_path(p, style) or str(Path(p).resolve()) for p in paths]
    return "\n".join(formatted)


def copy_to_clipboard(text: str) -> None:
    # Nautilus owns the clipboard natively through GTK. That is instant and needs
    # no window focus. wl-copy/xclip are only a fallback, and are started without
    # waiting: on GNOME/Wayland wl-copy needs a focused surface to take the
    # clipboard, so waiting for it can hang until another window is focused.
    try:
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        if display:
            display.get_clipboard().set(text)
            return
    except Exception:
        pass

    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.stdin.write(text.encode("utf-8"))
                proc.stdin.close()
            except Exception:
                pass
            return


def notify(summary: str, body: str = "") -> None:
    config = load_config()
    if not config.get("notifications", True):
        return
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(
                [
                    "notify-send",
                    "-t",
                    "1500",
                    "-h",
                    "int:transient:1",
                    "-a",
                    "Files",
                    "-i",
                    "edit-copy",
                    summary,
                    body,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


try:
    import gi

    for _ver in ("4.1", "4.0", "3.0"):
        try:
            gi.require_version("Nautilus", _ver)
            break
        except ValueError:
            pass
    for _ver in ("4.0", "3.0"):
        try:
            gi.require_version("Gdk", _ver)
            break
        except ValueError:
            pass
    from gi.repository import GObject, Nautilus

    HAS_NAUTILUS = True
except Exception:
    HAS_NAUTILUS = False
    GObject = type("GObject", (), {"GObject": object})
    Nautilus = type("Nautilus", (), {"MenuProvider": object, "MenuItem": object, "Menu": object})


class CopyPathExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        super().__init__()

    def _resolve_path(self, item: Nautilus.FileInfo) -> str | None:
        location = item.get_location()
        if location:
            p = location.get_path()
            if p:
                return p
        uri = item.get_uri()
        if uri and uri.startswith("file://"):
            return urllib.parse.unquote(uri[7:])
        return uri

    def _activate_single(self, _menu: Nautilus.MenuItem, path: str, style: str) -> None:
        result = format_single_path(path, style)
        if result:
            copy_to_clipboard(result)
            notify("Path copied", result)

    def _activate_multi(self, _menu: Nautilus.MenuItem, paths: list[str], style: str) -> None:
        result = format_multiple_paths(paths, style)
        if result:
            copy_to_clipboard(result)
            count = len(paths)
            notify(f"{count} paths copied", f"Format: {style}")

    def get_file_items(self, *args) -> list[Nautilus.MenuItem]:
        if not HAS_NAUTILUS:
            return []
        files = args[-1]
        if not files:
            return []

        config = load_config()
        paths = [self._resolve_path(f) for f in files]
        paths = [p for p in paths if p]
        if not paths:
            return []

        if len(paths) == 1:
            path = paths[0]
            default_style = config.get("default_format", "absolute")
            main_item = Nautilus.MenuItem(
                name="CopyPath::Main",
                label="Copy Path",
                tip="Copy path to clipboard",
                icon="edit-copy",
            )
            main_item.connect("activate", self._activate_single, path, default_style)

            if not config.get("show_submenu", True):
                return [main_item]

            submenu_item = Nautilus.MenuItem(
                name="CopyPath::Submenu",
                label="Copy as...",
                tip="Copy path in alternative formats",
                icon="edit-copy",
            )
            submenu = Nautilus.Menu()
            submenu_item.set_submenu(submenu)

            formats = [
                ("Absolute Path", "absolute"),
                ("Home Path (~)", "tilde"),
            ]
            if get_git_relative_path(path):
                formats.append(("Git Relative Path", "git"))
            formats.extend(
                [
                    ("Shell Quoted", "shell"),
                    ("Name Only", "basename"),
                    ("File URI", "uri"),
                    ("Markdown Link", "markdown"),
                ]
            )

            for idx, (label, style) in enumerate(formats):
                sub_item = Nautilus.MenuItem(
                    name=f"CopyPath::Single_{idx}_{style}",
                    label=label,
                )
                sub_item.connect("activate", self._activate_single, path, style)
                submenu.append_item(sub_item)

            return [main_item, submenu_item]

        count = len(paths)
        default_style = config.get("default_format", "absolute")
        main_item = Nautilus.MenuItem(
            name="CopyPath::MainMulti",
            label=f"Copy Paths ({count})",
            tip="Copy paths to clipboard",
            icon="edit-copy",
        )
        main_item.connect("activate", self._activate_multi, paths, default_style)

        if not config.get("show_submenu", True):
            return [main_item]

        submenu_item = Nautilus.MenuItem(
            name="CopyPath::SubmenuMulti",
            label="Copy as...",
            tip="Copy paths in alternative formats",
            icon="edit-copy",
        )
        submenu = Nautilus.Menu()
        submenu_item.set_submenu(submenu)

        multi_formats = [
            ("Newline Separated", "absolute"),
            ("Shell Quoted (Space-separated)", "shell_spaced"),
            ("Home Paths (~)", "tilde"),
            ("Names Only", "basename"),
            ("Markdown Links", "markdown"),
            ("JSON Array", "json"),
        ]
        for idx, (label, style) in enumerate(multi_formats):
            sub_item = Nautilus.MenuItem(
                name=f"CopyPath::Multi_{idx}_{style}",
                label=label,
            )
            sub_item.connect("activate", self._activate_multi, paths, style)
            submenu.append_item(sub_item)

        return [main_item, submenu_item]

    def get_background_items(self, *args) -> list[Nautilus.MenuItem]:
        if not HAS_NAUTILUS:
            return []
        folder = args[-1]
        if not folder:
            return []

        path = self._resolve_path(folder)
        if not path:
            return []

        config = load_config()
        default_style = config.get("default_format", "absolute")
        main_item = Nautilus.MenuItem(
            name="CopyPath::BgMain",
            label="Copy Folder Path",
            tip="Copy current folder path to clipboard",
            icon="edit-copy",
        )
        main_item.connect("activate", self._activate_single, path, default_style)

        if not config.get("show_submenu", True):
            return [main_item]

        submenu_item = Nautilus.MenuItem(
            name="CopyPath::BgSubmenu",
            label="Copy as...",
            tip="Copy folder path in alternative formats",
            icon="edit-copy",
        )
        submenu = Nautilus.Menu()
        submenu_item.set_submenu(submenu)

        formats = [
            ("Absolute Path", "absolute"),
            ("Home Path (~)", "tilde"),
        ]
        if get_git_relative_path(path):
            formats.append(("Git Relative Path", "git"))
        formats.extend(
            [
                ("Shell Quoted", "shell"),
                ("Folder URI", "uri"),
            ]
        )

        for idx, (label, style) in enumerate(formats):
            sub_item = Nautilus.MenuItem(
                name=f"CopyPath::Bg_{idx}_{style}",
                label=label,
            )
            sub_item.connect("activate", self._activate_single, path, style)
            submenu.append_item(sub_item)

        return [main_item, submenu_item]
