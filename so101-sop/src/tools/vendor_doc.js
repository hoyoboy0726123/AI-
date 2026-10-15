// Generate the vendor print-order brief for SO-101 parts as a Word document.
// usage: NODE_PATH=<folder with the docx npm package> node src/tools/vendor_doc.js "docs/SO-101_廠商列印需求說明.docx"
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, LevelFormat, BorderStyle, Footer, PageNumber, TableLayoutType, ImageRun,
} = require('docx');
const ROOT = path.resolve(__dirname, '../..');

const OUT = process.argv[2];
const GREEN = '1D6B4F', GREEN_SOFT = 'DCEBE3', AMBER_SOFT = 'F8EDD6', RED = 'AE2A20', GREY = 'CFD9D3', INK2 = '4C5C54';
const FONT = { ascii: 'Arial', hAnsi: 'Arial', eastAsia: 'Microsoft JhengHei', cs: 'Arial' };
const W = 9638; // A4 width 11906 minus 2 cm margins

const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], spacing: { after: 120, line: 320 }, ...o });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text)], spacing: { before: 320, after: 140 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREEN, space: 4 } } });
const num = (runs, ref = 'num', level = 0) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], numbering: { reference: ref, level }, spacing: { after: 80, line: 300 } });
const bullet = (runs) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], numbering: { reference: 'bullet', level: 0 }, spacing: { after: 80, line: 300 } });
const b = (text) => t(text, { bold: true });

const border = { style: BorderStyle.SINGLE, size: 4, color: GREY };
const borders = { top: border, bottom: border, left: border, right: border };
function cell(content, width, o = {}) {
  const paras = (Array.isArray(content) ? content : [content]).map(c => c instanceof Paragraph ? c
    : new Paragraph({ children: Array.isArray(c) ? c : [t(String(c), o.bold ? { bold: true } : {})], alignment: o.align, spacing: { before: 40, after: 40 } }));
  return new TableCell({ children: paras, width: { size: width, type: WidthType.DXA }, borders,
    shading: o.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fill } : undefined,
    margins: { top: 60, bottom: 60, left: 110, right: 110 } });
}
function table(widths, header, rows, o = {}) {
  const head = new TableRow({ tableHeader: true, children: header.map((h, i) => cell([[t(h, { bold: true, color: 'FFFFFF' })]], widths[i], { fill: GREEN })) });
  const body = rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(Array.isArray(c) ? [c] : c, widths[i],
    { align: (o.right || []).includes(i) ? AlignmentType.RIGHT : (o.center || []).includes(i) ? AlignmentType.CENTER : undefined,
      fill: o.total && ri === rows.length - 1 ? GREEN_SOFT : undefined })) }));
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, rows: [head, ...body] });
}
function callout(title, text, fill, color) {
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [new TableCell({
    width: { size: W, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, color: 'auto', fill },
    borders: { top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' }, bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' }, left: { style: BorderStyle.SINGLE, size: 24, color } },
    margins: { top: 100, bottom: 100, left: 180, right: 180 },
    children: [new Paragraph({ children: [t(title, { bold: true, color })], spacing: { after: 60 } }),
      new Paragraph({ children: Array.isArray(text) ? text : [t(text)], spacing: { line: 300 } })] })] })] });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 60 } });

const shared = [
  ['Base_SO101', '底座'], ['Base_motor_holder_SO101', '馬達 1 固定座'], ['Motor_holder_SO101_Base', '馬達 2 固定座'],
  ['Rotation_Pitch_SO101', '肩部零件'], ['Upper_arm_SO101', '上臂'], ['Under_arm_SO101', '前臂'],
  ['Motor_holder_SO101_Wrist', '馬達 4 固定座'], ['Wrist_Roll_Pitch_SO101', '手腕座'], ['WaveShare_Mounting_Plate_SO101', '驅動板固定板（Waveshare 版）'],
];
const single = [
  ['Wrist_Roll_Follower_SO101', '夾爪本體（執行臂）'], ['Moving_Jaw_SO101', '活動爪（執行臂）'],
  ['Wrist_Roll_SO101', '主控臂手腕座'], ['Handle_SO101', '握把（主控臂）'], ['Trigger_SO101', '扳機（主控臂）'],
];
const partRows = [
  ...shared.map(([f, n], i) => [String(i + 1), [t(f + '.stl', { font: { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: 'Microsoft JhengHei' }, size: 19 })], n, '2']),
  ...single.map(([f, n], i) => [String(shared.length + i + 1), [t(f + '.stl', { font: { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: 'Microsoft JhengHei' }, size: 19 })], n, '1']),
  ['', [b('合計')], '', [b('23')]],
];

const doc = new Document({
  creator: 'SO-101 專案', title: 'SO-101 機械手臂零件列印需求說明',
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: '16201B' } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { size: 40, bold: true, font: FONT, color: '16201B' }, paragraph: { spacing: { after: 80 } } },
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: GREEN }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 0 } },
    ],
  },
  numbering: { config: [
    { reference: 'bullet', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 300 } } } }] },
    ...['num', 'num2', 'num3', 'num4', 'num5'].map(ref => ({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 360 } } } }] })),
  ] },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t('SO-101 零件列印需求說明　第 ', { size: 18, color: INK2 }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: INK2, font: FONT }), t(' 頁', { size: 18, color: INK2 })] })] }) },
    children: [
      new Paragraph({ style: 'Title', children: [t('SO-101 機械手臂零件列印需求說明')] }),
      p([t('開源機械手臂 SO-101 結構零件　材料 PLA+　共 23 件，另加量規 2 件', { color: INK2 })], { spacing: { after: 200 } }),
      table([1900, 2919, 1900, 2919], ['項目', '內容', '項目', '內容'], [
        ['訂購單位', '', '聯絡人', ''],
        ['電話', '', '需求日期', ''],
        ['材料', 'PLA+', '數量', '23 件＋量規 2 件'],
      ]),
      gap(),
      p('您好，這批是開源機械手臂 SO-101 的結構零件，零件要裝馬達、鎖螺絲，尺寸精度比外觀重要。麻煩依照以下規格列印，謝謝！'),

      h1('一、檔案與數量'),
      bullet([t('檔案在附件 '), b('SO-101-official-STL.zip'), t(' 的 Individual 資料夾，也可以從官方 GitHub 下載：')]),
      p([t('https://github.com/TheRobotStudio/SO-ARM100/tree/main/STL/SO101/Individual', { color: GREEN, size: 20 })], { indent: { left: 480 } }),
      bullet([t('第 1 到 9 項是兩隻手臂共用的零件，'), b('每種各印 2 個'), t('；第 10 到 14 項各印 1 個。')]),
      gap(),
      table([700, 4538, 3200, 1200], ['#', '檔名', '零件名稱', '數量'], partRows, { center: [0, 3], total: true }),
      gap(),
      callout('請注意', [t('請'), b('不要印 SO101 Assembly.stl'), t('，那是整隻手臂的參考模型，不是零件。驅動板固定板只印 Waveshare 版，Seeedstudio_Mounting_Plate_SO101 不用印。')], AMBER_SOFT, '8F5B00'),
      gap(),
      p([b('長得幾乎一樣的兩個零件，請分開包裝：'), t('第 3 項 Motor_holder_SO101_Base 和第 7 項 Motor_holder_SO101_Wrist 外形非常像，尺寸只差 1 mm 多。差別在底邊：第 3 項底下有兩個突出的小卡勾，第 7 項底邊是平的，有三條橫紋。')]),
      new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [4819, 4819], layout: TableLayoutType.FIXED, rows: [
        new TableRow({ children: [['Motor_holder_SO101_Base', '第 3 項　馬達 2 固定座', '底下有小卡勾　55.1 × 38.1 × 28.0 mm'], ['Motor_holder_SO101_Wrist', '第 7 項　馬達 4 固定座', '底邊平的有橫紋　56.4 × 36.9 × 28.0 mm']].map(([f, title, note]) => {
          const img = fs.readFileSync(path.join(ROOT, 'assets/img/parts', f + '_side.png'));
          const h = img.readUInt32BE(20), w = img.readUInt32BE(16);
          return new TableCell({ width: { size: 4819, type: WidthType.DXA }, borders, margins: { top: 80, bottom: 80, left: 110, right: 110 }, children: [
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: 'png', data: img, transformation: { width: 150, height: Math.round(150 * h / w) },
              altText: { title: f, description: title + '，' + note, name: f } })] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [b(title)], spacing: { before: 60 } }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [t(f + '.stl', { size: 18 })] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [t(note, { size: 18, color: INK2 })] }),
          ] });
        }) }),
      ] }),

      h1('二、材料與參數'),
      table([2600, 7038], ['項目', '規格'], [
        ['材料', [b('PLA+')]],
        ['線材', [t('所有零件'), b('用同一品牌、同一捲線材'), t('，不同捲的收縮會有差異。線材請先烘乾。')]],
        ['噴嘴／層高', '0.4 mm 噴嘴，0.2 mm 層高'],
        ['填充', '20%'],
        ['外牆', [b('4 圈'), t('。螺絲是鎖在外牆上，牆要夠厚。')]],
        ['上下實心層', '至少 4 層'],
        ['縮放', [b('100%，不要縮放'), t('，單位 mm')]],
        ['校正', '請先做過流量校正，第一層開象腳補償。擠出過多會讓孔和馬達凹槽變小，裝不進去。'],
      ]),

      h1('三、支撐'),
      num('支撐全部區域，但與水平面夾角大於 45° 的斜面不用支撐。', 'num'),
      num([b('水平方向的螺絲孔裡面不要加支撐。')], 'num'),
      num([t('支撐請完全清除，'), b('特別是馬達凹槽和螺絲孔'), t('，不能留殘渣。')], 'num'),

      h1('四、請先印量規確認'),
      p('正式下單前，請先用同一捲線材、同一組參數印下面兩個量規，寄給我們試裝馬達：'),
      table([4819, 4819], ['檔名', '位置'], [
        [[t('Gauge_0.STL', { font: { ascii: 'Consolas', hAnsi: 'Consolas' } })], 'zip 內的 Gauges 資料夾'],
        [[t('Gauge_tight_1.STL', { font: { ascii: 'Consolas', hAnsi: 'Consolas' } })], 'zip 內的 Gauges 資料夾'],
      ]),
      gap(),
      p([t('我們確認鬆緊沒問題後，再用'), b('完全相同的設定'), t('印正式零件。')]),

      h1('五、出貨前檢查'),
      p('請用游標卡尺抽量以下零件的外形，誤差希望在 ±0.2 mm 以內：'),
      table([3600, 3838, 2200], ['零件', '外形尺寸（mm）', '實測'], [
        ['Upper_arm_SO101 上臂', '142.1 × 67.3 × 24.5', '☐'],
        ['Under_arm_SO101 前臂', '130.7 × 64.4 × 24.0', '☐'],
        ['Base_SO101 底座', '110.9 × 87.0 × 72.0', '☐'],
      ], { center: [2] }),
      gap(),
      table([7438, 2200], ['檢查項目', '確認'], [
        ['長條零件 Upper_arm、Under_arm 放在平面上不翹', '☐'],
        ['M3 螺絲能順順穿過 3.2 mm 的孔；太緊可用 3.2 mm 鑽頭輕輕清孔', '☐'],
        [[b('直徑 1.6 mm 的小孔沒有擴孔'), t('（那是讓螺絲直接鎖進塑膠的導孔）')], '☐'],
        ['接合面、馬達凹槽、孔位沒有打磨或噴漆', '☐'],
        ['馬達凹槽和螺絲孔內沒有殘留支撐', '☐'],
        ['活動爪 Moving_Jaw 尖端包裝時有保護', '☐'],
        [[b('每種零件分袋包裝，袋子上標示檔名'), t('（第 3 項和第 7 項外形很像）')], '☐'],
        ['23 件數量齊全', '☐'],
      ], { center: [1] }),

      h1('六、選購：力感測治具'),
      p('如果一併列印，檔案另外提供，材料用 PLA+ 或 PETG，設定同上，填充改為 40% 以上：'),
      table([4819, 3619, 1200], ['檔名', '零件名稱', '數量'], [
        [[t('probe_block.stl', { font: { ascii: 'Consolas', hAnsi: 'Consolas' } })], '治具座', '1'],
        [[t('probe_tip.stl', { font: { ascii: 'Consolas', hAnsi: 'Consolas' } })], '推頭', '1'],
      ], { center: [2] }),

      gap(),
      p([t('有任何問題請先跟我們確認，謝謝！', { bold: true })], { spacing: { before: 200, after: 200 } }),
      p([t('規格依據：材料、層高、填充、支撐設定來自官方 TheRobotStudio/SO-ARM100 的 README 與 3DPRINT.md。外牆 4 圈、±0.2 mm 公差、1.6 mm 孔不擴孔為本專案額外要求。', { size: 18, color: INK2 })]),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => { fs.mkdirSync(path.dirname(OUT), { recursive: true }); fs.writeFileSync(OUT, buf); console.log('wrote', OUT, buf.length, 'bytes'); });
