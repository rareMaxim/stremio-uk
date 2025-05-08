import json
import time
from typing import List, Optional
from bs4 import BeautifulSoup, Tag
from app.schemas import Preview, Series, Stream, Videos
from .settings import settings
import aiohttp
import re


async def get_session():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        yield session


async def get_previews_metadata(html_content: str, type_: str) -> dict[str, list[Preview]]:
    previews_metadata = {"metas": []}
    soup = BeautifulSoup(html_content, "html.parser")

    for item in soup.find_all("div", class_="movie-item short-item"):
        title_tag = item.find("a", class_="movie-title")
        if not title_tag:
            continue

        name = title_tag.get_text(strip=True)
        href = title_tag.get("href")

        if not href:
            continue

        item_id = href.replace(settings.main_url, "").lstrip(
            "/").replace(".html", "")

        poster_tag = item.find("div", class_="movie-img")
        poster_src = None
        if poster_tag and poster_tag.find("img"):
            img_src = poster_tag.find("img").get("src")
            if img_src:
                poster_src = f"{settings.main_url}{img_src}" if img_src.startswith(
                    "/") else img_src

        description = ""
        desc_tag = item.find("div", class_="movie-text")
        if desc_tag:
            about_text_tag = desc_tag.find("span", class_="desc-about-text")
            if about_text_tag:
                description = about_text_tag.get_text(strip=True)

        genres = []
        genre_label_tag = item.find(
            "div", class_="fi-label", string=re.compile(r"Жанр:"))
        if genre_label_tag:
            genre_value_tag = genre_label_tag.find_next_sibling(
                "div", class_="deck-value")
            if genre_value_tag:
                genres = [genre.strip() for genre in genre_value_tag.get_text(
                    separator=",").split(',') if genre.strip()]

        previews_metadata["metas"].append(
            Preview(
                id=item_id,
                type=type_,  # movie або series
                name=name,
                poster=poster_src,
                description=description,
                genres=genres,
            )
        )
    return previews_metadata


async def get_series_metadata(
    item_id: str, html_content: str, videos: list[Videos], type_: str
) -> dict[str, Series]:
    soup = BeautifulSoup(html_content, "html.parser")

    title_tag = soup.find("h1").find(
        "span", class_="solototle", itemprop="name")
    name = title_tag.get_text(strip=True) if title_tag else "Назва не знайдена"

    poster_tag = soup.find(
        "div", class_="film-poster").find("img", itemprop="image")
    poster_src = poster_tag.get("src") if poster_tag else None
    full_poster_url = f"{settings.main_url}{poster_src}" if poster_src and poster_src.startswith(
        "/") else poster_src

    background_url = full_poster_url

    description_tag = soup.find("div", itemprop="description")
    description = description_tag.get_text(
        strip=True) if description_tag else ""

    def find_sibling_div_by_label_text(label_text: str) -> Optional[Tag]:
        label_tags = soup.find_all("div", class_="fi-label")
        for label_tag in label_tags:
            # Шукаємо текст мітки всередині label_tag (враховуючи вкладені теги)
            if re.search(rf"{label_text}\s*:", label_tag.get_text(strip=True), re.IGNORECASE):
                desc_tag = label_tag.find_next_sibling("div", class_="fi-desc")
                return desc_tag
        return None

    genres: List[str] = []
    genres_desc_tag = find_sibling_div_by_label_text("Жанр")
    if genres_desc_tag:
        links = genres_desc_tag.find_all("a")
        if links:
            genres = [a.get_text(strip=True) for a in links]
        else:
            text = genres_desc_tag.get_text(
                strip=True, separator=',').replace(' , ', ', ')
            if text:
                genres = [t.strip() for t in text.split(',') if t.strip()]

    director: List[str] = []
    director_desc_tag = find_sibling_div_by_label_text("Режисер")
    if director_desc_tag:
        links = director_desc_tag.find_all("a")
        if links:
            director = [a.get_text(strip=True) for a in links]
        else:
            text = director_desc_tag.get_text(
                strip=True, separator=',').replace(' , ', ', ')
            if text:
                director = [t.strip() for t in text.split(',') if t.strip()]

    runtime: Optional[str] = None
    runtime_desc_tag = find_sibling_div_by_label_text("Тривалість")
    if runtime_desc_tag:
        runtime = runtime_desc_tag.get_text(strip=True)

    meta_object = Series(
        id=item_id,
        type=type_,
        name=name,
        genres=genres,
        poster=full_poster_url,
        description=description,
        director=director,
        runtime=runtime,
        background=background_url,
        videos=videos,
    )

    return {"meta": meta_object}


async def get_videos(
    item_id: str, html_content: str, session: aiohttp.ClientSession, type_: str
) -> list[Videos]:
    videos = []
    soup = BeautifulSoup(html_content, "html.parser")

    detail_page_url = f"{settings.main_url}/{item_id}.html"

    if type_ == "movie":
        title_tag = soup.find("h1").find(
            "span", class_="solototle", itemprop="name")
        movie_title = title_tag.get_text(strip=True) if title_tag else "Фільм"
        poster_tag = soup.find(
            "div", class_="film-poster").find("img", itemprop="image")
        poster_src = poster_tag.get("src") if poster_tag else None
        thumbnail_url = f"{settings.main_url}{poster_src}" if poster_src and poster_src.startswith(
            "/") else poster_src
        released_tag = soup.find("meta", itemprop="dateCreated")
        released_date = released_tag.get("content") if released_tag else None
        videos.append(
            Videos(
                id=item_id, title=movie_title, thumbnail=thumbnail_url,
                released=released_date, season=None, episode=None,
            )
        )
    elif type_ == "series":
        playlist_div = soup.find("div", id="pre", class_="playlists-ajax")
        if not playlist_div or not playlist_div.has_attr("data-news_id"):
            print(f"Помилка: Не знайдено data-news_id для серіалу {item_id}")
            return []

        news_id = playlist_div["data-news_id"]

        playlist_url = f"{settings.main_url}/engine/ajax/playlists.php"
        current_timestamp = int(time.time())
        params = {
            "news_id": news_id,
            "xfield": "playlist",
            "time": current_timestamp
        }

        ajax_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "uk,en;q=0.9,en-GB;q=0.8,en-US;q=0.7,ru;q=0.6,de-DE;q=0.5,de;q=0.4",
            "Dnt": "1",
            "Referer": detail_page_url,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest"

        }
        # ------------------------------------------------------------------

        print(
            f"Завантаження плейлиста для news_id={news_id} з URL: {playlist_url} з параметрами: {params} та заголовками: {ajax_headers}")

        try:
            async with session.get(playlist_url, params=params, headers=ajax_headers) as playlist_response:
                print(
                    f"Статус відповіді плейлиста: {playlist_response.status}")
                playlist_response.raise_for_status()

                playlist_data_raw = await playlist_response.text()

                try:
                    outer_json = json.loads(playlist_data_raw)
                    if outer_json.get("success") and "response" in outer_json:

                        inner_html_str = outer_json["response"]
                        inner_soup = BeautifulSoup(
                            inner_html_str, "html.parser")
                        current_season_number = 1
                        main_title_tag = soup.find("h1").find(
                            "span", class_="solototle", itemprop="name")
                        main_title_text = main_title_tag.get_text() if main_title_tag else ""
                        season_match = re.search(
                            r"(\d+)\s+сезон", main_title_text, re.IGNORECASE)
                        if season_match:
                            current_season_number = int(season_match.group(1))
                        else:
                            print(
                                f"Попередження: Не вдалося визначити номер сезону з заголовку '{main_title_text}'. Використовується {current_season_number}.")
                        episode_list_items = inner_soup.select(
                            "div.playlists-videos div.playlists-items ul li")
                        if not episode_list_items:
                            print(
                                f"Не знайдено елементів серій у внутрішньому HTML для news_id={news_id}")
                        series_poster_tag = soup.find(
                            "div", class_="film-poster-serial").find("img", itemprop="image")
                        series_poster_src = series_poster_tag.get(
                            "src") if series_poster_tag else None
                        series_thumbnail_url = f"{settings.main_url}{series_poster_src}" if series_poster_src and series_poster_src.startswith(
                            "/") else series_poster_src
                        for item_li in episode_list_items:
                            episode_title = item_li.get_text(strip=True)
                            episode_num_match = re.search(
                                r'(\d+)', episode_title)
                            episode_number = int(episode_num_match.group(
                                1)) if episode_num_match else None
                            if episode_number is None:
                                print(
                                    f"Не вдалося визначити номер серії для '{episode_title}'")
                                continue
                            season_number = current_season_number
                            video_id = f"{item_id}/{season_number}:{episode_number}"
                            videos.append(Videos(id=video_id, title=episode_title, season=season_number,
                                          episode=episode_number, thumbnail=series_thumbnail_url, released=None))
                        print(
                            f"Знайдено {len(videos)} серій для сезону {season_number}.")
                        # -------------------------------------------------------------
                    else:
                        print(
                            f"Відповідь AJAX не містить {{\"success\":true, \"response\":\"...\"}} для news_id={news_id}")
                except json.JSONDecodeError:
                    print(
                        f"Не вдалося розпарсити JSON відповідь AJAX для {news_id}. Відповідь: {playlist_data_raw[:500]}...")
        except aiohttp.ClientError as e:
            # Обробка помилок
            if isinstance(e, aiohttp.client_exceptions.ClientResponseError) and e.status == 403:
                print(
                    f"Помилка 403 Forbidden при завантаженні плейлиста для {news_id}. Ймовірно, потрібні Cookies або обхід Cloudflare.")
            else:
                print(
                    f"Помилка HTTP при завантаженні плейлиста для {news_id}: {e}")
        except Exception as e:
            print(
                f"Неочікувана помилка при обробці плейлиста для {news_id}: {e}")

    videos.sort(key=lambda v: (v.season or 0, v.episode or 0))
    return videos


async def get_streams(type_: str, video_id: str, session: aiohttp.ClientSession) -> dict[str, List[Stream]]:
    streams = {"streams": []}
    player_page_url = None
    stream_name_prefix = "Stream"  # Назва стріму за замовчуванням
    final_stream_url = None  # Тут буде фінальне посилання .m3u8

    try:
        # --- Крок 1: Отримуємо URL сторінки плеєра ---
        item_id_parts = video_id.split('/')
        season_episode_info = None
        if type_ == "series" and ':' in item_id_parts[-1]:
            season_episode_info = item_id_parts[-1]
            item_id = "/".join(item_id_parts[:-1])
        else:
            item_id = video_id

        detail_page_url = f"{settings.main_url}/{item_id}.html"
        print(
            f"get_streams: Крок 1 -> Пошук URL сторінки плеєра для {type_} | video_id: {video_id}")

        if type_ == "movie":
            async with session.get(detail_page_url) as response:
                response.raise_for_status()
                html_content = await response.text()
                soup = BeautifulSoup(html_content, "html.parser")
                iframe = soup.select_one(".box.full-text.visible iframe#pre")
                if iframe and iframe.has_attr("src"):
                    player_page_url = iframe["src"]
                    # Визначення якості для назви стріму
                    quality_label = soup.find(
                        "div", class_="fi-label", string=re.compile(r"Якість:"))
                    quality = quality_label.find_next_sibling("div", class_="fi-desc").get_text(
                        strip=True) if quality_label and quality_label.find_next_sibling("div", class_="fi-desc") else "HD"
                    stream_name_prefix = f"Фільм ({quality})"
                else:
                    print(f"Не знайдено iframe для фільму {item_id}")

        elif type_ == "series":
            # Отримуємо плейлист, щоб знайти data-file
            async with session.get(detail_page_url) as page_response:
                if page_response.status != 200:
                    raise Exception(
                        f"Failed to load series page {detail_page_url}")
                html_content_main = await page_response.text()
                soup_main_page = BeautifulSoup(
                    html_content_main, "html.parser")
                playlist_div = soup_main_page.find(
                    "div", id="pre", class_="playlists-ajax")
                if not playlist_div or not playlist_div.has_attr("data-news_id"):
                    raise Exception(f"No news_id found for {item_id}")
                news_id = playlist_div["data-news_id"]

            playlist_url = f"{settings.main_url}/engine/ajax/playlists.php"
            params = {"news_id": news_id, "xfield": "playlist"}
            ajax_headers = {"Referer": detail_page_url,
                            "X-Requested-With": "XMLHttpRequest"}

            async with session.get(playlist_url, params=params, headers=ajax_headers) as playlist_response:
                playlist_response.raise_for_status()
                playlist_data_raw = await playlist_response.text()
                outer_json = json.loads(playlist_data_raw)

                if outer_json.get("success") and "response" in outer_json:
                    inner_html_str = outer_json["response"]
                    inner_soup = BeautifulSoup(inner_html_str, "html.parser")
                    req_season, req_episode = None, None
                    if season_episode_info:
                        try:
                            s_e_parts = season_episode_info.split(':')
                            req_season = int(s_e_parts[0])
                            req_episode = int(s_e_parts[1])
                        except:
                            pass

                    if req_season is not None and req_episode is not None:
                        episode_list_items = inner_soup.select(
                            "div.playlists-videos div.playlists-items ul li")
                        for item_li in episode_list_items:
                            episode_title = item_li.get_text(strip=True)
                            episode_num_match = re.search(
                                r'(\d+)', episode_title)
                            episode_number = int(episode_num_match.group(
                                1)) if episode_num_match else None
                            if episode_number == req_episode:
                                player_page_url_part = item_li.get("data-file")
                                voice = item_li.get("data-voice", "Default")
                                stream_name_prefix = f"{voice} - Серія {episode_number}"
                                if player_page_url_part:
                                    player_page_url = player_page_url_part
                                    break
                        if not player_page_url:
                            print(
                                f"Не знайдено data-file для серії {req_season}:{req_episode}")
                    else:
                        print(
                            f"Не вдалося розпарсити сезон/серію з {season_episode_info}")
                else:
                    print(
                        f"AJAX відповідь не містить success/response для {item_id}")

        # Переконуємося, що URL плеєра має протокол
        if player_page_url and player_page_url.startswith("//"):
            player_page_url = "https:" + player_page_url

        # --- Крок 2 & 3: Завантажуємо сторінку плеєра та витягуємо фінальний URL ---
        if player_page_url:
            print(
                f"get_streams: Крок 2 -> Завантаження сторінки плеєра: {player_page_url}")
            player_headers = {"Referer": detail_page_url}
            async with session.get(player_page_url, headers=player_headers) as player_response:
                if player_response.status == 200:
                    player_html = await player_response.text()

                    match = re.search(
                        r'file\s*:\s*"([^"]+\.m3u8[^"]*)"', player_html)
                    if not match:
                        match = re.search(r'file\s*:\s*"([^"]+)"', player_html)

                    if match:
                        final_stream_url = match.group(1)
                        print(
                            f"get_streams: Крок 3 -> Знайдено фінальний URL: {final_stream_url}")
                    else:
                        print(
                            f"Не вдалося знайти 'file:\"...\"' в HTML плеєра: {player_page_url}")
                else:
                    print(
                        f"Помилка завантаження сторінки плеєра {player_page_url}. Статус: {player_response.status}")
        else:
            print(f"URL сторінки плеєра не знайдено для {video_id}")

        # --- Крок 4: Додаємо фінальний стрім до результату ---
        if final_stream_url:
            streams["streams"].append(
                Stream(name=stream_name_prefix, url=final_stream_url)
            )
        else:
            print(f"Фінальний URL стріму не знайдено для {video_id}")

    except aiohttp.ClientError as e:
        print(
            f"Помилка HTTP при отриманні інформації про стрім для {video_id}: {e}")
    except Exception as e:
        print(
            f"Неочікувана помилка при отриманні інформації про стрім для {video_id}: {e}")

    return streams
