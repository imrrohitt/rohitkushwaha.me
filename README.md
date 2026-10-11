# rohitkushwaha — personal site

A hand-built static site: Python + Jinja2 generate plain HTML/CSS, Netlify hosts it.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python generator/build.py --serve      # http://localhost:8000
```

`--drafts` also renders posts marked `draft: true`.

## Where things live

| What | File |
| --- | --- |
| Name, bio, links, highlights, skills, awards | `data/site.yaml` |
| Work experience | `data/experience.yaml` |
| Projects (featured case studies + "More on GitHub") | `data/projects.yaml` |
| Medium articles (auto-synced) | `data/medium.yaml` |
| Talks (with optional photo) | `data/talks.yaml` |
| Videos you've watched | `data/videos.yaml` |
| Papers you've read | `data/papers.yaml` |
| Blog posts | `content/blogs/*.md` |
| Layouts | `templates/` |
| Styles / scripts / images | `static/` |

## Add a blog post

Create `content/blogs/my-post.md`:

```markdown
---
title: My post title
date: 2026-10-20
description: One line for the list page and RSS.
tags: [rag, agents]
draft: false
---

Write in Markdown here.
```

Rebuild, and it shows up on the home page, `/blogs/`, the RSS feed and the sitemap.

## Medium articles

```bash
.venv/bin/python generator/sync_medium.py
```

Pulls your latest Medium posts into `data/medium.yaml` and merges them with what's already
there. Your hand edits to `excerpt`, `topic`, `featured` or `hidden` are kept. Netlify runs this
on every deploy, so a new Medium article shows up the next time the site builds.

## Deploy (Netlify)

1. Push this folder to a GitHub repo.
2. In Netlify: **Add new site → Import from Git** and pick the repo. `netlify.toml` already sets
   the build command and the `dist` publish directory.
3. When your domain is ready, add it in Netlify's domain settings and update `url` in `data/site.yaml`.
