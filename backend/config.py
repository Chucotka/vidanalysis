from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    STORAGE_PATH: str = "./storage"
    REDIS_URL: str = "redis://localhost:6379/0"
    MAX_FILE_SIZE_MB: int = 4000
    OPENAI_API_KEY: str = ""
    MOCK_AI: bool = False
    AUTH_TOKEN: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
