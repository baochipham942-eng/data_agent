#!/usr/bin/env python3
"""检查数据库状态脚本"""
import sqlite3
from pathlib import Path

system_db = Path("logs/system.db")
if not system_db.exists():
    print(f"❌ 系统数据库不存在: {system_db}")
    exit(1)

conn = sqlite3.connect(str(system_db))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("数据库状态检查")
print("=" * 60)

# 1. Prompt激活状态
print("\n1. Prompt激活状态:")
cur.execute("SELECT name, version, is_active FROM prompt_versions ORDER BY name, version")
prompts = cur.fetchall()
prompt_groups = {}
for p in prompts:
    name = p["name"]
    if name not in prompt_groups:
        prompt_groups[name] = []
    prompt_groups[name].append((p["version"], p["is_active"]))

for name, versions in prompt_groups.items():
    print(f"\n  {name}:")
    for version, is_active in versions:
        status = "✅ 已激活" if is_active else "⚪ 未激活"
        print(f"    {version}: {status}")

# 2. 业务知识库
print("\n2. 业务知识库:")
cur.execute("SELECT COUNT(*) as count FROM business_terms")
terms_count = cur.fetchone()["count"]
cur.execute("SELECT COUNT(*) as count FROM field_mappings")
mappings_count = cur.fetchone()["count"]
cur.execute("SELECT COUNT(*) as count FROM time_rules")
rules_count = cur.fetchone()["count"]
print(f"  业务术语: {terms_count}")
print(f"  字段映射: {mappings_count}")
print(f"  时间规则: {rules_count}")

# 3. Schema记忆
print("\n3. Schema记忆:")
cur.execute("SELECT COUNT(*) as count FROM text_memory")
text_count = cur.fetchone()["count"]
print(f"  Schema记忆数量: {text_count}")

# 4. SQL学习记录
print("\n4. SQL学习记录:")
cur.execute("SELECT COUNT(*) as count FROM tool_memory")
tool_count = cur.fetchone()["count"]
cur.execute("SELECT COUNT(*) as count FROM tool_memory WHERE success = 1")
success_count = cur.fetchone()["count"]
print(f"  总记录: {tool_count}")
print(f"  成功记录: {success_count}")

# 5. RAG高分案例
print("\n5. RAG高分案例:")
cur.execute("SELECT COUNT(*) as count FROM rag_qa_pairs WHERE score >= 4.0")
rag_high_count = cur.fetchone()["count"]
cur.execute("SELECT COUNT(*) as count FROM rag_qa_pairs")
rag_total_count = cur.fetchone()["count"]
print(f"  总分案例: {rag_total_count}")
print(f"  高分案例(>=4.0): {rag_high_count}")

conn.close()
print("\n" + "=" * 60)









