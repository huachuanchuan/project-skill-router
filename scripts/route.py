#!/usr/bin/env python3
"""Shortlist installed Agent Skills for a task; never execute candidate skills."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import sys


SKIP_DIRS = {".git", ".agents", ".venv", "venv", "node_modules", "__pycache__", "work", "outputs"}
WORDS = re.compile(r"[a-z][a-z0-9+#./-]*|[\u3400-\u9fff]+", re.IGNORECASE)
STOP = {"a", "an", "and", "for", "from", "in", "is", "of", "on", "or", "the", "to", "use", "using", "when", "with", "skill", "skills", "agent", "agents", "project", "task"}
ZH_HINTS = {
    "论文": "paper manuscript",
    "文献": "literature papers",
    "综述": "literature review survey",
    "引用": "citation reference bibliography",
    "科研": "scientific research",
    "研究": "research",
    "实验": "experiment experimental design",
    "数据": "data analysis",
    "统计": "statistics statistical analysis",
    "绘图": "figure visualization plotting",
    "图表": "chart figure visualization",
    "流程图": "diagram flowchart drawio",
    "架构图": "architecture diagram drawio",
    "图片": "image picture",
    "网页": "web frontend website",
    "网站": "website web design",
    "界面": "ui ux interface design",
    "代码": "code coding software",
    "调试": "debugging bug troubleshoot",
    "报错": "error bug debugging",
    "错误": "error bug debugging",
    "修复": "fix bug debugging",
    "解析": "parse parser parsing",
    "测试": "testing tests",
    "表格": "spreadsheet excel xlsx",
    "幻灯片": "presentation slides pptx",
    "演示文稿": "presentation slides pptx",
    "文档": "document docx writing",
    "下载": "download retrieval",
    "检索": "search lookup retrieval",
    "搜索": "search lookup",
    "润色": "polish editing prose",
    "翻译": "translation translate",
    "仿真": "simulation modeling",
    "建模": "modeling model simulation",
    "材料": "materials science",
    "生物": "biology bioinformatics",
    "化学": "chemistry chemical",
    "医学": "medicine medical clinical",
}
ALIASES = {"sciencedirect": "sd", "draw.io": "drawio diagram", "bug": "debugging", "error": "debugging"}


def tokens(value: str, expand: bool = True) -> set[str]:
    result: set[str] = set()
    value = value.lower()
    for match in WORDS.finditer(value):
        word = match.group()
        if "\u3400" <= word[0] <= "\u9fff":
            result.add(word)
        else:
            result.update(part for part in re.split(r"[./+-]", word) if part and part not in STOP)
            if word not in STOP:
                result.add(word)
    if expand:
        for phrase, expansion in ZH_HINTS.items():
            if phrase in value:
                result.update(tokens(expansion, expand=False))
        for phrase, expansion in ALIASES.items():
            if phrase in value:
                result.update(tokens(expansion, expand=False))
    for phrase in ZH_HINTS:
        if phrase in value:
            result.add(phrase)
    return result


def frontmatter(path: Path) -> tuple[str, str] | None:
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace")[:16000].splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return None
    name = ""
    description = ""
    header = lines[1:end]
    for i, line in enumerate(header):
        if line.startswith("name:"):
            name = line.partition(":")[2].strip().strip('"\'')
        if line.startswith(("description:", "when_to_use:")):
            value = line.partition(":")[2].strip()
            if value in {">", ">-", "|", "|-"}:
                following = []
                for next_line in header[i + 1 :]:
                    if next_line and not next_line[0].isspace():
                        break
                    following.append(next_line.strip())
                value = " ".join(following)
            else:
                value = value.strip('"\'')
            description = f"{description} {value}".strip()
    if not name or not description:
        return None
    return name, description


def roots(project: Path, extra: list[Path], only_extra: bool) -> list[tuple[Path, str, int]]:
    if only_extra:
        return [(p, "custom", 2) for p in extra]
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    entries = [
        (project / ".agents" / "skills", "project", 5),
        (project / ".codex" / "skills", "project", 5),
        (project / ".claude" / "skills", "project", 5),
        (codex_home / "skills", "codex", 4),
        (home / ".agents" / "skills", "agents", 3),
        (codex_home / "plugins" / "cache", "plugin", 2),
    ]
    entries.extend((p, "custom", 2) for p in extra)
    seen = set()
    unique = []
    for path, source, priority in entries:
        key = os.path.normcase(str(path.resolve()))
        if key not in seen and path.is_dir():
            unique.append((path, source, priority))
            seen.add(key)
    return unique


def skill_files(root: Path):
    for directory, subdirs, files in os.walk(root, followlinks=False):
        subdirs[:] = [part for part in subdirs if part not in SKIP_DIRS]
        if "SKILL.md" in files:
            yield Path(directory) / "SKILL.md"


def project_terms(project: Path) -> set[str]:
    snippets = []
    for filename in ("package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod", "README.md"):
        path = project / filename
        if path.is_file():
            try:
                snippets.append(path.read_text(encoding="utf-8", errors="replace")[:3000])
            except OSError:
                pass
    for path in project.iterdir() if project.is_dir() else []:
        if path.is_file() and path.suffix.lower() in {".ipynb", ".tex", ".drawio", ".docx", ".xlsx", ".pptx"}:
            snippets.append(path.suffix[1:])
    return tokens(" ".join(snippets))


def positive_scope(description: str) -> str:
    """Exclude common 'do not use' clauses from lexical ranking only."""
    lower = description.lower()
    cut = len(description)
    for marker in ("skip:", "not for ", "do not use", "用户仅", "不要使用", "不适用于"):
        location = lower.find(marker)
        if location >= 0:
            cut = min(cut, location)
    return description[:cut]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, help="The user's original task")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project root")
    parser.add_argument("--query", action="append", default=[], help="Additional paraphrase or domain terms; repeatable")
    parser.add_argument("--catalog-root", action="append", type=Path, default=[], help="Additional skill directory; repeatable")
    parser.add_argument("--only-catalog-roots", action="store_true", help="Search only --catalog-root directories")
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    project = args.project.expanduser().resolve()
    primary_words = tokens(args.task, expand=False)
    primary_words.update(tokens(" ".join(args.query), expand=False))
    task_words = tokens(args.task)
    task_words.update(tokens(" ".join(args.query)))
    expanded_words = task_words - primary_words
    context_words = project_terms(project) - task_words
    found = []
    for root, source, priority in roots(project, args.catalog_root, args.only_catalog_roots):
        for path in skill_files(root):
            metadata = frontmatter(path)
            if metadata is None:
                continue
            name, description = metadata
            if name.casefold() == "project-skill-router":
                continue
            found.append({"name": name, "description": description, "path": str(path.resolve()), "source": source, "priority": priority,
                          "name_words": tokens(name, expand=False), "description_words": tokens(positive_scope(description), expand=False)})
    if not found:
        print(json.dumps({"catalog_size": 0, "candidates": []}) if args.json else "No local skills found.")
        return 0
    frequency = Counter(word for item in found for word in item["name_words"] | item["description_words"])
    def importance(word: str) -> float:
        return 1.0 + math.log((len(found) + 1) / (frequency[word] + 1))
    for item in found:
        name_hits = task_words & item["name_words"]
        description_hits = task_words & item["description_words"]
        primary_name_hits = primary_words & item["name_words"]
        primary_description_hits = primary_words & item["description_words"]
        expanded_name_hits = expanded_words & item["name_words"]
        expanded_description_hits = expanded_words & item["description_words"]
        context_hits = context_words & (item["name_words"] | item["description_words"])
        item["score"] = round(sum(6 * importance(w) for w in primary_name_hits)
                              + sum(3 * importance(w) for w in primary_description_hits)
                              + sum(5 * importance(w) for w in expanded_name_hits)
                              + sum(0.8 * importance(w) for w in expanded_description_hits)
                              + sum(0.5 * importance(w) for w in context_hits), 2)
        item["matched_task_terms"] = sorted(name_hits | description_hits)
        item["matched_project_terms"] = sorted(context_hits)[:10]
    grouped = defaultdict(list)
    for item in found:
        grouped[re.sub(r"[^a-z0-9]+", "-", item["name"].casefold()).strip("-")].append(item)
    candidates = []
    for variants in grouped.values():
        variants.sort(key=lambda item: (item["priority"], item["score"]), reverse=True)
        best = variants[0]
        if best["score"] <= 0 or not best["matched_task_terms"]:
            continue
        candidates.append({key: best[key] for key in ("name", "description", "path", "source", "score", "matched_task_terms", "matched_project_terms")}
                          | {"alternates": [other["path"] for other in variants[1:4]]})
    candidates.sort(key=lambda item: (item["score"], len(item["matched_task_terms"])), reverse=True)
    output = {"catalog_size": len(found), "unique_names": len(grouped), "project": str(project), "candidates": candidates[: args.top]}
    if args.json:
        print(json.dumps(output, ensure_ascii=True, indent=2))
    else:
        print(f"Scanned {len(found)} local skill files ({len(grouped)} names). Relative scores are not quality ratings.")
        for number, item in enumerate(output["candidates"], 1):
            print(f"{number:2}. {item['name']} [{item['score']:.2f}] ({item['source']})")
            print(f"    {item['path']}")
            print(f"    {item['description'][:220]}")
            print(f"    task matches: {', '.join(item['matched_task_terms'])}")
            if item["alternates"]:
                print(f"    same-name alternatives: {', '.join(item['alternates'])}")
        if not output["candidates"]:
            print("No lexical match. Try --query with a domain paraphrase or inspect the catalog directly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
