from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import re
from werkzeug.utils import secure_filename
import os
from PIL import Image
import hashlib

app = Flask(__name__)
CORS(app)

# 配置
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB限制
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('hs_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def preprocess_text(text):
    """文本预处理：分词、去停用词、标准化"""
    if not text:
        return ""
    # 转为小写，去除标点
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text.lower())
    # 简单的中文分词（空格分割）
    words = text.split()
    # 移除常见停用词
    stopwords = {'的', '了', '和', '与', '或', '及', '等', '个', '种', '台', '张', '把'}
    filtered = [w for w in words if w not in stopwords]
    return ' '.join(filtered)

def extract_features(text, material, dimensions):
    """从用户输入中提取特征关键词"""
    features = {
        'keywords': [],
        'detected_material': None,
        'dimensions': dimensions
    }
    
    # 关键词提取
    processed = preprocess_text(text)
    features['keywords'] = processed.split()
    
    # 材质检测
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
    """
    基于特征匹配搜索HS编码
    使用加权匹配算法：标题匹配权重高，关键词匹配次之
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 构建搜索条件
    keywords = features['keywords']
    detected_material = features['detected_material']
    
    # 基础查询 - 获取所有编码
    query = "SELECT * FROM hs_codes"
    cursor.execute(query)
    all_codes = cursor.fetchall()
    conn.close()
    
    # 计算每个编码的匹配分数
    results = []
    for code in all_codes:
        score = 0
        match_reasons = []
        
        # 1. 关键词匹配（在商品名称中匹配权重高）
        name = code['name'].lower() if code['name'] else ''
        desc = code['description'].lower() if code['description'] else ''
        code_keywords = code['keywords'].lower() if code['keywords'] else ''
        
        for kw in keywords:
            if kw and len(kw) > 1:  # 忽略单字符
                if kw in name:
                    score += 30
                    match_reasons.append(f"商品名称包含「{kw}」")
                elif kw in desc or kw in code_keywords:
                    score += 15
                    match_reasons.append(f"描述/关键词包含「{kw}」")
        
        # 2. 材质匹配
        material_constraint = code['material_constraint'] if code['material_constraint'] else ''
        if detected_material and material_constraint:
            if detected_material in material_constraint:
                score += 25
                match_reasons.append(f"材质「{detected_material}」符合")
            else:
                # 材质不符合，大幅降分
                score -= 50
                match_reasons.append(f"材质「{detected_material}」可能不匹配")
        
        # 3. 用户输入的材质精确匹配
        if material and material_constraint:
            if any(mat.strip() in material_constraint for mat in material.split(',')):
                score += 20
                match_reasons.append(f"材质描述与约束匹配")
        
        # 4. 编码精度加分（10位编码更精确）
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
                'match_reasons': match_reasons[:3]  # 只保留前3条匹配原因
            })
    
    # 按分数降序排序，取前top_n个
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_image():
    """上传图片（选填）"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 生成唯一文件名
        unique_name = hashlib.md5(f"{filename}{os.urandom(8)}".encode()).hexdigest()[:16]
        extension = filename.rsplit('.', 1)[1].lower()
        saved_name = f"{unique_name}.{extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
        file.save(filepath)
        
        # 简单的图片分析（仅获取基本信息）
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
    """搜索HS编码主接口"""
    data = request.get_json()
    
    # 获取表单数据
    description = data.get('description', '').strip()
    material = data.get('material', '').strip()
    dimensions = data.get('dimensions', '')
    
    # 验证必填字段
    if not description:
        return jsonify({'success': False, 'error': '请填写货物描述'}), 400
    if not material:
        return jsonify({'success': False, 'error': '请填写主要材质'}), 400
    
    # 提取特征
    features = extract_features(description, material, dimensions)
    
    # 搜索HS编码
    results = search_hs_codes(features, material, top_n=3)
    
    # 生成简短说明
    for result in results:
        brief = f"该编码适用于「{result['name']}」，"
        if result['match_reasons']:
            brief += f"匹配依据：{'；'.join(result['match_reasons'])}。"
        else:
            brief += "基于关键词和材质匹配。"
        
        # 添加监管条件说明
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
