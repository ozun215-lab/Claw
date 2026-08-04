import markdown
import os
import sys

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

# Markdown 파일 읽기
md_path = r'D:\Claw\workspace\luks-backup-rollback-guide.md'
with open(md_path, 'r', encoding='utf-8') as f:
    md_content = f.read()

# Markdown을 HTML로 변환
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

# 개선된 CSS 스타일
css_style = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        color: #666;
    }
}

body {
    font-family: "Malgun Gothic", "맑은 고딕", "Nanum Gothic", "나눔고딕", "Noto Sans KR", sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #2c3e50;
    background: #fff;
}

/* 제목 스타일 */
h1 {
    font-size: 24pt;
    color: #1a252f;
    border-bottom: 4px solid #e74c3c;
    padding-bottom: 15px;
    margin-top: 0;
    margin-bottom: 25px;
    page-break-after: avoid;
}

h2 {
    font-size: 16pt;
    color: #2980b9;
    border-left: 5px solid #3498db;
    border-bottom: 2px solid #ecf0f1;
    padding: 10px 15px;
    margin-top: 30px;
    margin-bottom: 15px;
    background: linear-gradient(90deg, #f8f9fa 0%, transparent 100%);
    page-break-after: avoid;
}

h3 {
    font-size: 13pt;
    color: #27ae60;
    margin-top: 20px;
    margin-bottom: 10px;
    page-break-after: avoid;
}

/* 코드 블록 */
pre {
    background-color: #f4f6f7;
    border: 1px solid #d5dbdb;
    border-left: 4px solid #e74c3c;
    border-radius: 0 5px 5px 0;
    padding: 15px;
    overflow-x: auto;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: 9pt;
    line-height: 1.5;
    margin: 15px 0;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}

code {
    background-color: #f0f3f4;
    color: #c0392b;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Consolas", "Monaco", monospace;
    font-size: 9.5pt;
    border: 1px solid #e5e8e8;
}

pre code {
    background: none;
    color: inherit;
    padding: 0;
    border: none;
}

/* 표 스타일 */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-size: 10pt;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

th {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 12px;
    text-align: left;
    font-weight: 600;
    border: 1px solid #5a67d8;
}

td {
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
    background: #fff;
}

tr:nth-child(even) td {
    background: #f8fafc;
}

tr:hover td {
    background: #edf2f7;
}

/* 인용구/박스 */
blockquote {
    border-left: 5px solid #3498db;
    margin: 15px 0;
    padding: 15px 20px;
    background: linear-gradient(90deg, #ebf5fb 0%, #f8f9fa 100%);
    font-style: normal;
    color: #2c3e50;
    border-radius: 0 5px 5px 0;
}

/* 목록 */
ul, ol {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin: 8px 0;
    line-height: 1.6;
}

li::marker {
    color: #3498db;
    font-weight: bold;
}

/* 수평선 */
hr {
    border: none;
    height: 3px;
    background: linear-gradient(90deg, #3498db 0%, transparent 100%);
    margin: 30px 0;
}

/* 강조 텍스트 */
strong {
    color: #e74c3c;
    font-weight: 600;
}

em {
    color: #8e44ad;
    font-style: italic;
}

/* 페이지 나누기 */
.page-break {
    page-break-before: always;
}
"""

# HTML 문서 생성
full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Debian LUKS Multi-Disk Single Passphrase Guide</title>
    <style>{css_style}</style>
</head>
<body>
    {html_content}
</body>
</html>"""

# HTML 파일 저장
html_path = r'D:\Claw\workspace\temp_v2.html'
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(full_html)

print(f"HTML file created: {html_path}")
print(f"File size: {os.path.getsize(html_path):,} bytes")
