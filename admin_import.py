import sqlite3
import pandas as pd
import sys
import os
import re
from pathlib import Path

DB_PATH = 'hs_data.db'

# ██████████████████████████████████████████████
# ██ 列名映射：Excel表头 → 数据库字段
# ██████████████████████████████████████████████
COLUMN_MAP = {
    # 核心字段
    '商品编码': 'hs_code',
    'hs编码': 'hs_code',
    'code': 'hs_code',
    '商品名称': 'name',
    '货品名称': 'name',

    # 描述/申报要素 → 都存入description
    '商品描述': 'description',
    '申报要素': 'description',

    # 税率字段：明确区分，避免覆盖
    '最惠国进口税率': 'import_tax_rate',
    '最惠国税率': 'import_tax_rate',
    '普通进口税率': 'general_import_tax_rate',       # 新字段
    '暂定进口税率': 'temporary_import_tax_rate',     # 新字段
    '消费税率': 'consumption_tax_rate',              # 新字段
    '出口关税率': 'export_tax_rate',                 # 新字段

    '增值税率': 'vat_rate',
    '增值税': 'vat_rate',
    '出口退税率': 'export_rebate_rate',
    '出口退税': 'export_rebate_rate',

    # 单位
    '法定第一单位': 'unit_1',
    '法定第二单位': 'unit_2',

    # 监管及检验
    '海关监管条件': 'supervision_conditions',
    '监管条件': 'supervision_conditions',
    '检验检疫类别': 'inspection_category',

    # 分类
    '大类': 'category',
    '子类': 'subcategory',
}

# ██████████████████████████████████████████████
# ██ 关键词提取函数
# ██████████████████████████████████████████████
def extract_keywords(name, description='', material=''):
    """从商品名称、描述、材质中提取搜索关键词"""
    keywords = set()

    text = f"{name} {description} {material}"
    # 分词：按中文常见分隔符
    parts = re.split(r'[，。；：、；\s/|]+', text)

    # 材质关键词权重
    material_words = ['木', '塑料', '金属', '钢', '铁', '铝', '铜', '玻璃', '陶瓷',
                      '橡胶', '皮革', '纺织', '棉', '丝', '化纤', '竹', '藤', '石']

    for part in parts:
        part = part.strip()
        if len(part) >= 1 and len(part) <= 15:
            keywords.add(part)

    # 额外提取材质词
    for word in material_words:
        if word in name or word in description or word in material:
            keywords.add(word)

    return ' '.join(keywords)

# ██████████████████████████████████████████████
# ██ 监管条件说明映射
# ██████████████████████████████████████████████
SUPERVISION_DESC_MAP = {
    'A': '入境货物通关单',
    'B': '出境货物通关单',
    'M': '进口商品检验',
    'N': '出口商品检验',
    'P': '进境动植物检疫',
    'Q': '出境动植物检疫',
    'R': '进口食品卫生监督检验',
    'S': '出口食品卫生监督检验',
    'V': '自动进口许可证',
    'O': '机电产品自动进口许可证',
    '1': '进口许可证',
    '4': '出口许可证',
    '5': '纺织品临时出口许可证',
    '7': '自动进口许可证(非机电)',
    '9': '禁止进口商品',
    '8': '禁止出口商品',
    'X': '出口许可证(加工贸易)',
    'Y': '出口许可证(边境小额贸易)',
}

def get_supervision_description(codes):
    """将监管条件代码转为中文说明"""
    if not codes or not isinstance(codes, str):
        return ''
    codes = codes.upper().strip()
    descs = [SUPERVISION_DESC_MAP.get(c, c) for c in codes if c.isalpha() or c.isdigit()]
    return '; '.join(descs)

# ██████████████████████████████████████████████
# ██ 导入主函数
# ██████████████████████████████████████████████
def import_excel(file_path):
    """导入Excel/CSV文件到数据库"""

    if not os.path.exists(file_path):
        print(f"❌ 错误：文件不存在 - {file_path}")
        return False

    try:
        # 读取文件
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file_path, dtype=str)

        print(f"📄 读取到 {len(df)} 行数据")
        print(f"📋 列名: {list(df.columns)}")

        # 重命名列
        rename_dict = {}
        for excel_col, db_col in COLUMN_MAP.items():
            if excel_col in df.columns:
                rename_dict[excel_col] = db_col

        df.rename(columns=rename_dict, inplace=True)
        print(f"🔄 映射了 {len(rename_dict)} 个列: {list(rename_dict.keys())}")

        # 确保关键字段存在
        required_fields = ['hs_code', 'name']
        for field in required_fields:
            if field not in df.columns:
                print(f"❌ 错误：缺少必要字段映射 - '{field}'")
                print("   请确保Excel包含「商品编码」或「hs编码」列")
                return False

        # 清理数据
        df = df.dropna(subset=['hs_code', 'name'])
        df['hs_code'] = df['hs_code'].str.strip().str.replace(r'\s+', '', regex=True)
        df['name'] = df['name'].str.strip()

        # 填充缺失字段（保证所有字段都存在，即使为空）
        all_possible_fields = [
            'description', 'import_tax_rate', 'general_import_tax_rate',
            'temporary_import_tax_rate', 'consumption_tax_rate', 'export_tax_rate',
            'vat_rate', 'export_rebate_rate', 'supervision_conditions',
            'unit_1', 'unit_2', 'category', 'subcategory', 'inspection_category'
        ]
        for field in all_possible_fields:
            if field not in df.columns:
                df[field] = ''

        # 生成监管条件说明
        df['supervision_description'] = df['supervision_conditions'].apply(get_supervision_description)

        # 生成关键词
        df['keywords'] = df.apply(
            lambda row: extract_keywords(
                str(row.get('name', '')),
                str(row.get('description', '')),
                ''  # 命令行工具没有单独的material输入，后续可扩展
            ), axis=1
        )

        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查数据库表结构
        cursor.execute("PRAGMA table_info(hs_codes)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        print(f"🗄️  当前数据库字段: {existing_columns}")

        # 清空旧数据
        cursor.execute("DELETE FROM hs_codes")
        print("🗑️  已清空旧数据")

        # 只插入数据库表中实际存在的字段
        insert_fields = [
            'hs_code', 'name', 'description', 'category', 'subcategory',
            'supervision_conditions', 'supervision_description', 'import_tax_rate',
            'general_import_tax_rate', 'temporary_import_tax_rate',
            'consumption_tax_rate', 'export_tax_rate',
            'vat_rate', 'export_rebate_rate', 'keywords', 'material_constraint',
            'parent_code', 'unit_1', 'unit_2', 'inspection_category'
        ]
        available_fields = [f for f in insert_fields if f in existing_columns and f in df.columns]

        if not available_fields:
            print("❌ 错误：没有可插入的字段，请检查数据库表结构")
            conn.close()
            return False

        # 构建INSERT语句
        placeholders = ', '.join(['?' for _ in available_fields])
        fields_str = ', '.join(available_fields)
        sql = f"INSERT INTO hs_codes ({fields_str}) VALUES ({placeholders})"

        inserted = 0
        skipped = 0
        for idx, row in df.iterrows():
            values = []
            for f in available_fields:
                val = row.get(f, '')
                if pd.isna(val) or str(val).strip() == '':
                    values.append('')
                else:
                    values.append(str(val).strip())
            try:
                cursor.execute(sql, values)
                inserted += 1
            except Exception as e:
                skipped += 1
                if skipped <= 5:  # 只打印前5条错误
                    print(f"   ⚠️ 跳过第{idx+2}行: {str(e)[:100]}")

        conn.commit()
        conn.close()

        print(f"✅ 成功导入 {inserted} 条HS编码记录")
        if skipped > 0:
            print(f"⚠️  跳过了 {skipped} 条（共{len(df)}行原始数据）")
        return True

    except Exception as e:
        print(f"❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# ██████████████████████████████████████████████
# ██ 命令行入口
# ██████████████████████████████████████████████
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 60)
        print("  HS编码数据导入工具")
        print("=" * 60)
        print("用法: python admin_import.py <文件路径.xlsx/.csv>")
        print("示例: python admin_import.py HS编码表2026.xlsx")
        print("")
        print("注意：导入前会自动清空数据库中的旧数据")
        print("     请确保Excel包含「商品编码」和「商品名称」列")
        sys.exit(1)

    file_path = sys.argv[1]
    success = import_excel(file_path)
    if not success:
        sys.exit(1)