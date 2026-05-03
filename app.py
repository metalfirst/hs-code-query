from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import re
import os
import hashlib
from werkzeug.utils import secure_filename
from PIL import Image
import pandas as pd

app = Flask(__name__)
CORS(app)

# ==================== 配置 ====================
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 是否允许通过 Web 上传 Excel（默认 False，生产环境建议保持关闭）
ALLOW_WEB_IMPORT = os.environ.get('ALLOW_WEB_IMPORT', 'False').lower() == 'true'

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== 数据库初始化 ====================
def init_db():
    conn = sqlite3.connect('hs_data.db')
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()
    print("数据库表已就绪")

init_db()

# ==================== 辅助函数 ====================
def get_db_connection():
    conn = sqlite3.connect('hs_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_text(text):
    if not text:
        return ""
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text.lower())
    words = text.split()
    stopwords = {'的', '了', '和', '与', '或', '及', '等', '个', '种', '台', '张', '把'}
    filtered = [w for w in words if w not in stopwords]
    return ' '.join(filtered)

def extract_features(text, material, dimensions):
    features = {
        'keywords': [],
        'detected_material': None,
        'dimensions': dimensions
    }
    processed = preprocess_text(text)
    features['keywords'] = processed.split()

    material_keywords = {
        '木质': ['木', '木质', '木制', '实木', '人造板', '密度板', '刨花板', '中纤板', 'MDF'],
        '塑料': ['塑料', '塑胶', 'PVC', 'PE', 'PP', 'ABS', '亚克力', '树脂'],
        '金属': ['金属', '铁', '钢', '不锈钢', '铝', '合金', '铸铁', '铜'],
        '纺织': ['布', '织物', '纺织', '棉', '毛', '丝', '化纤', '涤纶', '尼龙'],
        '玻璃': ['玻璃', '水晶', '钢化'],
        '皮革': ['皮革', '皮', '真皮', 'PU皮', '人造革'],
        '陶瓷': ['陶瓷', '瓷', '陶'],
        '石材': ['石', '石材', '大理石', '花岗岩']
    }

    for material_type, keywords in material_keywords.items():
        for kw in keywords:
            if kw in text or (material and kw in material):
                features['detected_material'] = material_type
                break
        if features['detected_material']:
            break
    return features

def search_hs_codes(features, material, top_n=3):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hs_codes")
    all_codes = cursor.fetchall()
    conn.close()

    keywords = features['keywords']
    detected_material = features['detected_material']
    results = []

    for code in all_codes:
        score = 0
        match_reasons = []
        name = code['name'].lower() if code['name'] else ''
        desc = code['description'].lower() if code['description'] else ''
        code_keywords = code['keywords'].lower() if code['keywords'] else ''

        for kw in keywords:
            if kw and len(kw) > 1:
                if kw in name:
                    score += 30
                    match_reasons.append(f"商品名称包含「{kw}」")
                elif kw in desc or kw in code_keywords:
                    score += 15
                    match_reasons.append(f"描述/关键词包含「{kw}」")

        material_constraint = code['material_constraint'] if code['material_constraint'] else ''
        if detected_material and material_constraint:
            if detected_material in material_constraint:
                score += 25
                match_reasons.append(f"材质「{detected_material}」符合")
            else:
                score -= 50
                match_reasons.append(f"材质「{detected_material}」可能不匹配")

        if material and material_constraint:
            if any(mat.strip() in material_constraint for mat in material.split(',')):
                score += 20
                match_reasons.append(f"材质描述与约束匹配")

        if len(code['hs_code']) >= 10:
            score += 5

        if score > 0:
            results.append({
                'hs_code': code['hs_code'],
                'name': code['name'],
                'description': code['description'],
                'supervision_conditions': code['supervision_conditions'],
                'supervision_description': code['supervision_description'],
                'import_tax_rate': code['import_tax_rate'],
                'vat_rate': code['vat_rate'],
                'export_rebate_rate': code['export_rebate_rate'],
                'score': score,
                'match_reasons': match_reasons[:3]
            })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]

# ==================== 公共导入函数（供命令行复用） ====================
def import_excel_data(filepath, clear_existing=True):
    """
    从 Excel/CSV 文件导入数据到 hs_codes 表
    :param filepath: 文件路径
    :param clear_existing: 是否清空现有数据（默认 True）
    :return: (success, message, inserted_count)
    """
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
            raise ValueError(f'Excel中缺少必要列，检测到的列：{list(df.columns)}')

        conn = get_db_connection()
        cursor = conn.cursor()

        if clear_existing:
            cursor.execute('DELETE FROM hs_codes')

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
        return True, f'成功导入 {inserted} 条记录', inserted
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e), 0

# ==================== 路由 ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = hashlib.md5(f"{filename}{os.urandom(8)}".encode()).hexdigest()[:16]
        extension = filename.rsplit('.', 1)[1].lower()
        saved_name = f"{unique_name}.{extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
        file.save(filepath)

        try:
            with Image.open(filepath) as img:
                width, height = img.size
                image_info = {
                    'filename': saved_name,
                    'width': width,
                    'height': height,
                    'format': img.format
                }
        except Exception as e:
            image_info = {'filename': saved_name, 'error': str(e)}

        return jsonify({
            'success': True,
            'filename': saved_name,
            'info': image_info
        })

    return jsonify({'success': False, 'error': 'Invalid file type'}), 400

@app.route('/api/search', methods=['POST'])
def search():
    data = request.get_json()
    description = data.get('description', '').strip()
    material = data.get('material', '').strip()
    dimensions = data.get('dimensions', '')

    if not description:
        return jsonify({'success': False, 'error': '请填写货物描述'}), 400
    if not material:
        return jsonify({'success': False, 'error': '请填写主要材质'}), 400

    features = extract_features(description, material, dimensions)
    results = search_hs_codes(features, material, top_n=3)

    for result in results:
        brief = f"该编码适用于「{result['name']}」，"
        if result['match_reasons']:
            brief += f"匹配依据：{'；'.join(result['match_reasons'])}。"
        else:
            brief += "基于关键词和材质匹配。"

        if result['supervision_conditions']:
            if 'B' in result['supervision_conditions']:
                brief += "【注意】该编码含有木质成分或动植物产品，出口需办理商检（出境货物通关单）。"
            elif 'A' in result['supervision_conditions']:
                brief += "该编码入境需办理入境货物通关单。"

        result['brief'] = brief

    return jsonify({
        'success': True,
        'results': results,
        'features': {
            'keywords': features['keywords'][:10],
            'detected_material': features['detected_material']
        }
    })

@app.route('/api/import_excel', methods=['POST'])
def import_excel():
    if not ALLOW_WEB_IMPORT:
        return jsonify({'success': False, 'error': '导入功能已禁用，请使用命令行工具（python admin_import.py）更新数据'}), 403

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未接收到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400

    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
        return jsonify({'success': False, 'error': '文件格式错误，需要 .xlsx, .xls 或 .csv 文件'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"import_{filename}")
    file.save(filepath)

    try:
        success, message, count = import_excel_data(filepath, clear_existing=True)
        if success:
            return jsonify({'success': True, 'message': message, 'total': count})
        else:
            return jsonify({'success': False, 'error': message}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

# ==================== 启动应用 ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)