#!/usr/bin/env python3
"""
HS编码数据命令行导入工具
用法：
    python admin_import.py <excel文件路径>
    python admin_import.py <excel文件路径> --append
"""
import sys
import os
import argparse
import pandas as pd
import sqlite3
import re

def get_db_connection():
    conn = sqlite3.connect('hs_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def import_excel_cli(filepath, clear_existing=True):
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return False

    try:
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath, dtype=str)
        else:
            df = pd.read_excel(filepath, sheet_name=0, dtype=str)

        column_mapping = {
            'hs_code': ['商品编码', 'HS编码', 'HS Code', '海关编码', '商品编号'],
            'name': ['商品名称', '货品名称', '名称'],
            'description': ['商品描述', '描述', '规格型号', '申报要素', '备注'],
            'import_tax_rate': ['最惠国税率', '进口关税率', '进口税率'],
            'vat_rate': ['增值税率', '增值税'],
            'export_rebate_rate': ['出口退税率', '退税率'],
            'supervision_conditions': ['监管条件', '监管类别']
        }

        mapped_cols = {}
        for db_field, possible_names in column_mapping.items():
            for col in df.columns:
                if col in possible_names or col.strip() in possible_names:
                    mapped_cols[db_field] = col
                    break

        if 'hs_code' not in mapped_cols or 'name' not in mapped_cols:
            print(f"❌ Excel中缺少必要列（商品编码/商品名称）")
            print(f"   检测到的列名: {list(df.columns)}")
            return False

        conn = get_db_connection()
        cursor = conn.cursor()

        if clear_existing:
            cursor.execute('DELETE FROM hs_codes')
            print("🗑️  已清空现有数据")

        inserted = 0
        for _, row in df.iterrows():
            hs_code = str(row[mapped_cols['hs_code']]).strip()
            name = str(row[mapped_cols['name']]).strip()
            if not hs_code or hs_code == 'nan' or not name or name == 'nan':
                continue

            description = ''
            if 'description' in mapped_cols:
                description = str(row[mapped_cols['description']])
                if description == 'nan':
                    description = ''

            import_tax = ''
            if 'import_tax_rate' in mapped_cols:
                val = row[mapped_cols['import_tax_rate']]
                if pd.notna(val):
                    import_tax = str(val)

            vat = ''
            if 'vat_rate' in mapped_cols:
                val = row[mapped_cols['vat_rate']]
                if pd.notna(val):
                    vat = str(val)

            export_rebate = ''
            if 'export_rebate_rate' in mapped_cols:
                val = row[mapped_cols['export_rebate_rate']]
                if pd.notna(val):
                    export_rebate = str(val)

            supervision = ''
            if 'supervision_conditions' in mapped_cols:
                val = row[mapped_cols['supervision_conditions']]
                if pd.notna(val):
                    supervision = str(val)

            keywords = re.sub(r'[^\u4e00-\u9fff0-9a-zA-Z]', '', f"{name} {description}")[:80]

            cursor.execute('''
            INSERT OR REPLACE INTO hs_codes (
                hs_code, name, description, category, subcategory,
                supervision_conditions, supervision_description,
                import_tax_rate, vat_rate, export_rebate_rate,
                keywords, material_constraint, parent_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hs_code, name, description, '', '',
                supervision, '',
                import_tax, vat, export_rebate,
                keywords, '', ''
            ))
            inserted += 1

        conn.commit()
        conn.close()
        print(f"✅ 导入完成！共 {inserted} 条记录")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='导入HS编码Excel文件到数据库')
    parser.add_argument('file', help='Excel/CSV文件路径')
    parser.add_argument('--append', action='store_true', help='追加模式（不清空现有数据）')
    args = parser.parse_args()
    import_excel_cli(args.file, clear_existing=not args.append)