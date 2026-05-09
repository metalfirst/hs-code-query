# -*- coding: utf-8 -*-
import os
import re
import sqlite3
import uuid
import base64
import json
import requests
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from PIL import Image

# 阿里云百炼依赖
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# ============================================================
# 配置
# ============================================================
DB_PATH = 'hs_data.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# 阿里云百炼 API 配置（从环境变量读取）
BAILIAN_API_KEY = os.environ.get('BAILIAN_API_KEY', '')
BAILIAN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
BAILIAN_MODEL = 'qwen-vl-max-latest'  # 推荐视觉模型，也可用 qwen-vl-plus-latest

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
# 关键词提取与评分（保留给 /api/search 使用）
# ============================================================
def extract_keywords_from_text(text):
    if not text:
        return []
    parts = re.split(r'[，。；：、；\s/|,;:]+', text)
    return [p.strip() for p in parts if 1 <= len(p.strip()) <= 15]

def extract_material_keywords(material_text):
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
    score = 0
    reasons = []
    
    name = row['name'] or ''
    description = row['description'] or ''
    db_keywords = row['keywords'] or ''
    material_constraint = row['material_constraint'] or ''
    
    query_keywords = extract_keywords_from_text(query_desc)
    material_keywords, detected_material = extract_material_keywords(query_material)
    all_query_words = set(query_keywords + material_keywords)
    
    # 1. 商品名称匹配
    for word in query_keywords:
        if word.lower() in name.lower():
            score += 8
            reasons.append(f'商品名称包含「{word}」')
    
    # 2. 关键词匹配
    db_kw_list = [k.strip().lower() for k in db_keywords.split() if k.strip()]
    matched_kw = [k for k in all_query_words if k.lower() in db_kw_list]
    if matched_kw:
        score += len(matched_kw) * 5
        reasons.append(f'关键词匹配: {", ".join(matched_kw[:3])}')
    
    # 3. 材质匹配
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
# 路由
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')

# HS 编码查询（保留，但你的前端已改用本地数据查询）
@app.route('/api/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    description = data.get('description', '').strip()
    material = data.get('material', '').strip()
    
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
                'match_reasons': reasons,
                'brief': (row['description'] or '')[:120],
                'score': score
            })
    
    scored_results.sort(key=lambda x: x['score'], reverse=True)
    conn.close()
    
    return jsonify({
        'success': True,
        'results': scored_results[:3],
        'features': {'keywords': keywords, 'detected_material': detected_material}
    })

# 原有的文件上传接口（保留，但前端主要用 base64）
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
        'info': {'width': width, 'height': height, 'format': img_format}
    })

# 新增：阿里云百炼视觉分析接口（接收 base64 图片）
@app.route('/api/analyze_image', methods=['POST'])
def analyze_image():
    """调用阿里云百炼视觉模型分析商品图片"""
    try:
        data = request.get_json()
        if not data or 'image_base64' not in data or 'mime_type' not in data:
            return jsonify({'success': False, 'error': '请求体必须包含 image_base64 和 mime_type'}), 400
        
        image_base64 = data['image_base64']
        mime_type = data['mime_type']  # 例如 image/jpeg, image/png
        
        # 检查 API Key
        if not BAILIAN_API_KEY:
            return jsonify({'success': False, 'error': '阿里云百炼 API Key 未配置'}), 500
        
        # 初始化 OpenAI 客户端（指向阿里云百炼兼容端点）
        client = OpenAI(
            api_key=BAILIAN_API_KEY,
            base_url=BAILIAN_BASE_URL,
        )
        
        # 构造消息：图片使用 data:image/...;base64,... 格式嵌入
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业的海关商品归类助手。请分析用户上传的商品图片，提取以下信息，"
                    "并严格按照 JSON 格式返回，不要包含任何其他文字：\n\n"
                    "{\n"
                    '  "objects": [{"name": "物品名称", "confidence": 0.95}],\n'
                    '  "materials": [{"name": "材质", "confidence": 0.9}],\n'
                    '  "raw_description": "一段简短的中文描述，包含物品、材质、主要特征"\n'
                    "}\n"
                    "要求：objects 1-3个，materials 1-3种，只用中文。只返回 JSON。"
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请分析这张商品图片，提取物品、材质和描述"
                    }
                ]
            }
        ]
        
        # 调用大模型
        completion = client.chat.completions.create(
            model=BAILIAN_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        
        content = completion.choices[0].message.content.strip()
        # 清洗可能出现的 markdown 代码块标记
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        analysis = json.loads(content)
        # 确保必要字段存在
        analysis.setdefault('objects', [])
        analysis.setdefault('materials', [])
        analysis.setdefault('raw_description', '')
        
        return jsonify({'success': True, 'analysis': analysis})
    
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'AI 返回格式解析失败，请重试'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'阿里云百炼 API 调用失败: {str(e)}'}), 500

# 禁用 Excel 导入接口
@app.route('/api/import_excel', methods=['POST'])
def import_excel():
    return jsonify({
        'success': False,
        'error': '导入功能已禁用。请使用命令行工具：python admin_import.py 文件.xlsx'
    }), 403

# ============================================================
# 启动（本地开发用，Railway 使用 gunicorn）
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("HS编码智能查询系统启动中...")
    print(f"阿里云百炼 API: {'已配置' if BAILIAN_API_KEY else '❌ 未配置'}")
    print("默认地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)