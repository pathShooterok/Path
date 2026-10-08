# Changelog

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
