import markdown
import pdfkit
import sys

# Markdown 파일 읽기
with open('luks-backup-rollback-guide.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# Markdown을 HTML로 변환
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

# HTML 문서 생성
full_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Debian LUKS Multi-Disk Single Passphrase Guide</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{
            font-size: 18pt;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
        }}
        h2 {{
            font-size: 14pt;
            color: #34495e;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 6px;
            margin-top: 20px;
        }}
        pre {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 12px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 9pt;
        }}
        code {{
            background-color: #f8f9fa;
            padding: 2px 5px;
            font-family: monospace;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 6px 10px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

# HTML 파일로 저장 (디버깅용)
with open('temp.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

print("HTML 파일 생성 완료: temp.html")
print("wkhtmltopdf가 설치되어 있어야 PDF 변환이 가능합니다.")
print("설치: https://wkhtmltopdf.org/downloads.html")
