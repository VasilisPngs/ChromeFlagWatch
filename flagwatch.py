import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DASH = "https://chromiumdash.appspot.com/fetch_releases"
RAW = "https://raw.githubusercontent.com/chromium/chromium"
ROOT = Path(__file__).parent
STATE = ROOT / "state"
REPORTS = ROOT / "reports"

SOURCES = {
    "desktop": {
        "entries": ["chrome/browser/about_flags.cc"],
        "strings": [
            "chrome/browser/flag_descriptions.h",
            "chrome/browser/flag_descriptions.cc",
        ],
    },
    "ios": {
        "entries": ["ios/chrome/browser/flags/about_flags.mm"],
        "strings": [
            "ios/chrome/browser/flags/ios_chrome_flag_descriptions.h",
            "ios/chrome/browser/flags/ios_chrome_flag_descriptions.mm",
        ],
    },
}

PLATFORMS = {
    "windows": {
        "label": "Windows",
        "dash": "Windows",
        "source": "desktop",
        "tokens": {"kOsWin", "kOsAll", "kOsDesktop", "kOsAura"},
    },
    "android": {
        "label": "Android",
        "dash": "Android",
        "source": "desktop",
        "tokens": {"kOsAndroid", "kOsAll"},
    },
    "ios": {
        "label": "iOS",
        "dash": "iOS",
        "source": "ios",
        "tokens": {"kOsIos"},
    },
}

ENTRY_RE = re.compile(
    r'\{\s*"(?P<name>[A-Za-z0-9][A-Za-z0-9\-\._]*)"\s*,\s*'
    r"flag_descriptions::(?P<title>k[A-Za-z0-9_]+)\s*,\s*"
    r"flag_descriptions::(?P<desc>k[A-Za-z0-9_]+)\s*,\s*"
    r"(?P<os>[A-Za-z0-9_ \|\n:]+?)\s*,",
    re.S,
)
STRING_RE = re.compile(
    r"(?:inline\s+)?(?:constexpr\s+)?(?:const\s+)?char\s+(k[A-Za-z0-9_]+)\s*\[\]\s*=\s*"
    r'((?:\s*"(?:[^"\\]|\\.)*")+)\s*;',
    re.S,
)
LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def fetch(url, allow_missing=False):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "flagwatch"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code == 404 and allow_missing:
                return None
            if error.code in (403, 429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    return None


def releases(platform, count):
    return json.loads(fetch(f"{DASH}?channel=Stable&platform={platform}&num={count}"))


def gather(version, paths):
    chunks = []
    for path in paths:
        body = fetch(f"{RAW}/{version}/{path}", allow_missing=True)
        if body:
            chunks.append(body)
    return "\n".join(chunks)


def parse_entries(text):
    result = {}
    for match in ENTRY_RE.finditer(text):
        tokens = {
            token.strip().replace("flags_ui::", "")
            for token in match.group("os").split("|")
        }
        result[match.group("name")] = {
            "title_key": match.group("title"),
            "desc_key": match.group("desc"),
            "os": sorted(tokens),
        }
    return result


def parse_strings(text):
    result = {}
    for match in STRING_RE.finditer(text):
        joined = "".join(LITERAL_RE.findall(match.group(2)))
        try:
            joined = joined.encode("latin-1", "ignore").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
        result[match.group(1)] = joined.strip()
    return result


def snapshot(version, source, cache):
    key = (version, source)
    if key in cache:
        return cache[key]
    spec = SOURCES[source]
    data = {
        "entries": parse_entries(gather(version, spec["entries"])),
        "strings": parse_strings(gather(version, spec["strings"])),
    }
    cache[key] = data
    return data


def select(data, tokens):
    return {
        name: entry
        for name, entry in data["entries"].items()
        if tokens & set(entry["os"])
    }


def describe(name, entry, data):
    title = data["strings"].get(entry["title_key"], name)
    body = data["strings"].get(entry["desc_key"], "")
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


def render(platform, version, milestone, baseline, baseline_milestone, new, selected, added):
    lines = [
        f"# Chrome {platform['label']} Stable M{milestone} — {version}",
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
            lines.append(describe(name, selected[name], new))
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
    REPORTS.mkdir(exist_ok=True)
    cache = {}
    summary = []

    for key, platform in PLATFORMS.items():
        history = releases(platform["dash"], 100)
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
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
        if previous.get("version") == version and previous.get("baseline") == baseline:
            continue

        new = snapshot(version, platform["source"], cache)
        old = snapshot(baseline, platform["source"], cache)
        selected = select(new, platform["tokens"])
        old_names = set(select(old, platform["tokens"]))
        added = sorted(set(selected) - old_names)

        report_path = f"reports/{key}/M{milestone}.md"
        destination = ROOT / report_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render(
                platform, version, milestone, baseline, baseline_milestone,
                new, selected, added,
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
                "platform": platform["label"],
                "key": key,
                "version": version,
                "milestone": milestone,
                "added": added,
                "fresh": fresh,
                "notify": bool(fresh),
                "report": report_path,
            }
        )

    (ROOT / "last_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    notify = [item for item in summary if item["notify"]]
    body, title = notification(notify, base_url)
    (ROOT / "last_run.md").write_text(body, encoding="utf-8")
    (ROOT / "last_run.title").write_text(title or "no flag changes", encoding="utf-8")
    print(title or "no flag changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
