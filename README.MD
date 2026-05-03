HS编码智能查询系统
基于 Flask + SQLite 的 HS 编码智能归类工具，支持商品描述、材质、尺寸及图片辅助识别，并提供 Excel 批量导入功能。

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask Version](https://img.shields.io/badge/flask-2.3.2-green)
![SQLite Version](https://img.shields.io/badge/sqlite-3-red)
![License](https://img.shields.io/badge/license-MIT-lightgrey)


📖 项目简介
本项目是一个用于中国海关进出口商品 HS 编码查询的开源 Web 应用。通过自然语言描述、材质信息、商品尺寸以及上传图片，系统会自动匹配最合适的 HS 编码，并展示对应的进口税率、增值税率、出口退税率及监管条件。同时，系统支持批量导入 Excel 格式的最新海关税则表，方便企业关务人员快速获取商品归类信息。

✨ 功能特性
🔍 智能匹配：基于商品名称、描述、材质及关键词的加权评分算法，返回 TOP-3 推荐编码

🖼️ 图片上传：支持上传商品图片（仅存储预览，后续可集成 OCR/CLIP 增强识别）

📊 Excel 批量导入：支持 .xlsx / .xls / .csv 格式，自动映射列名并导入最新税则数据

📈 完整税则信息：展示最惠国税率、增值税率、出口退税率、监管条件及说明

📱 响应式界面：移动端友好，卡片式布局，支持拖拽上传

📂 SQLite 数据库：轻量级存储，无需额外数据库服务

🛠️ 技术栈
层面	技术
后端框架	Flask 2.3.2, Flask-CORS
数据库	SQLite3
Excel 处理	Pandas, OpenPyXL
图片处理	Pillow
前端	HTML5, CSS3 (原生), Fetch API
部署方式	支持本地运行 / Docker / 云服务器
📦 安装与运行
1. 克隆仓库
bash
git clone https://github.com/metalfirst/hs-code-query.git
cd hs-code-query
2. 创建虚拟环境（推荐）
bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
3. 安装依赖
bash
pip install -r requirements.txt
requirements.txt 内容示例：

text
Flask==2.3.2
flask-cors==4.0.0
Pillow==10.0.0
pandas==2.0.3
openpyxl==3.1.2
4. 初始化数据库
bash
python init_db.py
该脚本会自动创建 hs_data.db 并导入少量示例数据（家具类）。生产环境中请使用 Excel 导入功能覆盖真实数据。

5. 运行应用
bash
python app.py
默认访问地址：http://127.0.0.1:5000

🚀 使用指南
查询 HS 编码
填写货物描述（必填），例如：儿童学习写字桌，可升降，带书架

填写主要材质（必填），例如：实木、塑料+金属

可选填写尺寸或上传商品图片

点击“开始查询”，系统返回最多 3 条推荐编码，包含：

HS 编码及商品名称

进口关税、增值税、出口退税

监管条件及说明

匹配原因简述

批量导入 Excel 税则表
在页面底部找到“批量导入HS编码表”区域

点击选择 Excel 文件（.xlsx, .xls, .csv）

点击“上传并导入数据库”

系统自动识别列名（支持“商品编码”、“商品名称”、“最惠国税率”等常见列）

导入成功后，旧数据会被替换（可修改 app.py 中的 DELETE 语句改为追加模式）

⚠️ 注意：导入操作会清空现有数据，请务必提前备份数据库文件 hs_data.db。

📡 API 接口文档
1. 查询 HS 编码
URL：/api/search

Method：POST

Content-Type：application/json

请求体：

json
{
  "description": "儿童学习写字桌 实木",
  "material": "实木",
  "dimensions": "120x60x75cm"
}
成功响应 (200)：

json
{
  "success": true,
  "results": [
    {
      "hs_code": "9403609990",
      "name": "其他木家具",
      "description": "非卧室用木制家具...",
      "import_tax_rate": "0%",
      "vat_rate": "13%",
      "export_rebate_rate": "13%",
      "supervision_conditions": "AB",
      "supervision_description": "A:入境货物通关单;B:出境货物通关单",
      "match_reasons": ["商品名称包含「学习」", "材质「实木」符合"],
      "brief": "该编码适用于「其他木家具」...",
      "score": 85
    }
  ],
  "features": {
    "keywords": ["儿童", "学习", "写字", "桌", "实木"],
    "detected_material": "木质"
  }
}
2. 上传图片
URL：/api/upload

Method：POST

Content-Type：multipart/form-data

参数：image (文件，支持 jpg/png/gif)

成功响应：

json
{
  "success": true,
  "filename": "abc123.jpg",
  "info": {
    "width": 800,
    "height": 600,
    "format": "JPEG"
  }
}
3. 导入 Excel
URL：/api/import_excel

Method：POST

Content-Type：multipart/form-data

参数：file (Excel/CSV 文件)

成功响应：

json
{
  "success": true,
  "message": "成功导入 12580 条HS编码记录",
  "total": 12580
}
🗄️ 数据库结构
表名：hs_codes

字段名	类型	说明
id	INTEGER	主键自增
hs_code	TEXT	HS 编码（10位）
name	TEXT	商品名称
description	TEXT	商品描述
category	TEXT	大类（可留空或后期生成）
subcategory	TEXT	子类
supervision_conditions	TEXT	监管条件代码（如 AB）
supervision_description	TEXT	监管条件中文说明
import_tax_rate	TEXT	最惠国进口税率
vat_rate	TEXT	增值税率
export_rebate_rate	TEXT	出口退税率
keywords	TEXT	搜索关键词（自动生成）
material_constraint	TEXT	材质约束关键词（可人工维护）
parent_code	TEXT	父级编码（预留）
导入 Excel 时，脚本会自动适配常见列名（商品编码、商品名称、最惠国税率等），其他未映射字段留空。

📂 项目结构
text
hs-code-query/
├── app.py               # Flask 主程序
├── init_db.py           # 数据库初始化脚本（含示例数据）
├── requirements.txt     # Python 依赖
├── templates/
│   └── index.html       # 前端页面
├── static/
│   └── style.css        # 样式文件（可选）
├── uploads/             # 上传图片临时存放目录（自动创建）
└── hs_data.db           # SQLite 数据库（首次运行自动生成）
💡 优化建议与未来计划
当前版本已实现基础查询与导入功能，后续计划包括：

全文搜索：集成 SQLite FTS5，大幅提升检索性能

评分算法优化：引入同义词词典、编码层级权重

图片识别集成：调用 OCR/CLIP 提取图片中的商品特征

用户系统：查询历史、收藏常用编码

RESTful API 规范化：版本管理、统一错误码

Docker 容器化部署：一键启动

对接海关总署最新税则：自动更新提醒

欢迎社区贡献代码或提出建议！

🤝 贡献指南
Fork 本仓库

创建特性分支 (git checkout -b feature/AmazingFeature)

提交更改 (git commit -m 'Add some AmazingFeature')

推送到分支 (git push origin feature/AmazingFeature)

开启 Pull Request

请确保代码符合 PEP8 规范，并为新功能添加必要的注释。

📄 许可证
本项目采用 MIT 许可证，详情参见 LICENSE 文件。

📧 联系方式
项目作者：metalfirst
GitHub 仓库：https://github.com/metalfirst/hs-code-query
如有问题请提交[Issue](https://github.com/metalfirst/hs-code-query/issues)