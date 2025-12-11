#!/usr/bin/env python3
"""激活v1.0版本的所有prompt类型"""
import sqlite3
from pathlib import Path

system_db = Path("logs/system.db")
if not system_db.exists():
    print(f"❌ 系统数据库不存在: {system_db}")
    exit(1)

conn = sqlite3.connect(str(system_db))
cur = conn.cursor()

# 获取所有prompt类型
prompt_names = [
    'system_prompt',
    'judge_prompt',
    'sql_fix_prompt',
    'sql_modify_prompt',
    'table_select_prompt',
    'rewrite_prompt',
    'intent_classify_prompt',
    'summary_prompt',
    'contact_expert_email',
]

version = 'v1.0'
print(f"正在激活所有prompt类型的 {version} 版本...")

activated_count = 0
for name in prompt_names:
    # 先取消该名称的所有激活状态
    cur.execute("UPDATE prompt_versions SET is_active = 0 WHERE name = ?", (name,))
    
    # 激活v1.0版本
    cur.execute("""
        UPDATE prompt_versions 
        SET is_active = 1 
        WHERE name = ? AND version = ?
    """, (name, version))
    
    if cur.rowcount > 0:
        print(f"  ✅ 已激活 {name} {version}")
        activated_count += 1
    else:
        print(f"  ⚠️  {name} {version} 不存在")

conn.commit()
conn.close()

print(f"\n完成！共激活 {activated_count} 个prompt类型")









