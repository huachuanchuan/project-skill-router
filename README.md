# Project Skill Router

[中文](#中文说明) · [English](#english)

## 中文说明

一个供 Codex 使用的本地技能入口。给它项目任务后，它会检索本机已安装的 Agent Skills，结合任务描述和项目文件生成候选清单，再阅读候选技能的完整说明，选出适合的一个或几个技能并继续完成原任务。

路由脚本只做**候选检索**，不会执行候选技能。最终选择由 Codex 根据技能适用范围、项目约束和可用工具判断。词汇分数不是技能质量评分；没有合适技能时也可以直接完成任务。

### 安装

需要 Python 3.10+，不需要第三方 Python 包。

将本仓库克隆或下载到 Codex 的技能目录：

```bash
git clone https://github.com/huachuanchuan/project-skill-router.git ~/.codex/skills/project-skill-router
```

Windows PowerShell：

```powershell
git clone https://github.com/huachuanchuan/project-skill-router.git "$env:USERPROFILE\.codex\skills\project-skill-router"
```

重新打开 Codex 会话后，使用 `$project-skill-router` 并描述要完成的任务，例如：

```text
$project-skill-router 分析这个项目的数据，生成可复现的统计图并写出结果说明。
```

### 工作方式

1. Codex 先检查任务、项目和适用的项目指令。
2. `scripts/route.py` 扫描项目级、Codex、agent 和插件缓存中的 `SKILL.md` 前置元数据，并根据任务词汇、中文领域词提示及少量项目上下文排序。
3. Codex 阅读候选技能全文，选择最小且职责清晰的组合，然后按所选技能完成原任务。

也可以单独运行检索脚本：

```bash
python scripts/route.py --task "review a scientific paper" --project /path/to/project --top 12 --json
```

可重复使用 `--query` 补充同义词或领域词；用 `--catalog-root` 增加本地技能目录；用 `--only-catalog-roots` 只检索指定目录。

### 边界

- 只查找本地已有技能，不会自动下载或安装新技能。
- 基于词汇匹配生成候选，无法保证最佳技能排在第一位；Codex 应阅读候选全文后决定。
- 脚本只读取技能元数据及项目根目录中的少量常见配置文件，不运行候选技能，也不授予额外权限。
- 对缺少 `name` 或 `description` 前置元数据的技能不会建立索引。

## English

Project Skill Router is a local entry-point skill for Codex. Given a project task, it shortlists installed Agent Skills, then instructs Codex to inspect the full candidate instructions, choose a small compatible set, and complete the original task.

The Python helper performs **candidate retrieval only**. It never executes candidate skills. Scores reflect lexical relevance, not skill quality. Codex makes the final selection after checking scope, project constraints, and available tools.

Install by cloning this repository into `~/.codex/skills/project-skill-router` (see the commands above), then start a new Codex session and invoke `$project-skill-router` with your task. Python 3.10+ is required; no third-party packages are needed.

Run the helper directly with `python scripts/route.py --task "your task" --project /path/to/project --json`. Use `--query` for additional wording, `--catalog-root` for another local catalog, and `--only-catalog-roots` to limit the search to those roots.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
