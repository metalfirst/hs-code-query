import sqlite3
import json

def init_database():
    """初始化数据库，创建表并导入示例数据"""
    conn = sqlite3.connect('hs_data.db')
    cursor = conn.cursor()
    
    # 创建表
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
        vat_rate TEXT,
        export_rebate_rate TEXT,
        keywords TEXT,
        material_constraint TEXT,
        parent_code TEXT
    )
    ''')
    
    # 示例数据（家具类，与您的儿童写字桌需求相关）
    sample_data = [
        {
            'hs_code': '9403609990',
            'name': '其他木家具',
            'description': '非卧室用木制家具，包括密度板、刨花板等人造板材制品',
            'category': '家具',
            'subcategory': '木家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单;B:出境货物通关单',
            'import_tax_rate': '0%',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '木制 木质 家具 桌 椅 柜 写字桌 学习桌 折叠 儿童 非卧室',
            'material_constraint': '木质,实木,人造板,密度板,刨花板,MDF'
        },
        {
            'hs_code': '9403700000',
            'name': '塑料家具',
            'description': '塑料制的家具，包括儿童用塑料桌椅',
            'category': '家具',
            'subcategory': '塑料家具',
            'supervision_conditions': '',
            'supervision_description': '无特殊监管要求',
            'import_tax_rate': '0%',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '塑料 塑胶 家具 桌 椅 儿童 折叠',
            'material_constraint': '塑料,塑胶,PVC,PE,PP,ABS'
        },
        {
            'hs_code': '9403899090',
            'name': '其他材料制家具',
            'description': '其他未列名材料制成的家具',
            'category': '家具',
            'subcategory': '其他材料家具',
            'supervision_conditions': '',
            'supervision_description': '无特殊监管要求',
            'import_tax_rate': '0%',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '其他 材料 家具',
            'material_constraint': '石材,玻璃,陶瓷,藤,竹'
        },
        {
            'hs_code': '9403509990',
            'name': '卧室用其他木家具',
            'description': '卧室用木制家具，包括床、床头柜、衣柜、梳妆台等',
            'category': '家具',
            'subcategory': '木家具',
            'supervision_conditions': 'AB',
            'supervision_description': 'A:入境货物通关单;B:出境货物通关单',
            'import_tax_rate': '0%',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '木制 木质 家具 卧室 床 床头柜 衣柜 梳妆台',
            'material_constraint': '木质,实木,人造板,密度板,刨花板'
        },
        {
            'hs_code': '9401790090',
            'name': '其他金属框架坐具',
            'description': '金属框架的座椅，非皮革软垫',
            'category': '家具',
            'subcategory': '金属家具',
            'supervision_conditions': '',
            'supervision_description': '无特殊监管要求',
            'import_tax_rate': '0%',
            'vat_rate': '13%',
            'export_rebate_rate': '13%',
            'keywords': '金属 框架 座椅 椅子 折叠 儿童',
            'material_constraint': '金属,铁,钢,不锈钢,铝'
        }
    ]
    
    # 清空现有数据（可选）
    cursor.execute('DELETE FROM hs_codes')
    
    # 插入数据
    for item in sample_data:
        cursor.execute('''
        INSERT INTO hs_codes (
            hs_code, name, description, category, subcategory,
            supervision_conditions, supervision_description,
            import_tax_rate, vat_rate, export_rebate_rate,
            keywords, material_constraint
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['hs_code'], item['name'], item['description'],
            item['category'], item['subcategory'],
            item['supervision_conditions'], item['supervision_description'],
            item['import_tax_rate'], item['vat_rate'], item['export_rebate_rate'],
            item['keywords'], item['material_constraint']
        ))
    
    conn.commit()
    conn.close()
    print("数据库初始化完成！已导入", len(sample_data), "条示例数据")
    print("请根据需要添加更多HS编码数据")

if __name__ == '__main__':
    init_database()