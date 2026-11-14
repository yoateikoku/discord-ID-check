#!/usr/bin/env python3
"""ID Check - Asynchronous Discord Username Generator & Availability Scanner.

A standalone CLI utility for generating pattern-based Discord usernames
and verifying availability via unauthenticated endpoints with optional
proxy rotation and Discord Webhook notifications.

Author: yoa
License: MIT
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
import itertools
import os
import random
import re
import string
import sys
import time
from typing import Final, Iterator, Optional

import aiohttp

# Enable virtual terminal processing for ANSI sequences on Windows
if os.name == "nt":
    os.system("")

# ---------------------------------------------------------------------------
# Runtime Constants
# ---------------------------------------------------------------------------
API_ENDPOINT: Final[str] = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_CONCURRENCY: Final[int] = 3
MAX_PROXY_CONCURRENCY: Final[int] = 20
REQUEST_DELAY: Final[float] = 1.0
REQUEST_TIMEOUT: Final[int] = 10
MAX_RETRIES: Final[int] = 5

# ---------------------------------------------------------------------------
# ANSI Escape Codes & Visual Assets
# ---------------------------------------------------------------------------
G_BRIGHT: Final[str] = "\033[92m"
G_DARK: Final[str] = "\033[32m"
WHITE: Final[str] = "\033[97m"
CYAN: Final[str] = "\033[96m"
YELLOW: Final[str] = "\033[93m"
RED: Final[str] = "\033[91m"
DIM: Final[str] = "\033[90m"
BOLD: Final[str] = "\033[1m"
RESET: Final[str] = "\033[0m"

HIDE_CURSOR: Final[str] = "\033[?25l"
SHOW_CURSOR: Final[str] = "\033[?25h"
CLEAR_LINE: Final[str] = "\r\033[K"

BANNER_LINES: Final[list[str]] = [
    f"{G_BRIGHT}{BOLD}  ██╗██████╗      ██████╗██╗  ██╗███████╗ ██████╗██╗  ██╗{RESET}",
    f"{G_BRIGHT}{BOLD}  ██║██╔══██╗    ██╔════╝██║  ██║██╔════╝██╔════╝██║ ██╔╝{RESET}",
    f"{G_BRIGHT}{BOLD}  ██║██║  ██║    ██║     ███████║█████╗  ██║     █████╔╝ {RESET}",
    f"{G_BRIGHT}{BOLD}  ██║██║  ██║    ██║     ██╔══██║██╔══╝  ██║     ██╔═██╗ {RESET}",
    f"{G_BRIGHT}{BOLD}  ██║██████╔╝    ╚██████╗██║  ██║███████╗╚██████╗██║  ██╗{RESET}",
    f"{G_BRIGHT}{BOLD}  ╚═╝╚═════╝      ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝{RESET}",
    f"{G_DARK}  ───────────────────────────────────────────────────────{RESET}",
    f"{G_BRIGHT}  [*] Discord Username Generator & Availability Scanner{RESET}",
    f"{G_DARK}  ───────────────────────────────────────────────────────{RESET}",
]

# Quadrant block characters for high-frequency terminal spinner
SPINNER_FRAMES: Final[list[str]] = [
    "▛▘", "▀▝", "▜▗", "▐▖", "▟▚", "▄▞", "▙▘", "▌▝",
    "▖▜", "▘▟", "▝▙", "▗▛", "▚▀", "▞▄", "▘▐", "▝▌",
]
SUB_BLOCKS: Final[list[str]] = ["▖", "▘", "▝", "▗", "▚", "▞", "▛", "▜", "▟", "▙"]

# ---------------------------------------------------------------------------
# Pattern Definitions & Validation Rules
# ---------------------------------------------------------------------------
LETTERS: Final[str] = string.ascii_lowercase
DIGITS: Final[str] = string.digits
SYMBOLS: Final[str] = "_."
CHAR_POOL: Final[str] = LETTERS + DIGITS + SYMBOLS

MODES: Final[dict[str, tuple[str, str]]] = {
    "1": ("semi4l", "3 Letters + 1 Digit (4 chars)"),
    "2": ("semi4c", "3 Alphanumeric + 1 Symbol (_/.) (4 chars)"),
    "3": ("4l",     "4 Letters only"),
    "4": ("4c",     "4 Mixed chars (Letters / Digits / _ / .)"),
    "5": ("4n",     "4 Digits only"),
    "6": ("5l",     "5 Letters only"),
    "7": ("5c",     "5 Mixed chars (Letters / Digits / _ / .)"),
    "8": ("5n",     "5 Digits only"),
    "9": ("custom", "Custom target list (Multi-line terminal input)"),
}

USERNAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_.]{2,32}$")


@dataclass
class ScanState:
    """Tracks real-time metrics across asynchronous worker coroutines."""

    total: int
    completed: int = 0
    available: int = 0
    taken: int = 0
    errors: int = 0
    current_target: str = "init"
    start_time: float = field(default_factory=time.time)
    active: bool = True


# ---------------------------------------------------------------------------
# Terminal UI & Animation Routines
# ---------------------------------------------------------------------------
async def render_boot_sequence() -> None:
    """Displays an initialization sequence and renders the main ASCII banner."""
    os.system("cls" if os.name == "nt" else "clear")
    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    stages = [
        "INITIALIZING ASYNC RUNTIME...",
        "LOADING PATTERN GENERATOR...",
        "CONFIGURING RATE-LIMIT HANDLER...",
        "READY.",
    ]

    for idx, label in enumerate(stages):
        for sq in ("▖", "▘", "▝", "▗"):
            filled = (idx + 1) * 5
            bar = ("█" * filled) + ("░" * (20 - filled))
            sys.stdout.write(
                f"{CLEAR_LINE}{G_BRIGHT}[{sq}] {WHITE}{label:<34} "
                f"{G_DARK}[{G_BRIGHT}{bar}{G_DARK}]{RESET}"
            )
            sys.stdout.flush()
            await asyncio.sleep(0.025)

    sys.stdout.write(CLEAR_LINE)
    sys.stdout.flush()

    for i, line in enumerate(BANNER_LINES):
        if i < 6:
            sys.stdout.write(f"{G_DARK}  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RESET}\r")
            sys.stdout.flush()
            await asyncio.sleep(0.02)
        print(f"{CLEAR_LINE}{line}")
        await asyncio.sleep(0.015)

    print()
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()


async def render_completion_bar() -> None:
    """Renders a 100% progress sweep animation upon scan completion."""
    for step in range(1, 21):
        bar = ("█" * step) + ("░" * (20 - step))
        sq = SPINNER_FRAMES[step % len(SPINNER_FRAMES)]
        sys.stdout.write(f"{CLEAR_LINE}{G_BRIGHT}{BOLD}[{sq}] SCAN COMPLETE [{bar}] 100%{RESET}")
        sys.stdout.flush()
        await asyncio.sleep(0.012)
    sys.stdout.write(CLEAR_LINE)
    sys.stdout.flush()


def write_log(message: str) -> None:
    """Clears the active status line and prints a permanent log entry."""
    sys.stdout.write(f"{CLEAR_LINE}{message}\n")
    sys.stdout.flush()


async def status_bar_worker(state: ScanState) -> None:
    """Continuously updates the bottom progress bar using fine block glyphs."""
    tick = 0
    width = 20

    while state.active:
        spinner = SPINNER_FRAMES[tick % len(SPINNER_FRAMES)]
        sub_sq = SUB_BLOCKS[(tick // 2) % len(SUB_BLOCKS)]
        elapsed = time.time() - state.start_time

        ratio = (state.completed / state.total) if state.total > 0 else 0.0
        exact_fill = ratio * width
        full_blocks = int(exact_fill)
        fraction = exact_fill - full_blocks

        if full_blocks >= width:
            gauge = "█" * width
        else:
            shade = "▓" if fraction >= 0.66 else "▒" if fraction >= 0.33 else "░"
            gauge = ("█" * full_blocks) + shade + ("░" * (width - full_blocks - 1))

        percent = int(ratio * 100)
        line = (
            f"{CLEAR_LINE}"
            f"{G_BRIGHT}{BOLD}[{spinner}]{RESET} "
            f"{G_DARK}[{G_BRIGHT}{gauge}{G_DARK}]{RESET} "
            f"{WHITE}{percent:>3}%{RESET} "
            f"{DIM}({state.completed}/{state.total}){RESET} "
            f"{G_BRIGHT}HIT:{state.available}{RESET} "
            f"{RED}TAKEN:{state.taken}{RESET} "
            f"{CYAN}{sub_sq} @{state.current_target:<10}{RESET} "
            f"{DIM}{elapsed:>5.1f}s{RESET}"
        )
        sys.stdout.write(line)
        sys.stdout.flush()

        tick += 1
        await asyncio.sleep(0.06)

    sys.stdout.write(CLEAR_LINE)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Username Validation & Candidate Generation
# ---------------------------------------------------------------------------
def validate_username(username: str) -> tuple[bool, str]:
    """Checks whether a candidate string conforms to Discord's naming rules.

    Args:
        username: Target username string without leading '@'.

    Returns:
        A tuple of (is_valid, reason_message).
    """
    if not USERNAME_PATTERN.match(username):
        return False, "Invalid characters or length (must be 2-32 chars)"
    if ".." in username:
        return False, "Consecutive periods (..) are prohibited"
    return True, "OK"


def build_candidate(mode: str) -> str:
    """Generates a single valid username matching the specified pattern mode."""
    while True:
        if mode == "semi4l":
            chars = random.choices(LETTERS, k=3) + random.choices(DIGITS, k=1)
            random.shuffle(chars)
            candidate = "".join(chars)
        elif mode == "semi4c":
            chars = random.choices(LETTERS + DIGITS, k=3) + random.choices(SYMBOLS, k=1)
            random.shuffle(chars)
            candidate = "".join(chars)
        elif mode == "4l":
            candidate = "".join(random.choices(LETTERS, k=4))
        elif mode == "4c":
            candidate = "".join(random.choices(CHAR_POOL, k=4))
        elif mode == "4n":
            candidate = "".join(random.choices(DIGITS, k=4))
        elif mode == "5l":
            candidate = "".join(random.choices(LETTERS, k=5))
        elif mode == "5c":
            candidate = "".join(random.choices(CHAR_POOL, k=5))
        elif mode == "5n":
            candidate = "".join(random.choices(DIGITS, k=5))
        else:
            candidate = "".join(random.choices(LETTERS, k=4))

        valid, _ = validate_username(candidate)
        if valid:
            return candidate


def generate_batch(mode: str, count: int) -> list[str]:
    """Generates a deduplicated list of candidate usernames."""
    if mode == "4n" and count > 10000:
        count = 10000

    results: set[str] = set()
    attempts = 0
    limit = count * 25

    while len(results) < count and attempts < limit:
        results.add(build_candidate(mode))
        attempts += 1

    return list(results)


# ---------------------------------------------------------------------------
# Interactive Terminal Input Parsers
# ---------------------------------------------------------------------------
def read_custom_targets() -> list[str]:
    """Reads multi-line custom usernames from standard input."""
    print(f"\n{G_BRIGHT}{BOLD}[?] Enter target IDs (1 per line, or paste multiple lines):{RESET}")
    print(f"{DIM}    * Press Enter on an empty line to finish{RESET}")

    collected: list[str] = []
    while True:
        prompt = f"{G_BRIGHT}{BOLD}ID » {RESET}" if not collected else f"{G_DARK}   » {RESET}"
        raw = input(prompt).strip()
        if not raw:
            break

        for token in re.split(r"[,\s]+", raw):
            cleaned = token.strip().lstrip("@").lower()
            if cleaned:
                collected.append(cleaned)

    return list(dict.fromkeys(collected))


def format_proxy_url(raw: str) -> Optional[str]:
    """Normalizes a raw proxy string into an HTTP proxy URL."""
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    if "://" not in line:
        return f"http://{line}"
    return line


def read_proxies() -> list[str]:
    """Reads proxies from either direct multi-line paste or a file path."""
    print(f"\n{G_BRIGHT}{BOLD}[?] Proxy Configuration (Press Enter to skip):{RESET}")
    print(f"{DIM}    * Paste proxies directly (press Enter on an empty line to confirm){RESET}")
    print(f"{DIM}    * Or enter a path to a proxy list file (e.g., proxies.txt){RESET}")

    proxies: list[str] = []
    while True:
        prompt = f"{G_BRIGHT}{BOLD}Proxy » {RESET}" if not proxies else f"{G_DARK}      » {RESET}"
        entry = input(prompt).strip()
        if not entry:
            break

        unquoted = entry.strip('"').strip("'")
        if not proxies and os.path.isfile(unquoted):
            with open(unquoted, "r", encoding="utf-8") as handle:
                for line in handle:
                    parsed = format_proxy_url(line)
                    if parsed:
                        proxies.append(parsed)
            break

        for token in re.split(r"[,\s]+", entry):
            parsed = format_proxy_url(token)
            if parsed:
                proxies.append(parsed)

    return list(dict.fromkeys(proxies))


def prompt_configuration() -> Optional[tuple[str, list[str], str, list[str]]]:
    """Collects runtime parameters interactively via the terminal."""
    print(f"{G_BRIGHT}{BOLD}[?] Select Scan Mode:{RESET}\n")
    for key, (code, desc) in MODES.items():
        print(f"  {G_BRIGHT}[{key}]{RESET} {BOLD}{code:<7}{RESET} {DIM}│ {desc}{RESET}")
    print()

    choice = input(f"{G_BRIGHT}{BOLD}Mode (1-9 or name) » {RESET}").strip().lower()
    if not choice:
        return None

    selected_mode: Optional[str] = None
    if choice in MODES:
        selected_mode = MODES[choice][0]
    else:
        for _, (code, _) in MODES.items():
            if choice == code:
                selected_mode = code
                break

    if not selected_mode:
        print(f"{RED}[!] Invalid mode selection.{RESET}")
        return None

    if selected_mode == "custom":
        targets = read_custom_targets()
        if not targets:
            print(f"{RED}[!] No target IDs provided. Aborting.{RESET}")
            return None
    else:
        raw_qty = input(f"{G_BRIGHT}{BOLD}Batch size (Default: 20) » {RESET}").strip()
        if not raw_qty:
            qty = 20
        elif raw_qty.isdigit() and int(raw_qty) > 0:
            qty = int(raw_qty)
        else:
            print(f"{RED}[!] Batch size must be a positive integer.{RESET}")
            return None
        targets = generate_batch(selected_mode, qty)

    webhook = input(f"{G_BRIGHT}{BOLD}Discord Webhook URL (Press Enter to skip) » {RESET}").strip()
    if webhook and not webhook.startswith("http"):
        print(f"{YELLOW}[!] Invalid URL format. Webhook disabled.{RESET}")
        webhook = ""

    proxies = read_proxies()
    return selected_mode, targets, webhook, proxies


# ---------------------------------------------------------------------------
# Network Workers (Webhook Notification & Endpoint Check)
# ---------------------------------------------------------------------------
async def dispatch_webhook(
    session: aiohttp.ClientSession,
    webhook_url: str,
    username: str,
    mode: str,
) -> None:
    """Sends an English embed notification with 1-tap/1-click copy formatting.

    Placing the username inside both an inline code span in `content` and a
    fenced code block in the embed description allows single-tap copying on
    mobile clients and single-click copying on desktop clients.
    """
    if not webhook_url:
        return

    unix_ts = int(time.time())
    payload = {
        "username": "ID Check",
        "content": f"[+] **Available ID Found** │ Tap to copy: `{username}`",
        "embeds": [
            {
                "title": "[+] AVAILABLE DISCORD USERNAME",
                "description": (
                    f"**Click or tap the block below to copy the ID:**\n"
                    f"```\n{username}\n```\n"
                    f"**Mobile Quick Copy:** `{username}`"
                ),
                "color": 0x00FF66,
                "fields": [
                    {
                        "name": "◆ Username",
                        "value": f"`@{username}`",
                        "inline": True,
                    },
                    {
                        "name": "◆ Pattern",
                        "value": f"`{mode.upper()}`",
                        "inline": True,
                    },
                    {
                        "name": "◆ Length",
                        "value": f"`{len(username)} chars`",
                        "inline": True,
                    },
                    {
                        "name": "◆ Timestamp",
                        "value": f"<t:{unix_ts}:R> (<t:{unix_ts}:T>)",
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "ID Check // Discord Username Availability Scanner",
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
    }

    try:
        async with session.post(webhook_url, json=payload) as resp:
            if resp.status not in (200, 204):
                write_log(f"{YELLOW}[!] Webhook delivery failed (HTTP {resp.status}){RESET}")
    except Exception as exc:
        write_log(f"{RED}[!] Webhook exception: {type(exc).__name__}{RESET}")


async def verify_username(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    username: str,
    mode: str,
    webhook_url: str,
    proxy_pool: Optional[Iterator[str]],
    use_proxies: bool,
    state: ScanState,
) -> dict[str, str]:
    """Queries the Discord API to verify if a username is available."""
    valid, reason = validate_username(username)
    if not valid:
        state.completed += 1
        state.errors += 1
        write_log(f"{DIM}[SKIP] @{username:<15} │ {reason}{RESET}")
        return {"username": username, "status": "INVALID"}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    attempts = 0
    async with semaphore:
        state.current_target = username
        while attempts < MAX_RETRIES:
            proxy = next(proxy_pool) if proxy_pool else None
            try:
                async with session.post(
                    API_ENDPOINT,
                    json={"username": username},
                    headers=headers,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        is_taken = body.get("taken", True)
                        await asyncio.sleep(REQUEST_DELAY)
                        state.completed += 1

                        if not is_taken:
                            state.available += 1
                            await dispatch_webhook(session, webhook_url, username, mode)
                            write_log(
                                f"{G_BRIGHT}{BOLD}[+] AVAILABLE{RESET} {G_DARK}│{RESET} "
                                f"{WHITE}{BOLD}@{username:<15}{RESET} {G_BRIGHT}◆ Available{RESET}"
                            )
                            return {"username": username, "status": "AVAILABLE"}

                        state.taken += 1
                        write_log(
                            f"{RED}[-] TAKEN    {RESET} {G_DARK}│{RESET} "
                            f"{DIM}@{username:<15} ◇ Taken{RESET}"
                        )
                        return {"username": username, "status": "TAKEN"}

                    if resp.status == 429:
                        body = await resp.json()
                        retry_after = float(body.get("retry_after", 3.0))
                        if use_proxies:
                            attempts += 1
                            write_log(
                                f"{YELLOW}[!] RATE LIMIT (@{username}) │ "
                                f"Rotating proxy ({attempts}/{MAX_RETRIES}){RESET}"
                            )
                            await asyncio.sleep(0.25)
                            continue

                        write_log(
                            f"{YELLOW}[!] RATE LIMIT (@{username}) │ "
                            f"Sleeping {retry_after:.2f}s...{RESET}"
                        )
                        await asyncio.sleep(retry_after + 0.5)
                        continue

                    attempts += 1
                    write_log(
                        f"{RED}[!] HTTP {resp.status} (@{username}) │ "
                        f"Retry ({attempts}/{MAX_RETRIES}){RESET}"
                    )
                    await asyncio.sleep(1.0)

            except (
                aiohttp.ClientProxyConnectionError,
                aiohttp.ClientHttpProxyError,
                asyncio.TimeoutError,
            ):
                attempts += 1
                write_log(
                    f"{YELLOW}[!] PROXY ERR (@{username}) │ "
                    f"Rotating proxy ({attempts}/{MAX_RETRIES}){RESET}"
                )
                await asyncio.sleep(0.2)
            except Exception as exc:
                attempts += 1
                write_log(
                    f"{RED}[!] NET ERR (@{username}) │ "
                    f"{type(exc).__name__} ({attempts}/{MAX_RETRIES}){RESET}"
                )
                await asyncio.sleep(0.5)

        state.completed += 1
        state.errors += 1
        write_log(f"{RED}[x] FAILED   {RESET} {G_DARK}│{RESET} @{username:<15} │ Max retries exceeded")
        return {"username": username, "status": "ERROR"}


def export_hits(mode: str, hits: list[str]) -> str:
    """Creates the output directory and writes available usernames to disk."""
    out_dir = "results"
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"available_{mode}_{stamp}.txt")
    with open(path, "w", encoding="utf-8") as handle:
        for item in hits:
            handle.write(f"{item}\n")
    return path


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
async def main() -> None:
    """Main execution flow."""
    await render_boot_sequence()

    config = prompt_configuration()
    if not config:
        return

    mode, targets, webhook_url, proxies = config
    use_proxies = len(proxies) > 0

    if use_proxies:
        random.shuffle(proxies)
        proxy_pool: Optional[Iterator[str]] = itertools.cycle(proxies)
        workers = min(len(proxies), MAX_PROXY_CONCURRENCY)
        proxy_label = f"{G_BRIGHT}{len(proxies)} loaded (Workers: {workers}){RESET}"
    else:
        proxy_pool = None
        workers = DEFAULT_CONCURRENCY
        proxy_label = f"{DIM}None (Direct / Workers: {workers}){RESET}"

    webhook_label = f"{G_BRIGHT}Active{RESET}" if webhook_url else f"{DIM}Disabled{RESET}"

    print(f"\n{G_DARK}───────────────────────────────────────────────────────{RESET}")
    print(f"{G_BRIGHT}[*] Mode    :{RESET} {BOLD}{mode}{RESET} ({len(targets)} targets)")
    print(f"{G_BRIGHT}[*] Proxies :{RESET} {proxy_label}")
    print(f"{G_BRIGHT}[*] Webhook :{RESET} {webhook_label}")
    print(f"{G_DARK}───────────────────────────────────────────────────────{RESET}\n")

    state = ScanState(total=len(targets))
    semaphore = asyncio.Semaphore(workers)

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    try:
        ui_task = asyncio.create_task(status_bar_worker(state))
        async with aiohttp.ClientSession() as session:
            tasks = [
                verify_username(
                    session,
                    semaphore,
                    candidate,
                    mode,
                    webhook_url,
                    proxy_pool,
                    use_proxies,
                    state,
                )
                for candidate in targets
            ]
            results = await asyncio.gather(*tasks)

        state.active = False
        await ui_task
        await render_completion_bar()
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    elapsed = time.time() - state.start_time
    hits = [r["username"] for r in results if r["status"] == "AVAILABLE"]

    print(f"{G_DARK}═══════════════════════════════════════════════════════{RESET}")
    print(f"{G_BRIGHT}{BOLD}[+] SCAN FINISHED ({elapsed:.2f}s){RESET}")
    print(
        f"    Mode: {mode} │ Available: {G_BRIGHT}{BOLD}{len(hits)}{RESET} / Total: {len(targets)}"
    )

    if hits:
        print(f"    {G_BRIGHT}{BOLD}◆ HITS: {', '.join('@' + u for u in hits)}{RESET}")
        saved_file = export_hits(mode, hits)
        print(f"    {CYAN}[*] Exported to » {saved_file}{RESET}")
    else:
        print(f"    {DIM}[*] 0 available usernames found. No file exported.{RESET}")

    print(f"{G_DARK}═══════════════════════════════════════════════════════{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.stdout.write(f"{SHOW_CURSOR}\n{YELLOW}[!] Process terminated by user.{RESET}\n")
        sys.exit(0)
