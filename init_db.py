import sqlite3
import os

DB_PATH = 'hs_data.db'

def init_database():
    """初始化数据库，创建表结构并导入示例数据"""
    
    # 如果数据库已存在，先删除
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️  已删除旧数据库")
    
    # 连接数据库（自动创建）
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ██████████████████████████████████████████████
    # ██ 创建表结构（完整版，包含所有税率字段）
    # ██████████████████████████████████████████████
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hs_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hs_code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            subcategory TEXT,
            supervision_conditions TEXT,
            supervision_description TEXT,
            import_tax_rate TEXT,
            general_import_tax_rate TEXT,
            temporary_import_tax_rate TEXT,
            consumption_tax_rate TEXT,
            export_tax_rate TEXT,
            vat_rate TEXT,
            export_rebate_rate TEXT,
            keywords TEXT,
            material_constraint TEXT,
            parent_code TEXT,
            unit_1 TEXT,
            unit_2 TEXT,
            inspection_category TEXT
        )
    ''')
    
    # ██████████████████████████████████████████████
    # ██ 创建索引（加速查询）
    # ██████████████████████████████████████████████
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hs_code ON hs_codes(hs_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON hs_codes(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords ON hs_codes(keywords)')
    
    # ██████████████████████████████████████████████
    # ██ 插入示例数据（仅用于测试，正式使用会被Excel覆盖）
    # ██████████████████████████████████████████████
    sample_data = [
        {
            'hs_code': '9403609990',
            'name': '其他木家具',
            'description': '非卧室用木制家具，包括办公桌、书架、餐桌等',
            'category': '家具',
            'subcategory': '木制家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单; B:出境货物通关单',
            'import_tax_rate': '0%',
            'general_import_tax_rate': '100%',
            'temporary_import_tax_rate': '',
            'consumption_tax_rate': '',
            'export_tax_rate': '',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '木 家具 办公桌 书架 餐桌 卧室 木制',
            'material_constraint': '木',
            'parent_code': '940360',
            'unit_1': '件',
            'unit_2': '千克',
            'inspection_category': 'P/Q'
        },
        {
            'hs_code': '9403899000',
            'name': '其他材料家具',
            'description': '非卧室用其他材料制家具，包括金属、塑料、竹藤等',
            'category': '家具',
            'subcategory': '其他家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单; B:出境货物通关单',
            'import_tax_rate': '0%',
            'general_import_tax_rate': '100%',
            'temporary_import_tax_rate': '',
            'consumption_tax_rate': '',
            'export_tax_rate': '',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '材料 家具 金属 塑料 竹藤 卧室 办公',
            'material_constraint': '金属 塑料 竹藤',
            'parent_code': '940389',
            'unit_1': '件',
            'unit_2': '千克',
            'inspection_category': 'P/Q'
        },
        {
            'hs_code': '9403509990',
            'name': '其他卧室用木家具',
            'description': '卧室用木制家具，包括床、衣柜、床头柜等',
            'category': '家具',
            'subcategory': '木制家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单; B:出境货物通关单',
            'import_tax_rate': '0%',
            'general_import_tax_rate': '100%',
            'temporary_import_tax_rate': '',
            'consumption_tax_rate': '',
            'export_tax_rate': '',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '卧室 木 家具 床 衣柜 床头柜',
            'material_constraint': '木',
            'parent_code': '940350',
            'unit_1': '件',
            'unit_2': '千克',
            'inspection_category': 'P/Q'
        },
        {
            'hs_code': '9403200000',
            'name': '其他金属家具',
            'description': '非卧室用金属家具，包括金属桌、金属椅、金属架等',
            'category': '家具',
            'subcategory': '金属家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单; B:出境货物通关单',
            'import_tax_rate': '0%',
            'general_import_tax_rate': '100%',
            'temporary_import_tax_rate': '',
            'consumption_tax_rate': '',
            'export_tax_rate': '',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '金属 家具 桌 椅 架 铁 钢 铝',
            'material_constraint': '金属',
            'parent_code': '940320',
            'unit_1': '件',
            'unit_2': '千克',
            'inspection_category': 'P/Q'
        },
        {
            'hs_code': '9401690000',
            'name': '其他木框架坐具',
            'description': '木框架坐具，包括木椅、木凳、木沙发等',
            'category': '家具',
            'subcategory': '坐具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单; B:出境货物通关单',
            'import_tax_rate': '0%',
            'general_import_tax_rate': '100%',
            'temporary_import_tax_rate': '',
            'consumption_tax_rate': '',
            'export_tax_rate': '',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '木 框架 坐具 椅 凳 沙发',
            'material_constraint': '木',
            'parent_code': '940169',
            'unit_1': '件',
            'unit_2': '千克',
            'inspection_category': 'P/Q'
        }
    ]
    
    # 插入示例数据
    for data in sample_data:
        cursor.execute('''
            INSERT INTO hs_codes (
                hs_code, name, description, category, subcategory,
                supervision_conditions, supervision_description,
                import_tax_rate, general_import_tax_rate,
                temporary_import_tax_rate, consumption_tax_rate,
                export_tax_rate, vat_rate, export_rebate_rate,
                keywords, material_constraint, parent_code,
                unit_1, unit_2, inspection_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['hs_code'], data['name'], data['description'],
            data['category'], data['subcategory'],
            data['supervision_conditions'], data['supervision_description'],
            data['import_tax_rate'], data['general_import_tax_rate'],
            data['temporary_import_tax_rate'], data['consumption_tax_rate'],
            data['export_tax_rate'], data['vat_rate'], data['export_rebate_rate'],
            data['keywords'], data['material_constraint'], data['parent_code'],
            data['unit_1'], data['unit_2'], data['inspection_category']
        ))
    
    conn.commit()
    conn.close()
    
    print("=" * 50)
    print("✅ 数据库初始化完成！")
    print(f"📁 数据库文件: {os.path.abspath(DB_PATH)}")
    print(f"📊 已导入 {len(sample_data)} 条示例数据（家具类）")
    print("")
    print("📌 下一步操作：")
    print("  1. 用管理员工具导入真实数据：")
    print("     python admin_import.py 你的2026年HS编码表.xlsx")
    print("  2. 或启动Web应用：")
    print("     python app.py")
    print("=" * 50)

if __name__ == '__main__':
    init_database()