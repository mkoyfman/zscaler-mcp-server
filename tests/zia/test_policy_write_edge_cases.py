from unittest.mock import MagicMock, patch

import pytest


def _mock_obj(data: dict):
    obj = MagicMock()
    obj.as_dict.return_value = data
    return obj


class TestWebDlpWriteEdgeCases:
    @patch("zscaler_mcp.tools.zia.web_dlp_rules.get_zscaler_client")
    def test_create_web_dlp_accepts_canonical_cloud_app_strings(self, mock_get_client):
        from zscaler_mcp.tools.zia.web_dlp_rules import zia_create_web_dlp_rule

        mock_client = MagicMock()
        mock_client.zia.dlp_web_rules.add_rule.return_value = (
            _mock_obj({"id": 42, "name": "GenAI DLP"}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_create_web_dlp_rule(
            name="GenAI DLP",
            rule_action="BLOCK",
            cloud_applications=["CHATGPT_AI", "CLAUDE_AI"],
            dlp_engines=[25],
            protocols=["ANY_RULE"],
            inspect_http_get_enabled=False,
            order=1,
        )

        assert result["id"] == 42
        mock_client.zia.dlp_web_rules.add_rule.assert_called_once()
        payload = mock_client.zia.dlp_web_rules.add_rule.call_args.kwargs
        assert payload["cloud_applications"] == ["CHATGPT_AI", "CLAUDE_AI"]
        assert payload["protocols"] == ["ANY_RULE"]
        assert payload["inspect_http_get_enabled"] is False


class TestCloudAppControlIsolationProfile:
    @patch("zscaler_mcp.tools.zia.cloud_app_control.validate_app_class", return_value="AI_ML")
    @patch("zscaler_mcp.tools.zia.cloud_app_control.get_zscaler_client")
    def test_create_isolate_rule_includes_cbi_profile(self, mock_get_client, _mock_validate):
        from zscaler_mcp.tools.zia.cloud_app_control import zia_create_cloud_app_control_rule

        mock_client = MagicMock()
        mock_client.zia.cloudappcontrol.add_rule.return_value = (
            _mock_obj({"id": 7, "name": "Iso ChatGPT"}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_create_cloud_app_control_rule(
            rule_type="AI_ML",
            name="Iso ChatGPT",
            actions=["ISOLATE_AI_ML_WEB_USE"],
            cloud_applications=["CHATGPT_AI"],
            isolation_profile_id=123,
            isolation_profile_name="Default Isolation",
            resolve_cloud_apps=False,
        )

        assert result["id"] == 7
        mock_client.zia.cloudappcontrol.add_rule.assert_called_once()
        payload = mock_client.zia.cloudappcontrol.add_rule.call_args.kwargs
        assert payload["cbiProfile"] == {"id": 123, "name": "Default Isolation"}

    @patch("zscaler_mcp.tools.zia.cloud_app_control.validate_app_class", return_value="AI_ML")
    def test_create_isolate_rule_requires_cbi_profile(self, _mock_validate):
        from zscaler_mcp.tools.zia.cloud_app_control import zia_create_cloud_app_control_rule

        with pytest.raises(ValueError, match="isolation profile"):
            zia_create_cloud_app_control_rule(
                rule_type="AI_ML",
                name="Iso ChatGPT",
                actions=["ISOLATE_AI_ML_WEB_USE"],
                cloud_applications=["CHATGPT_AI"],
                resolve_cloud_apps=False,
            )
