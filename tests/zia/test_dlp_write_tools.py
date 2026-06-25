from unittest.mock import MagicMock, patch

import pytest


def _mock_obj(data: dict):
    obj = MagicMock()
    obj.as_dict.return_value = data
    return obj


class TestZiaDlpWriteTools:
    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_create_dlp_dictionary_normalizes_entries(self, mock_get_client):
        from zscaler_mcp.tools.zia.dlp_write import zia_create_dlp_dictionary

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.get_body.return_value = {"id": 123, "name": "Sensitive Keywords"}
        mock_client.zia.dlp_dictionary._zia_base_endpoint = "/zia/api/v1"
        mock_client.zia.dlp_dictionary._request_executor.create_request.return_value = (
            "request",
            None,
        )
        mock_client.zia.dlp_dictionary._request_executor.execute.return_value = (
            mock_response,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_create_dlp_dictionary(
            name="Sensitive Keywords",
            phrases=["Abracadabra", {"action": "unique", "phrase": "Swordfish"}],
            patterns=[["all", r"ACME-\d{4}"]],
            description="Test dictionary",
        )

        assert result["id"] == 123
        mock_client.zia.dlp_dictionary._request_executor.create_request.assert_called_once_with(
            method="POST",
            endpoint="/zia/api/v1/dlpDictionaries",
            body={
                "name": "Sensitive Keywords",
                "customPhraseMatchType": "MATCH_ANY_CUSTOM_PHRASE_PATTERN_DICTIONARY",
                "dictionaryType": "PATTERNS_AND_PHRASES",
                "description": "Test dictionary",
                "phrases": [
                    {"action": "PHRASE_COUNT_TYPE_ALL", "phrase": "Abracadabra"},
                    {"action": "PHRASE_COUNT_TYPE_UNIQUE", "phrase": "Swordfish"},
                ],
                "patterns": [{"action": "PATTERN_COUNT_TYPE_ALL", "pattern": r"ACME-\d{4}"}],
            },
        )

    def test_create_dlp_dictionary_requires_content(self):
        from zscaler_mcp.tools.zia.dlp_write import zia_create_dlp_dictionary

        with pytest.raises(ValueError, match="At least one phrase or pattern"):
            zia_create_dlp_dictionary(name="Empty")

    def test_delete_dlp_dictionary_requires_confirmation(self):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_dictionary

        result = zia_delete_dlp_dictionary(dict_id=123)

        assert "CONFIRMATION REQUIRED" in result
        assert "DELETE Dlp Dictionary" in result
        assert "confirmation_token" in result

    @patch("zscaler_mcp.common.elicitation.check_confirmation", return_value=None)
    @patch("zscaler_mcp.common.elicitation.extract_confirmed_from_kwargs", return_value="token")
    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_delete_dlp_dictionary_deletes_custom_dictionary(
        self, mock_get_client, _mock_extract, _mock_confirm
    ):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_dictionary

        mock_client = MagicMock()
        mock_client.zia.dlp_dictionary.get_dict.return_value = (
            _mock_obj({"id": 123, "name": "Custom Dict", "custom": True}),
            None,
            None,
        )
        mock_client.zia.dlp_dictionary.delete_dict.return_value = (None, None, None)
        mock_get_client.return_value = mock_client

        result = zia_delete_dlp_dictionary(dict_id=123, kwargs='{"confirmation_token":"token"}')

        assert result == "DLP dictionary 123 deleted successfully."
        mock_client.zia.dlp_dictionary.delete_dict.assert_called_once_with(123)

    @patch("zscaler_mcp.common.elicitation.check_confirmation", return_value=None)
    @patch("zscaler_mcp.common.elicitation.extract_confirmed_from_kwargs", return_value="token")
    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_delete_dlp_dictionary_refuses_predefined_by_default(
        self, mock_get_client, _mock_extract, _mock_confirm
    ):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_dictionary

        mock_client = MagicMock()
        mock_client.zia.dlp_dictionary.get_dict.return_value = (
            _mock_obj({"id": 63, "name": "CREDIT_CARD", "custom": False}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="not custom"):
            zia_delete_dlp_dictionary(dict_id=63, kwargs='{"confirmation_token":"token"}')

        mock_client.zia.dlp_dictionary.delete_dict.assert_not_called()

    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_create_dlp_engine_validates_and_creates(self, mock_get_client):
        from zscaler_mcp.tools.zia.dlp_write import zia_create_dlp_engine

        mock_client = MagicMock()
        mock_client.zia.dlp_engine.validate_dlp_expression.return_value = (
            _mock_obj({"status": "VALID"}),
            None,
            None,
        )
        mock_client.zia.dlp_engine.add_dlp_engine.return_value = (
            _mock_obj({"id": 456, "name": "PII Engine"}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_create_dlp_engine(
            name="PII Engine",
            engine_expression="((D63.S > 0) OR (D50.S > 0))",
            description="Blocks CC or SIN",
        )

        assert result["id"] == 456
        mock_client.zia.dlp_engine.validate_dlp_expression.assert_called_once_with(
            "((D63.S > 0) OR (D50.S > 0))"
        )
        mock_client.zia.dlp_engine.add_dlp_engine.assert_called_once_with(
            name="PII Engine",
            engine_expression="((D63.S > 0) OR (D50.S > 0))",
            custom_dlp_engine=True,
            description="Blocks CC or SIN",
        )

    def test_delete_dlp_engine_requires_confirmation(self):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_engine

        result = zia_delete_dlp_engine(engine_id=456)

        assert "CONFIRMATION REQUIRED" in result
        assert "DELETE Dlp Engine" in result
        assert "confirmation_token" in result

    @patch("zscaler_mcp.common.elicitation.check_confirmation", return_value=None)
    @patch("zscaler_mcp.common.elicitation.extract_confirmed_from_kwargs", return_value="token")
    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_delete_dlp_engine_deletes_custom_engine(
        self, mock_get_client, _mock_extract, _mock_confirm
    ):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_engine

        mock_client = MagicMock()
        mock_client.zia.dlp_engine.get_dlp_engines.return_value = (
            _mock_obj({"id": 456, "name": "Custom Engine", "custom_dlp_engine": True}),
            None,
            None,
        )
        mock_client.zia.dlp_engine.delete_dlp_engine.return_value = (None, None, None)
        mock_get_client.return_value = mock_client

        result = zia_delete_dlp_engine(engine_id=456, kwargs='{"confirmation_token":"token"}')

        assert result == "DLP engine 456 deleted successfully."
        mock_client.zia.dlp_engine.delete_dlp_engine.assert_called_once_with(456)

    @patch("zscaler_mcp.common.elicitation.check_confirmation", return_value=None)
    @patch("zscaler_mcp.common.elicitation.extract_confirmed_from_kwargs", return_value="token")
    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_delete_dlp_engine_refuses_predefined_by_default(
        self, mock_get_client, _mock_extract, _mock_confirm
    ):
        from zscaler_mcp.tools.zia.dlp_write import zia_delete_dlp_engine

        mock_client = MagicMock()
        mock_client.zia.dlp_engine.get_dlp_engines.return_value = (
            _mock_obj({"id": 61, "predefined_engine_name": "PCI", "custom_dlp_engine": False}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="not custom"):
            zia_delete_dlp_engine(engine_id=61, kwargs='{"confirmation_token":"token"}')

        mock_client.zia.dlp_engine.delete_dlp_engine.assert_not_called()

    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_attach_dictionary_to_engine_appends_expression(self, mock_get_client):
        from zscaler_mcp.tools.zia.dlp_write import zia_attach_dictionary_to_engine

        mock_client = MagicMock()
        mock_client.zia.dlp_engine.get_dlp_engines.return_value = (
            _mock_obj(
                {
                    "id": 10,
                    "name": "Existing",
                    "description": "desc",
                    "engine_expression": "(D63.S &gt; 0)",
                    "custom_dlp_engine": True,
                }
            ),
            None,
            None,
        )
        mock_client.zia.dlp_engine.validate_dlp_expression.return_value = (
            _mock_obj({"status": "VALID"}),
            None,
            None,
        )
        mock_client.zia.dlp_engine.update_dlp_engine.return_value = (
            _mock_obj(
                {
                    "id": 10,
                    "name": "Existing",
                    "engine_expression": "((D63.S > 0)) OR (D50.S > 0)",
                    "custom_dlp_engine": True,
                }
            ),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_attach_dictionary_to_engine(engine_id=10, dictionary_id=50)

        assert result["id"] == 10
        args, kwargs = mock_client.zia.dlp_engine.update_dlp_engine.call_args
        assert args == (10,)
        assert kwargs["engine_expression"] == "((D63.S > 0)) OR (D50.S > 0)"

    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_attach_dictionary_to_engine_refuses_predefined_by_default(self, mock_get_client):
        from zscaler_mcp.tools.zia.dlp_write import zia_attach_dictionary_to_engine

        mock_client = MagicMock()
        mock_client.zia.dlp_engine.get_dlp_engines.return_value = (
            _mock_obj({"id": 61, "predefined_engine_name": "PCI", "custom_dlp_engine": False}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="not custom"):
            zia_attach_dictionary_to_engine(engine_id=61, dictionary_id=50)

    @patch("zscaler_mcp.tools.zia.dlp_write.get_zscaler_client")
    def test_attach_engine_to_policy_preserves_scope_and_appends(self, mock_get_client):
        from zscaler_mcp.tools.zia.dlp_write import zia_attach_engine_to_policy

        mock_client = MagicMock()
        mock_client.zia.dlp_web_rules.get_rule.return_value = (
            _mock_obj(
                {
                    "id": 99,
                    "name": "Existing DLP",
                    "description": "desc",
                    "action": "BLOCK",
                    "state": "ENABLED",
                    "rank": 7,
                    "order": 1,
                    "dlp_engines": [{"id": 11}],
                    "url_categories": ["CUSTOM_01"],
                    "groups": [1, 2],
                }
            ),
            None,
            None,
        )
        mock_client.zia.dlp_web_rules.update_rule.return_value = (
            _mock_obj({"id": 99, "name": "Existing DLP", "dlp_engines": [{"id": 11}, {"id": 12}]}),
            None,
            None,
        )
        mock_get_client.return_value = mock_client

        result = zia_attach_engine_to_policy(policy_rule_id=99, engine_id=12)

        assert result["id"] == 99
        args, kwargs = mock_client.zia.dlp_web_rules.update_rule.call_args
        assert args == (99,)
        assert kwargs["dlp_engines"] == [11, 12]
        assert kwargs["url_categories"] == ["CUSTOM_01"]
        assert kwargs["groups"] == [1, 2]

    def test_simulate_dlp_match_inline_dictionary_and_expression(self):
        from zscaler_mcp.tools.zia.dlp_write import zia_simulate_dlp_match

        result = zia_simulate_dlp_match(
            content="Project Umbrella contains ACME-1234.",
            dictionaries=[
                {
                    "id": 777,
                    "name": "Test",
                    "phrases": [{"phrase": "Project Umbrella"}],
                    "patterns": [{"pattern": r"ACME-\d{4}"}],
                }
            ],
            engine_expression="(D777.S > 1)",
        )

        assert result["matched"] is True
        assert result["dictionary_counts"]["777"] == 2
        assert result["engine_expression_result"] is True
