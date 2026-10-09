#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quiz-bank-search.py
===================
题库搜索引擎（5 步 SOP 自动化）

参考：
- references/quiz-bank-workflow.md（完整 SOP）
- references/quiz-bank-design.md（schema + AI 自审）

支持的模式（--mode）：
  init-sources    初始化 source-sites.json（首次建库）
  search-kp       按 KP 搜索候选题
  self-review     AI 自审候选题（需调 LLM）
  insert          入库 + 索引同步
  full-cycle      完整跑 search → self-review → insert（默认）

执行示例：
  # 1. 初始化来源清单
  python quiz-bank-search.py --subject 语文 --mode init-sources

  # 2. 按 KP 搜索（搜深圳教育云 + 粤教沪外版等）
  python quiz-bank-search.py --subject 语文 --mode search-kp --kp-id u1.k1

  # 3. 完整跑一个 KP（搜 + 自审 + 入库）
  python quiz-bank-search.py --subject 语文 --mode full-cycle --kp-id u1.k1

作者：Hermes 家庭教师系统
最后更新：2026-09-12
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))


def now_cst() -> str:
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S")


def auto_detect_base_dir() -> Path:
    for cand in [Path("D:/家教"), Path("/d/家教"), Path("D:\\家教")]:
        if cand.exists():
            return cand
    raise FileNotFoundError("未找到家教根目录")


def load_kp_index(subject_dir: Path) -> dict:
    return json.loads((subject_dir / "知识点及掌握情况/index.json").read_text(encoding="utf-8"))


def load_kp_detail(subject_dir: Path, kp_id: str) -> dict:
    return json.loads((subject_dir / f"知识点及掌握情况/{kp_id}.json").read_text(encoding="utf-8"))


# === Step 1: 初始化 source-sites.json ===

DEFAULT_SOURCES = {
    "语文": {
        "深圳本地": [
            {"name": "深圳教育云", "url": "https://szerc.sz.gov.cn/", "access": "需登录", "vip": False, "owner": "深圳市教育局"},
            {"name": "深圳外国语学校", "url": "https://www.sfls.net.cn/", "access": "公开", "vip": False},
            {"name": "深圳实验学校", "url": "http://www.szsy.net/", "access": "公开", "vip": False},
            {"name": "深圳中学", "url": "https://www.shenzhong.net/", "access": "公开", "vip": False},
            {"name": "深圳百合外国语", "url": "https://www.szbh.net/", "access": "公开", "vip": False},
        ],
        "广东省": [
            {"name": "广东省教育研究院", "url": "http://www.gdedu123.com/", "access": "公开", "vip": False},
            {"name": "广东教育出版社", "url": "http://www.gdtextbook.com/", "access": "公开", "vip": False},
            {"name": "广州市教研院", "url": "https://www.gzedu.gov.cn/", "access": "公开", "vip": False},
        ],
        "其他版本真题": [
            {"name": "人教社官网", "url": "https://www.pep.com.cn/", "access": "公开"},
            {"name": "苏教社", "url": "https://www.108teacher.com/", "access": "公开"},
            {"name": "北师大社", "url": "http://www.bnupg.com/", "access": "公开"},
        ],
        "教辅资源": [
            {"name": "21 世纪教育网", "url": "https://www.21cnjy.com/", "vip": True, "vip_owner": "user"},
            {"name": "学科网", "url": "https://www.zxxk.com/", "vip": True, "vip_owner": "user"},
            {"name": "教习网", "url": "https://www.51jiaoxi.com/", "vip": False},
            {"name": "组卷网", "url": "https://www.zujuan.com/", "vip": True, "vip_owner": "user"},
        ],
        "LLM 兜底": {
            "model": "MiniMax-M3",
            "via": "new-api 网关",
            "fallback_when": "某 KP 搜不到 ≥ 6 道真题",
        },
    },
    "数学": {
        "深圳本地": [
            {"name": "深圳教育云", "url": "https://szerc.sz.gov.cn/", "access": "需登录"},
            {"name": "深圳中学", "url": "https://www.shenzhong.net/"},
            {"name": "深圳外国语学校", "url": "https://www.sfls.net.cn/"},
        ],
        "广东省": [
            {"name": "广东省教育研究院", "url": "http://www.gdedu123.com/"},
            {"name": "广州教研院", "url": "https://www.gzedu.gov.cn/"},
        ],
        "其他版本真题": [
            {"name": "人教社数学", "url": "https://www.pep.com.cn/"},
            {"name": "北师大社", "url": "http://www.bnupg.com/"},
            {"name": "苏教社", "url": "https://www.108teacher.com/"},
        ],
        "教辅资源": [
            {"name": "21 世纪教育网", "url": "https://www.21cnjy.com/", "vip": True},
            {"name": "学科网", "url": "https://www.zxxk.com/", "vip": True},
            {"name": "组卷网", "url": "https://www.zujuan.com/", "vip": True},
        ],
        "LLM 兜底": {
            "model": "MiniMax-M3",
            "via": "new-api 网关",
            "fallback_when": "LLM 主出（数学 LLM 占比 ≥ 60%）",
            "note": "数学结构化强，LLM 出题可控，主用 LLM",
        },
    },
    "英语": {
        "深圳本地": [
            {"name": "深圳教育云", "url": "https://szerc.sz.gov.cn/", "access": "需登录"},
            {"name": "深圳外国语学校", "url": "https://www.sfls.net.cn/", "note": "英语资源最丰富"},
        ],
        "广东省": [
            {"name": "广东教育出版社", "url": "http://www.gdtextbook.com/", "note": "粤教沪外版官方"},
            {"name": "广东省教育研究院", "url": "http://www.gdedu123.com/"},
        ],
        "其他版本真题": [
            {"name": "人教社英语", "url": "https://www.pep.com.cn/"},
            {"name": "外研社", "url": "https://www.fltrp.com/"},
        ],
        "教辅资源": [
            {"name": "21 世纪教育网", "url": "https://www.21cnjy.com/", "vip": True},
            {"name": "学科网", "url": "https://www.zxxk.com/", "vip": True},
            {"name": "组卷网", "url": "https://www.zujuan.com/", "vip": True},
        ],
        "LLM 兜底": {
            "model": "MiniMax-M3",
            "via": "new-api 网关",
            "fallback_when": "某 KP 搜不到 ≥ 6 道真题",
        },
    },
}


def mode_init_sources(args, base_dir: Path):
    """Step 1: 初始化 source-sites.json"""
    subject_dir = base_dir / args.subject
    meta_dir = subject_dir / "测验" / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    sources_file = meta_dir / "source-sites.json"
    sources = DEFAULT_SOURCES.get(args.subject, {})

    output = {
        "subject": args.subject,
        "created_at": now_cst(),
        "updated_at": now_cst(),
        "version": "2026-09-12",
        "sites": sources,
        "notes": [
            "1. 用户可登录 VIP 教辅网（21 世纪教育网/学科网/组卷网）补充账号信息",
            "2. credentials 引用环境变量，不要明文存密码",
            "3. 每搜完一个 KP 必须更新 last_used 字段",
            "4. 新城市/新教材时，整体替换 sites 但保留 schema",
        ],
    }

    sources_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 已生成 {sources_file}")
    print(f"  来源类别数：{len(sources)}")
    for cat, items in sources.items():
        if isinstance(items, list):
            print(f"  {cat}: {len(items)} 个")
        else:
            print(f"  {cat}: {items.get('model', '?')}")


# === Step 2: 按 KP 搜索候选题 ===

SEARCH_TEMPLATES = {
    "语文": {
        "字音字形": "{生字} 读音 拼音 六年级 单元测试",
        "近义词辨析": "{词} 近义词 反义词 六年级 语文",
        "古诗词默写": "{诗名} 默写 六年级上 必背",
        "现代文阅读": "{主题} 阅读理解 六年级 现代文",
        "习作片段": "{主题} 习作 六年级范文",
        "句子理解与改写": "句子改写 六年级 修辞",
    },
    "数学": {
        "计算题": "{关键词} 计算题 六年级 北师大版",
        "应用题": "{关键词} 应用题 六年级 数学",
        "图形与几何": "{图形} 面积 周长 六年级",
        "分数小数百分数": "分数百分数 六年级 应用题",
        "解方程": "解方程 六年级 数学",
    },
    "英语": {
        "单词拼写": "{词} 单词 默写 六年级 粤教沪外",
        "句型转换": "{句型} 句型转换 六年级",
        "时态填空": "{时态} 填空 六年级 英语",
        "阅读理解": "{主题} 阅读理解 六年级",
        "完形填空": "完形填空 六年级 英语",
    },
}


def build_search_queries(args, kp_detail: dict, base_dir: Path) -> list:
    """根据 KP 类型生成搜索词列表"""
    subject = args.subject
    kp_type = kp_detail.get("type", "")
    kp_name = kp_detail.get("name", "")

    templates = SEARCH_TEMPLATES.get(subject, {})

    # 找匹配的模板
    queries = []
    for type_key, tmpl in templates.items():
        if type_key in kp_type or type_key in kp_name:
            query = tmpl.replace("{关键词}", kp_name).replace("{词}", kp_name).replace("{诗名}", kp_name).replace("{主题}", kp_name).replace("{句型}", kp_name).replace("{时态}", kp_name).replace("{图形}", kp_name).replace("{生字}", kp_name)
            queries.append({"type_key": type_key, "query": query, "template": tmpl})

    # 兜底查询
    if not queries:
        queries.append({"type_key": "generic", "query": f"{kp_name} 六年级 单元测试 {subject}", "template": "通用"})

    return queries


def mode_search_kp(args, base_dir: Path):
    """Step 2: 按 KP 搜索候选题（生成搜索词清单 + 候选占位文件）"""
    subject_dir = base_dir / args.subject
    kp_index = load_kp_index(subject_dir)
    kp_detail = load_kp_detail(subject_dir, args.kp_id)

    # 生成搜索词
    queries = build_search_queries(args, kp_detail, base_dir)

    # 创建 candidates 文件（搜索结果待人工/AI 填入）
    meta_dir = subject_dir / "测验/_meta/candidates"
    meta_dir.mkdir(parents=True, exist_ok=True)
    cand_file = meta_dir / f"{args.kp_id}_candidates.json"

    output = {
        "kp_id": args.kp_id,
        "kp_name": kp_detail.get("name", ""),
        "subject": args.subject,
        "searched_at": now_cst(),
        "search_queries": queries,
        "candidates": [],
        "search_instructions": [
            "1. 用上面 search_queries 去对应网站搜索",
            "2. 每搜到一道题，提取：题干/选项/答案/解析/来源URL/网站名",
            "3. 填到 candidates 数组里（candidate_id 自动生成）",
            "4. 至少 10 道候选再走 self-review",
            "5. 真实环境可调用 web_search + web_extract 自动搜（TODO）",
        ],
    }

    cand_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 已生成搜索任务 {cand_file}")
    print(f"  KP: {args.kp_id} ({kp_detail.get('name', '')})")
    print(f"  搜索词数：{len(queries)}")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. [{q['type_key']}] {q['query']}")
    print()
    print(f"📝 候选文件已生成，请人工/搜索工具填入 candidates 数组")
    print(f"   下一步：python quiz-bank-search.py --subject {args.subject} --mode self-review --kp-id {args.kp_id}")


# === Step 3: AI 自审（占位实现，真实环境调 LLM） ===

def mode_self_review(args, base_dir: Path):
    """Step 3: 3 模型投票自审（调 vote-judge.py）"""
    import subprocess
    subject_dir = base_dir / args.subject
    cand_file = subject_dir / f"测验/_meta/candidates/{args.kp_id}_candidates.json"

    if not cand_file.exists():
        print(f"❌ 未找到候选文件：{cand_file}")
        print(f"   请先运行 mode=search-kp")
        sys.exit(1)

    candidates_data = json.loads(cand_file.read_text(encoding="utf-8"))
    candidates = candidates_data.get("candidates", [])

    if not candidates:
        print(f"⚠ candidates 为空，请先填入搜索结果")
        sys.exit(1)

    print(f"⏳ 3 模型投票自审 {len(candidates)} 道候选题...")
    print(f"   调 vote-judge.py 串行调用 MiniMax-M3 + deepseek-v4-pro + muse-spark-1.3-contributor-free")

    cmd = [
        "python",
        str(base_dir / "系统/scripts/vote-judge.py"),
        "--subject", args.subject,
        "--input", str(cand_file),
        "--output", str(cand_file).replace("_candidates.json", "_reviews.json"),
        "--base-dir", str(base_dir),
    ]
    print(f"   执行：{' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    print(r.stdout[-2000:])
    if r.returncode != 0:
        print(f"   ⚠ vote-judge exit {r.returncode}")
        print(f"   stderr: {r.stderr[-1000:]}")

    review_file = str(cand_file).replace("_candidates.json", "_reviews.json")
    if not Path(review_file).exists():
        print(f"❌ vote-judge 未输出 {review_file}")
        sys.exit(1)

    # 把 vote 结果回写到 candidates 里的每个 candidate
    summary = json.loads(Path(review_file).read_text(encoding="utf-8"))
    by_qid = {r["qid"]: r for r in summary.get("results", [])}

    updated = 0
    for cand in candidates:
        qid = cand.get("qid") or f"{args.subject}_{args.kp_id}_{candidates.index(cand)+1:03d}"
        if qid in by_qid:
            cand["self_review"] = {
                "passed": by_qid[qid]["consensus"]["passed"],
                "votes": by_qid[qid]["votes"],
                "errors": by_qid[qid].get("errors", {}),
                "consensus": by_qid[qid]["consensus"],
                "reviewed_at": by_qid[qid]["voted_at"],
            }
            updated += 1

    cand_file.write_text(json.dumps(candidates_data, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(1 for c in candidates if c.get("self_review", {}).get("passed"))
    print(f"\n✓ 自审完成：{passed}/{len(candidates)} 通过")
    print(f"   详细：{review_file}")
    print(f"   下一步：python quiz-bank-search.py --subject {args.subject} --mode insert --kp-id {args.kp_id}")


# === Step 4: 入库 ===

def mode_insert(args, base_dir: Path):
    """Step 4: 入库 + 索引同步"""
    subject_dir = base_dir / args.subject
    cand_file = subject_dir / f"测验/_meta/candidates/{args.kp_id}_candidates.json"

    if not cand_file.exists():
        print(f"❌ 未找到候选文件：{cand_file}")
        sys.exit(1)

    candidates_data = json.loads(cand_file.read_text(encoding="utf-8"))
    candidates = candidates_data.get("candidates", [])

    # 只入通过自审的
    passed = [c for c in candidates if c.get("self_review", {}).get("passed") and c.get("enabled", True)]

    if not passed:
        print(f"⚠ 没有 self_review.passed=true 的候选题")
        sys.exit(1)

    # 1. 写 KP 文件
    unit_id = passed[0].get("unit_id", args.kp_id.split(".")[0])
    unit_dir = subject_dir / "测验" / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    kp_file = unit_dir / f"{args.kp_id}.json"

    existing = []
    if kp_file.exists():
        existing = json.loads(kp_file.read_text(encoding="utf-8"))

    new_qids = set(q["qid"] for q in existing)
    added = []
    for c in passed:
        # 构造符合 schema 的题（参考 quiz-bank-design.md §2）
        q = {
            "qid": c.get("qid") or f"{args.subject}_{args.kp_id}_{len(existing) + len(added) + 1:03d}",
            "subject": args.subject,
            "kp_id": args.kp_id,
            "unit_id": unit_id,
            "difficulty": c.get("difficulty", "中"),
            "type": c.get("type", ""),
            "stem": c.get("stem", ""),
            "options": c.get("options"),
            "answer": c.get("answer"),
            "explanation": c.get("explanation", ""),
            "source": c.get("source", {}),
            "cross_version": c.get("cross_version", {"applicable": True, "reason": "未填"}),
            "self_review": c.get("self_review", {}),
            "enabled": True,
            "created_at": now_cst()[:10],
            "use_count": 0,
        }
        if q["qid"] not in new_qids:
            existing.append(q)
            new_qids.add(q["qid"])
            added.append(q)

    kp_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 更新 by-type 聚合
    if added:
        type_name = added[0].get("type", "未分类")
        by_type_dir = subject_dir / "测验/by-type"
        by_type_dir.mkdir(parents=True, exist_ok=True)
        type_file = by_type_dir / f"{type_name}.json"

        type_existing = []
        if type_file.exists():
            type_existing = json.loads(type_file.read_text(encoding="utf-8"))

        type_qids = set(q["qid"] for q in type_existing)
        for q in added:
            if q["qid"] not in type_qids:
                type_existing.append(q)
                type_qids.add(q["qid"])

        type_file.write_text(json.dumps(type_existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. 更新 index.json
    update_index(base_dir, args.subject, args.kp_id, added)

    # 4. 写 extraction log
    log_file = subject_dir / "测验/_meta/extraction-log.md"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n## {now_cst()[:10]} {args.subject} {args.kp_id} 入库\n")
        f.write(f"- 候选：{len(candidates)} 道\n")
        f.write(f"- 通过：{len(added)} 道\n")
        sources = set(q.get("source", {}).get("site", "?") for q in added)
        f.write(f"- 来源：{', '.join(sources)}\n\n")

    print(f"✓ 已入库 {len(added)} 道题到 {kp_file}")
    if added:
        for q in added[:3]:
            print(f"  - {q['qid']} [{q['difficulty']}] {q['stem'][:40]}...")
    print(f"✓ extraction-log.md 已追加")


def update_index(base_dir: Path, subject: str, kp_id: str, added_questions: list):
    """更新题库 index.json"""
    index_file = base_dir / subject / "测验/index.json"
    if not index_file.exists():
        # 创建新索引
        index = {
            "version": now_cst()[:10],
            "subject": subject,
            "total_kps": 0,
            "total_questions": 0,
            "difficulty_distribution": {"易": 0, "中": 0, "难": 0},
            "kp_coverage": {},
            "source_distribution": {},
            "last_updated": now_cst(),
        }
    else:
        index = json.loads(index_file.read_text(encoding="utf-8"))

    # 更新 KP 覆盖
    if kp_id not in index["kp_coverage"]:
        index["kp_coverage"][kp_id] = {"total": 0, "易": 0, "中": 0, "难": 0, "enabled": 0}

    kp_cov = index["kp_coverage"][kp_id]
    for q in added_questions:
        kp_cov["total"] += 1
        kp_cov["enabled"] += 1
        diff = q.get("difficulty", "中")
        if diff in kp_cov:
            kp_cov[diff] += 1
        if diff in index["difficulty_distribution"]:
            index["difficulty_distribution"][diff] += 1
        index["total_questions"] = index.get("total_questions", 0) + 1

        site = q.get("source", {}).get("site", "其他")
        if site not in index["source_distribution"]:
            index["source_distribution"][site] = 0
        index["source_distribution"][site] += 1

    index["last_updated"] = now_cst()
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="题库搜索引擎（5 步 SOP 自动化）")
    parser.add_argument("--subject", required=True, choices=["数学", "语文", "英语"])
    parser.add_argument("--mode", required=True, choices=["init-sources", "search-kp", "self-review", "insert", "full-cycle"])
    parser.add_argument("--kp-id", help="KP 编号（如 u1.k1）")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()

    base_dir = auto_detect_base_dir() if not args.base_dir else Path(args.base_dir)

    if not (base_dir / args.subject).exists():
        print(f"❌ 未找到科目目录：{base_dir / args.subject}")
        sys.exit(1)

    if args.mode == "init-sources":
        mode_init_sources(args, base_dir)
    elif args.mode == "search-kp":
        if not args.kp_id:
            print("❌ search-kp 必须指定 --kp-id")
            sys.exit(1)
        mode_search_kp(args, base_dir)
    elif args.mode == "self-review":
        if not args.kp_id:
            print("❌ self-review 必须指定 --kp-id")
            sys.exit(1)
        mode_self_review(args, base_dir)
    elif args.mode == "insert":
        if not args.kp_id:
            print("❌ insert 必须指定 --kp-id")
            sys.exit(1)
        mode_insert(args, base_dir)
    elif args.mode == "full-cycle":
        if not args.kp_id:
            print("❌ full-cycle 必须指定 --kp-id")
            sys.exit(1)
        print("⏳ 跑完整 cycle：search-kp → self-review → insert")
        mode_search_kp(args, base_dir)
        input("  按 Enter 继续到 self-review...")
        mode_self_review(args, base_dir)
        input("  按 Enter 继续到 insert...")
        mode_insert(args, base_dir)


if __name__ == "__main__":
    main()
