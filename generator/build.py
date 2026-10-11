#!/usr/bin/env python3
"""A small, handmade static site generator.

    python generator/build.py              build the site into dist/
    python generator/build.py --serve      build, then serve it on http://localhost:8000
    python generator/build.py --drafts     also include posts marked `draft: true`

Content lives in three places:
    content/blogs/*.md   blog posts (YAML front matter + Markdown)
    data/*.yaml          profile, projects, talks, videos, papers, experience
    templates/*.html     Jinja2 layouts
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import os
import re
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
WORDS_PER_MINUTE = 220


# --------------------------------------------------------------------------- data

def load_yaml(name: str):
    path = DATA / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def to_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def sort_key(item: dict) -> str:
    """Sort key for data entries whose date may be a full date, 'YYYY-MM' or just a year."""
    return str(item.get("date", ""))


def load_medium() -> list[dict]:
    """Articles synced from Medium (see sync_medium.py), shaped like local posts."""
    if not (DATA / "medium.yaml").exists():
        return []
    articles = []
    for a in load_yaml("medium"):
        if a.get("hidden"):
            continue
        articles.append({
            "title": a["title"],
            "url": a["url"],
            "external": True,
            "source": "Medium",
            "date": to_date(a["date"]),
            "description": a.get("excerpt", ""),
            "topic": a.get("topic", "Writing"),
            "reading_time": a.get("reading_time", 5),
            "featured": bool(a.get("featured")),
            "draft": False,
        })
    return articles


def load_posts(include_drafts: bool) -> list[dict]:
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "footnotes", "smarty", "toc"],
        extension_configs={"toc": {"permalink": "#", "permalink_class": "anchor"}},
    )
    posts = []
    for path in sorted((CONTENT / "blogs").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = FRONT_MATTER.match(raw)
        if not match:
            raise SystemExit(f"{path.relative_to(ROOT)}: missing front matter (--- ... ---)")
        meta = yaml.safe_load(match.group(1)) or {}
        body = raw[match.end():]
        if meta.get("draft") and not include_drafts:
            continue
        for field in ("title", "date"):
            if field not in meta:
                raise SystemExit(f"{path.relative_to(ROOT)}: front matter needs '{field}'")

        md.reset()
        slug = meta.get("slug", path.stem)
        words = len(re.findall(r"\w+", body))
        posts.append({
            "slug": slug,
            "url": f"/blogs/{slug}/",
            "external": False,
            "title": meta["title"],
            "date": to_date(meta["date"]),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "topic": meta.get("topic", "Notes"),
            "source": "This site",
            "featured": bool(meta.get("featured")),
            "draft": bool(meta.get("draft")),
            "html": Markup(md.convert(body)),
            "reading_time": max(1, round(words / WORDS_PER_MINUTE)),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


# ------------------------------------------------------------------------ filters

def format_date(value, fmt: str = "%b %d, %Y") -> str:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime(fmt)
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return dt.datetime.strptime(text, "%Y-%m").strftime("%b %Y")
    return text  # a bare year, or free text like "Present"


def md_inline(text: str) -> Markup:
    """Render a short Markdown string (links, emphasis) without the wrapping <p>."""
    html = markdown.markdown(str(text), extensions=["smarty"])
    return Markup(re.sub(r"\A<p>(.*)</p>\Z", r"\1", html, flags=re.S))


# ------------------------------------------------------------------------- output

def write(path: str, text: str) -> None:
    target = DIST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_feed(site: dict, base_url: str, posts: list[dict]) -> str:
    items = []
    for post in posts[:20]:
        link = post["url"] if post["external"] else base_url + post["url"]
        pub = dt.datetime.combine(post["date"], dt.time(9, 0), dt.timezone.utc)
        items.append(
            "<item>"
            f"<title>{escape(post['title'])}</title>"
            f"<link>{link}</link><guid>{link}</guid>"
            f"<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
            f"<description>{escape(post['description'])}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{escape(site['name'])}</title>"
        f"<link>{base_url}/</link>"
        f"<description>{escape(site['description'])}</description>"
        + "".join(items)
        + "</channel></rss>\n"
    )


def build_sitemap(base_url: str, paths: list[str]) -> str:
    urls = "".join(f"<url><loc>{base_url}{p}</loc></url>" for p in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    )


def build(include_drafts: bool = False) -> None:
    site = load_yaml("site")
    # Netlify exposes the production URL as $URL during builds.
    base_url = os.environ.get("URL", site["url"]).rstrip("/")

    posts = load_posts(include_drafts)
    writing = sorted(posts + load_medium(), key=lambda w: w["date"], reverse=True)
    featured_article = next((w for w in writing if w["featured"]), writing[0] if writing else None)
    project_data = load_yaml("projects")
    projects, more_projects = project_data["projects"], project_data.get("more", [])
    experience = load_yaml("experience")
    milestones = load_yaml("milestones")
    talks = sorted(load_yaml("talks"), key=sort_key, reverse=True)
    videos = sorted(load_yaml("videos"), key=sort_key, reverse=True)
    papers = sorted(load_yaml("papers"), key=sort_key, reverse=True)

    explore = [
        {"label": "Writing", "url": "/blogs/", "count": len(writing), "desc": "Articles on AI, systems and cloud"},
        {"label": "Projects", "url": "/projects/", "count": len(projects), "desc": "Things I've built and open-sourced"},
        {"label": "Talks", "url": "/talks/", "count": len(talks), "desc": "Sessions for students and developers"},
        {"label": "Videos", "url": "/videos/", "count": len(videos), "desc": "Videos I've watched and learned from"},
        {"label": "Papershelf", "url": "/papers/", "count": len(papers), "desc": "Research papers I've read"},
        {"label": "About", "url": "/about/", "count": None, "desc": "Experience, skills and contact"},
    ]

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date"] = format_date
    env.filters["md"] = md_inline
    env.globals.update(
        site=site,
        base_url=base_url,
        year=dt.date.today().year,
        build_id=dt.datetime.now().strftime("%Y%m%d%H%M%S"),
    )

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST / "static")
    if (STATIC / "favicon.ico").exists():
        shutil.copy(STATIC / "favicon.ico", DIST / "favicon.ico")
    for name in ("CNAME", ".nojekyll"):
        if (STATIC / name).exists():
            shutil.copy(STATIC / name, DIST / name)

    pages: list[str] = []

    def render(template: str, path: str, active: str = "", **ctx) -> None:
        out = path.lstrip("/") + "index.html" if path.endswith("/") else path.lstrip("/")
        write(out, env.get_template(template).render(active=active, path=path, **ctx))
        if path.endswith("/"):
            pages.append(path)

    render("index.html", "/", featured_article=featured_article,
           writing=[w for w in writing if w is not featured_article][:5], projects=projects,
           experience=experience, talks=talks[:2], videos=videos[:5], papers=papers[:5], explore=explore,
           milestones=[m for m in milestones if m.get("home")])
    render("blog_list.html", "/blogs/", "blogs", writing=writing, featured_article=featured_article)
    for i, post in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        render("post.html", post["url"], "blogs", post=post, newer=newer, older=older)
    render("projects.html", "/projects/", "projects", projects=projects, more_projects=more_projects)
    render("talks.html", "/talks/", "talks", talks=talks)
    render("videos.html", "/videos/", "videos", videos=videos)
    render("papers.html", "/papers/", "papers", papers=papers)
    render("about.html", "/about/", "about", experience=experience, milestones=milestones)
    render("milestones.html", "/milestones/", "milestones", milestones=milestones)
    render("404.html", "/404.html")

    write("feed.xml", build_feed(site, base_url, writing))
    write("sitemap.xml", build_sitemap(base_url, pages))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n")

    print(f"Built {len(pages)} pages ({len(posts)} posts) into {DIST.relative_to(ROOT)}/")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving on http://localhost:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true", help="serve dist/ after building")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--drafts", action="store_true", help="include draft posts")
    args = parser.parse_args()
    build(include_drafts=args.drafts)
    if args.serve:
        serve(args.port)
