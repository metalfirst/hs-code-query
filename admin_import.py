import sqlite3
import pandas as pd
import sys
import os
import re

DB_PATH = 'hs_data.db'

COLUMN_MAP = {
    '商品编码': 'hs_code', 'hs编码': 'hs_code', 'code': 'hs_code',
    '商品名称': 'name', '货品名称': 'name',
    '商品描述': 'description', '申报要素': 'description',
    '最惠国进口税率': 'import_tax_rate', '最惠国税率': 'import_tax_rate',
    '普通进口税率': 'general_import_tax_rate',
    '暂定进口税率': 'temporary_import_tax_rate',
    '消费税率': 'consumption_tax_rate',
    '出口关税率': 'export_tax_rate',
    '增值税率': 'vat_rate', '增值税': 'vat_rate',
    '出口退税率': 'export_rebate_rate', '出口退税': 'export_rebate_rate',
    '法定第一单位': 'unit_1', '法定第二单位': 'unit_2',
    '海关监管条件': 'supervision_conditions', '监管条件': 'supervision_conditions',
    '检验检疫类别': 'inspection_category',
    '大类': 'category', '子类': 'subcategory',
}

def extract_keywords(name, description='', material=''):
    keywords = set()
    text = f"{name} {description} {material}"
    parts = re.split(r'[，。；：、；\s/|]+', text)
    material_words = ['木', '塑料', '金属', '钢', '铁', '铝', '铜', '玻璃', '陶瓷',
                      '橡胶', '皮革', '纺织', '棉', '丝', '化纤', '竹', '藤', '石']
    for part in parts:
        part = part.strip()
        if len(part) >= 1 and len(part) <= 15:
            keywords.add(part)
    for word in material_words:
        if word in name or word in description or word in material:
            keywords.add(word)
    return ' '.join(keywords)

SUPERVISION_DESC_MAP = {
    'A':'入境货物通关单','B':'出境货物通关单','M':'进口商品检验','N':'出口商品检验',
    'P':'进境动植物检疫','Q':'出境动植物检疫','R':'进口食品卫生监督检验','S':'出口食品卫生监督检验',
    'V':'自动进口许可证','O':'机电产品自动进口许可证','1':'进口许可证','4':'出口许可证',
    '5':'纺织品临时出口许可证','7':'自动进口许可证(非机电)','9':'禁止进口商品','8':'禁止出口商品',
    'X':'出口许可证(加工贸易)','Y':'出口许可证(边境小额贸易)',
}

def get_supervision_description(codes):
    if not codes or not isinstance(codes, str):
        return ''
    codes = codes.upper().strip()
    descs = [SUPERVISION_DESC_MAP.get(c, c) for c in codes if c.isalpha() or c.isdigit()]
    return '; '.join(descs)

def import_excel(file_path):
    if not os.path.exists(file_path):
        print(f"❌ 错误：文件不存在 - {file_path}")
        return False

    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file_path, dtype=str)

        print(f"📄 读取到 {len(df)} 行数据")
        print(f"📋 原始列名: {list(df.columns)}")

        # 1. 构建重命名字典（严格去重）
        rename_dict = {}
        used_targets = set()
        for src_col, target_col in COLUMN_MAP.items():
            if src_col in df.columns and target_col not in used_targets:
                rename_dict[src_col] = target_col
                used_targets.add(target_col)
        print(f"🔄 实际映射列: {list(rename_dict.keys())}")

        # 2. 重命名
        df.rename(columns=rename_dict, inplace=True)

        # 3. 删除任何重复列（保留第一次出现）
        df = df.loc[:, ~df.columns.duplicated(keep='first')]

        # 4. 确保关键字段
        if 'hs_code' not in df.columns or 'name' not in df.columns:
            print("❌ 缺少关键列 hs_code 或 name")
            return False

        # 5. 清洗基础数据
        df['hs_code'] = df['hs_code'].str.strip().str.replace(r'\s+', '', regex=True)
        df['name'] = df['name'].str.strip()

        # 6. 补全缺失字段（统一填充空字符串）
        needed_fields = [
            'description', 'import_tax_rate', 'general_import_tax_rate',
            'temporary_import_tax_rate', 'consumption_tax_rate', 'export_tax_rate',
            'vat_rate', 'export_rebate_rate', 'supervision_conditions',
            'unit_1', 'unit_2', 'category', 'subcategory', 'inspection_category'
        ]
        for f in needed_fields:
            if f not in df.columns:
                df[f] = ''

        # 7. 生成监管描述和关键词（现在都是标量，安全）
        df['supervision_description'] = df['supervision_conditions'].apply(get_supervision_description)
        df['keywords'] = df.apply(
            lambda row: extract_keywords(str(row['name']), str(row['description']), ''), axis=1
        )

        # 8. 转换为字典列表，彻底消除 Series 歧义
        records = df.to_dict(orient='records')

        # 9. 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(hs_codes)")
        existing_cols = [col[1] for col in cursor.fetchall()]
        print(f"🗄️ 数据库字段: {existing_cols}")

        cursor.execute("DELETE FROM hs_codes")
        print("🗑️ 已清空旧数据")

        insert_fields = [
            'hs_code', 'name', 'description', 'category', 'subcategory',
            'supervision_conditions', 'supervision_description', 'import_tax_rate',
            'general_import_tax_rate', 'temporary_import_tax_rate',
            'consumption_tax_rate', 'export_tax_rate', 'vat_rate', 'export_rebate_rate',
            'keywords', 'material_constraint', 'parent_code', 'unit_1', 'unit_2', 'inspection_category'
        ]
        avail = [f for f in insert_fields if f in existing_cols]
        if not avail:
            print("❌ 没有可插入的字段")
            conn.close()
            return False

        placeholders = ', '.join(['?' for _ in avail])
        sql = f"INSERT INTO hs_codes ({', '.join(avail)}) VALUES ({placeholders})"

        inserted = 0
        skipped = 0
        for idx, row in enumerate(records, start=1):
            values = []
            for f in avail:
                # 直接从字典取值，并转为字符串，安全处理 NaN
                val = row.get(f, '')
                if pd.isna(val) if isinstance(val, float) else False:
                    val = ''
                else:
                    val = str(val).strip()
                values.append(val)
            try:
                cursor.execute(sql, values)
                inserted += 1
            except Exception as e:
                skipped += 1
                if skipped <= 5:
                    print(f"   ⚠️ 跳过第 {idx} 行: {str(e)[:100]}")

        conn.commit()
        conn.close()
        print(f"✅ 成功导入 {inserted} 条记录（跳过 {skipped} 条）")
        return True

    except Exception as e:
        print(f"❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python admin_import.py <文件路径.xlsx/.csv>")
        sys.exit(1)
    import_excel(sys.argv[1])