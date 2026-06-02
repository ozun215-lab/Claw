// generate-docx.js
// Node.js + jszip ?쇰줈 libvirt-win11-boot-optimization.md ??.docx 蹂??// Open XML (OOXML) 理쒖냼 援ъ“濡?吏곸젒 ?앹꽦

const fs   = require('fs');
const path = require('path');
const JSZip = require('C:\\Users\\zunn\\AppData\\Roaming\\Genspark Claw\\bundled-resources\\openclaw\\node_modules\\jszip');

const WORKSPACE = path.dirname(__filename);
const MD_FILE   = path.join(WORKSPACE, 'libvirt-win11-boot-optimization.md');
const OUT_FILE  = path.join(WORKSPACE, 'libvirt-win11-boot-optimization.docx');

// ?? 留덊겕?ㅼ슫 ?뚯떛 (媛꾨떒 ?뚯꽌) ????????????????????????????????????????????????
function parseMd(md) {
  const lines = md.split('\n');
  const blocks = [];
  let inCode = false, codeLang = '', codeLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (!inCode) {
        inCode = true;
        codeLang = line.slice(3).trim();
        codeLines = [];
      } else {
        blocks.push({ type: 'code', lang: codeLang, text: codeLines.join('\n') });
        inCode = false; codeLines = []; codeLang = '';
      }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }

    if (/^#{1,6}\s/.test(line)) {
      const m = line.match(/^(#{1,6})\s+(.*)/);
      blocks.push({ type: 'heading', level: m[1].length, text: m[2].replace(/\s*\{.*\}$/, '') });
    } else if (/^>\s/.test(line)) {
      blocks.push({ type: 'quote', text: line.replace(/^>\s*/, '') });
    } else if (/^[-*]\s/.test(line)) {
      blocks.push({ type: 'li', text: line.replace(/^[-*]\s/, '') });
    } else if (/^\d+\.\s/.test(line)) {
      blocks.push({ type: 'oli', text: line.replace(/^\d+\.\s/, '') });
    } else if (/^\|/.test(line) && line.includes('|')) {
      blocks.push({ type: 'table_row', text: line });
    } else if (/^---+$/.test(line.trim())) {
      blocks.push({ type: 'hr' });
    } else if (line.trim() === '') {
      blocks.push({ type: 'empty' });
    } else {
      blocks.push({ type: 'para', text: line });
    }
  }
  return blocks;
}

// ?? XML ?댁뒪耳?댄봽 ????????????????????????????????????????????????????????????
function esc(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ?? ?몃씪??留덊겕?ㅼ슫 泥섎━ (bold/code/italic) ??????????????????????????????????
function inlineToXml(text) {
  // **bold**, `code`, *italic* 泥섎━
  const parts = [];
  let rest = text;

  // 媛꾨떒 ?좏겕?섏씠?
  while (rest.length > 0) {
    const boldM   = rest.match(/^\*\*(.+?)\*\*/);
    const codeM   = rest.match(/^`([^`]+)`/);
    const italicM = rest.match(/^\*(.+?)\*/);
    const linkM   = rest.match(/^\[([^\]]+)\]\([^)]+\)/);

    if (boldM) {
      parts.push(`<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">${esc(boldM[1])}</w:t></w:r>`);
      rest = rest.slice(boldM[0].length);
    } else if (codeM) {
      parts.push(`<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/><w:color w:val="C7254E"/></w:rPr><w:t xml:space="preserve">${esc(codeM[1])}</w:t></w:r>`);
      rest = rest.slice(codeM[0].length);
    } else if (italicM) {
      parts.push(`<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">${esc(italicM[1])}</w:t></w:r>`);
      rest = rest.slice(italicM[0].length);
    } else if (linkM) {
      parts.push(`<w:r><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr><w:t xml:space="preserve">${esc(linkM[1])}</w:t></w:r>`);
      rest = rest.slice(linkM[0].length);
    } else {
      // 일반 문자
      let endIdx = 1;
      while (endIdx < rest.length && !/[*`\[]/.test(rest[endIdx])) endIdx++;
      parts.push(`<w:r><w:t xml:space="preserve">${esc(rest.slice(0, endIdx))}</w:t></w:r>`);
      rest = rest.slice(endIdx);
    }
  }
  return parts.join('');
}

// ?? ?⑤씫 XML ?앹꽦 ?????????????????????????????????????????????????????????????
function makeHeading(level, text) {
  const styleMap = { 1:'Heading1', 2:'Heading2', 3:'Heading3', 4:'Heading4', 5:'Heading5', 6:'Heading6' };
  const style = styleMap[level] || 'Heading1';
  return `<w:p><w:pPr><w:pStyle w:val="${style}"/></w:pPr>${inlineToXml(text)}</w:p>`;
}

function makePara(text, styleId) {
  const style = styleId ? `<w:pPr><w:pStyle w:val="${styleId}"/></w:pPr>` : '';
  return `<w:p>${style}${inlineToXml(text)}</w:p>`;
}

function makeCode(text) {
  const lines = text.split('\n');
  return lines.map(l =>
    `<w:p><w:pPr><w:pStyle w:val="CodeBlock"/></w:pPr>` +
    `<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr>` +
    `<w:t xml:space="preserve">${esc(l)}</w:t></w:r></w:p>`
  ).join('\n');
}

function makeListItem(text, ordered) {
  const numId = ordered ? '2' : '1';
  return `<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="${numId}"/></w:numPr></w:pPr>${inlineToXml(text)}</w:p>`;
}

function makeQuote(text) {
  return `<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr>${inlineToXml(text)}</w:p>`;
}

function makeHr() {
  return `<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="CCCCCC"/></w:pBdr></w:pPr></w:p>`;
}

// ?뚯씠釉????뚯떛
function makeTable(rows) {
  const dataRows = rows.filter(r => !r.text.match(/^[\s|:-]+$/));
  if (dataRows.length < 2) return dataRows.map(r => makePara(r.text)).join('\n');

  const header = dataRows[0].text.split('|').map(c => c.trim()).filter(c => c);
  const body   = dataRows.slice(1);

  const headerXml = header.map(c =>
    `<w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="2E74B5"/></w:tcPr>` +
    `<w:p><w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr><w:t xml:space="preserve">${esc(c)}</w:t></w:r></w:p></w:tc>`
  ).join('');

  const bodyXml = body.map((r, ri) => {
    const cells = r.text.split('|').map(c => c.trim()).filter(c => c);
    const fill  = ri % 2 === 0 ? 'FFFFFF' : 'EEF3F8';
    const cellsXml = cells.map(c =>
      `<w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="${fill}"/></w:tcPr>` +
      `<w:p>${inlineToXml(c)}</w:p></w:tc>`
    ).join('');
    return `<w:tr>${cellsXml}</w:tr>`;
  }).join('\n');

  return `<w:tbl>
    <w:tblPr>
      <w:tblStyle w:val="TableGrid"/>
      <w:tblW w:w="9000" w:type="dxa"/>
      <w:tblBorders>
        <w:top w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:left w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:bottom w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:right w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:insideH w:val="single" w:sz="4" w:color="BDD7EE"/>
        <w:insideV w:val="single" w:sz="4" w:color="BDD7EE"/>
      </w:tblBorders>
    </w:tblPr>
    <w:tr>${headerXml}</w:tr>
    ${bodyXml}
  </w:tbl>`;
}

// ?? ?꾩껜 釉붾줉 ??document.xml body ????????????????????????????????????????????
function blocksToXml(blocks) {
  const xmlParts = [];
  let i = 0;

  while (i < blocks.length) {
    const b = blocks[i];

    if (b.type === 'heading') {
      xmlParts.push(makeHeading(b.level, b.text));
      i++;
    } else if (b.type === 'code') {
      xmlParts.push(makeCode(b.text));
      i++;
    } else if (b.type === 'quote') {
      xmlParts.push(makeQuote(b.text));
      i++;
    } else if (b.type === 'li') {
      xmlParts.push(makeListItem(b.text, false));
      i++;
    } else if (b.type === 'oli') {
      xmlParts.push(makeListItem(b.text, true));
      i++;
    } else if (b.type === 'hr') {
      xmlParts.push(makeHr());
      i++;
    } else if (b.type === 'table_row') {
      // ?뚯씠釉????섏쭛
      const tableRows = [];
      while (i < blocks.length && blocks[i].type === 'table_row') {
        tableRows.push(blocks[i]);
        i++;
      }
      xmlParts.push(makeTable(tableRows));
    } else if (b.type === 'para' && b.text && b.text.trim()) {
      xmlParts.push(makePara(b.text));
      i++;
    } else {
      i++;
    }
  }
  return xmlParts.join('\n');
}

// ?? OOXML ?뚯씪 援ъ꽦 ???????????????????????????????????????????????????????????
function buildDocx(bodyXml) {
  // [Content_Types].xml
  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/word/document.xml"  ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml"  ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>`;

  // _rels/.rels
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

  // word/_rels/document.xml.rels
  const docRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"    Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"  Target="settings.xml"/>
</Relationships>`;

  // word/document.xml
  const document = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
            xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
            xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
${bodyXml}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080"/>
    </w:sectPr>
  </w:body>
</w:document>`;

  // word/styles.xml
  const styles = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="留묒? 怨좊뵓" w:hAnsi="留묒? 怨좊뵓" w:cs="留묒? 怨좊뵓"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr></w:rPrDefault>
  </w:docDefaults>

  <w:style w:type="paragraph" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:numPr><w:ilvl w:val="0"/></w:numPr>
      <w:spacing w:before="480" w:after="160"/>
      <w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="2E74B5"/></w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="留묒? 怨좊뵓" w:hAnsi="留묒? 怨좊뵓"/>
      <w:b/><w:color w:val="2E74B5"/><w:sz w:val="40"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="360" w:after="120"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="留묒? 怨좊뵓" w:hAnsi="留묒? 怨좊뵓"/>
      <w:b/><w:color w:val="2E74B5"/><w:sz w:val="32"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="留묒? 怨좊뵓" w:hAnsi="留묒? 怨좊뵓"/>
      <w:b/><w:color w:val="1F4E79"/><w:sz w:val="26"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading4">
    <w:name w:val="heading 4"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="200" w:after="60"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="留묒? 怨좊뵓" w:hAnsi="留묒? 怨좊뵓"/>
      <w:b/><w:i/><w:color w:val="2E74B5"/><w:sz w:val="24"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="CodeBlock"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
      <w:shd w:val="clear" w:color="auto" w:fill="F5F5F5"/>
      <w:pBdr>
        <w:top    w:val="single" w:sz="4" w:space="2" w:color="CCCCCC"/>
        <w:left   w:val="single" w:sz="12" w:space="4" w:color="2E74B5"/>
        <w:bottom w:val="single" w:sz="4" w:space="2" w:color="CCCCCC"/>
        <w:right  w:val="single" w:sz="4" w:space="2" w:color="CCCCCC"/>
      </w:pBdr>
      <w:ind w:left="240" w:right="240"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>
      <w:sz w:val="18"/><w:color w:val="333333"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Quote">
    <w:name w:val="Quote"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:ind w:left="480"/>
      <w:shd w:val="clear" w:color="auto" w:fill="EBF3FB"/>
      <w:pBdr>
        <w:left w:val="single" w:sz="16" w:space="4" w:color="2E74B5"/>
      </w:pBdr>
    </w:pPr>
    <w:rPr><w:i/><w:color w:val="555555"/></w:rPr>
  </w:style>

  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:tblPr>
      <w:tblBorders>
        <w:top    w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:left   w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:bottom w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:right  w:val="single" w:sz="4" w:color="2E74B5"/>
        <w:insideH w:val="single" w:sz="4" w:color="BDD7EE"/>
        <w:insideV w:val="single" w:sz="4" w:color="BDD7EE"/>
      </w:tblBorders>
    </w:tblPr>
    <w:tcPr><w:tcMar>
      <w:top    w:w="80"  w:type="dxa"/>
      <w:left   w:w="120" w:type="dxa"/>
      <w:bottom w:w="80"  w:type="dxa"/>
      <w:right  w:w="120" w:type="dxa"/>
    </w:tcMar></w:tcPr>
  </w:style>
</w:styles>`;

  // word/numbering.xml (bullet + ordered list)
  const numbering = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/>
      <w:lvlText w:val="??/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="480" w:hanging="240"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="480" w:hanging="240"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>`;

  // word/settings.xml
  const settings = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="709"/>
  <w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>`;

  return { contentTypes, rels, docRels, document, styles, numbering, settings };
}

// ?? 硫붿씤 ?????????????????????????????????????????????????????????????????????
async function main() {
  console.log('Reading markdown...');
  const md = fs.readFileSync(MD_FILE, 'utf-8');

  console.log('Parsing blocks...');
  const blocks = parseMd(md);

  console.log(`Total blocks: ${blocks.length}`);
  const bodyXml = blocksToXml(blocks);

  console.log('Building OOXML structure...');
  const parts = buildDocx(bodyXml);

  console.log('Creating ZIP (docx)...');
  const zip = new JSZip();
  zip.file('[Content_Types].xml', parts.contentTypes);
  zip.file('_rels/.rels',         parts.rels);
  zip.file('word/document.xml',   parts.document);
  zip.file('word/styles.xml',     parts.styles);
  zip.file('word/numbering.xml',  parts.numbering);
  zip.file('word/settings.xml',   parts.settings);
  zip.file('word/_rels/document.xml.rels', parts.docRels);

  const buf = await zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 }
  });

  fs.writeFileSync(OUT_FILE, buf);
  console.log(`??????꾨즺: ${OUT_FILE}`);
  console.log(`   ?뚯씪 ?ш린: ${(buf.length / 1024).toFixed(1)} KB`);
}

main().catch(err => { console.error('ERROR:', err); process.exit(1); });



