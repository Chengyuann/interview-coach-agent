#!/usr/bin/env python3
"""Build a ModelScope-safe interview article without hard-wrapped prose."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "interview-coach-article-draft.md"
OUTPUT = ROOT / "docs" / "interview-coach-article-publish.md"
HTML_OUTPUT = ROOT / "docs" / "interview-coach-article-publish.html"
IMAGE_URLS = ROOT / "docs" / "modelscope-article-images.json"

BLOCK_PREFIXES = ("#", "- ", "* ", "+ ", "|", "![", "<!--")
ORDERED_LIST = re.compile(r"^\d+[.)]\s")
ASCII_WORD = re.compile(r"[A-Za-z0-9]")
IMAGE = re.compile(r"^!\[(?P<alt>.*)]\((?P<src>.*)\)$")
LINK = re.compile(r"\[([^]]+)]\(([^)]+)\)")
PUNCTUATION = set(
    "，。；：！？、,.!?;:)]}）】》”’"
)


def join_prose(parts: list[str]) -> str:
    result = parts[0].strip()
    for part in parts[1:]:
        next_text = part.strip()
        separator = (
            " "
            if (
                (
                    ASCII_WORD.match(result[-1:])
                    or ASCII_WORD.match(next_text[:1])
                    or result[-1:] == "`"
                    or next_text[:1] == "`"
                )
                and result[-1:] not in PUNCTUATION
                and next_text[:1] not in PUNCTUATION
            )
            else ""
        )
        result += separator + next_text
    return result


def reflow_markdown(text: str) -> str:
    output: list[str] = []
    paragraph: list[str] = []
    quote: list[str] = []
    in_fence = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(join_prose(paragraph))
            paragraph.clear()

    def flush_quote() -> None:
        if quote:
            output.append("> " + join_prose(quote))
            quote.clear()

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            flush_paragraph()
            flush_quote()
            output.append(line)
            in_fence = not in_fence
            continue

        if in_fence:
            output.append(line)
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote.append(stripped[1:].lstrip())
            continue

        flush_quote()

        if not stripped:
            flush_paragraph()
            if output and output[-1] != "":
                output.append("")
            continue

        is_block = stripped.startswith(BLOCK_PREFIXES) or ORDERED_LIST.match(
            stripped
        )
        if is_block:
            flush_paragraph()
            output.append(line)
            continue

        paragraph.append(line)

    flush_paragraph()
    flush_quote()
    return "\n".join(output).rstrip() + "\n"


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return LINK.sub(r'<a href="\2">\1</a>', escaped)


def render_html_fragment(
    text: str, image_urls: list[str] | None = None
) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    image_index = 0

    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped or stripped.startswith("<!--"):
            index += 1
            continue

        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith(
                "```"
            ):
                code.append(lines[index])
                index += 1
            index += 1
            class_name = (
                f' class="language-{html.escape(language)}"'
                if language
                else ""
            )
            output.append(
                f"<pre><code{class_name}>"
                f"{html.escape(chr(10).join(code))}</code></pre>"
            )
            continue

        image = IMAGE.match(stripped)
        if image:
            image_index += 1
            alt = html.escape(image.group("alt"))
            if image_urls and image_index <= len(image_urls):
                src = html.escape(image_urls[image_index - 1], quote=True)
                output.append(f'<p><img src="{src}" alt="{alt}"></p>')
            else:
                output.append(f"<p>【配图 {image_index:02d}：{alt}】</p>")
            index += 1
            continue

        if stripped.startswith("# "):
            index += 1
            continue
        if stripped.startswith("## "):
            output.append(f"<h2>{render_inline(stripped[3:])}</h2>")
            index += 1
            continue
        if stripped.startswith("### "):
            output.append(f"<h3>{render_inline(stripped[4:])}</h3>")
            index += 1
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].lstrip())
                index += 1
            output.append(
                f"<blockquote><p>{render_inline(join_prose(quote))}"
                "</p></blockquote>"
            )
            continue

        if stripped.startswith("|") and index + 1 < len(lines):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [
                [cell.strip() for cell in row.strip("|").split("|")]
                for row in table_lines
            ]
            if len(rows) >= 2 and all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]
            ):
                header = "".join(
                    f"<th>{render_inline(cell)}</th>" for cell in rows[0]
                )
                body = "".join(
                    "<tr>"
                    + "".join(
                        f"<td>{render_inline(cell)}</td>" for cell in row
                    )
                    + "</tr>"
                    for row in rows[2:]
                )
                output.append(
                    f"<table><thead><tr>{header}</tr></thead>"
                    f"<tbody>{body}</tbody></table>"
                )
            else:
                output.extend(f"<p>{render_inline(row)}</p>" for row in table_lines)
            continue

        if stripped.startswith(("- ", "* ", "+ ")):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(
                ("- ", "* ", "+ ")
            ):
                items.append(lines[index].strip()[2:])
                index += 1
            output.append(
                "<ul>"
                + "".join(f"<li>{render_inline(item)}</li>" for item in items)
                + "</ul>"
            )
            continue

        if ORDERED_LIST.match(stripped):
            items = []
            while index < len(lines) and ORDERED_LIST.match(lines[index].strip()):
                items.append(ORDERED_LIST.sub("", lines[index].strip()))
                index += 1
            output.append(
                "<ol>"
                + "".join(f"<li>{render_inline(item)}</li>" for item in items)
                + "</ol>"
            )
            continue

        output.append(f"<p>{render_inline(stripped)}</p>")
        index += 1

    return "\n".join(output) + "\n"


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    published = reflow_markdown(source)
    image_urls = (
        json.loads(IMAGE_URLS.read_text(encoding="utf-8"))
        if IMAGE_URLS.exists()
        else None
    )
    OUTPUT.write_text(published, encoding="utf-8")
    HTML_OUTPUT.write_text(
        render_html_fragment(published, image_urls),
        encoding="utf-8",
    )
    print(OUTPUT)
    print(HTML_OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
