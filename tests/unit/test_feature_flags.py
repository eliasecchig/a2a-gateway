# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import pytest

from gateway.config import SlackAccountConfig, load_config
from gateway.core.a2a_client import A2AClient
from gateway.core.router import Router


@pytest.fixture
def router():
    return Router(A2AClient("http://localhost:9999"))


class TestFeatureEnabled:
    def test_returns_true_when_no_features_registered(self, router):
        assert router._feature_enabled("slack", "typing") is True

    def test_returns_true_when_feature_explicitly_enabled(self, router):
        router._account_features["slack"] = {"typing": True}
        assert router._feature_enabled("slack", "typing") is True

    def test_returns_false_when_feature_explicitly_disabled(self, router):
        router._account_features["slack"] = {"typing": False}
        assert router._feature_enabled("slack", "typing") is False

    def test_returns_true_for_unmentioned_feature(self, router):
        router._account_features["slack"] = {"ack": False}
        assert router._feature_enabled("slack", "typing") is True

    def test_different_channels_independent(self, router):
        router._account_features["slack"] = {"typing": False}
        router._account_features["whatsapp"] = {"typing": True}
        assert router._feature_enabled("slack", "typing") is False
        assert router._feature_enabled("whatsapp", "typing") is True


class TestRegisterWithFeatures:
    def test_register_stores_features(self, router):
        from tests.helpers.mock_adapter import MockAdapter

        adapter = MockAdapter("test_ch")
        router.register(adapter, features={"typing": True, "ack": False})
        assert router._account_features["test_ch"] == {
            "typing": True,
            "ack": False,
        }

    def test_register_without_features_no_entry(self, router):
        from tests.helpers.mock_adapter import MockAdapter

        adapter = MockAdapter("test_ch")
        router.register(adapter)
        assert "test_ch" not in router._account_features


class TestConfigFeaturesParsing:
    def test_features_dict_on_account_config(self):
        cfg = SlackAccountConfig(
            enabled=True,
            bot_token="xoxb-test",
            features={"typing": True, "ack": False},
        )
        assert cfg.features == {"typing": True, "ack": False}

    def test_features_default_empty(self):
        cfg = SlackAccountConfig()
        assert cfg.features == {}

    def test_features_parsed_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
channels:
  slack:
    enabled: true
    bot_token: "xoxb-test"
    app_token: "xapp-test"
    features:
      typing: true
      ack: false
"""
        )
        cfg = load_config(config_file)
        assert len(cfg.slack_accounts) == 1
        assert cfg.slack_accounts[0].features == {
            "typing": True,
            "ack": False,
        }
