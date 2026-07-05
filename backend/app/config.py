from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "QuizForge"
    secret_key: str = "change-me-in-env"
    database_url: str = "postgresql+psycopg2://quizforge:quizforge@db:5432/quizforge"
    redis_url: str = "redis://redis:6379/0"
    generation_provider: str = "anthropic"  # anthropic|openai|deepseek
    anthropic_api_key: str = ""
    generation_model: str = "claude-haiku-4-5"       # cheap + fast default
    generation_model_hq: str = "claude-sonnet-4-6"   # "high quality" toggle
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_generation_model: str = "gpt-4o-mini"
    openai_generation_model_hq: str = "gpt-4o"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_generation_model: str = "deepseek-v4-pro"
    deepseek_generation_model_hq: str = "deepseek-v4-pro"
    deepseek_thinking_enabled: bool = True
    deepseek_reasoning_effort: str = "max"  # high|max
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 25
    max_pages: int = 150
    session_cookie: str = "qf_session"
    session_max_age: int = 60 * 60 * 24 * 30  # 30 days
    cookie_secure: bool = True  # set COOKIE_SECURE=0 for plain-http local dev
    cards_per_chunk: int = 10
    mcq_per_chunk: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
