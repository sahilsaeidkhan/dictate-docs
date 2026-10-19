"""Command-line interface for dictate-docs."""

import argparse
import subprocess
import sys
from pathlib import Path

from . import commit as commit_mod
from . import llm, pipeline
from . import __version__


def _read_notes(args) -> str:
    if args.notes:
        return args.notes
    if args.notes_file:
        return Path(args.notes_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("error: provide --notes, --notes-file, or pipe text via stdin",
          file=sys.stderr)
    sys.exit(2)


def _read_diff(args) -> str:
    if args.diff:
        return Path(args.diff).read_text(encoding="utf-8")
    staged = commit_mod.get_staged_diff()
    if staged is None:
        print("error: no --diff given and no staged changes found "
              "(`git diff --cached` empty or not a git repo)", file=sys.stderr)
        sys.exit(2)
    return staged


def cmd_commit(args) -> int:
    diff_text = _read_diff(args)
    notes = _read_notes(args)
    result = pipeline.run("commit", notes, diff=diff_text,
                          backend=args.backend)
    message = result["output"]
    if args.commit:
        proc = subprocess.run(["git", "commit", "-m", message],
                              capture_output=True, text=True)
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(proc.stderr, end="", file=sys.stderr)
            return proc.returncode
        return 0
    print(message)
    if args.verbose:
        print(f"\n[engine: {result['backend']}]", file=sys.stderr)
    return 0


def cmd_readme(args) -> int:
    notes = _read_notes(args)
    existing = (Path(args.readme).read_text(encoding="utf-8")
                if args.readme else None)
    result = pipeline.run("readme", notes, readme_text=existing,
                          project_name=args.name, backend=args.backend)
    out = result["output"]
    if args.in_place and args.readme:
        Path(args.readme).write_text(out, encoding="utf-8")
        print(f"updated {args.readme}")
    elif args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(out)
    if args.verbose:
        print(f"\n[engine: {result['backend']}]", file=sys.stderr)
    return 0


def cmd_polish(args) -> int:
    if args.text:
        text = args.text
    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("error: provide --text, --file, or pipe text via stdin",
              file=sys.stderr)
        return 2
    result = pipeline.run("polish", text, backend=args.backend)
    print(result["output"])
    if args.verbose:
        print(f"\n[engine: {result['backend']}]", file=sys.stderr)
    return 0


def cmd_serve(args) -> int:
    # web/ lives next to the package, not inside it.
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from web.server import run_server
    print(f"dictate-docs web UI on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    run_server(args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dictate-docs",
        description="Turn dictated developer notes into polished docs "
                    "(commits, READMEs, clean text).",
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    p.add_argument("--backend", default="auto",
                   choices=["auto", "local", "llm"],
                   help="processing backend (default: auto = LLM if "
                        "configured via DICTATE_DOCS_LLM, else local offline)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print which engine produced the output")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("commit",
                       help="build a conventional commit message")
    c.add_argument("--diff",
                   help="diff file to read (default: git diff --cached)")
    c.add_argument("-n", "--notes",
                   help="dictated notes as a string")
    c.add_argument("--notes-file",
                   help="file with dictated notes (or pipe via stdin)")
    c.add_argument("--commit", action="store_true",
                   help="actually run `git commit` with the message")
    c.set_defaults(func=cmd_commit)

    r = sub.add_parser("readme",
                       help="generate README sections from a walkthrough")
    r.add_argument("-n", "--notes", help="dictated walkthrough as a string")
    r.add_argument("--notes-file",
                   help="file with dictated walkthrough (or pipe via stdin)")
    r.add_argument("--readme",
                   help="existing README to update (merged, not overwritten)")
    r.add_argument("-o", "--out", help="write output to this file")
    r.add_argument("--in-place", action="store_true",
                   help="update --readme file in place")
    r.add_argument("--name", help="project name if not detectable")
    r.set_defaults(func=cmd_readme)

    pl = sub.add_parser("polish", help="clean up dictated text")
    pl.add_argument("-t", "--text", help="text as a string")
    pl.add_argument("--file", help="file to polish (or pipe via stdin)")
    pl.set_defaults(func=cmd_polish)

    s = sub.add_parser("serve", help="start the web UI")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--host", default="127.0.0.1")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
