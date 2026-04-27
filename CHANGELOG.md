# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-04-27

### Added

- Multi-channel A2A gateway with Slack, WhatsApp, Google Chat, and Email support
- A2A protocol client (JSON-RPC 2.0, `message/send`)
- Per-channel markdown adaptation (WhatsApp, Slack formatting)
- Message chunking with code fence awareness and per-channel limits
- Message debouncing with configurable window, max messages, and max chars
- Fixed-window rate limiting for A2A and per-channel sends
- Retry with exponential backoff and jitter
- Group policies (open / mention-only / disabled) with per-group overrides
- Multi-account support for all channels
- File attachment support (inbound and outbound) across all channels
- Comprehensive test suite (unit, integration, contract, live tests)
- Docker support
- GitHub Actions CI
