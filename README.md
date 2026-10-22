# sereen

Discover and control Epson projectors from Linux.

`sereen` finds projectors on the local network and drives them over the
protocols they actually speak. It is a pure-Python, dependency-free
implementation — no proprietary Epson software, no Windows.

```
$ sereen scan
NAME          HOST           PORT  PROTOCOL  VENDOR
Meeting Room  192.168.1.42   4352  pjlink    Epson

$ sereen power on
$ sereen input hdmi1
$ sereen status
power                   True
input_source            HDMI 1
volume                  45
```

## Status

Alpha. Discovery and PJLink/ESC-VP.net control are implemented; the GUI is
not.

## Features

- **Discovery** by four independent methods, merged into one list:
  - TCP connect sweep of the local subnets (works with anything that has an
    open control port)
  - Epson SDP broadcast probe
  - SSDP (UPnP)
  - mDNS / DNS-SD
- **Control** via **PJLink** (the cross-vendor standard, port 4352) and
  **ESC/VP.net** (Epson's own protocol, port 3620): power, input source,
  volume, mute.
- **Saved projectors** and per-host passwords, stored in
  `~/.config/sereen/` with `0600` permissions.

## Install

```sh
pipx install .          # or: pip install .
```

Requires Python 3.10+.

## Usage

```sh
sereen scan                    # find projectors
sereen scan --json             # machine readable
sereen info 192.168.1.42       # device information
sereen status                  # power / input / volume
sereen power on|off
sereen input hdmi1|hdmi2|video|computer
sereen volume 30
sereen mute on|off
sereen saved                   # remembered projectors
sereen forget 192.168.1.42
```

If a projector asks for a password, pass `--password`, or store it once:

```sh
sereen --password hunter2 info 192.168.1.42
```

## Compatibility

What your projector supports depends on the model. This is the honest
picture:

| Capability | Requirement |
|---|---|
| Discovery | Any of the four methods; most projectors answer at least one |
| Control | PJLink (port 4352) or ESC/VP.net (port 3620) |
| Screen mirroring | **Not implemented.** Most Epson business projectors do not accept standard Miracast or Chromecast — they need Epson's proprietary iProjection/HDCP service, which is a separate (much larger) piece of work. |

PJLink support is common on Epson business models (the EB-L and EB-P
ranges) but is absent on many home models. ESC/VP.net is the older,
Epson-only fallback and is more widely available.

## Development

```sh
pip install -e ".[dev]"
pytest
```

The project is a package under `src/sereen/`:

| Module | Purpose |
|---|---|
| `models.py` | `Projector`, `ProjectorState`, protocol enums |
| `netutil.py` | Local subnet enumeration |
| `discovery/` | The four discovery strategies |
| `protocol/` | Byte-level PJLink and ESC/VP.net codecs |
| `control/` | Protocol-independent session API |
| `cli.py` | The `sereen` command |

## Licence

GPL-3.0-or-later.
