# Changelog

## Unreleased

- Improved user-facing weather description wording.

## v1.1 — Safe refactor and wording polish

- Split `AiWeatherService` internals into dedicated `ai/*` helper modules.
- Added pytest coverage for AI signatures, location assist, and service facade.
- Extracted pure location compare helpers from `handlers/locations.py`.
- Added tests for compare helper logic.
- Improved Russian location label wording in compare outputs.
- Bumped compare-by-date cache signature version.
- Removed `User_Data.json` from Git tracking and added it to `.gitignore`.
- Verified deployment with Docker Compose.

