# Changelog

## 0.3.0
- HTML report: `--html FILE` writes a self-contained page (escaped, dark mode, http/https links only)
- 13 platforms probed through public APIs/pages: GitHub, GitLab, Habr, Keybase, DEV, Pikabu, Telegram, Hacker News, Docker Hub, Bluesky, Lichess, Chess.com, Codeberg
- Public profile fields (name, bio, location, company, website, email) become findings; links in bios and Keybase proofs are followed as cross-links
- Social parser knows 12 more platforms (Hacker News, Docker Hub, Lichess, Chess.com, Codeberg, PyPI, npm, Replit, Codeforces, LeetCode, Linktree, Mastodon)
- Correlation uses shared websites and shared emails as strong signals (social-network hosts ignored)
- On-disk request cache (`cache.enabled|ttl|dir`, `--no-cache`); block pages and errors are never cached
- Captcha / bot-check pages are detected in every search source and reported with a hint instead of "0 results"
- More tests (cache, block detection, API probes, new platforms, correlation, HTML escaping)

## 0.2.1
- Search sources, platform probes and profile reads now run concurrently (`sources.parallel`, `profiles.workers`)
- A failing source no longer breaks the whole trace
- Removed comments and docstrings from the code

## 0.2.0
- Social profile parser (~20 platforms): canonical URLs, non-profile filtering, username match scoring
- Direct profile probing by username (GitHub, GitLab, Habr, Keybase, DEV, Pikabu, Telegram) with
  spelling variants, plus public GitHub API fields
- Profile correlation: groups profiles that likely belong to one person, flags the rest as unconfirmed
- `config.json` (+ git-ignored `config.local.json`): sources, queries, limits, http, profiles
- Shared HTTP layer with retry/backoff; DuckDuckGo redirect decoding fixed; Bing locale fixed
- Relevance filter for search results (with Cyrillic transliteration)
- Email extractor no longer reports `icon@2x.png`-style asset names
- CLI: `--config`, `--json`, `--no-profiles`, `--no-probe`, `trace --sources`
- Tests and CI

## 0.1.0
- Initial release
