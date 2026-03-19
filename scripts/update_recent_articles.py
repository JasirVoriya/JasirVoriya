#!/usr/bin/env python3
"""Refresh the generated recent-posts block in the profile README."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


START_MARKER = "<!-- recent-posts:start -->"
END_MARKER = "<!-- recent-posts:end -->"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Article:
    title: str
    url: str
    slug: str
    date: str
    sort_key: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blog-repo", required=True, type=Path)
    parser.add_argument("--readme", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def iter_article_files(blog_repo: Path) -> list[Path]:
    docs_dir = blog_repo / "docs"
    files: list[Path] = []
    for path in sorted(docs_dir.rglob("*.md")):
        rel = path.relative_to(docs_dir)
        if rel.name == "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(path)
    return files


def parse_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    frontmatter_match = FRONTMATTER_RE.search(text)
    if frontmatter_match:
        title_match = TITLE_RE.search(frontmatter_match.group(1))
        if title_match:
            return title_match.group(1).strip().strip("'\"")

    h1_match = H1_RE.search(text)
    if h1_match:
        return h1_match.group(1).strip()

    return path.stem.replace("-", " ")


def to_public_url(path: Path, blog_repo: Path) -> tuple[str, str]:
    rel = path.relative_to(blog_repo / "docs")
    slug = rel.with_suffix("").as_posix()
    return f"https://jasirvoriya.github.io/{slug}.html", slug


def article_from_path(path: Path, blog_repo: Path) -> Article:
    commit_iso = git_output(blog_repo, "log", "-1", "--format=%cI", "--", str(path))
    commit_date = git_output(blog_repo, "log", "-1", "--format=%cs", "--", str(path))
    url, slug = to_public_url(path, blog_repo)
    return Article(
        title=parse_title(path),
        url=url,
        slug=slug,
        date=commit_date,
        sort_key=commit_iso,
    )


def build_recent_posts(blog_repo: Path, limit: int) -> str:
    articles = [article_from_path(path, blog_repo) for path in iter_article_files(blog_repo)]
    articles.sort(key=lambda item: item.sort_key, reverse=True)
    lines = []
    for article in articles[:limit]:
        lines.append(
            f"- `{article.date}` [`{article.title}`]({article.url})  \n"
            f"  `{article.slug}`"
        )
    return "\n".join(lines)


def replace_block(readme_path: Path, content: str) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL,
    )
    if not pattern.search(readme):
        raise SystemExit("Failed to locate recent-posts markers in README.md")

    replacement = f"{START_MARKER}\n{content}\n{END_MARKER}"
    updated = pattern.sub(replacement, readme, count=1)
    readme_path.write_text(updated, encoding="utf-8")


def main() -> None:
    args = parse_args()
    content = build_recent_posts(args.blog_repo.resolve(), args.limit)
    replace_block(args.readme.resolve(), content)


if __name__ == "__main__":
    main()
