"""番茄小说 (fanqienovel.com) 实时榜单抓取与书籍/章节链接解析器."""
from __future__ import annotations

import re
from typing import Any, Dict, List
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class FanqieProvider:
    """从番茄小说官网 (fanqienovel.com) 实时获取热门小说榜单及解析指定书籍/章节链接."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    @staticmethod
    def clean_pua(text: str) -> str:
        """过滤番茄网页端自定义字体私有区字符 (U+E000..U+F8FF)，保证 100% 纯净中文文本."""
        if not text:
            return ""
        return re.sub(r"[\uE000-\uF8FF]", "", text)

    @classmethod
    def fetch_rank_books(cls, limit: int = 8) -> List[Dict[str, Any]]:
        """实时抓取番茄小说排行榜单及书籍简介与章节脉络."""
        resp = requests.get("https://fanqienovel.com/rank", headers=cls.HEADERS, timeout=12)
        resp.raise_for_status()
        book_ids = list(dict.fromkeys(re.findall(r"/page/(\d+)", resp.text)))[:limit]

        results: List[Dict[str, Any]] = []
        for bid in book_ids:
            try:
                info = cls.fetch_book_by_id(bid)
                if info and info.get("title"):
                    results.append(info)
            except Exception:
                continue
        return results

    @classmethod
    def fetch_book_by_url_or_id(cls, url_or_id: str) -> Dict[str, Any]:
        """根据用户输入的番茄小说链接、分享文本或 book_id 提取真实书籍内容."""
        text = url_or_id.strip()
        m_page = re.search(r"/page/(\d+)", text)
        if m_page:
            return cls.fetch_book_by_id(m_page.group(1))

        m_reader = re.search(r"/reader/(\d+)", text)
        if m_reader:
            return cls.fetch_chapter_by_id(m_reader.group(1))

        m_id = re.search(r"\b(\d{15,22})\b", text)
        if m_id:
            return cls.fetch_book_by_id(m_id.group(1))

        raise ValueError("未能从输入内容中识别出有效的番茄小说链接 (如 https://fanqienovel.com/page/xxx)")

    @classmethod
    def fetch_book_by_id(cls, book_id: str) -> Dict[str, Any]:
        """解析 https://fanqienovel.com/page/{book_id} 页面提取纯净书名、分类标签、核心剧情简介与前序章节大纲."""
        url = f"https://fanqienovel.com/page/{book_id}"
        resp = requests.get(url, headers=cls.HEADERS, timeout=10)
        resp.raise_for_status()
        if BeautifulSoup:
            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.find("h1")
            title = cls.clean_pua(h1.get_text(strip=True)) if h1 else ""

            author_el = soup.select_one(".author-name-text")
            author = cls.clean_pua(author_el.get_text(strip=True)) if author_el else "番茄作者"

            labels = [
                cls.clean_pua(el.get_text(strip=True))
                for el in soup.select(".info-label span")
                if cls.clean_pua(el.get_text(strip=True))
            ]
            genre = " · ".join(labels[:3]) if labels else "番茄热门爽文"

            desc_el = soup.select_one(".page-abstract-content")
            abstract = cls.clean_pua(desc_el.get_text("\n", strip=True)) if desc_el else ""

            chap_els = soup.select(".chapter-item a")
            chap_titles = [
                cls.clean_pua(el.get_text(strip=True))
                for el in chap_els[:6]
                if cls.clean_pua(el.get_text(strip=True))
            ]
            first_chap_title = chap_titles[0] if chap_titles else "第1章"
        else:
            m_title = re.search(r"<h1[^>]*>([^<]+)</h1>", resp.text)
            title = cls.clean_pua(m_title.group(1).strip()) if m_title else ""
            m_author = re.search(r'class="author-name-text"[^>]*>([^<]+)</span>', resp.text)
            author = cls.clean_pua(m_author.group(1).strip()) if m_author else "番茄作者"
            labels = [cls.clean_pua(x) for x in re.findall(r'class="info-label"[^>]*>.*?<span>([^<]+)</span>', resp.text)]
            genre = " · ".join(labels[:3]) if labels else "番茄热门爽文"
            m_desc = re.search(r'class="page-abstract-content"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
            abstract = cls.clean_pua(re.sub(r"<[^>]+>", "\n", m_desc.group(1)).strip()) if m_desc else ""
            chap_titles = [cls.clean_pua(x) for x in re.findall(r'class="chapter-item"[^>]*>.*?<a[^>]*>([^<]+)</a>', resp.text)[:6]]
            first_chap_title = chap_titles[0] if chap_titles else "第1章"

        combined_story = abstract
        if chap_titles:
            chap_outline = " -> ".join(chap_titles)
            combined_story = f"【作品核心剧情】\n{abstract}\n\n【开篇主线脉络】\n{chap_outline}"

        return {
            "book_id": book_id,
            "title": title,
            "author": author,
            "genre": genre,
            "abstract": abstract,
            "first_chapter_title": first_chap_title,
            "story_text": combined_story.strip(),
            "url": url,
        }

    @classmethod
    def fetch_chapter_by_id(cls, item_id: str) -> Dict[str, Any]:
        """抓取番茄小说章节阅读页并自动关联其所属书籍的完整纯净剧情简介."""
        url = f"https://fanqienovel.com/reader/{item_id}"
        resp = requests.get(url, headers=cls.HEADERS, timeout=10)
        resp.raise_for_status()
        if BeautifulSoup:
            soup = BeautifulSoup(resp.text, "html.parser")
            title_el = soup.select_one("h1.muye-reader-title, h1")
            chap_title = cls.clean_pua(title_el.get_text(strip=True)) if title_el else "第1章"

            book_link = soup.select_one('a[href*="/page/"]')
            if book_link:
                href = str(book_link.get("href", ""))
                m_bid = re.search(r"/page/(\d+)", href)
                if m_bid:
                    book_info = cls.fetch_book_by_id(m_bid.group(1))
                    book_info["first_chapter_title"] = chap_title
                    return book_info

            book_title = cls.clean_pua(book_link.get_text(strip=True)) if book_link else chap_title
            paragraphs = [
                cls.clean_pua(p.get_text(strip=True))
                for p in soup.select(".muye-reader-content p, article p")
                if cls.clean_pua(p.get_text(strip=True))
            ]
            content = "\n".join(paragraphs[:15])
        else:
            m_t = re.search(r'<h1[^>]*class="[^"]*muye-reader-title[^"]*"[^>]*>([^<]+)</h1>', resp.text)
            chap_title = cls.clean_pua(m_t.group(1).strip()) if m_t else "第1章"
            m_b = re.search(r'/page/(\d+)', resp.text)
            if m_b:
                book_info = cls.fetch_book_by_id(m_b.group(1))
                book_info["first_chapter_title"] = chap_title
                return book_info
            book_title = chap_title
            m_c = re.findall(r'<p[^>]*>([^<]+)</p>', resp.text)
            paragraphs = [cls.clean_pua(p.strip()) for p in m_c if cls.clean_pua(p.strip())]
            content = "\n".join(paragraphs[:15])

        return {
            "book_id": item_id,
            "title": book_title,
            "author": "番茄作者",
            "genre": "番茄连载小说",
            "abstract": content[:120],
            "first_chapter_title": chap_title,
            "story_text": content or chap_title,
            "url": url,
        }
