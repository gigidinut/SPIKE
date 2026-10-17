// Builds the presenter's reading script (.docx) from the slide deck's own
// speaker notes, so the script and the slides always say the same thing.
//
//   cd docs
//   node make_script.js
//
// The deck's files are in presentation/project/ (copied from the Slides
// artifact). Change a slide's <aside> there and in the artifact, then run this.
'use strict';
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, LevelFormat,
} = require('docx');

const DECK = path.join(__dirname, 'presentation', 'project');
const OUT = path.join(__dirname, 'Rover Software - Presentation Script.docx');
const WPM = 130;              // a calm speaking pace, words per minute
const FONT = 'Arial', TEAL = '1F5C66', INK = '1B2425', MUTED = '5B6867', W = 9638;

const deck = JSON.parse(fs.readFileSync(path.join(DECK, 'deck.json'), 'utf8'));
const decode = s => s.replace(/<br\s*\/?>/g, ' ').replace(/<[^>]+>/g, '').replace(/&#160;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const slides = deck.order.map((id, i) => {
  const html = fs.readFileSync(path.join(DECK, 'slides', id + '.html'), 'utf8');
  const title = decode((/<h[12][^>]*>([\s\S]*?)<\/h[12]>/.exec(html) || [, id])[1]);
  const notes = decode((/<aside>([\s\S]*?)<\/aside>/.exec(html) || [, ''])[1]);
  const words = notes.split(' ').filter(Boolean).length;
  return { n: i + 1, id, title, notes, seconds: Math.max(20, Math.round(words / WPM * 60) + 10) };
});
const total = slides.reduce((a, s) => a + s.seconds, 0);
const mmss = s => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

const P = (text, opts = {}, run = {}) => new Paragraph({ spacing: { after: 120 }, ...opts, children: [new TextRun({ text, ...run })] });
const H1 = (text, pageBreakBefore = false) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore, children: [new TextRun(text)] });
const bullet = text => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun(text)] });
const line = { style: BorderStyle.SINGLE, size: 4, color: 'C9D2CB' };
function table(rows, fractions) {
  const widths = fractions.map(f => Math.round(f * W));
  widths[widths.length - 1] = W - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: line, bottom: line, left: line, right: line, insideHorizontal: line, insideVertical: line },
    rows: rows.map((r, ri) => new TableRow({ tableHeader: ri === 0, children: r.map((c, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 100, right: 100 },
      shading: ri === 0 ? { type: ShadingType.CLEAR, fill: TEAL, color: 'auto' } : undefined,
      children: [new Paragraph({ children: [new TextRun({ text: c, bold: ri === 0, color: ri === 0 ? 'FFFFFF' : INK })] })],
    })) })),
  });
}

const placeholders = [...new Set(slides.flatMap(s => {
  const html = fs.readFileSync(path.join(DECK, 'slides', s.id + '.html'), 'utf8');
  return (decode(html).match(/\[[^\]]+\]/g) || []);
}))];

const children = [
  new Paragraph({ spacing: { before: 1800, after: 200 }, children: [new TextRun({ text: 'Rover Software for Teams', bold: true, size: 52, color: TEAL })] }),
  new Paragraph({ spacing: { after: 400 }, children: [new TextRun({ text: 'Presentation script', size: 32 })] }),
  P('A word-for-word script to read from, one section per slide. The words are the speaker notes of the slide deck, so the two always match.', {}, { color: MUTED }),
  P('Speaking time: about ' + Math.round(total / 60) + ' minutes at a calm pace (' + WPM + ' words a minute), plus questions.', {}, { color: MUTED }),

  H1('Before you present', true),
  P('Fill in these placeholders on the slides and in this script:'),
  ...placeholders.map(p => bullet(p)),
  P('Then check:', { spacing: { before: 160, after: 120 } }),
  bullet('The prices of the three packages, and how many points autonomy is worth, are final.'),
  bullet('Share the deck from its Share menu if anyone else needs to open it; it is private until you do.'),
  bullet('Have the simulator open on the presenting computer, in case someone asks to see it running.'),
  P('Running order', { spacing: { before: 240, after: 120 } }, { bold: true, size: 26, color: TEAL }),
  table([['#', 'Slide', 'Time', 'Clock']].concat((() => {
    let clock = 0;
    return slides.map(s => { clock += s.seconds; return [String(s.n), s.title, mmss(s.seconds), mmss(clock)]; });
  })()), [0.06, 0.66, 0.14, 0.14]),
];

for (const s of slides) {
  children.push(
    new Paragraph({ heading: HeadingLevel.HEADING_2, pageBreakBefore: s.n === 1, keepNext: true, spacing: { before: 360, after: 80 },
      children: [new TextRun({ text: 'Slide ' + s.n + '  ·  ' + s.title })] }),
    new Paragraph({ keepNext: true, spacing: { after: 120 }, children: [new TextRun({ text: 'About ' + mmss(s.seconds), italics: true, size: 20, color: MUTED })] }),
    new Paragraph({ spacing: { after: 200, line: 360 }, children: [new TextRun({ text: s.notes, size: 26 })] }),
  );
}

children.push(
  H1('Questions teams may ask', true),
  ...[
    ['Can we try the software before we buy it?', 'The simulator is free for every team, and so are the basic functions inside every package. The autonomy itself comes with the package you buy. [Your rule: for example, a demonstration of each package on the course.]'],
    ['Can we change package later?', '[Your rule.] The software is rebuilt for the new package and keeps your own program; your settings and colour actions need copying across.'],
    ['Does it work with four or six wheels?', 'Yes, as long as the wheels on each side are driven. Turns are slower because the wheels slide; setup_check tests 5 and 6 measure it, and you type the numbers into the simulator.'],
    ['Can we mix our own moves with the autonomy?', 'Yes. In your program you can drive to a good starting point, then call follow_wall() or explore(), and add your own moves afterwards.'],
    ['What if the explorer never finds a colour?', 'It searches everywhere it can reach, then once more, then explore(find=...) gives back False, so your program can decide what to do next.'],
    ['What if our rover has no colour sensor?', 'It still drives and finds walls, and prints a warning that colours are ignored. But it cannot find the patches.'],
    ['Why did the rover get lost in the simulator?', 'Almost always a wrong setting, usually the wheel size. Look for the red badge, and the Rover tab lists what does not match.'],
  ].flatMap(([q, a]) => [
    new Paragraph({ keepNext: true, spacing: { before: 200, after: 60 }, children: [new TextRun({ text: q, bold: true })] }),
    P(a),
  ]),
);

const doc = new Document({
  creator: 'Rover software', title: 'Rover Software for Teams - Presentation script',
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 34, bold: true, color: TEAL, font: FONT }, paragraph: { spacing: { after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 28, bold: true, color: TEAL, font: FONT }, paragraph: { outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: 'Presentation script  ·  page ', size: 16, color: MUTED }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('Wrote ' + path.basename(OUT) + ': ' + slides.length + ' slides, about ' + Math.round(total / 60) + ' minutes'); });
