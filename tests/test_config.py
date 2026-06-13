"""测试 config.py — AgentSettings。"""



class TestAgentSettings:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("AGENT_PROVIDER", raising=False)
        from config import AgentSettings
        settings = AgentSettings()
        assert settings.provider_name == "totoro"
        assert settings.max_iterations == 50
        assert settings.max_tokens == 4096
        assert settings.temperature == 0.1
        assert settings.tool_preset == "full"

    def test_resolve_provider(self, monkeypatch):
        monkeypatch.setenv("AGENT_PROVIDER", "openai")
        from config import AgentSettings
        settings = AgentSettings()
        assert settings.resolve_provider() == "openai"

    def test_totoro_config(self, monkeypatch):
        monkeypatch.setenv("TOTORO_API_KEY", "my_key")
        from config import AgentSettings
        settings = AgentSettings()
        assert settings.totoro.api_key == "my_key"
        assert "longcat.chat" in settings.totoro.base_url

    def test_openai_config(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oai_key")
        from config import AgentSettings
        settings = AgentSettings()
        assert settings.openai.api_key == "oai_key"

    def test_anthropic_config(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant_key")
        from config import AgentSettings
        settings = AgentSettings()
        assert settings.anthropic.api_key == "ant_key"
