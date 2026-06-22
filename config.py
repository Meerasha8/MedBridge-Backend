from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    GROQ_API_KEY: str
    MCP_SERVER_URL: str = "https://medbridge-mcp.onrender.com"
    MCP_SECRET_KEY: str
    JWT_SECRET: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
