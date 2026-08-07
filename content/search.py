"""Поиск картинок и клипов во внешних источниках."""
import os
import re
import random
import logging
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from config import YOUTUBE_API_KEY
from filters import MIN_DATE, check_date_in_content

logger = logging.getLogger(__name__)

def search_bing(query):
    """Поиск изображений через Bing Картинки"""
    if not query:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        encoded_query = quote(query)
        url = f"https://www.bing.com/images/search?q={encoded_query}&form=HDRSC3&first=1&count=35&safeSearch=moderate"
        response = requests.get(url, headers=headers, timeout=15)
        patterns = [
            r'"murl":"([^"]+)"',
            r'"mediaurl":"([^"]+)"',
            r'"contentUrl":"([^"]+)"',
            r'"url":"([^"]+)"',
        ]
        images = []
        for pattern in patterns:
            found = re.findall(pattern, response.text)
            images.extend(found)
        clean_images = []
        for img in images:
            img = img.replace('\\u0026', '&').replace('\\/', '/')
            if not any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                continue
            if any(x in img.lower() for x in ['gstatic', 'google', 'favicon', 'logo', 'bing', 'avatar']):
                continue
            clean_images.append(img)
        if clean_images:
            clean_images = list(dict.fromkeys(clean_images))
            return random.choice(clean_images)
        return None
    except Exception as e:
        logger.error(f"Ошибка Bing: {e}")
        return None

def search_google_direct(query):
    """Поиск изображений через Google Картинки"""
    if not query:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        encoded_query = quote(query)
        url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&safe=active&tbs=isz:l,itp:photo"
        response = requests.get(url, headers=headers, timeout=15)
        pattern = r'imgurl=([^&]+)'
        images = re.findall(pattern, response.text)
        pattern2 = r'"([^"]+\.jpg[^"]*)"'
        images.extend(re.findall(pattern2, response.text))
        clean_images = []
        for img in images:
            img = img.replace('\\u0026', '&')
            img = img.replace('\\/', '/')
            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                if not any(x in img.lower() for x in ['gstatic', 'google', 'favicon', 'logo']):
                    if not img.startswith('data:'):
                        clean_images.append(img)
        clean_images = list(dict.fromkeys(clean_images))
        if clean_images:
            return random.choice(clean_images)
        return None
    except Exception as e:
        logger.error(f"Ошибка Google Картинки: {e}")
        return None

def search_yandex(query):
    """Поиск изображений через Яндекс Картинки"""
    if not query:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        encoded_query = quote(query)
        url = f"https://yandex.ru/images/search?text={encoded_query}&rdrnd=1&rpt=imageview&noreask=1"
        response = requests.get(url, headers=headers, timeout=15)
        patterns = [
            r'"img_url":"([^"]+)"',
            r'"url":"([^"]+\.(jpg|jpeg|png|webp))"',
            r'<img[^>]+src="([^"]+\.(jpg|jpeg|png|webp))"',
        ]
        images = []
        for pattern in patterns:
            found = re.findall(pattern, response.text)
            for item in found:
                if isinstance(item, tuple):
                    item = item[0]
                if item and not any(x in item.lower() for x in ['logo', 'favicon', 'gif']):
                    images.append(item.replace('\\u0026', '&').replace('\\/', '/'))
        clean_images = []
        for img in images:
            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                if not any(x in img.lower() for x in ['gstatic', 'google', 'favicon', 'logo']):
                    if not img.startswith('data:'):
                        clean_images.append(img)
        clean_images = list(dict.fromkeys(clean_images))
        if clean_images:
            return random.choice(clean_images)
        return None
    except Exception as e:
        logger.error(f"Ошибка Яндекс Картинки: {e}")
        return None

def search_pexels(query):
    """Поиск изображений через Pexels API"""
    if not query:
        return None
    try:
        PEXELS_KEY = os.getenv("PEXELS_KEY")
        if not PEXELS_KEY:
            return None
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_KEY}
        params = {
            "query": query,
            "per_page": 30,
            "orientation": "portrait",
            "size": "large"
        }
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("photos"):
                photos = data["photos"]
                random.shuffle(photos)
                for photo in photos:
                    url = photo["src"]["large"]
                    if check_date_in_content("", url):
                        return url
        return None
    except Exception as e:
        logger.error(f"Ошибка Pexels: {e}")
        return None

def search_instagram(streamer_name: str, streamer_display: str) -> Optional[str]:
    """Поиск изображений через Instagram (через Google Картинки с site:instagram.com)"""
    try:
        queries = [
            f"{streamer_display} стрим",
            f"{streamer_display} стример",
            f"{streamer_display} фото",
            f"{streamer_display} лицо",
            f"@{streamer_name}",
        ]
        
        for query in queries[:3]:
            search_query = f"{query} site:instagram.com"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            encoded_query = quote(search_query)
            url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&safe=active"
            response = requests.get(url, headers=headers, timeout=15)
            
            pattern = r'imgurl=([^&]+)'
            images = re.findall(pattern, response.text)
            
            for img in images:
                img = img.replace('\\u0026', '&').replace('\\/', '/')
                if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if 'instagram.com' in img.lower() or 'cdninstagram.com' in img.lower():
                        if not any(x in img.lower() for x in ['gstatic', 'google', 'favicon', 'logo']):
                            if check_date_in_content("", img):
                                logger.info(f"✅ Найдено фото из Instagram для {streamer_display}")
                                return img
        
        return None
    except Exception as e:
        logger.error(f"Ошибка поиска в Instagram: {e}")
        return None

def search_streamer_screenshot(streamer_key: str, streamer_display: str) -> Optional[str]:
    """Поиск скринов стримера со стримов"""
    queries = [
        f"{streamer_display} на стриме скрин",
        f"{streamer_display} стрим лицо",
        f"{streamer_display} стример лицо",
        f"{streamer_display} на стриме фото",
    ]
    
    random.shuffle(queries)
    
    search_functions = [
        (search_bing, "Bing Картинки"),
        (search_google_direct, "Google Картинки"),
        (search_yandex, "Яндекс Картинки"),
        (search_instagram, "Instagram"),
    ]
    random.shuffle(search_functions)
    
    for query in queries[:3]:
        for search_func, source_name in search_functions:
            try:
                logger.info(f"Поиск скрина для {streamer_display} в {source_name}: {query}")
                photo = search_func(query)
                if photo:
                    if check_date_in_content("", photo):
                        logger.info(f"✅ Найден скрин для {streamer_display}")
                        return photo
            except Exception as e:
                logger.error(f"Ошибка поиска скрина в {source_name}: {e}")
                continue
    
    return None

def search_youtube_clip(streamer_name: str, streamer_display: str) -> Optional[str]:
    """Поиск клипа стримера на YouTube"""
    if not YOUTUBE_API_KEY:
        logger.warning("⚠️ YouTube API ключ не настроен")
        return None
    
    try:
        search_queries = [
            f"{streamer_display} клип стрим",
            f"{streamer_display} момент стрим",
            f"{streamer_display} на стриме",
            f"{streamer_display} стрим",
        ]
        
        meme_queries = {
            'Вудуш': [f"{streamer_display} перезагрузка", f"{streamer_display} ладно я пошёл"],
            'Праден': [f"{streamer_display} проиграл", f"{streamer_display} обиделся"],
            'Братишкин': [f"{streamer_display} лысина", f"{streamer_display} качалка"],
            'Сасавот': [f"{streamer_display} смех", f"{streamer_display} засмеялся"],
            'Алина Рин': [f"{streamer_display} орёт", f"{streamer_display} эмоции"],
            'Ласка': [f"{streamer_display} забил", f"{streamer_display} сейчас"],
            'Аравудус': [f"{streamer_display} тильт", f"{streamer_display} проблемы"],
            'Эвелон': [f"{streamer_display} краш", f"{streamer_display} устал"],
            'Бустер': [f"{streamer_display} накрутил", f"{streamer_display} зрители"],
        }
        
        if streamer_display in meme_queries:
            search_queries.extend(meme_queries[streamer_display])
        
        random.shuffle(search_queries)
        
        for query in search_queries[:5]:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "relevance",
                "maxResults": 10,
                "videoDuration": "short",
                "key": YOUTUBE_API_KEY,
                "relevanceLanguage": "ru",
            }
            
            logger.info(f"🔍 Поиск клипа для {streamer_display}: {query}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("items") and len(data["items"]) > 0:
                    for item in data["items"]:
                        video_id = item["id"]["videoId"]
                        title = item["snippet"]["title"]
                        channel_title = item["snippet"]["channelTitle"]
                        description = item["snippet"].get("description", "")
                        published_at = item["snippet"].get("publishedAt", "")
                        
                        if published_at:
                            try:
                                pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                                if pub_date < MIN_DATE:
                                    logger.info(f"⏭️ Пропускаем видео от {pub_date.strftime('%Y-%m-%d')} (старше 2026 года)")
                                    continue
                            except:
                                pass
                        
                        combined_text = f"{title} {description} {channel_title}".lower()
                        streamer_names = [streamer_display.lower(), streamer_name.lower()]
                        
                        if streamer_display == "Эвелон":
                            streamer_names.extend(["evelon", "эвелон"])
                        elif streamer_display == "Братишкин":
                            streamer_names.extend(["bratishkin", "братишкин", "вова братишкин"])
                        elif streamer_display == "Вудуш":
                            streamer_names.extend(["voodoo", "voodoosh"])
                        elif streamer_display == "Праден":
                            streamer_names.extend(["praden"])
                        elif streamer_display == "Сасавот":
                            streamer_names.extend(["sasavot"])
                        elif streamer_display == "Алина Рин":
                            streamer_names.extend(["alina rin", "алина рин"])
                        elif streamer_display == "Ласка":
                            streamer_names.extend(["lasqa"])
                        elif streamer_display == "Аравудус":
                            streamer_names.extend(["arrowwoods"])
                        elif streamer_display == "Бустер":
                            streamer_names.extend(["buster"])
                        
                        has_streamer_name = any(name in combined_text for name in streamer_names)
                        
                        exclude_words = ['самолет', 'авиа', 'flight', 'plane', 'avalon', 'airport', 
                                       'автомобиль', 'car', 'auto', 'машина', 'игра', 'game']
                        has_exclude = any(word in combined_text for word in exclude_words)
                        
                        if not has_streamer_name or has_exclude:
                            logger.info(f"⏭️ Пропускаем видео: {title[:50]}... (не связано со стримером)")
                            continue
                        
                        if "подкаст" in title.lower() or "podcast" in title.lower():
                            continue
                        
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        logger.info(f"✅ Найден клип для {streamer_display}: {title[:50]}...")
                        return video_url
            else:
                logger.error(f"❌ Ошибка YouTube API: {response.status_code}")
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска клипа: {e}")
        return None
