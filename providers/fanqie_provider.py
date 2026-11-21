"""番茄小说 (fanqienovel.com) 实时榜单抓取与书籍/章节链接解析器 (含 PUA 字体还原表)."""
from __future__ import annotations

import re
from typing import Any, Dict, List
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from core.net_safety import (
        MAX_TEXT_BYTES,
        safe_fetch_text,
        validate_fanqie_id,
        validate_safe_public_https_url,
    )
except ImportError:
    from omnidrama.core.net_safety import (
        MAX_TEXT_BYTES,
        safe_fetch_text,
        validate_fanqie_id,
        validate_safe_public_https_url,
    )

_FANQIE_ALLOWED_HOSTS = ("fanqienovel.com", "www.fanqienovel.com")


class FanqieProvider:
    """从番茄小说官网 (fanqienovel.com) 实时获取热门小说榜单及解析指定书籍/章节链接."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    # 番茄小说网页端自定义字体 PUA 映射表 (U+E3E8..U+E55B / 58344..58715, 共 372 个高频字)
    PUA_CODE_ST = 58344
    PUA_CODE_ED = 58715
    FANQIE_PUA_CHARSET = (
        "D在主特家军然表场4要只v和?6别还g现儿岁??此象月3出战工相o男首失世F都平文什VO将真T那当?会立些u是十张"
        "学气大爱两命全后东性通被1它乐接而感车山公了常以何可话先pi叫轻M士w着变尔快l个说少色里安花远7难师放t报认"
        "面道S?克地度I好机U民写把万同水新没书电吃像斯5为y白几日教看但第加候作上拉住有法r事应位利你声身国问马女他"
        "Y比父xAHNsX边美对所金活回意到z从j知又内因点Q三定8Rb正或夫向德听更?得告并本q过记L让打f人就者去原满"
        "体做经K走如孩cG给使物?最笑部?员等受k行一条果动光门头见往自解成处天能于名其发总母的死手入路进心来h时力多"
        "开己许d至由很界n小与Z想代么分生口再妈望次西风种带J?实情才这?E我神格长觉间年眼无不亲关结0友信下却重己老"
        "2音字m呢明之前高PB目太e9起稜她也W用方子英每理便西数期中C外样a海们任"
    )

    @classmethod
    def decode_pua(cls, text: str) -> str:
        """将番茄网页端自定义字体私有区字符 (U+E3E8..U+E55B) 精准还原为原始汉字."""
        if not text:
            return ""
        out: List[str] = []
        charset_len = len(cls.FANQIE_PUA_CHARSET)
        for ch in text:
            code = ord(ch)
            if cls.PUA_CODE_ST <= code <= cls.PUA_CODE_ED:
                idx = code - cls.PUA_CODE_ST
                if 0 <= idx < charset_len:
                    mapped = cls.FANQIE_PUA_CHARSET[idx]
                    if mapped != "?":
                        out.append(mapped)
                    continue
            if 0xE000 <= code <= 0xF8FF:
                continue
            out.append(ch)
        return "".join(out)

    @classmethod
    def clean_pua(cls, text: str) -> str:
        """兼容旧接口：解码还原番茄网页端 PUA 字体字符，保证 100% 完整通顺中文文本."""
        return cls.decode_pua(text)

    @classmethod
    def is_pua_corrupted(cls, raw_text: str) -> bool:
        """判断文本在解码 PUA 后是否仍然残缺成碎词或孤立标点."""
        if not raw_text:
            return True
        cleaned = cls.decode_pua(raw_text).strip()
        if not cleaned:
            return True
        if re.search(r"(?m)(?:[，,。！？]{2,}|^\s*[。，,！？\.]+\s*$)", cleaned):
            return True
        clauses = [c.strip() for c in re.split(r"[，,。！？!?\n]+", cleaned) if c.strip()]
        if len(clauses) >= 4:
            short_ratio = sum(1 for c in clauses if len(c) <= 3) / len(clauses)
            if short_ratio >= 0.45:
                return True
        return False

    @classmethod
    def build_clean_drama_script(cls, book_title: str, chap_title: str, abstract: str) -> str:
        """基于解码后的作品简介或章节正文组装分镜原文（严禁注入与原著无关的玄幻套话）."""
        clean_abs = cls.decode_pua(abstract).strip()
        if clean_abs:
            return f"【《{book_title}》· {chap_title}】\n{clean_abs}"
        return f"【《{book_title}》· {chap_title}】\n围绕《{book_title}》{chap_title}展开的核心剧情。"

    @classmethod
    def is_junk_reader_text(cls, text: str) -> bool:
        """识别番茄小说网页端的章末字数统计、更新时间、作者说明等非剧情废话."""
        t = (text or "").strip()
        if not t or len(t) < 2:
            return True
        if re.search(r"本章字数\s*[:：]|\b更新时间\s*[:：]|作者有话说|最新网址|加入书架|目录|下一[页章]|点击下载|请收藏", t):
            return True
        # 纯章节标题且携带字数时间戳: "第 01章 爱哭本章字数：2102字更新时间：2022-04-08"
        if re.match(r"^第\s*\d+\s*章.*(?:字数|时间)", t):
            return True
        return False

    @classmethod
    def clean_chapter_paragraph(cls, text: str) -> str:
        """剥离段落内夹杂的元数据标记."""
        t = cls.decode_pua(text or "").strip()
        t = re.sub(r"本章字数\s*[:：]\s*\d+\s*字?", "", t)
        t = re.sub(r"更新时间\s*[:：]\s*[\d\-:\s]+", "", t)
        t = re.sub(r"\s{2,}", " ", t).strip()
        return t

    @classmethod
    def fetch_chapter_content(cls, item_id: str, max_paragraphs: int = 20) -> Dict[str, Any]:
        """直接抓取并解码番茄小说单章正文 (https://fanqienovel.com/reader/{item_id})."""
        safe_item_id = validate_fanqie_id(item_id)
        url = f"https://fanqienovel.com/reader/{safe_item_id}"
        html_text = safe_fetch_text(
            url,
            max_bytes=MAX_TEXT_BYTES,
            timeout=10,
            headers=cls.HEADERS,
            allowed_hosts=_FANQIE_ALLOWED_HOSTS,
        )
        chap_title = "第1章"
        paragraphs: List[str] = []
        if BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            title_el = soup.select_one("h1.muye-reader-title, h1")
            if title_el:
                chap_title = cls.decode_pua(title_el.get_text(strip=True)) or chap_title
            for p in soup.select(".muye-reader-content p, article p"):
                decoded = cls.clean_chapter_paragraph(p.get_text(strip=True))
                if decoded and not cls.is_junk_reader_text(decoded):
                    paragraphs.append(decoded)
        else:
            m_t = re.search(r'<h1[^>]*class="[^"]*muye-reader-title[^"]*"[^>]*>([^<]+)</h1>', html_text)
            if m_t:
                chap_title = cls.decode_pua(m_t.group(1).strip()) or chap_title
            for raw_p in re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.DOTALL):
                clean_p = cls.clean_chapter_paragraph(re.sub(r"<[^>]+>", "", raw_p))
                if clean_p and not cls.is_junk_reader_text(clean_p):
                    paragraphs.append(clean_p)

        chap_title = cls.clean_chapter_paragraph(chap_title) or "第1章"
        content = "\n\n".join(paragraphs[:max_paragraphs]).strip()
        return {
            "chapter_id": safe_item_id,
            "title": chap_title,
            "content": content,
            "url": url,
        }

    @classmethod
    def fetch_rank_books(cls, limit: int = 8) -> List[Dict[str, Any]]:
        """实时抓取番茄小说排行榜单及书籍简介与章节脉络."""
        html_text = safe_fetch_text(
            "https://fanqienovel.com/rank",
            max_bytes=MAX_TEXT_BYTES,
            timeout=12,
            headers=cls.HEADERS,
            allowed_hosts=_FANQIE_ALLOWED_HOSTS,
        )
        book_ids = list(dict.fromkeys(re.findall(r"/page/(\d+)", html_text)))[:limit]

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
        """根据用户输入的番茄小说链接或纯数字 book_id 提取真实书籍内容."""
        text = (url_or_id or "").strip()
        if not text:
            raise ValueError("请输入番茄小说链接或作品 ID")

        # 若包含任意 URL 协议/链接，必须先通过番茄域名白名单 HTTPS 校验
        url_match = re.search(r"https?://[^\s]+", text, re.IGNORECASE)
        if url_match or "://" in text or text.lower().startswith(("http", "www.")):
            candidate_url = url_match.group(0) if url_match else text
            if candidate_url.lower().startswith("www."):
                candidate_url = f"https://{candidate_url}"
            safe_url = validate_safe_public_https_url(
                candidate_url,
                allowed_hosts=_FANQIE_ALLOWED_HOSTS,
            )
            m_page = re.search(r"/page/(\d+)", safe_url)
            if m_page:
                return cls.fetch_book_by_id(validate_fanqie_id(m_page.group(1)))
            m_reader = re.search(r"/reader/(\d+)", safe_url)
            if m_reader:
                return cls.fetch_chapter_by_id(validate_fanqie_id(m_reader.group(1)))
            raise ValueError("番茄链接缺少有效的 /page/{id} 或 /reader/{id}")

        # 纯 ID 路径：必须严格匹配 1-30 位纯数字
        safe_id = validate_fanqie_id(text)
        return cls.fetch_book_by_id(safe_id)

    @classmethod
    def fetch_book_by_id(cls, book_id: str) -> Dict[str, Any]:
        """解析 https://fanqienovel.com/page/{book_id} 页面提取纯净书名、分类标签、核心剧情简介与真实首章正文."""
        safe_book_id = validate_fanqie_id(book_id)
        url = f"https://fanqienovel.com/page/{safe_book_id}"
        html_text = safe_fetch_text(
            url,
            max_bytes=MAX_TEXT_BYTES,
            timeout=10,
            headers=cls.HEADERS,
            allowed_hosts=_FANQIE_ALLOWED_HOSTS,
        )
        chapters: List[Dict[str, Any]] = []
        if BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            h1 = soup.find("h1")
            title = cls.decode_pua(h1.get_text(strip=True)) if h1 else ""

            author_el = soup.select_one(".author-name-text")
            author = cls.decode_pua(author_el.get_text(strip=True)) if author_el else "番茄作者"

            labels = [
                cls.decode_pua(el.get_text(strip=True))
                for el in soup.select(".info-label span")
                if cls.decode_pua(el.get_text(strip=True))
            ]
            genre = " · ".join(labels[:3]) if labels else "番茄热门小说"

            desc_el = soup.select_one(".page-abstract-content")
            abstract = cls.decode_pua(desc_el.get_text("\n", strip=True)) if desc_el else ""

            chap_els = soup.select(".chapter-item a")
            for idx, el in enumerate(chap_els[:50]):
                ctitle = cls.decode_pua(el.get_text(strip=True))
                href = str(el.get("href", ""))
                m_cid = re.search(r"/reader/(\d+)", href)
                cid = m_cid.group(1) if m_cid else ""
                if ctitle:
                    chapters.append({"chapter_id": cid, "title": ctitle, "order": idx + 1})
            first_chap_title = chapters[0]["title"] if chapters else "第1章"
        else:
            m_title = re.search(r"<h1[^>]*>([^<]+)</h1>", html_text)
            title = cls.decode_pua(m_title.group(1).strip()) if m_title else ""
            m_author = re.search(r'class="author-name-text"[^>]*>([^<]+)</span>', html_text)
            author = cls.decode_pua(m_author.group(1).strip()) if m_author else "番茄作者"
            labels = [cls.decode_pua(x) for x in re.findall(r'class="info-label"[^>]*>.*?<span>([^<]+)</span>', html_text)]
            genre = " · ".join(labels[:3]) if labels else "番茄热门小说"
            m_desc = re.search(r'class="page-abstract-content"[^>]*>(.*?)</div>', html_text, re.DOTALL)
            abstract = cls.decode_pua(re.sub(r"<[^>]+>", "\n", m_desc.group(1)).strip()) if m_desc else ""
            for idx, (cid, ctitle_raw) in enumerate(
                re.findall(r'<a[^>]*href="/reader/(\d+)"[^>]*>(.*?)</a>', html_text, re.DOTALL)[:50]
            ):
                ctitle = cls.decode_pua(re.sub(r"<[^>]+>", "", ctitle_raw).strip())
                if ctitle:
                    chapters.append({"chapter_id": cid, "title": ctitle, "order": idx + 1})
            first_chap_title = chapters[0]["title"] if chapters else "第1章"

        first_chap_content = ""
        if chapters and chapters[0].get("chapter_id"):
            try:
                chap_data = cls.fetch_chapter_content(chapters[0]["chapter_id"], max_paragraphs=16)
                first_chap_content = chap_data.get("content", "").strip()
            except Exception:
                first_chap_content = ""

        if first_chap_content:
            combined_story = f"【《{title or '番茄小说'}》· {first_chap_title}】\n{first_chap_content}"
        else:
            combined_story = cls.build_clean_drama_script(title or "番茄热门短剧", first_chap_title, abstract)

        return {
            "book_id": safe_book_id,
            "title": title,
            "author": author,
            "genre": genre,
            "abstract": abstract,
            "first_chapter_title": first_chap_title,
            "chapters": chapters,
            "story_text": combined_story.strip(),
            "url": url,
        }

    @classmethod
    def fetch_chapter_by_id(cls, item_id: str) -> Dict[str, Any]:
        """抓取番茄小说章节阅读页并解码还原真实章节正文，同时关联所属书籍元数据."""
        safe_item_id = validate_fanqie_id(item_id)
        url = f"https://fanqienovel.com/reader/{safe_item_id}"
        html_text = safe_fetch_text(
            url,
            max_bytes=MAX_TEXT_BYTES,
            timeout=10,
            headers=cls.HEADERS,
            allowed_hosts=_FANQIE_ALLOWED_HOSTS,
        )
        chap_title = "第1章"
        book_title = ""
        book_id = ""
        paragraphs: List[str] = []

        if BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            title_el = soup.select_one("h1.muye-reader-title, h1")
            if title_el:
                chap_title = cls.decode_pua(title_el.get_text(strip=True)) or chap_title
            book_link = soup.select_one('a[href*="/page/"]')
            if book_link:
                book_title = cls.decode_pua(book_link.get_text(strip=True))
                href = str(book_link.get("href", ""))
                m_bid = re.search(r"/page/(\d+)", href)
                if m_bid:
                    book_id = m_bid.group(1)
            for p in soup.select(".muye-reader-content p, article p"):
                decoded = cls.decode_pua(p.get_text(strip=True)).strip()
                if decoded:
                    paragraphs.append(decoded)
        else:
            m_t = re.search(r'<h1[^>]*class="[^"]*muye-reader-title[^"]*"[^>]*>([^<]+)</h1>', html_text)
            if m_t:
                chap_title = cls.decode_pua(m_t.group(1).strip()) or chap_title
            m_b = re.search(r'/page/(\d+)', html_text)
            if m_b:
                book_id = m_b.group(1)
            for raw_p in re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.DOTALL):
                clean_p = cls.decode_pua(re.sub(r"<[^>]+>", "", raw_p)).strip()
                if clean_p:
                    paragraphs.append(clean_p)

        chap_content = "\n".join(paragraphs[:18]).strip()

        if book_id:
            try:
                book_info = cls.fetch_book_by_id(book_id)
                book_info["first_chapter_title"] = chap_title
                if chap_content:
                    book_info["story_text"] = f"【《{book_info.get('title') or book_title or '番茄短剧'}》· {chap_title}】\n{chap_content}"
                return book_info
            except Exception:
                pass

        resolved_title = book_title or chap_title
        return {
            "book_id": book_id or item_id,
            "title": resolved_title,
            "author": "番茄作者",
            "genre": "番茄连载小说",
            "abstract": chap_content[:160] if chap_content else chap_title,
            "first_chapter_title": chap_title,
            "story_text": f"【《{resolved_title}》· {chap_title}】\n{chap_content}" if chap_content else chap_title,
            "url": url,
        }
