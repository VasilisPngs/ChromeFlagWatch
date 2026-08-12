# ChromeFlagWatch

ChromeFlagWatch monitors the Chromium source for newly introduced Chrome flags and reports changes between Chrome Stable milestones.

## What it does

For each supported platform, ChromeFlagWatch:

- Checks the latest Chrome Stable release.
- Compares its available `chrome://flags` entries with the previous Stable milestone.
- Detects flags that are newly present in the current milestone.
- Generates a per-platform Markdown report containing the new flag name, title, description, and direct `chrome://flags/#...` URL.
- Keeps platform state so future runs can identify only changes that were not reported before.
- Publishes the generated reports automatically through GitHub Actions.

Chrome flags are experimental features. Google notes that they can change, break, or be removed without notice, so ChromeFlagWatch is intended for monitoring and discovery rather than treating flags as permanent Chrome settings.

## Supported platforms

ChromeFlagWatch currently monitors:

- **Windows**
- **Android**
- **iOS**

The platform detection is based on the Chromium source code and the operating-system tokens used by Chrome's flag definitions. macOS and Linux are not currently tracked by this project.

## Where to find new flags

The easiest place to see the latest changes is the `reports/` directory:

- [`reports/windows/`](reports/windows/) — Windows flags
- [`reports/android/`](reports/android/) — Android flags
- [`reports/ios/`](reports/ios/) — iOS flags

Each milestone report lists the flags newly detected for that platform. For example:

`reports/android/M151.md`

Each reported flag also includes its direct Chrome URL, such as:

`chrome://flags/#flag-name`

You can open `chrome://flags` in Chrome and search for the flag name. Google documents `chrome://flags` as the place where available experimental Chrome flags can be enabled or disabled.

## Official sources

ChromeFlagWatch reads the flag definitions directly from the [Chromium source code](https://chromium.googlesource.com/chromium/src/) and uses Chrome Stable release information to determine the current and previous milestones.

For general information about Chrome flags, see Google's official documentation:

- [Learn about Chrome flags](https://support.google.com/chrome/answer/16552482)
- [Chrome flags for developers](https://developer.chrome.com/docs/web-platform/chrome-flags)

## Automatic updates

GitHub Actions runs ChromeFlagWatch automatically every day and can also be triggered manually. When a new flag is detected, the corresponding report and state files are committed to the repository.

This means the repository can be used as a historical record of Chrome flag changes across Stable milestones.

## Repository structure

```text
.
├── flagwatch.py
├── reports/
│   ├── android/
│   ├── ios/
│   └── windows/
├── state/
├── last_run.md
├── last_run.title
└── .github/workflows/flagwatch.yml
```

## Important note

Chrome flags are experimental and are not guaranteed to remain available. A flag may be renamed, changed, moved to another platform, enabled by default, or removed entirely in a later Chrome release.
