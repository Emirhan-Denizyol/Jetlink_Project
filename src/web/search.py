# src/web/search.py
from __future__ import annotations
from typing import List, Dict
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

def web_search(query: str, max_results: int = 6, region: str = "tr-tr", safesearch: str = "moderate") -> List[Dict]:
    """
    DuckDuckGo metin araması. ddgs 9.x için text(query, ...) kullanır.
    Dönüş: [{title, href, body}], body çoğu zaman kısa/boş olabilir.
    """
    out: List[Dict] = []
    with DDGS() as ddgs:
        for r in ddgs.text(
            query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
        ):
            out.append({
                "title": (r.get("title") or "").strip(),
                "href": (r.get("href") or r.get("url") or "").strip(),
                "body": (r.get("body") or r.get("description") or "").strip(),
            })
    return out

def _fetch_snippet(url: str, timeout: int = 6, max_chars: int = 360) -> str:
    """
    URL'den kısa bir özet çıkar: <meta name=description> ya da ilk paragraflar.
    Ağır kütüphaneler yok: requests + BeautifulSoup.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        if r.status_code >= 400 or not r.text:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")

        # 1) meta description
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            txt = md["content"].strip()

            if len(txt) >= 60:
                return (txt[:max_chars].rstrip() + "…") if len(txt) > max_chars else txt

        # 2) og:description
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            txt = og["content"].strip()
            return (txt[:max_chars].rstrip() + "…") if len(txt) > max_chars else txt

        # 3) ilk anlamlı <p> blokları
        paras = []
        for p in soup.find_all("p"):
            t = (p.get_text(" ", strip=True) or "").strip()
            if len(t) >= 50:
                paras.append(t)
            if len(paras) >= 2:
                break
        txt = " ".join(paras).strip()
        if txt:
            return (txt[:max_chars].rstrip() + "…") if len(txt) > max_chars else txt
    except Exception:
        return ""
    return ""

def enrich_results_with_snippets(results: List[Dict]) -> List[Dict]:
    """
    Body alanı boş/kısaysa, sayfadan kısa özet çekip doldur.
    """
    enriched: List[Dict] = []
    for r in results:
        title = r.get("title", "")
        href  = r.get("href", "") or r.get("url", "")
        body  = (r.get("body") or "").strip()

        if not body or len(body) < 60:
            snippet = _fetch_snippet(href)
            if snippet:
                body = snippet

        enriched.append({"title": title, "href": href, "body": body})
    return enriched

def format_web_context(results: List[Dict], max_items: int = 3, max_body_chars: int = 400) -> str:
    """
    LLM'e verilecek kaynaklı, kısa WEB CONTEXT.
    """
    lines = []
    for r in results[:max_items]:
        title = (r.get("title") or "").strip()
        href  = (r.get("href")  or "").strip()
        body  = (r.get("body")  or "").strip().replace("\n", " ")
        if len(body) > max_body_chars:
            body = body[:max_body_chars].rstrip() + "…"
        if title or body:
            lines.append(f"- {title}\n  {body}\n  Kaynak: {href}")
    return "\n".join(lines) if lines else "(none)"

if __name__ == "__main__":
    q = "İstanbul hava durumu"
    print(f"🔎 Test: {q}")
    raw = web_search(q)
    enr = enrich_results_with_snippets(raw)
    print(format_web_context(enr))
