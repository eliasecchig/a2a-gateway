from __future__ import annotations

from pathlib import Path

import yaml

from gateway.config import (
    load_config,
)


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.a2a_server_url == "http://localhost:8001"
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.slack_accounts == []

    def test_single_account_dict_format(self, tmp_path: Path):
        data = {
            "channels": {
                "slack": {
                    "enabled": True,
                    "bot_token": "xoxb-123",
                    "app_token": "xapp-123",
                }
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert len(cfg.slack_accounts) == 1
        assert cfg.slack_accounts[0].bot_token == "xoxb-123"
        assert cfg.slack_accounts[0].account_id == "default"

    def test_multi_account_list_format(self, tmp_path: Path):
        data = {
            "channels": {
                "slack": [
                    {
                        "account_id": "ws_a",
                        "enabled": True,
                        "bot_token": "xoxb-a",
                        "app_token": "xapp-a",
                    },
                    {
                        "account_id": "ws_b",
                        "enabled": True,
                        "bot_token": "xoxb-b",
                        "app_token": "xapp-b",
                    },
                ]
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert len(cfg.slack_accounts) == 2
        assert cfg.slack_accounts[0].account_id == "ws_a"
        assert cfg.slack_accounts[1].account_id == "ws_b"

    def test_disabled_accounts_filtered(self, tmp_path: Path):
        data = {
            "channels": {
                "slack": [
                    {
                        "account_id": "a",
                        "enabled": True,
                        "bot_token": "xoxb-a",
                        "app_token": "xapp-a",
                    },
                    {
                        "account_id": "b",
                        "enabled": False,
                        "bot_token": "xoxb-b",
                        "app_token": "xapp-b",
                    },
                ]
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert len(cfg.slack_accounts) == 1
        assert cfg.slack_accounts[0].account_id == "a"

    def test_disabled_single_account_filtered(self, tmp_path: Path):
        data = {"channels": {"slack": {"enabled": False, "bot_token": "x"}}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.slack_accounts == []

    def test_default_on_features_have_defaults(self, tmp_path: Path):
        data = {"channels": {}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.chunking is not None
        assert cfg.debounce is not None
        assert cfg.rate_limiting is not None
        assert cfg.health is not None
        assert cfg.session is not None
        assert cfg.concurrency is not None
        assert cfg.streaming is not None

    def test_opt_in_features_none_when_absent(self, tmp_path: Path):
        data = {"channels": {}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.group_policies is None
        assert cfg.typing is None
        assert cfg.ack is None
        assert cfg.logging is None

    def test_chunking_config_parsed(self, tmp_path: Path):
        data = {"chunking": {"mode": "length", "default_limit": 2000}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.chunking is not None
        assert cfg.chunking.mode == "length"
        assert cfg.chunking.default_limit == 2000

    def test_debounce_config_parsed(self, tmp_path: Path):
        data = {"debounce": {"window_ms": 300, "max_messages": 5, "max_chars": 2000}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.debounce is not None
        assert cfg.debounce.window_ms == 300

    def test_group_policies_with_overrides(self, tmp_path: Path):
        data = {
            "group_policies": {
                "slack": {"mode": "mention_only", "overrides": {"C123": "open"}},
                "whatsapp": {"mode": "open"},
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.group_policies is not None
        assert cfg.group_policies.slack.mode == "mention_only"
        assert cfg.group_policies.slack.overrides == {"C123": "open"}

    def test_rate_limiting_nested_config(self, tmp_path: Path):
        data = {
            "rate_limiting": {
                "a2a": {"max_requests": 100, "window_seconds": 30},
                "channel": {"max_requests": 20, "window_seconds": 60},
                "backoff": {
                    "initial": 0.5,
                    "factor": 3.0,
                    "max_delay": 120,
                    "max_retries": 3,
                },
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.rate_limiting is not None
        assert cfg.rate_limiting.a2a.max_requests == 100
        assert cfg.rate_limiting.channel.max_requests == 20
        assert cfg.rate_limiting.backoff.factor == 3.0

    def test_features_can_be_disabled(self, tmp_path: Path):
        data = {
            "chunking": {"enabled": False},
            "debounce": {"enabled": False},
            "rate_limiting": {"enabled": False},
            "health": {"enabled": False},
            "session": {"enabled": False},
            "concurrency": {"enabled": False},
            "streaming": {"enabled": False},
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.chunking.enabled is False
        assert cfg.debounce.enabled is False
        assert cfg.rate_limiting.enabled is False
        assert cfg.health.enabled is False
        assert cfg.session.enabled is False
        assert cfg.concurrency.enabled is False
        assert cfg.streaming.enabled is False

    def test_a2a_server_url(self, tmp_path: Path):
        data = {"a2a": {"server_url": "http://myagent:9000"}}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert cfg.a2a_server_url == "http://myagent:9000"


class TestEnvOverrides:
    def test_a2a_server_url_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("A2A_SERVER_URL", "http://agent:9999")
        cfg = load_config(tmp_path / "nope.yaml")
        assert cfg.a2a_server_url == "http://agent:9999"

    def test_host_and_port_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("GATEWAY_HOST", "127.0.0.1")
        monkeypatch.setenv("GATEWAY_PORT", "9000")
        cfg = load_config(tmp_path / "nope.yaml")
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9000

    def test_slack_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-env")
        cfg = load_config(tmp_path / "nope.yaml")
        assert len(cfg.slack_accounts) == 1
        assert cfg.slack_accounts[0].bot_token == "xoxb-env"
        assert cfg.slack_accounts[0].app_token == "xapp-env"
        assert cfg.slack_accounts[0].enabled is True

    def test_slack_env_does_not_override_yaml(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env")
        data = {
            "channels": {
                "slack": {
                    "enabled": True,
                    "bot_token": "xoxb-yaml",
                    "app_token": "xapp-yaml",
                }
            }
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(data))
        cfg = load_config(p)
        assert len(cfg.slack_accounts) == 1
        assert cfg.slack_accounts[0].bot_token == "xoxb-yaml"

    def test_whatsapp_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "wa-token")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "vt")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "secret")
        cfg = load_config(tmp_path / "nope.yaml")
        assert len(cfg.whatsapp_accounts) == 1
        assert cfg.whatsapp_accounts[0].access_token == "wa-token"
        assert cfg.whatsapp_accounts[0].phone_number_id == "12345"

    def test_google_chat_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_SERVICE_ACCOUNT_PATH", "/sa.json")
        cfg = load_config(tmp_path / "nope.yaml")
        assert len(cfg.google_chat_accounts) == 1
        assert cfg.google_chat_accounts[0].service_account_path == "/sa.json"

    def test_email_from_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("EMAIL_SMTP_PORT", "465")
        monkeypatch.setenv("EMAIL_FROM_ADDRESS", "bot@example.com")
        cfg = load_config(tmp_path / "nope.yaml")
        assert len(cfg.email_accounts) == 1
        assert cfg.email_accounts[0].smtp_host == "smtp.example.com"
        assert cfg.email_accounts[0].smtp_port == 465
        assert cfg.email_accounts[0].from_address == "bot@example.com"
