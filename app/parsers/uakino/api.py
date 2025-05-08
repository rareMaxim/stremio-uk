from typing import List
from fastapi import Depends, APIRouter
from fastapi_cache.decorator import cache
from app.schemas import Manifest, Catalogs, Preview, Series, Stream
from .settings import settings
from .services import (
    get_series_metadata,
    get_session,
    get_previews_metadata,
    get_streams,
    get_videos,
)
import aiohttp

router = APIRouter(prefix="/uakino")  # Префікс для uakino


@router.get("/manifest.json", tags=[settings.name])
@cache()  # Кешування маніфесту
async def addon_manifest() -> Manifest:
    manifest = Manifest(
        id="ua.stremio.uakino",  # ID  адону
        version="0.1.0",  # Початкова версія
        logo=f"{settings.main_url}/favicon.ico",
        name=settings.name,
        description="Фільми, серіали, мультфільми та аніме з сайту uakino.me українською.",
        types=["movie", "series"],  # Типи контенту, які підтримує адон
        catalogs=[
            Catalogs(
                type="movie",
                id="uakino_movies_year",
                name="Фільми (за роком)",
                extra=[],  # Можна додати, якщо потрібні додаткові опції як сортування, жанри
            ),
            Catalogs(
                type="series",
                id="uakino_series_year",
                name="Серіали (за роком)",
                extra=[],
            ),
            Catalogs(
                type="movie",  # Мультфільми зазвичай відносять до movie type в Stremio
                id="uakino_cartoons_year",
                name="Мультфільми (за роком)",
                extra=[],
            ),
            Catalogs(
                type="series",  # Аніме-серіали до series type
                id="uakino_anime_year",
                name="Аніме (за роком)",
                extra=[],
            ),
            # TODO: Можна додати каталог для пошуку
        ],
        resources=[
            "catalog",
            "meta",
            "stream",
        ],
    )
    return manifest

# Словник для зіставлення ID каталогу з шляхом на сайті
CATALOG_PATHS = {
    "uakino_movies_year": "/filmy/f/c.year=1980,2025/sort=d.year;desc/",
    "uakino_series_year": "/seriesss/f/c.year=1980,2025/sort=d.year;desc/",
    "uakino_cartoons_year": "/cartoon/f/c.year=1980,2025/sort=d.year;desc/",
    "uakino_anime_year": "/animeukr/f/c.year=1980,2025/sort=d.year;desc/",
}


@router.get("/catalog/{type_}/{id}.json", tags=[settings.name])
@cache(expire=24 * 60 * 60)
async def addon_catalog(
    type_: str,
    id: str,
    session: aiohttp.ClientSession = Depends(get_session),
) -> dict[str, list[Preview]]:
    if id not in CATALOG_PATHS:
        return {"metas": []}

    catalog_path = CATALOG_PATHS[id]
    url = f"{settings.main_url}{catalog_path}"

    async with session.get(url) as response:
        response.raise_for_status()
        html_content = await response.text()
        return await get_previews_metadata(html_content, type_)


@router.get("/catalog/{type_}/{id}/skip={skip}.json", tags=[settings.name])
@cache(expire=24 * 60 * 60)
async def addon_catalog_skip(
    type_: str,
    id: str,
    skip: int,
    session: aiohttp.ClientSession = Depends(get_session),
) -> dict[str, list[Preview]]:
    if id not in CATALOG_PATHS:
        return {"metas": []}

    catalog_path = CATALOG_PATHS[id]
    page_number = (skip // settings.items_per_page) + 1

    paginated_url_part = f"page/{page_number}/" if page_number > 1 else ""
    url = f"{settings.main_url}{catalog_path}{paginated_url_part}"

    async with session.get(url) as response:
        response.raise_for_status()
        html_content = await response.text()
        return await get_previews_metadata(html_content, type_)


@router.get("/meta/{type_}/{id:path}.json", tags=[settings.name], response_model=dict[str, Series])
@cache(expire=24 * 60 * 60)
async def addon_meta(
    type_: str,
    id: str,
    session: aiohttp.ClientSession = Depends(get_session),
) -> dict[str, Series]:
    detail_page_url = f"{settings.main_url}/{id}.html"

    try:
        async with session.get(detail_page_url) as response:
            response.raise_for_status()
            html_content = await response.text()

            videos = await get_videos(id, html_content, session, type_)
            series_metadata = await get_series_metadata(id, html_content, videos, type_)

        return series_metadata
    except aiohttp.client_exceptions.ClientResponseError as e:
        print(f"Error fetching meta for {id}: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error fetching meta for {id}: {e}")
        return {}


@router.get("/stream/{type_}/{video_id:path}.json", tags=[settings.name], response_model=dict[str, List[Stream]])
@cache(expire=6 * 60 * 60)
async def addon_stream(
    type_: str,
    video_id: str,
    session: aiohttp.ClientSession = Depends(get_session)
) -> dict[str, List[Stream]]:

    print(f"Запит стрімів для type={type_}, video_id={video_id}")
    streams_response = await get_streams(type_, video_id, session)
    print(f"Знайдено стрімів: {streams_response}")
    return streams_response
