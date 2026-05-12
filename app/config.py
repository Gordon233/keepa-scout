from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    keepa_api_keys: str = ""
    openrouter_api_key: str = ""
    llm_model: str = "openai/gpt-5.5"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    db_path: str = "data/scout.db"

    @property
    def keepa_keys(self) -> list[str]:
        return [k.strip() for k in self.keepa_api_keys.split(",") if k.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
