# ID Check

An asynchronous CLI utility for generating pattern-based Discord usernames and checking their availability in real time. Built with Python and `aiohttp`, featuring automatic rate-limit handling, proxy rotation, terminal progress animations, and instant-copy Discord Webhook notifications.

---

## Features

* **Pattern-Based Generation:** Supports `semi4l`, `semi4c`, `4l`, `4c`, `4n`, `5l`, `5c`, `5n`, and `custom` multi-line input modes.
* **Zero Pre-Configuration:** Everything is configured interactively via the terminal at runtime (no config files or source edits required).
* **Asynchronous Engine:** Powered by `asyncio` and `aiohttp` with configurable concurrency and automatic `429 Retry-After` backoff.
* **Proxy Rotation:** Paste proxies directly into the terminal or load from a `.txt` file (`ip:port` or `user:pass@ip:port`). Automatically rotates on rate limits or timeouts.
* **1-Tap Copy Webhook Alerts:** Sends clean English Discord Embeds formatted with inline and fenced code blocks for instant 1-tap copying on mobile and 1-click copying on desktop.
* **On-Demand File Export:** Automatically creates a timestamped file under `results/` only when available usernames are discovered.

---

## Available Modes

| Option | Mode | Pattern Description | Example |
| :--- | :--- | :--- | :--- |
| `[1]` | `semi4l` | 3 Letters + 1 Digit (4 chars total) | `k9ab` |
| `[2]` | `semi4c` | 3 Alphanumeric + 1 Symbol (`_` or `.`) | `a7_x` |
| `[3]` | `4l` | 4 Letters only | `wxyz` |
| `[4]` | `4c` | 4 Mixed chars (Letters, Digits, `_`, `.`) | `v.4k` |
| `[5]` | `4n` | 4 Digits only | `0492` |
| `[6]` | `5l` | 5 Letters only | `qwert` |
| `[7]` | `5c` | 5 Mixed chars (Letters, Digits, `_`, `.`) | `z_9a.b` |
| `[8]` | `5n` | 5 Digits only | `83920` |
| `[9]` | `custom` | Custom multi-line list pasted directly into terminal | `yoa`, `admin` |

---

## Installation

### Requirements
* Python 3.10+
* `aiohttp`

### Setup

```bash
git clone [https://github.com/YOUR_USERNAME/id-check.git](https://github.com/YOUR_USERNAME/id-check.git)
cd id-check
pip install aiohttp
```

---

## Usage

Run the script directly from your terminal:

```bash
python id_check.py
```

Follow the interactive prompts:
1. **Mode Selection:** Enter `1`–`9` or the mode name (e.g., `semi4l`, `custom`).
2. **Batch Size / Custom List:** Specify the number of IDs to generate, or paste your custom list line-by-line.
3. **Discord Webhook URL:** Paste a Webhook URL to receive real-time embed alerts, or press `Enter` to skip.
4. **Proxies:** Paste your proxy list directly into the terminal (press `Enter` on an empty line to finish), provide a file path, or press `Enter` to run without proxies.

---

## Disclaimer

This tool is intended for educational purposes and personal username availability research. Please respect Discord's Terms of Service and API rate limits when using this software.

## License

Released under the [MIT License](LICENSE).
