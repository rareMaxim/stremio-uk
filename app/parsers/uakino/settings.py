from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    name: str = "UAKino"
    main_url: str = "https://uakino.me"
    items_per_page: int = 20


settings = Settings()
