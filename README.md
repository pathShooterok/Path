# PATH

### OSINT & Identity Intelligence

> Because sometimes "who the fuck is this guy?" deserves a proper investigation.

PATH is a small command-line OSINT tool for digging through publicly available information about usernames, identifiers and public URLs.

It searches.  
It extracts.  
It follows links.  
It occasionally finds something useful.

And sometimes Bing returns 120 KB of HTML just to tell you absolutely nothing.

That's life.

## What does it actually do?

PATH currently supports:

- tracing usernames and identifiers
- searching public web results
- scanning public URLs
- extracting email addresses
- detecting email providers
- classifying email addresses
- extracting links
- recursively scanning interesting linked pages
- extracting page metadata
- detecting public identity information
- deduplicating findings
- retrying temporary network failures
- caching static data that doesn't need to be read from disk 700 times

No magic.  
No private databases.  
No FBI mainframe.

Just public information and an unhealthy amount of Python.

## Requirements

- Python 3.10+
- Internet connection
- approximately 30 seconds of patience when the network decides to become sentient

PATH currently uses only the Python standard library.

There is no:

```text
pip install 47 packages
```

followed by:

```text
ERROR: Microsoft Visual C++ Build Tools not found
```

## Installation

Clone the repository:

```bash
git clone https://github.com/pathShooterok/Path.git
cd Path
```

Then:

```bash
python path.py --help
```

That's it.

If it doesn't work, congratulations, you've discovered a bug.

## Usage

### Trace a username

```bash
python path.py trace username
```

For example:

```bash
python path.py trace github
```

PATH searches public web sources and tries to find anything related to the target.

Example:

```text
[*] Searching public web for: github
[*] Searching Bing...
[*] Bing HTML received: 121069 chars

Target: github
────────────────────────────────────────
Findings: 10
```

Yes, it really does tell you how much HTML Bing threw at it.

## Scan a URL

```bash
python path.py -url https://example.com
```

PATH can extract things like:

- page title
- metadata
- email addresses
- links
- public identity information

It can also follow selected links and scan them.

Because apparently opening one webpage wasn't enough.

## Config

`config.json` (all keys optional, missing ones fall back to defaults in `core/config.py`):

- `sources.parallel` — query search engines concurrently; `profiles.workers` — threads for platform probes and profile reads
- `sources.order` / `sources.<name>.enabled|limit` — which search engines run and in what order
- `trace.queries` — search queries, `{target}` is substituted
- `trace.scan_social_profiles`, `max_profiles`, `min_profile_match` (`exact|normalized|partial`)
- `trace.require_target_in_result` — drop search results that don't mention the target
- `profiles.enabled|platforms|github_api` — probe GitHub, GitLab, Habr, Keybase, DEV, Pikabu, Telegram directly for `<platform>/<username>` and read public fields (GitHub API: name, bio, blog, publicly listed email)
- `scan.max_linked_pages`, `scan.follow_social_links`
- `http.timeout|retries|backoff|user_agents`

CLI: `--config FILE`, `--json FILE|-`, `--no-profiles`, `--no-probe`, `trace --sources duckduckgo,bing`.

Google is disabled by default: it almost always serves a JS-only page to non-browser clients.

## Social profile parser

`extractors/social.py` recognises ~20 platforms (GitHub, GitLab, X, Telegram, VK, YouTube, TikTok,
Instagram, Reddit, Steam, Habr, ...), filters out non-profile pages (`/login`, `/status/..`, repos),
canonicalises URLs and scores how close the profile username is to the traced target.

Tests: `python tests/test_social.py && python tests/test_sources.py`

## Help

```bash
python path.py --help
```

Output:

```text
usage: path [-h] [-url URL] {trace} ...

Path — OSINT & Identity Intelligence
```

## How it works

The general idea is pretty simple:

```text
             target
                |
                v
        +---------------+
        |     PATH      |
        +---------------+
                |
       +--------+--------+
       |        |        |
       v        v        v
     Bing     Web       DDG
       |        |        |
       +--------+--------+
                |
                v
          extractors
                |
       +--------+--------+
       |        |        |
       v        v        v
     Email    Links   Metadata
       |        |        |
       +--------+--------+
                |
                v
            findings
```

The project is intentionally modular, so sources and extractors can be expanded without turning `path.py` into a 2000-line crime scene.

## Findings

Every finding contains information about where it came from and why it was collected.

For example:

```text
[MEDIUM] WEB_RESULT
  Value:       GitHub
  Source:      https://github.com/github
  Source type: search_engine
  Evidence:    Search result returned for identifier: github
```

PATH isn't supposed to magically decide that a random search result is definitely the person you're looking for.

It collects evidence.

You decide what the evidence means.

## Project structure

```text
Path/
├── core/
│   ├── engine.py
│   └── models.py
│
├── extractors/
│   ├── email.py
│   ├── email_classification.py
│   ├── link_filter.py
│   ├── links.py
│   ├── mail_provider.py
│   ├── metadata.py
│   └── public_identity.py
│
├── sources/
│   ├── bing.py
│   ├── duckduckgo.py
│   ├── google.py
│   └── web.py
│
├── output/
│   └── console.py
│
├── core/data/
│
├── tools/
│   └── import_mailcat.py
│
└── path.py
```

## Current state

`v0.2.0`

This is an early version.

Things will probably break.

Some things will break in extremely creative ways.

If PATH suddenly starts reporting that your microwave has a GitHub account, please open an issue instead of trusting it.

## Roadmap

Some things I'd like to add eventually:

- more search sources
- better result ranking
- stronger identity correlation
- more extractors
- better URL handling
- improved output formats
- JSON export
- more useful confidence scoring
- probably several bugs I haven't discovered yet

The roadmap is subject to change because this project is being developed by one person who occasionally gets distracted by completely unrelated shit.

## Disclaimer

PATH is intended for legitimate OSINT, research, security testing and educational purposes.

Only investigate information you are legally allowed to access.

Publicly available does not automatically mean "do whatever the fuck you want with it."

Don't use this tool for stalking, harassment, doxxing or other illegal activity.

## Contributing

Found a bug?

Open an issue.

Made something better?

Pull request.

Found a critical vulnerability?

Please don't post:

```text
lol ur tool is fucked
```

and disappear.

Tell me what happened and, preferably, how to reproduce it.

## License

See `LICENSE`.

---

### Built because manually checking 15 tabs at once gets old.

**PATH — OSINT & Identity Intelligence**