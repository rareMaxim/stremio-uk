from bs4 import BeautifulSoup
from app.schemas import Preview, Series, Stream, Videos
from .settings import settings

import aiohttp
import json
from .utils import extract_numbers
import re


async def get_session():
    async with aiohttp.ClientSession() as session:
        yield session


async def get_previews_metadata(response_data, type_) -> dict[str, list[Preview]]:
    previews_metadata = {"metas": []}
    soup = BeautifulSoup(response_data, "html.parser")
    for item in soup.find_all("article", class_="short"):
        previews_metadata["metas"].append(
            Preview(
                id=item.find("a", class_="short_title")["href"].split("/")[-1].split(".")[0],
                type=type_,
                name=item.find("a", class_="short_title").text,
                genres=[],
                poster=f"https://eneyida.tv{item.find('img')['data-src']}",
                description=item.find("div", class_="short_subtitle").text,
            )
        )

    return previews_metadata


async def get_series_metadata(
    id: str, response_text: str, videos: list[Videos], type_title: str
) -> dict[str, Series]:
    soup = BeautifulSoup(response_text, "html.parser")
    full_info = soup.find("ul", class_="full_info").find_all("li")
    return {
        "meta": Series(
            id=f"{id}",
            type=type_title,
            name=soup.find("div", class_="full_header-title").find("h1").text,
            poster=f'{settings.main_url}{soup.find("div", class_="full_content-poster").find("img")["src"]}',
            genres=[tag.text for tag in full_info[1].find_all("a")],
            description=soup.find("article", class_="full_content-desc").text,
            director=[],
            runtime="",
            background=f'{settings.main_url}{soup.find("div", class_="full_content-poster").find("img")["src"]}',
            videos=videos,
        )
    }


async def get_videos(
    id: str, response_text: str, session: aiohttp.ClientSession
) -> list[Videos]:
    videos = []

    soup = BeautifulSoup(response_text, "html.parser")
    async with session.get(soup.select_one(".tabs_b.visible iframe")["src"]) as response:
        if "/vid/" in soup.select_one(".tabs_b.visible iframe")["src"]:
            plr_soup = BeautifulSoup(await response.text(), "html.parser")
            videos.append(
                Videos(
                    id=f'{id}',
                    title=soup.find("div", class_="full_header-title").find("h1").text,
                    thumbnail=soup.select_one(".full_header__bg-img").get('style').split("(")[1][:-2],
                    released=None,
                    season=None,
                    episode=None,
                )
            )
        else:
            plr_soup = BeautifulSoup(await response.text(), "html.parser")
            script_tag = plr_soup.body.find("script")
            print(script_tag.text)
            # Regex to extract the `file` value
            file_match = re.search(r'file:\s*\'(\[.*?\])\'', script_tag.string, re.DOTALL)
            if not file_match:
                raise ValueError("File content not found in the script.")

            # Extracted file content as a JSON string
            file_content = file_match.group(1)
            print("FILE MATCH")
            print(file_content)
#             plr_json = json.loads(plr_soup.body.find("script", type="text/javascript").text.split("file: '")[1].split("',")[0])

            try:
                plr_json = json.loads(file_match.group(1))
            except json.JSONDecodeError as e:
                raise ValueError("Failed to parse JSON data from the file field.") from e

            seen_titles = set()
            for dub in plr_json:
                for season in dub["folder"]:
                    for episode in season["folder"]:
                        if episode["title"] not in seen_titles:
                            seen_titles.add(episode["title"])
                            videos.append(
                                Videos(
                                    id=f'{id}/{season["title"]}/{episode["title"]}',
                                    title=episode["title"],
                                    thumbnail=episode["poster"],
                                    released=None,
                                    season=extract_numbers(season["title"])[0],
                                    episode=extract_numbers(episode["title"])[0],
                                )
                            )
    return videos


async def get_streams(
    id: str, season_param: str, episode_param: str, session: aiohttp.ClientSession, response_text
) -> dict[str, list[Stream]]:
    streams = {"streams": []}

    soup = BeautifulSoup(response_text, "html.parser")
    async with session.get(soup.select_one(".tabs_b.visible iframe")["src"]) as response:

        plr_soup = BeautifulSoup(await response.text(), "html.parser")
        if "/vid/" in soup.select_one(".tabs_b.visible iframe")["src"]:
            script_tag = plr_soup.body.find("script")
            print(script_tag)
            if not script_tag:
                raise ValueError("Script tag with Playerjs initialization not found.")
            file_url_match = re.search(r'file:\s*"(.*?)"', script_tag.text)
            if not file_url_match:
                raise ValueError("File URL not found in the script.")

            plr_url = file_url_match.group(1)
            streams["streams"].append(
                Stream(
                    name="Фільм",
                    url=plr_url,
                )
            )
        else:
            script_tag = plr_soup.body.find("script")
            if not script_tag:
                raise ValueError("Script tag with Playerjs initialization not found.")
            file_match = re.search(r'file:\s*\'(\[.*?\])\'', script_tag.string, re.DOTALL)
            if not file_match:
                raise ValueError("File URL not found in the script.")

#             plr_json = file_match.group(1)
#             print(plr_json)

            plr_json = json.loads(file_match.group(1))
            for dub in plr_json:
                print(dub)
                for season in dub["folder"]:
                    if season["title"] == season_param:
                        for episode in season["folder"]:
                            if episode["title"] == episode_param:
                                streams["streams"].append(
                                    Stream(
                                        name=dub["title"],
                                        url=episode["file"],
                                    )
                                )



    return streams
