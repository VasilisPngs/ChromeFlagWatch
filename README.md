# ChromeFlagWatch

**ChromeFlagWatch watches Google Chrome for new experimental flags and shows you what has changed.**

You do not need to know how the project works. If you just want to see which new Chrome flags have appeared, this repository gives you an easy way to find them.

## What is a Chrome Flag?

Chrome Flags are experimental features that you can turn on or off in Chrome.

You can find them by opening:

`chrome://flags`

They can be useful if you want to try new Chrome features before they become available normally.

## What does ChromeFlagWatch do?

When a new Chrome version is released, ChromeFlagWatch checks the available flags and looks for flags that were not present in the previous Stable version.

It then creates a simple report showing:

- The new flag's name
- What the flag does
- Which platform it is available on
- A direct `chrome://flags/#...` link to the flag

The project runs automatically, so the reports are updated as new Chrome Stable versions appear.

## Supported platforms

ChromeFlagWatch currently tracks Chrome on:

- **Windows**
- **Android**
- **iOS (iPhone and iPad)**

macOS and Linux are not currently tracked.

## Where can I see the new flags?

Go to the folder for your device:

- **Windows:** [`reports/windows/`](reports/windows/)
- **Android:** [`reports/android/`](reports/android/)
- **iPhone/iPad:** [`reports/ios/`](reports/ios/)

Inside each folder, you will find reports for different Chrome versions, for example:

`M151.md`

The `M151` means **Chrome version 151**.

Open the report for the latest version to see which new flags were added.

## How do I use a flag?

1. Open Chrome.
2. Open `chrome://flags`.
3. Search for the flag you found in ChromeFlagWatch.
4. Select the option you want.
5. Restart Chrome if Chrome asks you to.

Each report also includes the direct address of the flag, for example:

`chrome://flags/#example-flag`

## Important

Chrome Flags are **experimental**. They are not normal Chrome settings.

A flag can:

- Change or stop working in a future Chrome version.
- Be removed completely.
- Become available by default and no longer need a flag.
- Cause unexpected behaviour in Chrome.

Use them only if you understand that they can change at any time.

## Where does the information come from?

ChromeFlagWatch gets Chrome's flag information directly from the **Chromium project**, the open-source project behind Google Chrome.

The project also checks Chrome Stable release information to compare the current version with the previous one.

## Automatic updates

ChromeFlagWatch runs automatically every day using GitHub Actions.

When new flags are found, the project creates or updates the corresponding report in this repository.

This also means that the repository keeps a history of Chrome flag changes over time.

## For developers

ChromeFlagWatch is a small Python project. The main script is [`flagwatch.py`](flagwatch.py), while the generated reports are stored under [`reports/`](reports/).

The project does not modify Chrome or enable any flags on your device. It only monitors the Chromium source and reports changes.
