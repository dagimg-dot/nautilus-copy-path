# nautilus-copy-path

A Nautilus (GNOME Files) extension that adds a customizable "Copy Path" and "Copy as..." context menu for files, folders, and directory backgrounds.

![Context Menu Screenshot](assets/screenshot.svg)

## Features

- Single click primary action to copy the default path format.
- Submenu with multiple path formatting options:
  - Absolute Path: `/home/user/project/file.txt`
  - Home Path: `~/project/file.txt`
  - Git Relative Path: `src/main.py` (automatically detected when inside a Git repository)
  - Shell Quoted: `'/path/with spaces/file.txt'`
  - Name Only: `file.txt`
  - File URI: `file:///home/user/project/file.txt`
  - Markdown Link: `[file.txt](file:///home/user/project/file.txt)`
- Multi-file selection support (newline-separated, shell-quoted, JSON array).
- Folder background support to copy current folder path from empty space.
- Wayland and X11 clipboard compatibility using the GTK4 GDK clipboard, with `wl-copy` and `xclip` only as a non-blocking fallback.
- Transient desktop notification on copy.
- Optional JSON configuration file.

## Requirements

- GNOME Files (Nautilus) 43 or later
- python-nautilus (nautilus-python)
- Python 3.8+
- wl-clipboard (Wayland) or xclip (X11), optional: only used if the GTK clipboard is unavailable
- libnotify / notify-send (optional, for notifications)

### Package Installation

Arch Linux / Manjaro:
```bash
sudo pacman -S python-nautilus wl-clipboard libnotify
```

Fedora:
```bash
sudo dnf install nautilus-python wl-clipboard libnotify
```

Ubuntu / Debian:
```bash
sudo apt install python3-nautilus wl-clipboard libnotify-bin
```

## Installation

Clone the repository and run the install script:

```bash
git clone https://github.com/dagimg-dot/nautilus-copy-path.git
cd nautilus-copy-path
./scripts/install.sh
```

Or using Make:

```bash
make install
```

The installer copies the extension to `~/.local/share/nautilus-python/extensions/copy-path.py` and restarts Nautilus.

## Configuration

The extension works with default settings out of the box. To customize behavior, create a configuration file at `~/.config/nautilus-copy-path/config.json`:

```json
{
  "notifications": true,
  "show_submenu": true,
  "default_format": "absolute"
}
```

### Available Options

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `notifications` | boolean | `true` | Show transient notification when a path is copied |
| `show_submenu` | boolean | `true` | Display the "Copy as..." submenu |
| `default_format` | string | `"absolute"` | Format used by the top-level item (`absolute`, `tilde`, `git`, `shell`, `basename`, `uri`, `markdown`) |

## Development

Run tests:

```bash
make test
```

Check linting and formatting with Ruff:

```bash
make check
```

Automatically format code:

```bash
make format
```

Run linter with auto-fixes:

```bash
make lint
```

## Uninstallation

To remove the extension:

```bash
./scripts/uninstall.sh
```

Or using Make:

```bash
make uninstall
```

## License

MIT License. See [LICENSE](LICENSE) for details.
