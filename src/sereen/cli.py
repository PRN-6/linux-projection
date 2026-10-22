"""Command line interface for sereen."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .config import Config, get_secret
from .discovery import ScanOptions, discover_all, scan_network
from .models import Projector

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_FOUND = 2


# --------------------------------------------------------------------- output
def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


# ------------------------------------------------------------------ commands
def cmd_scan(args: argparse.Namespace) -> int:
    opts = ScanOptions(timeout=args.timeout, workers=args.workers)
    if args.no_broadcast:
        projectors = scan_network(opts)
    else:
        projectors = discover_all(opts)

    if args.json:
        _print_json([p.to_dict() for p in projectors])
        return EXIT_OK

    rows = [
        [p.display_name, p.host, str(p.port), str(p.protocol), p.manufacturer or "-"]
        for p in projectors
    ]
    _table(rows, ["NAME", "HOST", "PORT", "PROTOCOL", "VENDOR"])
    if not rows:
        print("No projectors found.", file=sys.stderr)
        return EXIT_NOT_FOUND
    return EXIT_OK


def cmd_saved(args: argparse.Namespace) -> int:
    config = Config.load()
    if args.json:
        _print_json([s.__dict__ for s in config.saved])
        return EXIT_OK
    rows = [
        [s.name or s.host, s.host, str(s.port), str(s.protocol)]
        for s in config.saved
    ]
    _table(rows, ["NAME", "HOST", "PORT", "PROTOCOL"])
    return EXIT_OK


def cmd_forget(args: argparse.Namespace) -> int:
    config = Config.load()
    if not config.forget(args.host):
        print(f"{args.host} is not in the saved list.", file=sys.stderr)
        return EXIT_ERROR
    print(f"Removed {args.host}.")
    return EXIT_OK


def _resolve_target(args: argparse.Namespace) -> str:
    if getattr(args, "host", None):
        return args.host
    config = Config.load()
    if len(config.saved) == 1:
        return config.saved[0].host
    if not config.saved:
        print("No host given and no saved projectors.", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)
    print(
        "Several projectors are saved, please give one explicitly: "
        + ", ".join(s.host for s in config.saved),
        file=sys.stderr,
    )
    raise SystemExit(EXIT_ERROR)


def cmd_info(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        info = session.info()
    if args.json:
        _print_json(info)
    else:
        for key, value in info.items():
            print(f"{key:<24} {value}")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        state = session.state()
    if args.json:
        _print_json(state.to_dict())
    else:
        for key, value in state.to_dict().items():
            print(f"{key:<24} {value}")
    return EXIT_OK


def cmd_power(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        if args.state == "on":
            session.power_on()
        elif args.state == "off":
            session.power_off()
        else:
            print(session.state().power)
            return EXIT_OK
    print(f"Power {args.state} sent to {host}.")
    return EXIT_OK


def cmd_input(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        if args.source is None:
            print(session.state().input_source or "unknown")
            return EXIT_OK
        session.set_input(args.source)
    print(f"Input set to {args.source}.")
    return EXIT_OK


def cmd_volume(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        if args.level is None:
            print(session.state().volume)
            return EXIT_OK
        session.set_volume(args.level)
    print(f"Volume set to {args.level}.")
    return EXIT_OK


def cmd_mute(args: argparse.Namespace) -> int:
    from .control import open_session

    host = _resolve_target(args)
    with open_session(host, password=args.password) as session:
        session.set_mute(args.state)
    print(f"Mute {args.state} sent to {host}.")
    return EXIT_OK


# -------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sereen",
        description="Discover and control Epson projectors.",
    )
    parser.add_argument("--version", action="version", version=f"sereen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="look for projectors on the network")
    p.add_argument("--timeout", type=float, default=2.0, help="seconds per probe")
    p.add_argument("--workers", type=int, default=128, help="parallel probes")
    p.add_argument(
        "--no-broadcast",
        action="store_true",
        help="only do the TCP sweep, skip SDP/SSDP/mDNS",
    )
    p.add_argument("--json", action="store_true", help="machine readable output")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("saved", help="list remembered projectors")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_saved)

    p = sub.add_parser("forget", help="remove a projector from the saved list")
    p.add_argument("host")
    p.set_defaults(func=cmd_forget)

    def add_target_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("host", nargs="?", help="projector address (default: the only saved one)")
        sp.add_argument("--password", help="network / PJLink password")
        sp.add_argument("--json", action="store_true")

    p = sub.add_parser("info", help="read device information")
    add_target_args(p)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("status", help="read the current projector state")
    add_target_args(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("power", help="turn the projector on or off")
    add_target_args(p)
    p.add_argument("state", choices=("on", "off", "status"))
    p.set_defaults(func=cmd_power)

    p = sub.add_parser("input", help="switch the input source")
    add_target_args(p)
    p.add_argument("source", nargs="?", help="input name, e.g. hdmi1")
    p.set_defaults(func=cmd_input)

    p = sub.add_parser("volume", help="read or set the volume")
    add_target_args(p)
    p.add_argument("level", nargs="?", type=int, help="0-100")
    p.set_defaults(func=cmd_volume)

    p = sub.add_parser("mute", help="mute or unmute")
    add_target_args(p)
    p.add_argument("state", choices=("on", "off"))
    p.set_defaults(func=cmd_mute)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "password", None):
        args.password = get_secret(args.host) if getattr(args, "host", None) else None
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # pragma: no cover - top level guard
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
