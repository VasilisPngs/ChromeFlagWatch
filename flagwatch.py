import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

DASH = "https://chromiumdash.appspot.com/fetch_releases"
RAW = "https://raw.githubusercontent.com/chromium/chromium"
ROOT = Path(__file__).parent
STATE = ROOT / "state"

SOURCES = {
    "desktop": {
        "entries": "chrome/browser/about_flags.cc",
        "strings": "chrome/browser/flag_descriptions.h",
    },
    "ios": {
        "entries": "ios/chrome/browser/flags/about_flags.mm",
        "strings": "ios/chrome/browser/flags/ios_chrome_flag_descriptions.h",
    },
}

PLATFORMS = {
    "windows": {
        "name": "Windows",
        "source": "desktop",
        "tokens": {"kOsWin", "kOsAll", "kOsDesktop", "kOsAura"},
    },
    "android": {
        "name": "Android",
        "source": "desktop",
        "tokens": {"kOsAndroid", "kOsAll"},
    },
    "ios": {
        "name": "iOS",
        "source": "ios",
        "tokens": {"kOsIos"},
    },
}

ENTRY_RE = re.compile(
    r'\{\s*"(?P<name>[A-Za-z0-9][A-Za-z0-9\-\._]*)"\s*,\s*'
    r"flag_descriptions::(?P<title>k[A-Za-z0-9_]+)\s*,\s*"
    r"flag_descriptions::(?P<desc>k[A-Za-z0-9_]+)\s*,\s*"
    r"(?P<os>[A-Za-z0-9_ \|\n:]+?)\s*,"
)
STRING_RE = re.compile(
    r"(?:inline\s+)?(?:constexpr\s+)?(?:const\s+)?char\s+(k[A-Za-z0-9_]+)\s*\[\]\s*=\s*"
    r'((?:\s*"(?:[^"\\]|\\.)*")+)\s*;',
    re.S,
)
LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"', re.S)
ESCAPE_RE = re.compile(r"(?:\\x[0-9a-fA-F]{2})+|\\u([0-9a-fA-F]{4})|\\(.)", re.S)
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\n": ""}


def fetch(url):
    headers = {"User-Agent": "flagwatch", "Accept-Encoding": "gzip"}
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                encoding = response.headers.get("Content-Encoding", "")
                if encoding.lower() == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code in (403, 429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except OSError:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise


def expand(match):
    run, point, char = match.group(0), match.group(1), match.group(2)
    if char is not None:
        return ESCAPES.get(char, char)
    if point is not None:
        return chr(int(point, 16))
    return bytes.fromhex(run.replace("\\x", "")).decode("utf-8", "replace")


def parse_entries(text):
    result = {}
    for match in ENTRY_RE.finditer(text):
        result[match.group("name")] = {
            "title_key": match.group("title"),
            "desc_key": match.group("desc"),
            "os": {
                token.strip().replace("flags_ui::", "")
                for token in match.group("os").split("|")
            },
        }
    return result


def parse_strings(text):
    result = {}
    for match in STRING_RE.finditer(text):
        joined = "".join(LITERAL_RE.findall(match.group(2)))
        result[match.group(1)] = ESCAPE_RE.sub(expand, joined).strip()
    return result


PARSERS = {"entries": parse_entries, "strings": parse_strings}


def load(kind, version, source, cache):
    key = (kind, version, source)
    data = cache.get(key)
    if data is None:
        data = PARSERS[kind](fetch(f"{RAW}/{version}/{SOURCES[source][kind]}"))
        cache[key] = data
    return data


def releases(platform):
    return json.loads(fetch(f"{DASH}?channel=Stable&platform={platform}&num=60"))


def select(entries, tokens):
    return {name: entry for name, entry in entries.items() if tokens & entry["os"]}


def select_names(entries, tokens):
    return {name for name, entry in entries.items() if tokens & entry["os"]}


def describe(name, entry, strings):
    title = strings.get(entry["title_key"], name)
    body = strings.get(entry["desc_key"], "")
    return "\n".join(
        [
            f"### `#{name}`",
            f"**{title}**",
            "",
            body,
            "",
            f"`chrome://flags/#{name}`",
            "",
        ]
    )


def render(platform, version, milestone, baseline, baseline_milestone, strings, selected, added):
    lines = [
        f"# Chrome {platform['name']} Stable M{milestone} — {version}",
        "",
        f"Baseline M{baseline_milestone} — {baseline}",
        "",
        f"Added **{len(added)}** — Total **{len(selected)}**",
        "",
    ]
    if added:
        lines.append(f"## Added ({len(added)})")
        lines.append("")
        for name in added:
            lines.append(describe(name, selected[name], strings))
    return "\n".join(lines)


def notification(notify, base_url):
    lines = []
    for item in notify:
        link = f"{base_url}/{item['report']}" if base_url else item["report"]
        lines.append(f"## {item['platform']} M{item['milestone']} — {item['version']}")
        lines.append("")
        lines.append(f"Added {len(item['added'])} — [full report]({link})")
        lines.append("")
        lines.append(f"New since last run ({len(item['fresh'])}):")
        lines.append("")
        for name in item["fresh"]:
            lines.append(f"- `#{name}`")
        lines.append("")
    title = " / ".join(
        f"{item['platform']} M{item['milestone']} +{len(item['fresh'])}"
        for item in notify
    )
    return "\n".join(lines), title


def main():
    base_url = os.environ.get("REPORT_BASE_URL", "").rstrip("/")
    STATE.mkdir(exist_ok=True)
    cache = {}
    summary = []

    for key, platform in PLATFORMS.items():
        history = releases(platform["name"])
        if not history:
            continue
        version = history[0]["version"]
        milestone = history[0]["milestone"]

        newest = {}
        for item in history:
            newest.setdefault(item["milestone"], item["version"])
        baseline_milestone = milestone - 1
        while baseline_milestone not in newest and baseline_milestone > milestone - 8:
            baseline_milestone -= 1
        if baseline_milestone not in newest:
            continue
        baseline = newest[baseline_milestone]

        state_file = STATE / f"{key}.json"
        previous = (
            json.loads(state_file.read_text(encoding="utf-8"))
            if state_file.exists()
            else {}
        )
        if previous.get("version") == version and previous.get("baseline") == baseline:
            continue

        source = platform["source"]
        tokens = platform["tokens"]
        selected = select(load("entries", version, source, cache), tokens)
        old_names = select_names(load("entries", baseline, source, cache), tokens)
        added = sorted(set(selected) - old_names)

        report_path = f"reports/{key}/M{milestone}.md"
        destination = ROOT / report_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render(
                platform, version, milestone, baseline, baseline_milestone,
                load("strings", version, source, cache), selected, added,
            ),
            encoding="utf-8",
        )
        state_file.write_text(
            json.dumps(
                {
                    "version": version,
                    "milestone": milestone,
                    "baseline": baseline,
                    "added": added,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        fresh = sorted(set(added) - set(previous.get("added", [])))
        summary.append(
            {
                "platform": platform["name"],
                "version": version,
                "milestone": milestone,
                "added": added,
                "fresh": fresh,
                "report": report_path,
            }
        )

    notify = [item for item in summary if item["fresh"]]
    body, title = notification(notify, base_url)
    (ROOT / "last_run.md").write_text(body, encoding="utf-8")
    (ROOT / "last_run.title").write_text(title or "no flag changes", encoding="utf-8")
    print(title or "no flag changes")


if __name__ == "__main__":
    main()
