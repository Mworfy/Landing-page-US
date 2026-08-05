#!/usr/bin/env python3
"""
Populate static HTML pages from Webflow CMS CSV exports.
Run from repo root: python3 scripts/build_cms.py
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
CMS_DIR = ROOT / "CMS"
ASSETS_DIR = ROOT / "assets" / "cms"
MANIFEST_PATH = ROOT / "scripts" / "assets-to-download.json"

CDN_RE = re.compile(
    r"https://(?:cdn\.prod\.website-files\.com|uploads-ssl\.webflow\.com)/[^\s\"'<>]+"
)

# Global registry of CDN URLs → local paths (relative to repo root)
ASSET_MAP: dict[str, str] = {}
PENDING_DOWNLOADS: dict[str, dict] = {}


def load_csv(name_part: str) -> list[dict]:
    matches = list(CMS_DIR.glob(f"*{name_part}*.csv"))
    if not matches:
        raise FileNotFoundError(f"No CSV matching *{name_part}* in CMS/")
    with matches[0].open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(s: str) -> datetime:
    if not s:
        return datetime.min
    try:
        return datetime.strptime(s.split(" GMT")[0], "%a %b %d %Y %H:%M:%S")
    except ValueError:
        return datetime.min


def format_date(s: str) -> str:
    dt = parse_date(s)
    if dt == datetime.min:
        return ""
    return dt.strftime("%B %d, %Y")


def cdn_basename(url: str) -> str:
    path = unquote(urlparse(url.strip()).path)
    name = path.split("/")[-1]
    # Sanitize for filesystem
    name = re.sub(r'[<>:"|?*]', "_", name)
    return name or "asset.bin"


def register_asset(url: str, category: str = "cms") -> str:
    """Return local path (repo-relative) for a CDN URL."""
    url = url.strip()
    if not url:
        return ""
    if not CDN_RE.match(url):
        return url  # already local or external

    if url in ASSET_MAP:
        return ASSET_MAP[url]

    filename = cdn_basename(url)
    local = f"assets/{category}/{filename}"
    ASSET_MAP[url] = local

    dest = ROOT / local
    PENDING_DOWNLOADS[url] = {
        "url": url,
        "local_path": local,
        "filename": filename,
        "category": category,
        "exists_locally": dest.exists(),
    }
    return local


def local_path_for_page(page_path: Path, asset_rel: str) -> str:
    """Convert repo-relative asset path to path relative to an HTML page."""
    if not asset_rel or asset_rel.startswith(("http://", "https://", "//")):
        return asset_rel
    page_dir = page_path.parent
    asset_abs = (ROOT / asset_rel).resolve()
    return os_relpath(asset_abs, page_dir.resolve())


def os_relpath(target: Path, start: Path) -> str:
    try:
        rel = target.relative_to(start)
        return rel.as_posix() if str(rel) != "." else target.name
    except ValueError:
        return "/".join([".."] * len(start.parts)) + "/" + target.as_posix()


def rewrite_cdn_in_html(html: str, page_path: Path) -> str:
    def repl(match: re.Match) -> str:
        url = match.group(0)
        local = register_asset(url)
        return local_path_for_page(page_path, local)

    return CDN_RE.sub(repl, html)


def strip_wdyn(class_str: str) -> str:
    return " ".join(c for c in class_str.split() if c != "w-dyn-bind-empty")


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def faq_item_html(question: str, answer: str, h4_class: str, lottie_wid: str, docs_prefix: str) -> str:
    q = escape(question)
    # Answer is rich HTML from CMS — rewrite CDN inside
    a = answer
    for url in CDN_RE.findall(a):
        local = register_asset(url)
        a = a.replace(url, local)  # replaced with repo-relative; fixed per-page later

    return f"""                <div itemtype="https://schema.org/Question" itemscope="itemscope" itemprop="mainEntity" role="listitem" class="faq_item w-dyn-item">
                  <div class="faq_title">
                    <h4 itemprop="name" class="{h4_class}">{q}</h4>
                    <div data-is-ix2-target="1" class="faq_lottie" data-w-id="{lottie_wid}" data-animation-type="lottie" data-src="{docs_prefix}documents/lottieflow-dropdown-03-52565e-easey.json" data-loop="0" data-direction="1" data-autoplay="0" data-renderer="svg" data-default-duration="2" data-duration="0" data-loading="eager" data-ix2-initial-state="50"></div>
                  </div>
                  <div class="faq_body">
                    <div itemtype="https://schema.org/Answer" itemscope="itemscope" itemprop="acceptedAnswer" class="faq_pad">
                      <div itemprop="text" class="r-text w-richtext">{a}</div>
                    </div>
                  </div>
                </div>"""


FAQ_H3_MAP = {
    "About AIESEC": "About AIESEC",
    "General Donation Questions": "General Donation Questions",
    "Corporate Partners": "Corporate Partners",
    "Have another question?": "Have another question?",
    "Employer Giving FAQs": "Employer Giving",
    "Payroll Giving FAQs": "Payroll Giving",
}


def populate_faq_sections(html: str, faqs: list[dict], docs_prefix: str) -> str:
    lottie_ids = [
        "c2b357af-e022-63d0-5a82-1f7b7e4b9ced",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9cfd",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d0d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d1d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d2d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d3d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d4d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d5d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d6d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d7d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d8d",
        "c2b357af-e022-63d0-5a82-1f7b7e4b9d9d",
    ]
    faq_by_sub: dict[str, list[dict]] = {}
    for row in faqs:
        sub = row.get("Which Sub Section?", "").strip()
        faq_by_sub.setdefault(sub, []).append(row)
    for sub in faq_by_sub:
        faq_by_sub[sub].sort(key=lambda r: int(r.get("Order") or 999))

    def replace_section(match: re.Match) -> str:
        h3_text = match.group(1).strip()
        subsection = FAQ_H3_MAP.get(h3_text)
        if not subsection:
            return match.group(0)
        items = faq_by_sub.get(subsection, [])
        if not items:
            return match.group(0)
        h4_class = "h4 test" if "test" in match.group(0) else "h4"
        built = []
        for i, item in enumerate(items):
            wid = lottie_ids[i % len(lottie_ids)]
            built.append(
                faq_item_html(
                    item["Question"],
                    item["Answer"],
                    h4_class,
                    wid,
                    docs_prefix,
                )
            )
        items_html = "\n".join(built)
        return (
            f'<h3 class="h3">{match.group(1)}</h3>\n'
            f'            <div class="faq_wrap w-dyn-list">\n'
            f'              <div itemtype="https://schema.org/FAQPage" role="list" class="faq_list w-dyn-items">\n'
            f"{items_html}\n"
            f"              </div>\n"
            f'              <div class="w-dyn-empty" style="display:none">\n'
            f"                <div>No items found.</div>\n"
            f"              </div>\n"
            f"            </div>"
        )

    pattern = (
        r'<h3 class="h3">([^<]+)</h3>\s*'
        r'<div class="faq_wrap w-dyn-list">.*?</div>\s*</div>'
    )
    return re.sub(pattern, replace_section, html, flags=re.DOTALL)


def populate_scholarship_faq(html: str, faqs: list[dict]) -> str:
    items = [f for f in faqs if f.get("Which Sub Section?", "").strip() == "Get a scholarship"]
    items.sort(key=lambda r: int(r.get("Order") or 999))
    if not items:
        return html
    built = []
    lottie_ids = ["c2b357af-e022-63d0-5a82-1f7b7e4b9ced"] * 20
    for i, item in enumerate(items):
        built.append(
            faq_item_html(item["Question"], item["Answer"], "h4 test", lottie_ids[i], "../")
        )
    items_html = "\n".join(built)
    pattern = (
        r'(<div class="faq_wrap w-dyn-list">\s*'
        r'<div itemtype="https://schema.org/FAQPage" role="list" class="faq_list w-dyn-items">)'
        r".*?"
        r"(</div>\s*<div class=\"w-dyn-empty\">)"
    )
    replacement = rf"\1\n{items_html}\n              \2"
    return re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)


def populate_dyn_wrapper(html: str, wrapper_class: str, items_html: str, occurrence: int = 0) -> str:
    pattern = (
        rf'(<div class="{re.escape(wrapper_class)} w-dyn-list">\s*'
        rf'<div role="list" class="[^"]*w-dyn-items">)'
        rf".*?"
        rf'(</div>\s*<div class="w-dyn-empty">)'
    )
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        if count == occurrence:
            count += 1
            empty = ' style="display:none"' if items_html else ""
            return (
                f"{m.group(1)}{items_html}{m.group(2).replace('class=\"w-dyn-empty\"', f'class=\"w-dyn-empty\"{empty}')}"
            )
        count += 1
        return m.group(0)

    return re.sub(pattern, repl, html, flags=re.DOTALL)


def client_item(name: str, logo_url: str, prefix: str = "") -> str:
    src = register_asset(logo_url) if logo_url else ""
    src_attr = f'{prefix}{src}' if src else ""
    alt = escape(name)
    return (
        f'            <div role="listitem" class="client-logo-holder w-dyn-item">'
        f'<img src="{src_attr}" loading="lazy" alt="{alt}" class="b2b-logos"></div>'
    )


def lc_item(name: str, logo_url: str, website: str, prefix: str = "") -> str:
    src = register_asset(logo_url) if logo_url else ""
    src_attr = f"{prefix}{src}" if src else ""
    href = website.strip() if website else "#"
    alt = escape(name)
    return (
        f'              <div role="listitem" class="uni-cms-item w-dyn-item">\n'
        f'                <a href="{href}" target="_blank" class="uni-link w-inline-block">'
        f'<img src="{src_attr}" loading="lazy" alt="{alt}" class="b2b-logos uni"></a>\n'
        f"              </div>"
    )


def board_item(row: str, prefix: str = "") -> str:
    # row is dict - fix signature
    pass


def build_board_item(row: dict, prefix: str = "") -> str:
    photo = register_asset(row.get("Board Member Profile Picture", ""))
    name = escape(row["Name"])
    title = escape(row.get("Board Title") or "")
    job = escape(row.get("Job Title") or "")
    linkedin = row.get("Linkedin Profile", "#") or "#"
    src = f"{prefix}{photo}" if photo else ""
    return f"""            <div role="listitem" class="team-item-copy w-dyn-item"><img height="Auto" alt="{name}" width="Auto" src="{src}" loading="lazy" class="team-photo">
              <h3 class="h3-no-bot-space">{name}</h3>
              <h6 class="h4-25em-25ch">{title}</h6>
              <p class="p-15ch">{job}</p>
              <a aria-label="Linkedin Profile" href="{linkedin}" target="_blank" class="social-link linkedin w-inline-block"></a>
            </div>"""


def home_testimonial_item(row: dict, prefix: str = "") -> str:
    text = escape(row.get("Testimonial Text") or "")
    name = escape(row["Name"])
    loc = escape(row.get("Location / Position") or "")
    img_url = row.get("Testimonial Image", "")
    img_style = ""
    inner_img = ""
    if img_url:
        src = register_asset(img_url)
        img_style = f' style="background-image:url({prefix}{src})"'
    return f"""          <div role="listitem" class="testimonial-item w-dyn-item">
            <p class="testimonial-text">{text}</p>
            <div class="testimonial-img"{img_style}>{inner_img}</div>
            <div class="testimonial-title-stuff">
              <h3 class="h3-no-bot-space">{name}</h3>
              <div>{loc}</div>
            </div>
          </div>"""


def featured_testimonial_item(row: dict, prefix: str = "") -> str:
    text = escape(row.get("Testimonial Text") or "")
    name = escape(row["Name"])
    loc = escape(row.get("Location / Position") or "")
    img_url = row.get("Testimonial Image", "")
    src = register_asset(img_url) if img_url else ""
    src_attr = f"{prefix}{src}" if src else ""
    return f"""            <div role="listitem" class="testimonial-featured w-dyn-item">
              <div class="testimonial-img-ft"><img src="{src_attr}" loading="lazy" alt="{name}" class="image-testimonial-ft"></div>
              <div class="testimonial-text-hold-ft">
                <div class="product-logo-abroad-link w-inline-block">
                  <h3>{name}</h3>
                </div>
                <p class="testimonial-location-ft">{loc}</p>
                <p>{text}</p>
              </div>
            </div>"""


def list_testimonial_item(row: dict, prefix: str = "") -> str:
    return featured_testimonial_item(row, prefix).replace("testimonial-featured", "testimonial-item").replace(
        "testimonial-img-ft", "testimonial-img"
    ).replace("testimonial-text-hold-ft", "testimonial-title-stuff")


def blog_preview_item(post: dict, authors: dict, prefix: str = "", detail_prefix: str = "blog/") -> str:
    slug = post["Slug"]
    img = register_asset(post.get("Thumbnail image") or post.get("Main Image", ""))
    author_slug = post.get("Author", "")
    author_name = authors.get(author_slug, {}).get("Name", author_slug.replace("-", " ").title())
    href = f"{detail_prefix}{slug}.html"
    return f"""            <div role="listitem" class="blog-preview-item w-dyn-item">
              <a aria-label="Blog Article Link" href="{href}" class="blog-image-holder w-inline-block"><img src="{prefix}{img}" loading="lazy" alt="{escape(post['Name'])}" class="image-go-abroad"></a>
              <a href="{href}" class="product-logo-abroad-link w-inline-block">
                <h3 class="line-clamp-blog-title">{escape(post['Name'])}</h3>
              </a>
              <p class="line-clamp-blog-preview">{escape(post.get('Post Summary') or '')}</p>
              <div class="horizontal-div-1em">
                <a href="{href}" class="blog-mins-read-preview w-inline-block">
                  <div class="mins-number">{escape(post.get('Mins read') or '')}</div>
                  <div>min. read</div>
                </a>
                <div class="blog-mins-read-preview">
                  <div class="blog-written">Written by </div>
                  <a href="#" class="mins-number">{escape(author_name)}</a>
                </div>
              </div>
            </div>"""


def blog_hero_item(post: dict, prefix: str = "", detail_prefix: str = "blog/") -> str:
    slug = post["Slug"]
    img = register_asset(post.get("Main Image") or post.get("Thumbnail image", ""))
    href = f"{detail_prefix}{slug}.html"
    return f"""          <div role="listitem" class="w-dyn-item">
            <a aria-label="Blog Article Link" href="{href}" class="blog-main-article-image-wrap w-inline-block"><img src="{prefix}{img}" loading="eager" alt="{escape(post['Name'])}" class="image_full"></a>
            <div class="blog-main-article-text-wrap">
              <a href="{href}" class="link-block-arrow blog-h1 w-inline-block">
                <h1 class="h1-blog-hub">{escape(post['Name'])}</h1>
              </a>
              <div class="hero-blog-summary-wrap">
                <p class="p-1rem">{escape(post.get('Post Summary') or '')}</p>
                <a href="{href}" class="link-block-arrow top-1em w-inline-block">
                  <div>Read more</div><img src="{prefix}images/Arrow-right.svg" loading="lazy" alt="" class="arrow-link">
                  <div class="line arrow"></div>
                </a>
              </div>
            </div>
          </div>"""


def build_blog_detail(template: str, post: dict, authors: dict, all_posts: list[dict]) -> str:
    slug = post["Slug"]
    author_slug = post.get("Author", "")
    author = authors.get(author_slug, {})
    author_name = author.get("Name", author_slug.replace("-", " ").title())
    author_img = register_asset(author.get("Picture", ""))
    main_img = register_asset(post.get("Main Image", ""))

    body = post.get("Post Body") or ""
    for url in CDN_RE.findall(body):
        local = register_asset(url)
        body = body.replace(url, f"../{local}")

    html = template
    html = html.replace("<title>| AIESEC US Blog</title>", f"<title>{escape(post['Name'])} | AIESEC US Blog</title>")
    html = re.sub(r'<meta content="" name="description">', f'<meta content="{escape(post.get("Post Summary") or "")}" name="description">', html)
    html = re.sub(r'content="- AIESEC US Blog" property="og:title"', f'content="{escape(post["Name"])} - AIESEC US Blog" property="og:title"', html)
    html = re.sub(r'<link href="https://www\.aiesecus\.org/detail_blog" rel="canonical">',
                  f'<link href="https://www.aiesecus.org/blog/{slug}" rel="canonical">', html)

    html = re.sub(
        r'<div class="mins-number w-dyn-bind-empty"></div>\s*<div>min\. read</div>',
        f'<div class="mins-number">{escape(post.get("Mins read") or "")}</div>\n          <div>min. read</div>',
        html,
        count=1,
    )
    html = re.sub(
        r'<h1 class="h1-white-blog w-dyn-bind-empty"></h1>',
        f'<h1 class="h1-white-blog">{escape(post["Name"])}</h1>',
        html,
    )
    html = re.sub(
        r'<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="" loading="lazy" alt="" class="blog_author-img w-dyn-bind-empty">',
        f'<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="../{author_img}" loading="lazy" alt="{escape(author_name)}" class="blog_author-img">',
        html,
    )
    html = re.sub(
        r'(<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="../[^"]*" loading="lazy" alt="[^"]*" class="blog_author-img">\s*<div class="flex-vertical-stretch auto">\s*)<div class="mins-number w-dyn-bind-empty"></div>',
        rf'\1<div class="mins-number">{escape(author_name)}</div>',
        html,
    )
    date_str = format_date(post.get("Date of the Blog", ""))
    html = re.sub(
        r'<div class="date-blog w-dyn-bind-empty"></div>',
        f'<div class="date-blog">{date_str}</div>',
        html,
    )
    html = re.sub(
        r'<article class="r-text-blog w-dyn-bind-empty w-richtext"></article>',
        f'<article class="r-text-blog w-richtext">{body}</article>',
        html,
    )

    others = [p for p in all_posts if p["Slug"] != slug][:3]
    related = "\n".join(blog_preview_item(p, authors, "../", "blog/") for p in others)
    html = populate_dyn_wrapper(html, "blog-preview-wrap", "\n" + related + "\n          ")

    return rewrite_cdn_in_html(html, ROOT / "blog" / f"{slug}.html")


def build_news_detail(template: str, post: dict, authors: dict, all_posts: list[dict]) -> str:
    slug = post["Slug"]
    author_slug = post.get("Author", "")
    author = authors.get(author_slug, {})
    author_name = author.get("Name", author_slug.replace("-", " ").title())
    author_img = register_asset(author.get("Picture", ""))

    body = post.get("Post Body") or ""
    for url in CDN_RE.findall(body):
        local = register_asset(url)
        body = body.replace(url, f"../{local}")

    html = template
    html = html.replace("<title>| AIESEC US News</title>", f"<title>{escape(post['Name'])} | AIESEC US News</title>")
    html = re.sub(r'<link href="https://www\.aiesecus\.org/detail_news" rel="canonical">',
                  f'<link href="https://www.aiesecus.org/news/{slug}" rel="canonical">', html)
    html = re.sub(
        r'<h1 class="h1-white-blog w-dyn-bind-empty"></h1>',
        f'<h1 class="h1-white-blog">{escape(post["Name"])}</h1>',
        html,
    )
    html = re.sub(
        r'<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="" loading="lazy" alt="" class="blog_author-img w-dyn-bind-empty">',
        f'<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="../{author_img}" loading="lazy" alt="{escape(author_name)}" class="blog_author-img">',
        html,
    )
    html = re.sub(
        r'(<a href="#" class="blog-mins-read-preview author w-inline-block"><img src="../[^"]*" loading="lazy" alt="[^"]*" class="blog_author-img">\s*<div class="flex-vertical-stretch auto">\s*)<div class="mins-number w-dyn-bind-empty"></div>',
        rf'\1<div class="mins-number">{escape(author_name)}</div>',
        html,
    )
    date_str = format_date(post.get("Date of the News", ""))
    html = re.sub(
        r'<div class="date-blog w-dyn-bind-empty"></div>',
        f'<div class="date-blog">{date_str}</div>',
        html,
    )
    html = re.sub(
        r'<article class="r-text-blog w-dyn-bind-empty w-richtext"></article>',
        f'<article class="r-text-blog w-richtext">{body}</article>',
        html,
    )
    others = [p for p in all_posts if p["Slug"] != slug][:3]
    related = "\n".join(blog_preview_item(p, authors, "../", "news/") for p in others)
    html = populate_dyn_wrapper(html, "blog-preview-wrap", "\n" + related + "\n          ")
    return rewrite_cdn_in_html(html, ROOT / "news" / f"{slug}.html")


def fix_page_asset_paths(html: str, page_path: Path) -> str:
    def repl_attr(m: re.Match) -> str:
        attr, path = m.group(1), m.group(2)
        if path.startswith(("http", "//", "data:", "#")):
            return m.group(0)
        if path.startswith("assets/"):
            rel = local_path_for_page(page_path, path)
            return f'{attr}="{rel}"'
        return m.group(0)

    html = re.sub(r'(src|href)="(assets/cms/[^"]+)"', repl_attr, html)
    html = re.sub(
        r"url\((assets/cms/[^)]+)\)",
        lambda m: f"url({local_path_for_page(page_path, m.group(1))})",
        html,
    )
    return html


def write_page(rel_path: str, html: str) -> None:
    page_path = ROOT / rel_path
    html = fix_page_asset_paths(html, page_path)
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(html, encoding="utf-8")
    print(f"  wrote {rel_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading CMS data...")
    authors_list = load_csv("Authors")
    blogs = load_csv("Blog Posts")
    news = load_csv("News")
    board = load_csv("Board of Directors")
    clients = load_csv("Clients")
    faqs = load_csv("FAQs")
    lcs = load_csv("LCs")
    testimonials = load_csv("Testimonials")

    authors = {a["Slug"]: a for a in authors_list}

    blogs.sort(key=lambda b: parse_date(b.get("Date of the Blog", "")), reverse=True)
    news.sort(key=lambda n: parse_date(n.get("Date of the News", "")), reverse=True)
    board.sort(key=lambda b: int(b.get("Priority") or 999))

    print("\n=== Populating listing pages ===")

    # --- index.html ---
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    client_html = "\n".join(client_item(c["Name"], c.get("Client Logo", "")) for c in clients)
    html = populate_dyn_wrapper(html, "client-logo-wrapper", "\n" + client_html + "\n          ")

    lc_half = (len(lcs) + 1) // 2
    lc_row1 = "\n".join(lc_item(lc["Name"], lc.get("Logo", ""), lc.get("Website Link", "")) for lc in lcs[:lc_half])
    lc_row2 = "\n".join(lc_item(lc["Name"], lc.get("Logo", ""), lc.get("Website Link", "")) for lc in lcs[lc_half:])
    html = populate_dyn_wrapper(html, "uni-cms-wrap", "\n" + lc_row1 + "\n            ", occurrence=0)
    html = populate_dyn_wrapper(html, "uni-cms-wrap", "\n" + lc_row2 + "\n            ", occurrence=1)

    home_tests = [t for t in testimonials if t.get("Is it on Home Page?", "").lower() == "true"]
    test_html = "\n".join(home_testimonial_item(t) for t in home_tests)
    html = populate_dyn_wrapper(html, "testimonial-wrap", "\n" + test_html + "\n        ")
    write_page("index.html", rewrite_cdn_in_html(html, ROOT / "index.html"))

    # --- about-us.html ---
    html = (ROOT / "about-us.html").read_text(encoding="utf-8")
    board_html = "\n".join(build_board_item(b) for b in board)
    html = populate_dyn_wrapper(html, "team-wrapper-cms", "\n" + board_html + "\n          ")
    write_page("about-us.html", rewrite_cdn_in_html(html, ROOT / "about-us.html"))

    # --- join.html ---
    html = (ROOT / "join.html").read_text(encoding="utf-8")
    html = populate_dyn_wrapper(html, "uni-cms-wrap", "\n" + lc_row1 + "\n            ", occurrence=0)
    html = populate_dyn_wrapper(html, "uni-cms-wrap", "\n" + lc_row2 + "\n            ", occurrence=1)
    membership_test = next((t for t in testimonials if t.get("Membership Dummy", "").lower() == "true"), None)
    if membership_test:
        ft = featured_testimonial_item(membership_test)
        html = populate_dyn_wrapper(html, "testimonial-ft-wrap", "\n" + ft + "\n          ")
    write_page("join.html", rewrite_cdn_in_html(html, ROOT / "join.html"))

    # --- blog.html ---
    html = (ROOT / "blog.html").read_text(encoding="utf-8")
    main_blogs = [b for b in blogs if b.get("Main Article for Blug Hub", "").lower() == "true"]
    hero_post = main_blogs[0] if main_blogs else blogs[0]
    hero_html = blog_hero_item(hero_post)
    html = populate_dyn_wrapper(html, "blog-hub_wrap", "\n" + hero_html + "\n        ")
    preview_posts = [b for b in blogs if b["Slug"] != hero_post["Slug"]]
    preview_html = "\n".join(blog_preview_item(p, authors) for p in preview_posts)
    html = populate_dyn_wrapper(html, "blog-preview-wrap", "\n" + preview_html + "\n          ")
    write_page("blog.html", rewrite_cdn_in_html(html, ROOT / "blog.html"))

    # --- news.html ---
    html = (ROOT / "news.html").read_text(encoding="utf-8")
    main_news = [n for n in news if n.get("Main Article for News Hub", "").lower() == "true"]
    hero_news = main_news[0] if main_news else news[0]
    hero_html = blog_hero_item(hero_news, detail_prefix="news/")
    html = populate_dyn_wrapper(html, "blog-hub_wrap", "\n" + hero_html + "\n        ")
    preview_news = [n for n in news if n["Slug"] != hero_news["Slug"]]
    preview_html = "\n".join(blog_preview_item(p, authors, detail_prefix="news/") for p in preview_news)
    html = populate_dyn_wrapper(html, "blog-preview-wrap", "\n" + preview_html + "\n          ")
    write_page("news.html", rewrite_cdn_in_html(html, ROOT / "news.html"))

    # --- Donate FAQ pages ---
    donate_pages = [
        ("donate/legacy-fund.html", "../"),
        ("donate/empower-tomorrows-leaders.html", "../"),
        ("donate/employer-giving.html", "../"),
        ("donate/payroll-giving.html", "../"),
    ]
    for page, docs_prefix in donate_pages:
        html = (ROOT / page).read_text(encoding="utf-8")
        html = populate_faq_sections(html, faqs, docs_prefix)
        write_page(page, rewrite_cdn_in_html(html, ROOT / page))

    # --- get-scholarship FAQ ---
    html = (ROOT / "students/get-scholarship.html").read_text(encoding="utf-8")
    html = populate_scholarship_faq(html, faqs)
    write_page("students/get-scholarship.html", rewrite_cdn_in_html(html, ROOT / "students/get-scholarship.html"))

    # --- Product pages: clients + testimonials ---
    product_pages = [
        ("students/global-talent.html", "Employers - Global Talent", True, "../"),
        ("host/global-talent.html", "Employers - Global Talent", True, "../"),
        ("students/global-volunteer.html", "Students - Global Volunteer", True, "../"),
        ("students/global-teacher.html", None, True, "../"),
    ]
    for page, product_filter, has_clients, prefix in product_pages:
        html = (ROOT / page).read_text(encoding="utf-8")
        if has_clients:
            client_html = "\n".join(client_item(c["Name"], c.get("Client Logo", ""), prefix) for c in clients)
            html = populate_dyn_wrapper(html, "client-logo-wrapper", "\n" + client_html + "\n          ")

        if product_filter:
            matches = [t for t in testimonials if t.get("Product", "") == product_filter]
        else:
            matches = [t for t in testimonials if t.get("Highlighted Testimonial", "").lower() == "true"]
        if not matches:
            matches = testimonials[:1]
        ft = featured_testimonial_item(matches[0], prefix)
        html = populate_dyn_wrapper(html, "testimonial-ft-wrap", "\n" + ft + "\n          ")

        if "testimonial-wrap" in html and page == "host/global-talent.html":
            employer_tests = [t for t in testimonials if t.get("Product", "") == "Employers - Global Talent"]
            if employer_tests:
                t_html = "\n".join(home_testimonial_item(t, prefix) for t in employer_tests[:3])
                html = populate_dyn_wrapper(html, "testimonial-wrap", "\n" + t_html + "\n        ")

        write_page(page, rewrite_cdn_in_html(html, ROOT / page))

    print("\n=== Generating detail pages ===")
    blog_tpl = (ROOT / "detail_blog.html").read_text(encoding="utf-8")
    (ROOT / "blog").mkdir(exist_ok=True)
    for post in blogs:
        out = build_blog_detail(blog_tpl, post, authors, blogs)
        write_page(f"blog/{post['Slug']}.html", out)

    news_tpl = (ROOT / "detail_news.html").read_text(encoding="utf-8")
    (ROOT / "news").mkdir(exist_ok=True)
    for post in news:
        out = build_news_detail(news_tpl, post, authors, news)
        write_page(f"news/{post['Slug']}.html", out)

    # Scan all HTML for remaining CDN URLs (schema JS, OG images, 70th board photos, etc.)
    print("\n=== Scanning for remaining CDN references ===")
    for html_file in ROOT.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8", errors="ignore")
        for url in CDN_RE.findall(text):
            category = "schema" if "schema_" in url else "site"
            register_asset(url, category=category)

    # --- Write download manifest ---
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_urls": len(PENDING_DOWNLOADS),
        "missing_locally": sum(1 for v in PENDING_DOWNLOADS.values() if not v["exists_locally"]),
        "assets": sorted(PENDING_DOWNLOADS.values(), key=lambda x: x["local_path"]),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Also write plain URL list for wget/curl
    url_list = ROOT / "scripts" / "cdn-urls.txt"
    url_list.write_text("\n".join(sorted(PENDING_DOWNLOADS.keys())), encoding="utf-8")

    print(f"\n=== Done ===")
    print(f"  CMS pages populated")
    print(f"  {len(blogs)} blog detail pages → blog/")
    print(f"  {len(news)} news detail pages → news/")
    print(f"  {manifest['total_urls']} CDN assets referenced")
    print(f"  {manifest['missing_locally']} assets NOT yet downloaded locally")
    print(f"  Manifest: scripts/assets-to-download.json")
    print(f"  URL list: scripts/cdn-urls.txt")


if __name__ == "__main__":
    main()
