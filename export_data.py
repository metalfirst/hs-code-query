import sqlite3
import json
import os

DB_PATH = 'hs_data.db'
OUTPUT_FILE = 'hscode_data.js'

def export_to_js():
    # 1. 检查数据库是否存在
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件 {DB_PATH} 不存在，请先运行 admin_import.py 导入数据")
        return

    # 2. 读取全部数据
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果可以用列名访问
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hs_codes")
    rows = cursor.fetchall()

    # 3. 转换为字典列表（只保留前端需要的字段）
    data = []
    for row in rows:
        data.append({
            'hs_code': row['hs_code'] or '',
            'name': row['name'] or '',
            'description': row['description'] or '',
            'keywords': row['keywords'] or '',
            'material_constraint': row['material_constraint'] or '',
            'import_tax_rate': row['import_tax_rate'] or '',
            'general_import_tax_rate': row['general_import_tax_rate'] or '',
            'temporary_import_tax_rate': row['temporary_import_tax_rate'] or '',
            'consumption_tax_rate': row['consumption_tax_rate'] or '',
            'export_tax_rate': row['export_tax_rate'] or '',
            'vat_rate': row['vat_rate'] or '',
            'export_rebate_rate': row['export_rebate_rate'] or '',
            'supervision_conditions': row['supervision_conditions'] or '',
            'supervision_description': row['supervision_description'] or '',
            'unit_1': row['unit_1'] or '',
            'unit_2': row['unit_2'] or '',
        })

    # 4. 生成 JavaScript 文件
    js_content = f"const HS_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};"

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_content)

    conn.close()
    print(f"✅ 已导出 {len(data)} 条记录到 {OUTPUT_FILE}")

if __name__ == '__main__':
    export_to_js()