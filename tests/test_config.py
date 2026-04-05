"""Tests for CognitoConfig."""

import os
from pathlib import Path
from unittest import mock

import pytest
import yaml

from daylily_cognito.config import CognitoConfig


def _write_config_store(tmp_path, contexts, active_context=""):
    """Write a config YAML store under tmp_path/.config/daycog/."""
    cfg_dir = tmp_path / ".config" / "daycog"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    payload = {"contexts": contexts}
    if active_context:
        payload["active_context"] = active_context
    (cfg_dir / "config.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


class TestCognitoConfigValidate:
    """Tests for CognitoConfig.validate()."""

    def test_validate_success(self) -> None:
        """Valid config passes validation."""
        config = CognitoConfig(
            name="test",
            region="us-west-2",
            user_pool_id="us-west-2_abc123",
            app_client_id="client123",
        )
        config.validate()  # Should not raise

    def test_validate_missing_region(self) -> None:
        """Missing region raises ValueError."""
        config = CognitoConfig(
            name="test",
            region="",
            user_pool_id="us-west-2_abc123",
            app_client_id="client123",
        )
        with pytest.raises(ValueError, match="region"):
            config.validate()

    def test_validate_missing_multiple(self) -> None:
        """Missing multiple fields lists all in error."""
        config = CognitoConfig(
            name="test",
            region="",
            user_pool_id="",
            app_client_id="",
        )
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "region" in str(exc_info.value)
        assert "user_pool_id" in str(exc_info.value)
        assert "app_client_id" in str(exc_info.value)


class TestCognitoConfigFromEnv:
    """Tests for CognitoConfig.from_env()."""

    def test_from_env_success(self, tmp_path) -> None:
        """Loads config from the config store context."""
        _write_config_store(tmp_path, contexts={
            "PROD": {
                "COGNITO_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "us-east-1_pool",
                "COGNITO_APP_CLIENT_ID": "client_prod",
                "AWS_PROFILE": "prod-profile",
            }
        })
        # Clear AWS_PROFILE from env so the config store value wins
        with mock.patch("pathlib.Path.home", return_value=tmp_path), \
             mock.patch.dict(os.environ, {}, clear=True):
            config = CognitoConfig.from_env("PROD")

        assert config.name == "PROD"
        assert config.region == "us-east-1"
        assert config.user_pool_id == "us-east-1_pool"
        assert config.app_client_id == "client_prod"
        assert config.aws_profile == "prod-profile"

    def test_from_env_missing_vars(self, tmp_path) -> None:
        """Missing config values raises ValueError."""
        _write_config_store(tmp_path, contexts={
            "TEST": {"COGNITO_REGION": "us-west-2"}
        })
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(ValueError) as exc_info:
                CognitoConfig.from_env("TEST")
        assert "DAYCOG_TEST_USER_POOL_ID" in str(exc_info.value)
        assert "DAYCOG_TEST_APP_CLIENT_ID" in str(exc_info.value)

    def test_from_env_custom_prefix(self, tmp_path) -> None:
        """Custom prefix works (still reads from config store)."""
        _write_config_store(tmp_path, contexts={
            "DEV": {
                "COGNITO_REGION": "eu-west-1",
                "COGNITO_USER_POOL_ID": "eu-west-1_dev",
                "COGNITO_APP_CLIENT_ID": "client_dev",
            }
        })
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            config = CognitoConfig.from_env("DEV", prefix="MYCOG")

        assert config.region == "eu-west-1"

    def test_from_env_multi_config_isolation(self, tmp_path) -> None:
        """Two configs loaded concurrently don't cross-talk."""
        _write_config_store(tmp_path, contexts={
            "A": {
                "COGNITO_REGION": "us-west-2",
                "COGNITO_USER_POOL_ID": "pool_a",
                "COGNITO_APP_CLIENT_ID": "client_a",
            },
            "B": {
                "COGNITO_REGION": "eu-central-1",
                "COGNITO_USER_POOL_ID": "pool_b",
                "COGNITO_APP_CLIENT_ID": "client_b",
            },
        })
        with mock.patch("pathlib.Path.home", return_value=tmp_path):
            config_a = CognitoConfig.from_env("A")
            config_b = CognitoConfig.from_env("B")

        assert config_a.region == "us-west-2"
        assert config_a.user_pool_id == "pool_a"
        assert config_b.region == "eu-central-1"
        assert config_b.user_pool_id == "pool_b"


