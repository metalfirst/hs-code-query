# -*- coding: utf-8 -*-
import os
import re
import sqlite3
import uuid
import base64
import json
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from PIL import Image
import requests  # 用于调用 DeepSeek API

app = Flask(__name__)
CORS(app)

# ============================================================
# 配置
# ============================================================
DB_PATH = 'hs_data.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"  # 支持视觉的模型

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# ============================================================
# 数据库工具
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================
# 关键词提取与评分
# ============================================================
def extract_keywords_from_text(text):
    """从文本中提取关键词"""
    if not text:
        return []
    parts = re.split(r'[，。；：、；\s/|,;:]+', text)
    keywords = []
    for p in parts:
        p = p.strip()
        if 1 <= len(p) <= 15:
            keywords.append(p)
    return keywords

def extract_material_keywords(material_text):
    """从材质描述中提取关键词"""
    if not material_text:
        return [], '未知'
    material_text = material_text.strip()
    material_map = {
        '木': '木质', '实木': '木质', '板材': '木质', '竹': '竹制', '藤': '藤制',
        '钢': '钢制', '铁': '铁制', '铝': '铝制', '铜': '铜制', '金属': '金属',
        '不锈钢': '不锈钢', '合金': '合金',
        '塑料': '塑料', '树脂': '塑料', '亚克力': '塑料', 'pp': '塑料', 'pe': '塑料', 'pvc': '塑料',
        '玻璃': '玻璃', '陶瓷': '陶瓷', '石材': '石材', '大理石': '石材',
        '橡胶': '橡胶', '硅胶': '橡胶',
        '皮革': '皮革', '真皮': '皮革', 'pu皮': '皮革',
        '纺织': '纺织', '棉': '纺织', '麻': '纺织', '丝': '纺织', '化纤': '纺织', '涤纶': '纺织', '尼龙': '纺织',
        '纸': '纸质', '纸板': '纸质',
    }
    detected = '未知'
    for key, val in material_map.items():
        if key in material_text:
            detected = val
            break
    return extract_keywords_from_text(material_text), detected

def calculate_match_score(query_desc, query_material, row):
    """计算匹配分数"""
    score = 0
    reasons = []
    
    name = row['name'] or ''
    description = row['description'] or ''
    db_keywords = row['keywords'] or ''
    material_constraint = row['material_constraint'] or ''
    
    query_keywords = extract_keywords_from_text(query_desc)
    material_keywords, detected_material = extract_material_keywords(query_material)
    all_query_words = set(query_keywords + material_keywords)
    
    # 1. 商品名称匹配 (40分)
    name_lower = name.lower()
    for word in query_keywords:
        if word.lower() in name_lower:
            score += 8
            reasons.append(f'商品名称包含「{word}」')
    
    # 2. 关键词匹配 (35分)
    db_kw_list = [k.strip().lower() for k in db_keywords.split() if k.strip()]
    for word in all_query_words:
        if word.lower() in db_kw_list:
            score += 5
    if db_kw_list:
        matched_kw = [k for k in all_query_words if k.lower() in db_kw_list]
        if matched_kw:
            reasons.append(f'关键词匹配: {", ".join(matched_kw[:3])}')
    
    # 3. 材质匹配 (25分)
    for word in material_keywords:
        if word in material_constraint or word in description or word in name:
            score += 8
            reasons.append(f'材质「{word}」符合')
    if detected_material != '未知':
        if detected_material in material_constraint or detected_material in description:
            score += 10
            reasons.append(f'材质类型「{detected_material}」匹配')
    
    return min(score, 100), reasons[:5]

# ============================================================
# DeepSeek API 调用
# ============================================================
def analyze_image_with_deepseek(image_path):
    """
    使用 DeepSeek API 分析商品图片，提取物品、材质、描述
    返回格式：
    {
        "objects": [{"name": "桌子", "confidence": 0.95}, ...],
        "materials": [{"name": "实木", "confidence": 0.9}, ...],
        "raw_description": "一张实木学习桌，带书架"
    }
    """
    if DEEPSEEK_API_KEY == "你的API_KEY":
        raise ValueError("请先在 app.py 中配置 DEEPSEEK_API_KEY")

    # 读取图片并转为 base64
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    # 获取图片格式
    ext = image_path.rsplit('.', 1)[-1].lower()
    mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
    mime_type = mime_map.get(ext, 'image/jpeg')

    # 构造请求
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": """你是一个专业的海关商品归类助手。请分析用户上传的商品图片，提取以下信息，并严格按照 JSON 格式返回，不要包含任何其他文字：

{
  "objects": [{"name": "物品名称", "confidence": 0.0~1.0}],
  "materials": [{"name": "材质名称", "confidence": 0.0~1.0}],
  "raw_description": "一段简短的中文描述，包含物品名称、材质、主要特征"
}

要求：
1. objects 列出图片中识别到的商品物品（1-3个），confidence 表示确信度
2. materials 列出推测的材质（1-3种），使用中文（如：实木、不锈钢、塑料、棉、陶瓷等）
3. raw_description 是一句完整的中文描述，适合用于HS编码搜索
4. 只返回 JSON，不要带 ```json 标记或任何解释"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请分析这张商品图片，提取物品、材质和描述"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.3
    }

    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    content = result['choices'][0]['message']['content'].strip()
    
    # 清理可能的 markdown 标记
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    
    analysis = json.loads(content)
    
    # 确保必要字段存在
    analysis.setdefault('objects', [])
    analysis.setdefault('materials', [])
    analysis.setdefault('raw_description', '')
    
    return analysis

# ============================================================
# 路由：首页
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')

# ============================================================
# API：查询HS编码
# ============================================================
@app.route('/api/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    description = data.get('description', '').strip()
    material = data.get('material', '').strip()
    dimensions = data.get('dimensions', '').strip()
    
    if not description or not material:
        return jsonify({'success': False, 'error': '请提供货物描述和材质'}), 400
    
    keywords = extract_keywords_from_text(description)
    material_keywords, detected_material = extract_material_keywords(material)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hs_codes")
    rows = cursor.fetchall()
    
    scored_results = []
    for row in rows:
        score, reasons = calculate_match_score(description, material, row)
        if score > 0:
            scored_results.append({
                'hs_code': row['hs_code'],
                'name': row['name'],
                'description': row['description'],
                'import_tax_rate': row['import_tax_rate'],
                'general_import_tax_rate': row['general_import_tax_rate'] if 'general_import_tax_rate' in row.keys() else '',
                'temporary_import_tax_rate': row['temporary_import_tax_rate'] if 'temporary_import_tax_rate' in row.keys() else '',
                'consumption_tax_rate': row['consumption_tax_rate'] if 'consumption_tax_rate' in row.keys() else '',
                'export_tax_rate': row['export_tax_rate'] if 'export_tax_rate' in row.keys() else '',
                'vat_rate': row['vat_rate'],
                'export_rebate_rate': row['export_rebate_rate'],
                'supervision_conditions': row['supervision_conditions'],
                'supervision_description': row['supervision_description'],
                'unit_1': row['unit_1'] if 'unit_1' in row.keys() else '',
                'unit_2': row['unit_2'] if 'unit_2' in row.keys() else '',
                'match_reasons': reasons,
                'brief': row['description'][:120] if row['description'] else '',
                'score': score
            })
    
    scored_results.sort(key=lambda x: x['score'], reverse=True)
    top_results = scored_results[:3]
    
    conn.close()
    
    return jsonify({
        'success': True,
        'results': top_results,
        'features': {
            'keywords': keywords,
            'detected_material': detected_material,
        }
    })

# ============================================================
# API：AI 图片分析（新增）
# ============================================================
@app.route('/api/analyze_image', methods=['POST'])
def analyze_image():
    """接收图片，调用 DeepSeek 进行商品识别"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '未找到图片文件'}), 400
    
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的文件格式，请上传 JPG/PNG/GIF/WebP'}), 400
    
    # 保存临时文件
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"analyze_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        # 调用 DeepSeek 分析
        analysis = analyze_image_with_deepseek(filepath)
        return jsonify({
            'success': True,
            'analysis': analysis,
            'filename': filename
        })
    except ValueError as e:
        # API Key 未配置
        return jsonify({'success': False, 'error': str(e)}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'DeepSeek API 调用失败: {str(e)}'}), 500
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'AI 返回格式解析失败，请重试'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'分析失败: {str(e)}'}), 500
    finally:
        # 清理临时文件
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

# ============================================================
# API：上传图片（保留原接口）
# ============================================================
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '未找到图片文件'}), 400
    
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的文件格式'}), 400
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        img = Image.open(filepath)
        width, height = img.size
        img_format = img.format
    except Exception:
        width, height, img_format = 0, 0, 'Unknown'
    
    return jsonify({
        'success': True,
        'filename': filename,
        'info': {
            'width': width,
            'height': height,
            'format': img_format
        }
    })

# ============================================================
# API：导入Excel（已禁用）
# ============================================================
@app.route('/api/import_excel', methods=['POST'])
def import_excel():
    return jsonify({
        'success': False,
        'error': '导入功能已禁用。如需更新数据，请使用命令行工具：python admin_import.py 文件.xlsx'
    }), 403

# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("HS编码智能查询系统启动中...")
    print(f"DeepSeek API: {'已配置' if DEEPSEEK_API_KEY != '你的API_KEY' else '❌ 未配置，图片分析不可用'}")
    print("默认地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
