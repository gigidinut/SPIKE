// Builds the user manuals (.docx) for the rover software and the simulator.
//
//   cd docs
//   npm install        (once: installs the docx library)
//   node make_manuals.js
//
// The three package manuals share most chapters, written once below, so they
// cannot drift apart. When the modules change (setting names, setup_check
// tests, functions), update the text here and run it again. Screenshots are
// in img/; tools/takeshots.py retakes them from the simulator.
'use strict';
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, Footer, PageNumber, LevelFormat,
} = require('docx');

const VERSION = '1.2';
const DATE = '17 October 2026';
const OUT = __dirname;
const W = 9638;                  // text width in DXA: A4 with 2 cm margins
const FONT = 'Arial', MONO = 'Consolas';
const INK = '1B2425', TEAL = '1F5C66', MUTED = '5B6867';

/* ===================== Building blocks ===================== */

// Text with **bold** and `code` marks.
function runs(text, base = {}) {
  return String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).flatMap(part => {
    if (part.startsWith('**')) return runs(part.slice(2, -2), { ...base, bold: true });
    if (part.startsWith('`')) return new TextRun({ ...base, text: part.slice(1, -1), font: MONO, size: 20, color: '7A2E12' });
    return new TextRun({ ...base, text: part });
  });
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts });
const H1 = (text, newPage = true) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: newPage, keepNext: true, spacing: newPage ? undefined : { before: 400, after: 240 }, children: [new TextRun(text)] });
const H2 = text => new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [new TextRun(text)] });
const H3 = text => new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, children: [new TextRun(text)] });
const bullets = (items, level = 0) => items.map(t => new Paragraph({ numbering: { reference: 'bullets', level }, children: runs(t), spacing: { after: 60 } }));
let listInstance = 0;
const steps = items => {
  listInstance += 1;
  return items.map(t => new Paragraph({ numbering: { reference: 'steps', level: 0, instance: listInstance }, children: runs(t), spacing: { after: 80 } }));
};
const code = lines => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l === '' ? ' ' : l, font: MONO, size: 18 })],
  shading: { type: ShadingType.CLEAR, fill: 'EEF2EE', color: 'auto' },
  spacing: { before: i === 0 ? 80 : 0, after: i === lines.length - 1 ? 160 : 0, line: 250 },
  indent: { left: 170, right: 170 }, keepNext: i < lines.length - 1, keepLines: true,
}));
const NOTE_STYLE = { tip: ['Tip: ', 'E8F2EA', '2E8B4C'], warn: ['Watch out: ', 'FBF0DC', 'A86E12'], key: ['Remember: ', 'E6EEF8', '2459C4'] };
const note = (text, kind = 'tip') => {
  const [label, fill, edge] = NOTE_STYLE[kind];
  return new Paragraph({
    children: [new TextRun({ text: label, bold: true, color: edge }), ...runs(text)],
    shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 24, color: edge, space: 8 } },
    spacing: { before: 80, after: 160 }, indent: { left: 200, right: 120 },
  });
};
function cell(content, width, header) {
  const paras = (Array.isArray(content) ? content : [content]).map(t => new Paragraph({
    children: runs(t, header ? { bold: true, color: 'FFFFFF' } : {}), spacing: { before: 40, after: 40 },
  }));
  return new TableCell({
    children: paras, width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: TEAL, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
  });
}
// widths: fractions of the text width
function table(header, rows, fractions) {
  const widths = fractions.map(f => Math.round(f * W));
  widths[widths.length - 1] = W - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  const line = { style: BorderStyle.SINGLE, size: 4, color: 'C9D2CB' };
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: line, bottom: line, left: line, right: line, insideHorizontal: line, insideVertical: line },
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], false)) }))],
  });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 80 } });
function pngSize(file) {
  const b = fs.readFileSync(file);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}
// A screenshot, scaled to fit maxW x maxH pixels (96 per inch), with a caption.
function img(name, caption, maxW = 640, maxH = 840) {
  const file = path.join(OUT, 'img', name + '.png');
  const [w, h] = pngSize(file);
  const k = Math.min(maxW / w, maxH / h, 1);
  const out = [new Paragraph({
    alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: Math.round(w * k), height: Math.round(h * k) } })],
  })];
  if (caption) out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: caption, italics: true, size: 18, color: MUTED })] }));
  return out;
}

function titlePage(title, subtitle, lines) {
  return [
    new Paragraph({ spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: title, bold: true, size: 56, color: TEAL })] }),
    new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: subtitle, size: 30, color: INK })] }),
    ...lines.map(l => new Paragraph({ spacing: { after: 100 }, children: runs(l, { color: MUTED }) })),
  ];
}
function contents(items) {
  return [new Paragraph({ heading: HeadingLevel.HEADING_2, pageBreakBefore: true, children: [new TextRun('Contents')] }),
    ...items.map((t, i) => new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: (i + 1) + '.  ' + t })] }))];
}

function writeDoc(file, title, children) {
  const doc = new Document({
    creator: 'Rover software', title,
    styles: {
      default: { document: { run: { font: FONT, size: 21, color: INK } } },
      paragraphStyles: [
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 36, bold: true, color: TEAL, font: FONT }, paragraph: { spacing: { before: 0, after: 240 }, outlineLevel: 0 } },
        { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 27, bold: true, color: TEAL, font: FONT }, paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 } },
        { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 23, bold: true, color: INK, font: FONT }, paragraph: { spacing: { before: 220, after: 80 }, outlineLevel: 2 } },
      ],
    },
    numbering: { config: [
      { reference: 'bullets', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 800, hanging: 260 } } } }] },
      { reference: 'steps', levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 340 } } } }] },
    ] },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: title + '  ·  version ' + VERSION + '  ·  page ', size: 16, color: MUTED }),
          new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED })] })] }) },
      children,
    }],
  });
  return Packer.toBuffer(doc).then(buf => { fs.writeFileSync(path.join(OUT, file), buf); console.log('Wrote ' + file); });
}

/* ===================== The three packages ===================== */

const PACKAGES = {
  basic: { name: 'Basic functions', file: 'Rover Software - Basic Functions - User Manual.docx', main: 'my_program', grid: false },
  wall: { name: 'Wall follower', file: 'Rover Software - Wall Follower - User Manual.docx', main: 'follow_wall', grid: true },
  explorer: { name: 'Maze explorer', file: 'Rover Software - Maze Explorer - User Manual.docx', main: 'explore', grid: true },
};

function aboutChapter(pkg) {
  const k = PACKAGES[pkg];
  const what = {
    basic: 'Your rover can drive set distances, turn to exact directions using the hub’s gyro, stop before walls with the distance sensor and react to coloured patches. **You** decide the route: you write it as a list of moves.',
    wall: 'Everything in the Basic functions package, plus the **wall follower**: the rover keeps one hand on a wall and follows it round the course on its own, the way you could find your way round a maze in the dark. It reacts to coloured patches on the way.',
    explorer: 'Everything in the Basic functions package, plus the **maze explorer**: the rover draws a map as it goes and keeps heading for the nearest place it has not searched yet, until it has searched everywhere it can reach. It can find colours in the order your course needs.',
  }[pkg];
  return [
    H1('1. About your package'),
    P('This is the user manual for the **' + k.name + '** package of the rover software, version ' + VERSION + '. ' + what),
    H2('What you need'),
    ...bullets([
      'A rover built with a LEGO SPIKE Prime hub, with **two drive motors** (one driving the left side, one the right) so it can turn on the spot.',
      'A **distance sensor** pointing forwards and a **colour sensor** pointing down at the floor.',
      'The **SPIKE App** (version 3), set to Python.',
      'Your program file: the `.py` file you were given, with your team name at the top.',
      'The **rover simulator** and its manual, to test on a computer before you test on the floor.',
    ]),
    H2('The parts of the file you change first'),
    P('Your program file is long, but to get your rover going you only need to change three parts of it. Everything else is the rover software. Read it, play with it and change it if you like: that is the best way to understand how the rover works. Save a copy of a version that works first, so you can always go back.'),
    table(['Part', 'Where', 'What it is for'], [
      ['**SETTINGS**', 'Near the top', 'Describe your rover (ports, wheel size, where the sensors are) and your course.'],
      ['**YOUR PROGRAM**', 'At the very bottom', 'Choose what runs, or write your own list of moves.'],
      ['`on_colour_found()`', 'In the middle: search for **ADD YOUR OWN ACTIONS HERE**', 'What the rover does when it finds a colour. Only if you want your own colour actions.'],
    ], [0.22, 0.3, 0.48]),
    gap(),
    note('Chapter 2 is a checklist for your first hour. Do it in order, and you will have a working rover before you start on anything clever.', 'key'),
  ];
}

function firstHourChapter(pkg) {
  const k = PACKAGES[pkg];
  return [
    H1('2. Your first hour'),
    P('Work through these steps in order. Each one builds on the one before.'),
    H2('Step 1: Keep one master copy of your file'),
    P('The simulator reads your program from a file on the computer; the hub gets it from the SPIKE App. Keep **one master copy**: the `.py` file. Change it in a text editor (Notepad, IDLE, VS Code or similar), test it in the simulator, then copy the whole file into the SPIKE App to run it on the rover.'),
    note('Whenever you change the program in the SPIKE App instead, copy it back into the master file straight away, or your team will end up with two different versions.', 'warn'),
    H2('Step 2: Put the file into the SPIKE App'),
    ...steps([
      'Open the SPIKE App and start a **new project**. Choose **Python**.',
      'Delete the few lines the new project starts with.',
      'Open your `.py` file in a text editor, select **everything** (Ctrl+A), copy it (Ctrl+C) and paste it into the SPIKE App (Ctrl+V).',
      'Connect the hub and press **Run**. Messages from the program appear in the SPIKE App’s console.',
    ]),
    H2('Step 3: Fill in the SETTINGS for your rover'),
    P('Measure your rover and fill in the settings described in chapter 4. Get the ports right first; the measurements can be rough for now, because the tests in step 5 fine-tune them.'),
    H2('Step 4: Describe your rover in the simulator'),
    P('Open the simulator, load your file and draw your rover on its **Rover** tab (see the simulator manual). Its **Your program and this rover** box tells you if any setting in your file does not match the rover you drew.'),
    H2('Step 5: Run setup_check on the real rover'),
    P('At the bottom of the file, make the `setup_check` line the only one without a `#` in front, and run it. It tests every part of the rover, one at a time, and tells you which setting to change if something is wrong. Chapter 5 explains each test.'),
    ...code(['# runloop.run(run_program(my_program))', 'runloop.run(run_program(setup_check))'].concat(pkg === 'wall' ? ['# runloop.run(run_program(follow_wall))'] : pkg === 'explorer' ? ['# runloop.run(run_program(explore))'] : [])),
    H2('Step 6: Run a program'),
    P(pkg === 'basic'
      ? 'Put the `#` back in front of `setup_check` and take it away from `my_program`. The example program drives a 30 cm square. Then write your own route: chapter 6 shows how.'
      : 'Put the `#` back in front of `setup_check` and take it away from `' + k.main + '`. Try it in the simulator first, then on the floor. Chapter 8 explains what it does and how to get the most out of it.'),
  ];
}

function fileChapter(pkg) {
  const choices = ['my_program', 'setup_check'].concat(pkg === 'wall' ? ['follow_wall'] : pkg === 'explorer' ? ['explore'] : []);
  return [
    H1('3. Your program file'),
    H2('How the file is laid out'),
    table(['Section', 'What is in it'], [
      ['Header', 'Your team name, the package and its version. The first line the rover prints is `=== ROVER SOFTWARE ' + VERSION + ' ===`.'],
      ['Compass directions', '`NORTH`, `WEST`, `SOUTH`, `EAST` and the four in between. You use these names in your program.'],
      ['**SETTINGS**', 'The settings every team must fill in (chapter 4).'],
      ['FINE TUNING', 'Speeds and other numbers whose defaults work for most rovers (chapter 10).'],
      ['The rover software', 'One section per part: Setup, Movement, Distance sensor, Colour sensor' + (pkg === 'basic' ? '' : ', Grid moves, ' + (pkg === 'wall' ? 'Wall follower' : 'Maze explorer')) + '. Each section starts with a short description of what it does and which functions you can use.'],
      ['**YOUR PROGRAM**', 'Your own program, and the lines that choose what runs.'],
    ], [0.28, 0.72]),
    gap(),
    H2('Choosing what runs'),
    P('At the very bottom there is one `runloop.run(...)` line for each program. **Exactly one** of them must have no `#` in front: that is the one that runs.'),
    ...code(['# Choose what runs: exactly ONE of these lines must have no # in front.'].concat(choices.map((c, i) => (i === choices.length - 1 ? '' : '# ') + 'runloop.run(run_program(' + c + '))'))),
    P('`run_program` does three things before your program starts: it checks every setting, sets the gyro’s zero (the way the rover faces now becomes `NORTH`), and starts the clock for `MAX_RUN_SECONDS`. So **place the rover facing the way you want to call NORTH before you press Run.**'),
    H2('Messages from the rover'),
    P('Everything the program prints appears in the SPIKE App’s console (and in the simulator’s Log). The rover software prints a line for each move, such as `drive: done after 30.0 cm` or `turn: to 90, stopped at 89.4`. Add your own with `print(...)`:'),
    ...code(['print("Reached the bridge")', 'print("Distance ahead: " + str(read_distance()) + " cm")']),
    note('If the program finds a mistake in your settings it prints **SETTINGS PROBLEM:** and a message saying which setting is wrong and what it should be, and the rover does not move. Fix the setting and run again.', 'tip'),
    H2('Stopping'),
    P('Press the hub’s **middle button** to stop the program at any time. Inside your own program, `end_run()` stops the whole run from anywhere.'),
  ];
}

function settingsChapter(pkg) {
  const k = PACKAGES[pkg];
  const out = [
    H1('4. Describing your rover: the SETTINGS'),
    P('The SETTINGS tell the software how **your** rover is built. Every team’s rover is different, so every team must fill them in. A wrong setting makes the rover drive strangely, so take your time here.'),
    H2('The turning point'),
    P('Several settings are measured from the rover’s **turning point**: the spot that stays still when the rover spins on the spot.'),
    ...bullets([
      'With **two drive wheels and a caster** (or ball), the turning point is half way between the two drive wheels.',
      'With **four or more wheels that cannot swivel**, it is somewhere between them. `setup_check` test 6 finds it (chapter 5).',
    ]),
    P('Measure forwards and backwards along the middle of the rover, in centimetres. In front of the turning point is **plus**, behind it is **minus**.'),
    H2('Your rover'),
    table(['Setting', 'What it means', 'How to find it'], [
      ['`LEFT_MOTOR_PORT`\n`RIGHT_MOTOR_PORT`', 'The hub port of the motor driving the left wheels and the right wheels: `port.A` to `port.F`.', 'Look at the hub. Tests 1 and 2 tell you if they are swapped.'],
      ['`DISTANCE_SENSOR_PORT`\n`COLOUR_SENSOR_PORT`', 'The ports of the two sensors.', 'Look at the hub. Tests 7 and 8 check them.'],
      ['`LEFT_MOTOR_DIRECTION`\n`RIGHT_MOTOR_DIRECTION`', '`1` or `-1`: which way each motor must spin to roll the rover forwards. Motors mounted mirror-image need opposite numbers.', 'Tests 1 and 2.'],
      ['`WHEEL_DIAMETER_CM`', 'The diameter of the drive wheels, across the tyre.', 'Measure with a ruler; test 4 fine-tunes it.'],
      ['`WHEEL_GEAR_RATIO`', 'How many times the motor turns for one turn of the wheel. `1` if the wheel is fixed straight onto the motor. With gears: teeth on the wheel’s gear ÷ teeth on the motor’s gear.', 'Count the teeth.'],
      ['`ROVER_WIDTH_CM`', 'The width of the rover at its widest point.', 'Ruler.'],
      ['`ROVER_FRONT_CM`', 'From the turning point to the part that sticks out furthest at the front.', 'Test 6.'],
      ['`ROVER_BACK_CM`', 'From the turning point to the part that sticks out furthest at the back.', 'Ruler, from the turning point.'],
      ['`DISTANCE_SENSOR_POSITION_CM`', 'Where the front of the distance sensor is, measured from the turning point. Plus = in front.', 'Test 7 suggests the number.'],
      ['`COLOUR_SENSOR_POSITION_CM`', 'Where the colour sensor is, measured from the turning point. Plus = in front, minus = behind.', 'Ruler.'],
      ['`HUB_FACE_UP`', 'Which side of the hub faces up. `motion_sensor.TOP` when the hub lies flat with its light matrix facing up. Others: `BOTTOM`, `FRONT`, `BACK`, `LEFT`, `RIGHT`.', 'Test 3.'],
      ['`MAX_RUN_SECONDS`', 'End the run after this many seconds. `0` = no limit.', 'Your competition rules.'],
    ].map(r => [r[0].split('\n'), r[1], r[2]]), [0.37, 0.42, 0.21]),
    gap(),
    H2('Colours'),
    table(['Setting', 'What it means'], [
      ['`COLOURS_TO_FIND`', 'The colours the rover reacts to, for example `[color.GREEN, color.RED]`. The names are `color.RED`, `color.GREEN`, `color.BLUE`, `color.YELLOW` and so on (the SPIKE spelling, without a u).'],
      ['`COLOUR_PAUSE_MS`', 'How long the rover stops on a colour, in milliseconds. 5000 = 5 seconds.'],
      ['`REACT_ONCE`', '`True`: react to each colour only the first time. `False`: react every time the rover drives onto it.'],
    ], [0.3, 0.7]),
    gap(),
  ];
  if (k.grid) {
    out.push(
      H2('Your course'),
      table(['Setting', 'What it means'], [
        [['`COURSE_NORTH_CM`', '`COURSE_EAST_CM`', '`COURSE_WEST_CM`', '`COURSE_SOUTH_CM`'], 'How far the course reaches from the start, in each direction. The rover never goes outside these limits. NORTH is the way the rover faces at the start, EAST to its right, WEST to its left. Use `0` for SOUTH when the start is at the edge of the course, so the rover cannot wander out through the entrance. Keep them close to your real course: very large limits make the planning slow.'],
        ['`CHECK_BY_WALLS`', '`True`: also check the strip of floor next to each wall the rover meets, which its normal path never reaches. Slower, but finds patches against walls.'],
      ].concat(pkg === 'wall'
        ? [['`KEEP_WALL_ON_RIGHT`', '`True`: keep the right hand on the wall. `False`: the left hand. See chapter 8.']]
        : [['`HEAD_TOWARDS`', 'Which way to search first, as a heading in degrees (`0` = NORTH, `90` = WEST, `-90` = EAST), or `None` for no preference. See chapter 8.']]), [0.3, 0.7]),
      gap());
  }
  out.push(note('The **Copy settings for my program** button on the simulator’s Rover tab writes the rover settings for you, from the rover you drew.', 'tip'));
  return out;
}

function setupCheckChapter() {
  return [
    H1('5. setup_check: testing your rover'),
    P('`setup_check` tests each part of the rover, one at a time, and tells you which setting to change if something is wrong. Run it on every new rover, and again after you rebuild anything.'),
    H2('How to use it'),
    ...bullets([
      'Make `runloop.run(run_program(setup_check))` the only `runloop.run` line without a `#`, and run the program.',
      'Each test prints what it is about to do and waits. Press the hub’s **RIGHT** button to start it.',
      'When a test has finished, press **RIGHT** for the next test, or **LEFT** to do the same test again (for example to measure twice).',
      'Read the console in the SPIKE App: each test says what to look for and which setting to change.',
      'A changed setting only counts when you run the program again.',
      'You need about a metre of clear floor in front of the rover.',
    ]),
    H2('The eight tests'),
    table(['Test', 'What happens', 'If it is wrong'], [
      ['1. Left wheel', 'Only the left wheel turns for 1 second, rolling forwards.', 'The right wheel turned: swap `LEFT_MOTOR_PORT` and `RIGHT_MOTOR_PORT`. It rolled backwards: change `LEFT_MOTOR_DIRECTION` (1 ↔ -1).'],
      ['2. Right wheel', 'Only the right wheel turns, rolling forwards.', 'It rolled backwards: change `RIGHT_MOTOR_DIRECTION`.'],
      ['3. Gyro', 'The rover spins left for 1 second and prints the degrees the gyro measured. It should be a plus number.', 'It measured a right turn: if the rover really turned right, swap the motor ports; if it turned left, the hub is upside down, so change `HUB_FACE_UP`. Hardly any change: the hub is on its side, so change `HUB_FACE_UP`.'],
      ['4. Drive 30 cm', 'Mark the floor beside the middle of a wheel. The rover drives 30 cm.', 'Measure how far the mark beside the wheel really moved. If it was not 30 cm, the new `WHEEL_DIAMETER_CM` = the old value × (cm it really moved) ÷ 30. The test prints this sum for you.'],
      ['5. Turning', 'A quarter turn left, then back. The `turn:` lines should stop within 2 degrees of the target. It also prints the **motor degrees for a quarter turn**.', 'Turns wobble or overshoot a lot: lower `TURN_SLOW_SPEED` (chapter 10). Type the motor degrees into the simulator (Rover tab, Match my real rover).'],
      ['6. Turning point', 'Mark the floor at the very front of the rover, in the middle. The rover turns half a turn. Mark the front again.', 'The turning point is half way between the two marks, so `ROVER_FRONT_CM` is half the distance between them. Measure `ROVER_BACK_CM` and the sensor positions from that point too.'],
      ['7. Distance sensor', 'Live readings: move your hand in front of the sensor. Press RIGHT, then stand the rover facing a wall with its **turning point exactly 30 cm from the wall**, and press RIGHT again.', 'It prints the `DISTANCE_SENSOR_POSITION_CM` to use. No echo: point the sensor straight at the wall. A suggestion very different from your setting usually means the 30 cm was measured to the sensor instead of the turning point.'],
      ['8. Colour sensor', 'Live readings: slide coloured paper under the sensor and watch the colour names.', 'Wrong or no colours: check `COLOUR_SENSOR_PORT`, and that the sensor faces the floor and sits close to it.'],
    ], [0.17, 0.4, 0.43]),
  ];
}

function programChapter(pkg) {
  const out = [
    H1('6. Writing your own program'),
    P('Your own program goes in `my_program()`, in the YOUR PROGRAM section at the bottom of the file. It is a list of moves, done one after the other.'),
    ...code(['async def my_program():', '    await drive_forward(50)', '    await turn_left(90)', '    await drive_forward(30)']),
    H2('Two rules'),
    ...bullets([
      '**Every move needs `await` in front**: `await drive_forward(50)`, not `drive_forward(50)`. Without `await` the program does not wait for the move and goes straight on to the next line. The functions that need it are marked with `await` in the tables below.',
      '**Indent** every line of your program by four spaces, so Python knows it belongs to `my_program()`.',
    ]),
    H2('Directions'),
    P('`NORTH` is the way the rover faced when the program started. The other directions are fixed to the room, not to the rover: `WEST` is always 90 degrees to the left of the start direction, whichever way the rover faces now.'),
    table(['Name', 'Heading', 'Which way'], [
      ['`NORTH`', '0', 'The way the rover faced at the start'],
      ['`WEST`', '90', 'A quarter turn left of that'],
      ['`SOUTH`', '180', 'Back the way it came'],
      ['`EAST`', '-90', 'A quarter turn right of the start'],
      ['`NORTH_WEST`, `SOUTH_WEST`, `SOUTH_EAST`, `NORTH_EAST`', '45, 135, -135, -45', 'Half way between'],
    ], [0.42, 0.2, 0.38]),
    gap(),
    P('Headings are in degrees, and **turning left makes the number bigger**. Any number works, so `turn_to(30)` faces a little left of NORTH.'),
    note('`turn_to(WEST)` is more accurate than `turn_left(90)` over a long route: it always turns to the exact direction, so small errors do not add up.', 'tip'),
    H2('Moving'),
    table(['Function', 'What it does'], [
      ['`await drive_forward(cm)`', 'Drive forwards in a straight line. The gyro keeps it straight.'],
      ['`await drive_forward(cm, stop_at_wall_cm=10)`', 'The same, but stop early if a wall comes closer than 10 cm.'],
      ['`await drive_backward(cm)`', 'Drive backwards. There is no sensor at the back, so make sure there is room.'],
      ['`await turn_left(degrees)`\n`await turn_right(degrees)`', 'Turn on the spot by up to 180 degrees. Without a number, 90.'],
      ['`await turn_to(direction)`', 'Turn on the spot to face a direction: `NORTH`, `WEST`, … or any heading.'],
      ['`cm_driven()`', 'How far the last drive really went, in cm.'],
      ['`rover_position()`', 'Where the rover is: (cm to the right of the start, cm ahead of the start). Minus means left of, or behind, the start.'],
      ['`gyro_heading()`', 'Which way the rover faces now, in degrees.'],
    ].map(r => [r[0].split('\n'), r[1]]), [0.45, 0.55]),
    gap(),
    H2('The distance sensor'),
    table(['Function', 'What it does'], [
      ['`read_distance()`', 'The distance to whatever is ahead, in cm, right now. `-1` means no echo: nothing in range, or the sound bounced away.'],
      ['`await measure_distance()`', 'A careful reading, standing still: it takes three readings and uses the middle one. Use it for decisions.'],
      ['`await drive_to_wall(stop_cm)`', 'Drive forwards until something is `stop_cm` away (at most 2 m).'],
    ], [0.45, 0.55]),
    gap(),
    H2('Colours and the run'),
    table(['Function', 'What it does'], [
      ['`read_colour()`', 'The colour under the sensor right now, such as `color.GREEN`.'],
      ['`colour_name(colour)`', 'The name of a colour as text, for printing: `colour_name(color.GREEN)` gives `"GREEN"`.'],
      ['`found_colours`', 'A list of the colours found so far.'],
      ['`end_run()`', 'Finish the whole run straight away.'],
    ], [0.45, 0.55]),
    gap(),
    H2('What a move tells you'),
    P('Drives give back how they ended, and turns give back whether they worked. You can use that to decide what to do next:'),
    table(['Move', 'Gives back'], [
      ['drives', '`"done"`: drove the whole way. `"wall"`: stopped because a wall came closer than `stop_at_wall_cm`. `"stuck"`: the wheels stopped turning, because the rover is pushing against something.'],
      ['turns', '`True`: it now faces the new way. `False`: there was not enough room for its back to swing round (it tried the other way round, and shuffling sideways, first). It then still faces the way it did before.'],
    ], [0.2, 0.8]),
    gap(),
    ...code([
      'async def my_program():',
      '    result = await drive_forward(120, stop_at_wall_cm=12)',
      '    if result == "wall":',
      '        print("Wall after " + str(cm_driven()) + " cm")',
      '        await turn_to(WEST)',
      '        await drive_to_wall(12)',
    ]),
    H2('Examples'),
    H3('A route with compass directions'),
    ...code([
      'async def my_program():',
      '    await drive_forward(60)            # 60 cm north',
      '    await turn_to(WEST)',
      '    await drive_to_wall(15)            # on until 15 cm from the wall',
      '    await turn_to(NORTH)',
      '    await drive_forward(80, stop_at_wall_cm=10)',
    ]),
    H3('Doing something several times'),
    ...code([
      'async def my_program():',
      '    for side in range(4):              # a square: four sides',
      '        await drive_forward(30)',
      '        await turn_left(90)',
    ]),
  ];
  if (pkg !== 'basic') {
    out.push(H3('Driving to a good starting place, then going autonomous'),
      ...code(['async def my_program():', '    await drive_forward(40)', '    await turn_to(WEST)', '    await ' + (pkg === 'wall' ? 'follow_wall()' : 'explore()')]),
      P('Choose `my_program` at the bottom of the file to run this.'));
  }
  out.push(note('Plan a route with **walls**, not just distances: `drive_to_wall()` and `stop_at_wall_cm` correct small errors, because the wall is always where it is. A route made only of distances drifts a little further off with every move.', 'tip'));
  return out;
}

function colourChapter(pkg) {
  const out = [
    H1('7. Reacting to colours'),
    P('The colour sensor watches the floor during **every** drive and turn, including the autonomous ones, without you doing anything. When it arrives on a colour from `COLOURS_TO_FIND`, the rover stops and `on_colour_found()` runs. Afterwards the move it was making carries on.'),
    P('Out of the box, `on_colour_found()` prints the colour and pauses for `COLOUR_PAUSE_MS` (5 seconds). To add your own actions, find it in the file: search for **ADD YOUR OWN ACTIONS HERE**. Change the lines after the big comment, for example:'),
    ...code([
      'async def on_colour_found(colour):',
      '    # (the big comment stays here)',
      '    print("COLOUR: found " + colour_name(colour))',
      '    if colour == color.GREEN:',
      '        await motor.run_for_degrees(port.E, 180, 300)   # tip the payload out',
      '        await runloop.sleep_ms(1000)',
      '    if colour == color.RED:',
      '        end_run()                                       # finish the run here',
    ]),
    note('**Do not drive the rover** inside `on_colour_found()`. When it finishes, the move that was interrupted carries on' + (pkg === 'basic' ? '' : ', and the autonomy still thinks the rover is where it stopped') + '. Other motors (like a payload arm on port E), the lights and sounds are fine.', 'warn'),
    ...bullets([
      'The sensor reacts when it **arrives** on a colour, so sitting on a patch only counts once.',
      'With `REACT_ONCE = True`, each colour only counts the first time it is found.',
      '`found_colours` lists the colours found so far, so `if len(found_colours) == len(COLOURS_TO_FIND): end_run()` finishes once every colour has been found.',
    ]),
  ];
  if (pkg === 'explorer') out.push(note('Need to find colours in a set **order**, or drive as part of your colour actions? Use `explore(find=...)` instead (chapter 8). `on_colour_found()` is then switched off.', 'key'));
  return out;
}

function basicRouteChapter() {
  return [
    H1('8. Planning a route'),
    P('With the Basic functions package, your team plans the route and writes it as a list of moves. A good route is reliable more than it is fast.'),
    H2('Five steps to a reliable route'),
    ...steps([
      '**Measure the course.** Draw it on squared paper, with the start, every wall and every patch, in centimetres.',
      '**Draw it in the simulator** (Course tab), so you can test your route on a computer first.',
      '**Plan the route along walls.** Wherever you can, drive up to a wall with `drive_to_wall()` or `stop_at_wall_cm`: the wall corrects the small errors of the moves before it.',
      '**Turn to compass directions** with `turn_to(NORTH)` and so on, rather than `turn_left(90)`, so turn errors do not add up.',
      '**Test one move at a time.** Run the first few moves, check where the rover stops, then add the next ones.',
    ]),
    H2('Where does the rover pass over the floor?'),
    P('The colour sensor only sees the floor right under it. It is `COLOUR_SENSOR_POSITION_CM` in front of (or behind) the turning point, so when you plan a route over a patch, plan where the **sensor** will pass, not the middle of the rover.'),
    note('The simulator’s Path line shows where the turning point went. Turn on Echoes to see what the distance sensor saw.', 'tip'),
  ];
}

function wallChapter() {
  return [
    H1('8. The wall follower'),
    P('The wall follower keeps one hand on a wall and follows it round the course, the way you could find your way round a maze in the dark. It needs no map, so it is simple and easy to predict.'),
    H2('Running it'),
    P('Choose `follow_wall` at the bottom of the file:'),
    ...code(['runloop.run(run_program(follow_wall))']),
    P('or call it from your own program with `await follow_wall()`, for example after driving to a good place to start.'),
    H2('How it works'),
    P('The rover thinks of the floor as a grid of squares, `STEP_CM` (12 cm) wide, and moves one square at a time.'),
    ...steps([
      'It drives straight on (NORTH) until there is a wall ahead.',
      'It turns so that wall is on its hand side.',
      'At every square it tries these, in order: turn towards the hand, straight on, turn away from the hand, go back. It takes the first one that works.',
      'It stops when it is about to make its very first move again: it has been all the way round. It also stops if it finds itself going round the same loop again, or if it has no way out.',
    ]),
    P('It remembers every square it tried to drive into and could not, and treats it as wall from then on. Real walls do not line up with the grid, so this keeps its hand on the wall instead of wandering off in circles.'),
    H2('Choosing the hand'),
    P('`KEEP_WALL_ON_RIGHT = True` keeps the right hand on the wall; `False` the left hand. The rover only visits squares along the walls it follows, so choose the hand whose wall passes the places you need to reach. **Try both in the simulator with your course.**'),
    H2('Patches next to walls'),
    P('With `CHECK_BY_WALLS = True`, every time the rover meets a new piece of wall it also sweeps the colour sensor up to the wall and back (turning round first if the sensor is at the back), because its normal path through the middle of the squares never reaches that strip of floor. This finds patches against walls, but makes the run slower.'),
    H2('Reading its messages'),
    table(['Message', 'Meaning'], [
      ['`=== WALL FOLLOWER START ===`', 'It has started.'],
      ['`step: NORTH done`', 'It moved one square north.'],
      ['`step: WEST blocked (wall), going back`', 'Something was in the way; it went back to the middle of its square.'],
      ['`step: EAST - no room to turn that way`', 'Its back would have hit something while turning; it tries the next way.'],
      ['`wall check: driving up to the wall`', 'It is sweeping the colour sensor along a wall.'],
      ['`follow: back to its first move - all the way round, finished`', 'It has been all the way round.'],
    ], [0.5, 0.5]),
    gap(),
    H2('What it cannot do'),
    ...bullets([
      'It misses patches in **open floor**, away from the walls it follows, and walls that are not joined to the others (islands).',
      'It cannot pass through a gap narrower than the circle the rover needs to turn in (see chapter 9).',
      'It moves in 12 cm squares, so a patch smaller than about that can lie between its paths.',
      'The last few centimetres next to a wall (`WALL_CHECK_GAP_CM`, 5 cm) are never checked.',
    ]),
    note('If the course has a patch out in the open, drive to it with your own moves after (or before) `follow_wall()`.', 'tip'),
  ];
}

function explorerChapter() {
  return [
    H1('8. The maze explorer'),
    P('The explorer draws a map of the course as it goes. It keeps heading for the nearest square it has not searched yet, until it has searched everywhere it can reach. It finds patches out in the open that a wall follower would miss, but it takes longer.'),
    H2('Two ways to use it'),
    table(['Call', 'What it does'], [
      ['`await explore()`', 'Search everywhere. `on_colour_found()` reacts to colours on the way (chapter 7). Choose `explore` at the bottom of the file to run just this.'],
      ['`await explore(find=color.GREEN)`', 'Search until the colour sensor is on GREEN, stop there, and carry on with the next line of your program. Gives back `True` if it found it, or `False` if it searched everywhere it can reach (twice) without finding it.'],
    ], [0.4, 0.6]),
    gap(),
    H2('Finding colours in order'),
    P('Write one `explore(find=...)` for each colour, in the order they must be found, in `my_program()`. The lines after each one are your actions for that colour, **and they may drive**:'),
    ...code([
      'async def my_program():',
      '    if not await explore(find=color.GREEN, near=(-30, 110)):',
      '        return                    # no GREEN anywhere: stop here',
      '    await drive_forward(8)        # e.g. get the payload over the patch',
      '    # ...your payload code here...',
      '    await explore(find=color.RED, towards=30)',
    ]),
    ...bullets([
      'Only the colour it is looking for counts: driving over RED while it looks for GREEN does nothing. (`on_colour_found()` is switched off once you use `find`.)',
      'It keeps its map from one `explore()` to the next, so it never searches the same floor twice. If it drove over a colour before that colour’s turn, it goes straight back there.',
      'It keeps track of how far your own moves drive it, and starts the next `explore()` from the middle of the nearest square.',
    ]),
    H2('Telling it where to search first'),
    P('Both hints are optional. The rover still searches everywhere in the end; it just searches there first.'),
    table(['Hint', 'What it means'], [
      ['`near=(-30, 110)`', 'Roughly where the colour is: (cm to the **right** of the start, cm **ahead** of it). Use a minus for left or behind: (-30, 110) is 30 cm left and 110 cm ahead. The rover heads there, then searches around it.'],
      ['`towards=30`', 'Which way to search, as a heading in degrees. The rover keeps going that way until walls stop it.'],
      ['neither', 'It uses the `HEAD_TOWARDS` setting (`None` = just the nearest unsearched square).'],
    ], [0.25, 0.75]),
    gap(),
    note('Use a heading **between** two directions, like `30` (“mostly north, a bit west”), rather than exactly `NORTH_WEST` (45). At 45 north and west count exactly the same, so the rover cannot choose and just keeps going the way it faces, which can lead it into a dead end.', 'tip'),
    H2('How it works'),
    P('The rover thinks of the floor as a grid of squares, `STEP_CM` (12 cm) wide. It starts in square (0, 0) facing NORTH; the first number counts squares to the east (right), the second squares to the north (ahead). Its map remembers which squares it has stood on, which moves between squares are open or blocked by a wall, and which squares are too close to a wall to ever stand in. Each time round, it:'),
    ...steps([
      '**Plans**: picks the unsearched square to head for, with a “ripple search” that spreads out from the rover square by square, so it always finds the shortest route.',
      '**Looks**: if it does not know whether the first move of that route is open, it faces that way and measures. One look maps a whole line of squares.',
      '**Moves** one square, or marks that move as blocked if it could not.',
    ]),
    H2('Reading its messages'),
    table(['Message', 'Meaning'], [
      ['`explore: heading for square (-3, 8)`', 'Its next target: 3 squares west and 8 north of the start.'],
      ['`look: WEST from (-1, 3), 81.7 cm, 5 squares free`', 'It measured 81.7 cm to the west and marked 5 squares open.'],
      ['`step: NORTH blocked (wall), going back`', 'A wall stopped it; it marked that move as blocked.'],
      ['`map | ...`', 'A picture of its map, NORTH at the top. `R` = rover, `o` = visited, `.` = seen to be open, `#` = too close to a wall to stand in.'],
      ['`explore: searched every square it can reach - finished`', 'It has searched everywhere it can reach.'],
    ], [0.5, 0.5]),
    gap(),
    H2('What it cannot do'),
    ...bullets([
      'It is **slower** than a wall follower: a full search of a 2 m course can take several minutes. Use hints, and set `MAX_RUN_SECONDS` to your competition time.',
      'It cannot reach places through a gap narrower than the circle the rover needs to turn in (see chapter 9).',
      'It moves in 12 cm squares, so a patch smaller than about that can lie between its paths. `CHECK_BY_WALLS` covers the strips next to walls, except the last 5 cm (`WALL_CHECK_GAP_CM`).',
      'It trusts its map. If the rover is pushed, or slips a lot, the map no longer matches the course.',
    ]),
  ];
}

function roverFitChapter(pkg) {
  return [
    H1('9. Will the software work with my rover?'),
    P('The software works with most rover designs, but not all. Check yours before you build too much.'),
    H2('It must turn on the spot'),
    P('The software turns the rover by running the left wheels backwards and the right wheels forwards (or the other way). That needs **driven wheels on both sides**. Rovers that steer like a car, with a steering motor, cannot turn on the spot, so the turns, the wall follower and the explorer do not work with them.'),
    H2('Room to turn'),
    P('When the rover spins on the spot, its corners sweep a circle round the turning point. It needs a clear circle twice as wide as the distance from the turning point to its furthest corner. A rover 15 cm wide with 11 cm behind the turning point needs about 27 cm. The simulator’s Rover tab shows the number for your rover.'),
    ...bullets([
      'If a turn has no room, the rover swings back and tries the long way round, then shuffles a few centimetres sideways and tries again. If nothing works, the turn gives back `False`.',
      'A **compact** rover, with the turning point near the middle, gets through more of the course.',
    ]),
    H2('Different wheel layouts'),
    table(['Layout', 'Does it work?'], [
      ['Two drive wheels and a caster or ball', 'Yes: the simplest and most accurate.'],
      ['Four or six wheels, the wheels on each side geared to one motor (skid steer)', 'Yes. The wheels slide sideways when it turns, so turns take more motor degrees and the turning point is between the axles. Run tests 5 and 6 and enter the results in the simulator.'],
      ['Two drive wheels at the back, two free wheels at the front that cannot swivel', 'Works, but it turns round the front axle and needs a lot of room. A caster or ball at the front is much better.'],
      ['Driven wheels of different sizes on the same side', 'No: they roll at different speeds, fight each other and slip.'],
      ['Car steering', 'No (see above).'],
    ], [0.45, 0.55]),
    gap(),
    H2('Two motors on each side'),
    P('The software drives one motor per side. If your rover has a second motor on each side, you need to change three functions in the Setup section: `set_wheel_speeds`, `stop` and `reset_wheel_counters`. Add one line for each extra motor, like this (the extra motors here are on ports E and F):'),
    ...code([
      'def set_wheel_speeds(left, right):',
      '    motor.run(LEFT_MOTOR_PORT, int(left * LEFT_MOTOR_DIRECTION))',
      '    motor.run(RIGHT_MOTOR_PORT, int(right * RIGHT_MOTOR_DIRECTION))',
      '    motor.run(port.E, int(left * LEFT_MOTOR_DIRECTION))      # second left motor',
      '    motor.run(port.F, int(right * RIGHT_MOTOR_DIRECTION))    # second right motor',
      '',
      'def stop():',
      '    motor.stop(LEFT_MOTOR_PORT)',
      '    motor.stop(RIGHT_MOTOR_PORT)',
      '    motor.stop(port.E)',
      '    motor.stop(port.F)',
      '',
      'def reset_wheel_counters():',
      '    motor.reset_relative_position(LEFT_MOTOR_PORT, 0)',
      '    motor.reset_relative_position(RIGHT_MOTOR_PORT, 0)',
      '    motor.reset_relative_position(port.E, 0)',
      '    motor.reset_relative_position(port.F, 0)',
    ]),
    note('This assumes each extra motor is mounted the same way round as the first motor on its side. If it is mounted the other way round, use a minus: `int(-left * LEFT_MOTOR_DIRECTION)`. Check with tests 1 and 2: both motors on a side must roll their wheels forwards.', 'warn'),
    H2('Sensors'),
    ...bullets([
      'The **distance sensor** must point **straight ahead**, level, at the height of the walls. On the middle line is best: off to one side, it can see past corners the middle of the rover meets.',
      'The **colour sensor** must face the floor, close to it. It can be in front of or behind the wheels; set `COLOUR_SENSOR_POSITION_CM` to match.',
      'The **hub** can sit any way up, as long as `HUB_FACE_UP` says which way.',
    ]),
  ].concat(pkg === 'basic' ? [] : [
    note('**Front or back for the colour sensor?** Front is better. With `CHECK_BY_WALLS = True`, a rover with the sensor in front just drives up to each wall and back. With it behind, the rover must turn round at every wall and reverse blind (there is no sensor at the back), which is slower, riskier, and needs room to turn.', 'key'),
  ]);
}

function tuningChapter(pkg) {
  const k = PACKAGES[pkg];
  const rows = [
    ['`DRIVE_SPEED` (400)', 'Wheel speed when driving, in degrees per second (up to about 1000). Lower it if the wheels slip or the rover tips.'],
    ['`DRIVE_SLOW_SPEED` (150), `DRIVE_SPEED_UP_CM` (4), `DRIVE_SLOW_ZONE_CM` (4)', 'The rover speeds up gently over the first few cm of a drive and slows down gently over the last few, so it does not lurch and stops on the spot. If drives overshoot, make the slow zone bigger or the slow speed lower. If the rover still jerks, make both zones bigger.'],
    ['`TURN_SPEED` (200), `TURN_SLOW_SPEED` (100), `TURN_SLOW_ZONE` (15)', 'The same for turns, in degrees. If turns overshoot or wobble, lower `TURN_SLOW_SPEED`.'],
    ['`TURN_ACCURACY` (2), `TURN_NUDGE_SPEED` (30)', 'A turn that ends more than 2 degrees off is corrected with slow nudges. If the rover sits still trying to nudge (a heavy rover, or one with many wheels), raise `TURN_NUDGE_SPEED`.'],
    ['`STEERING` (10)', 'How strongly the gyro steers the rover back when it drifts off course. 0 = off. If it wiggles while driving, lower it.'],
    ['`STUCK_MS` (1000)', 'Wheels not moving for this long = stuck.'],
    ['`TICK_MS` (20)', 'How often it checks the sensors while moving. Leave it.'],
    ['`MAX_TRUSTED_CM` (200)', 'Distance readings further than this count as “no echo”. The sensor cannot see further than 2 m. If no straight path in your course is that long, set it a little below the longest one.'],
    ['`SETTLE_MS` (150)', 'How long a careful reading waits for the rover to stop wobbling.'],
  ];
  if (k.grid) rows.push(
    ['`STEP_CM` (12)', 'The size of one grid square. Smaller squares fit through narrower gaps and miss fewer small patches, but the search takes longer.'],
    ['`WALL_STOP_CM` (10)', 'A step stops early if a wall is this close.'],
    ['`WALL_CHECK_GAP_CM` (5)', 'How close the wall check brings the rover to the wall.']);
  if (pkg === 'explorer') rows.push(
    ['`HEAD_STRENGTH` (1)', 'How strongly the explorer follows a hint: how many extra steps it will drive to reach a square one step further the way you asked.'],
    ['`NO_ECHO_SQUARES` (2)', 'When a look gets no echo, how many squares ahead it counts as open.']);
  return [
    H1('10. Fine tuning'),
    P('The FINE TUNING settings are below the SETTINGS in your file. The default values (in brackets) work for most rovers. **Start with the defaults**, then change a setting when something below describes your problem, or when you want to see what it does.'),
    note('Change **one** setting at a time, write down the old value, and try it in the simulator before the real rover.', 'key'),
    table(['Setting (default)', 'What it does, and when to change it'], rows, [0.4, 0.6]),
  ];
}

function troubleChapter(pkg) {
  const rows = [
    ['`SETTINGS PROBLEM: ...` and the rover does not move', 'A setting is wrong. The message says which, and what it should be.'],
    ['Nothing happens, or the program ends at once', 'Exactly one `runloop.run(...)` line at the bottom must have no `#` in front.'],
    ['A move is skipped, or several happen at once', 'A move is missing `await` in front.'],
    ['The wrong wheel turns, or a wheel rolls backwards', '`setup_check` tests 1 and 2.'],
    ['The rover spins and spins, or turns the wrong way', '`setup_check` test 3 (`HUB_FACE_UP`, or swapped motor ports).'],
    ['Drives are too long or too short', '`setup_check` test 4 (`WHEEL_DIAMETER_CM`, `WHEEL_GEAR_RATIO`).'],
    ['Turns overshoot or wobble', 'Lower `TURN_SLOW_SPEED` (chapter 10).'],
    ['`turn: no room to turn ...`', 'The rover is too close to a wall to spin. Give it more room, or make the rover more compact (chapter 9).'],
    ['`drive: stuck after ...`', 'The rover was pushing against something.'],
    ['The distance sensor always says no echo (-1)', 'Check `DISTANCE_SENSOR_PORT` and that the sensor points straight at the walls. Walls seen at a slant bounce the sound away.'],
    ['Colours are never found', 'Check `COLOURS_TO_FIND`, `COLOUR_SENSOR_PORT` and `setup_check` test 8. Is the sensor close to the floor?'],
    ['The run stops after a while', '`MAX_RUN_SECONDS` is set.'],
    ['`TypeError: motor speeds must be whole numbers`', 'You used `motor.run` yourself with a decimal number: use `int(...)`.'],
    ['It works in the simulator but not on the floor', 'Compare your settings with the simulator’s Rover tab, and run `setup_check` again on the real rover.'],
  ];
  if (pkg !== 'basic') rows.push(['The rover wanders, and its map makes no sense', 'Usually `WHEEL_DIAMETER_CM` or the rover size is wrong: every step is then the wrong length. Check the settings with the simulator’s Rover tab.']);
  return [
    H1('11. Troubleshooting'),
    table(['What you see', 'What to do'], rows, [0.42, 0.58]),
  ];
}

function quickRefChapter(pkg) {
  const lines = [
    'await drive_forward(cm)                  await drive_forward(cm, stop_at_wall_cm=10)',
    'await drive_backward(cm)                 await drive_to_wall(stop_cm)',
    'await turn_left(degrees)                 await turn_right(degrees)',
    'await turn_to(NORTH / WEST / SOUTH / EAST / any heading)',
    'read_distance()     await measure_distance()     cm_driven()     rover_position()',
    'read_colour()       colour_name(colour)          found_colours   end_run()',
  ];
  if (pkg === 'wall') lines.push('await follow_wall()');
  if (pkg === 'explorer') lines.push('await explore()     await explore(find=color.GREEN, near=(x, y))     await explore(find=color.RED, towards=30)');
  return [
    H1('12. Quick reference'),
    H2('Functions'),
    ...code(lines),
    H2('Directions'),
    P('`NORTH` 0 (start direction) · `WEST` 90 · `SOUTH` 180 · `EAST` -90 · turning left makes the number bigger.'),
    H2('Your program'),
    ...code(['async def my_program():', '    await drive_forward(50)        # every move needs await', '    await turn_to(WEST)']),
    H2('setup_check'),
    P('RIGHT = start / next test · LEFT = repeat the test · middle button = stop. Tests: 1 left wheel, 2 right wheel, 3 gyro, 4 drive 30 cm, 5 turning, 6 turning point, 7 distance sensor, 8 colour sensor.'),
  ];
}

function packageManual(pkg) {
  const k = PACKAGES[pkg];
  const ch8 = { basic: 'Planning a route', wall: 'The wall follower', explorer: 'The maze explorer' }[pkg];
  listInstance = 0;
  const children = [
    ...titlePage('Rover Software', k.name + ' — User Manual', [
      'Software version ' + VERSION + ', ' + DATE + '.',
      'For teams using a LEGO SPIKE Prime hub with the SPIKE App 3 (Python).',
    ]),
    ...contents(['About your package', 'Your first hour', 'Your program file', 'Describing your rover: the SETTINGS', 'setup_check: testing your rover',
      'Writing your own program', 'Reacting to colours', ch8, 'Will the software work with my rover?', 'Fine tuning', 'Troubleshooting', 'Quick reference']),
    ...aboutChapter(pkg), ...firstHourChapter(pkg), ...fileChapter(pkg), ...settingsChapter(pkg), ...setupCheckChapter(),
    ...programChapter(pkg), ...colourChapter(pkg),
    ...(pkg === 'basic' ? basicRouteChapter() : pkg === 'wall' ? wallChapter() : explorerChapter()),
    ...roverFitChapter(pkg), ...tuningChapter(pkg), ...troubleChapter(pkg), ...quickRefChapter(pkg),
  ];
  return writeDoc(k.file, 'Rover Software — ' + k.name, children);
}

/* ===================== The simulator ===================== */

function simManual() {
  listInstance = 0;
  const children = [
    ...titlePage('Rover Simulator', 'User Manual', [
      'For rover software version ' + VERSION + ', ' + DATE + '.',
      'Test your rover and your program on a computer before you test them on the floor.',
    ]),
    ...contents(['What the simulator does', 'Starting the simulator', 'A tour of the screen', 'Running your program', 'Reading the map',
      'The Log tab', 'The Rover tab: describing your rover', 'The Parameters tab', 'The Course tab: drawing your course', 'The Code tab',
      'A good way to test', 'Troubleshooting']),

    H1('1. What the simulator does'),
    P('The simulator runs **your real program file** on a computer, with a pretend rover on a pretend course. It is the same Python code you put on the hub: there is nothing to translate. Every Run reads the file again, so you can change your program, save it and run it again straight away.'),
    P('Use it to:'),
    ...bullets([
      'check your settings match your rover, before you spend time on the floor',
      'try your own route, or the autonomy, on your competition course',
      'see what the rover “thought” at every moment: every message, where it was, and what its sensors saw',
      'try design ideas, such as moving a sensor or adding wheels, without rebuilding anything',
    ]),
    H2('What it cannot tell you'),
    P('The simulator is a model, so it is never perfect. Always test on the real rover too. In particular:'),
    ...bullets([
      'The floor is perfectly flat and grippy, the battery never runs low and the motors never get tired.',
      'The sensors are simple models. The pretend colour sensor only knows the **green** and **red** patches you draw; everywhere else it reads white.',
      'For rovers with four or more wheels that cannot swivel, the way it turns is an **estimate** until you enter measurements from your real rover (chapter 7).',
      'The hub’s buttons are pressed for you: whenever a program waits for the RIGHT button, the simulator presses it. LEFT is never pressed.',
      'It runs desktop Python, not the hub’s MicroPython. A few things that work here can still fail on the hub.',
    ]),

    H1('2. Starting the simulator'),
    P('You need **Google Chrome** or **Microsoft Edge**, and an internet connection the first time (the simulator downloads Python into the browser).'),
    H2('The simple way'),
    ...steps([
      'Double-click `rover_sim.html` in the simulator folder. It opens in your browser. Wait until the status at the top left of the map says **READY**.',
      'Click the **Code** tab, then **Choose a file instead**, and choose your program file (your `.py` file).',
      'Click **Run**.',
    ]),
    P('From then on, every Run reads the latest saved version of your file. You do not need to choose it again until you reopen the page.'),
    H2('With Python installed'),
    P('If your computer has Python, you can also start it with `python sim/serve_sim.py` from the folder that holds the `sim` folder. It opens the browser for you and reads `spike_all_in_one.py` from that folder, so save your program under that name (or choose a file as above).'),

    H1('3. A tour of the screen'),
    ...img('sim_overview_marked', 'The simulator after a run. The numbers match the table below.', 640, 470),
    table(['', 'Part', 'What it is for'], [
      ['1', 'Program', 'Which program to run. “As in the file” runs the one chosen at the bottom of your file.'],
      ['2', 'Tools and view', 'Draw the course, move and zoom the view, and choose what the map shows (chapters 5 and 9).'],
      ['3', 'Status bar', 'The run’s status, time, steps, looks and the colours found.'],
      ['4', 'Map', 'The course, the rover, and where it has been.'],
      ['5', 'Run controls', 'Run, Pause, Step, Reset and Speed (chapter 4).'],
      ['6', 'Tabs', 'Log, Parameters, Rover, Course and Code.'],
      ['7', 'Side panel', 'The open tab: here, the Log of everything the program printed.'],
    ], [0.06, 0.24, 0.7]),

    H1('4. Running your program'),
    ...img('sim_topbar', 'Program and run controls.', 640, 60),
    table(['Control', 'What it does'], [
      ['**Program**', 'Which program to run. It lists every program in the `runloop.run(...)` lines at the bottom of your file, so you can switch without editing the file.'],
      ['**Run**', 'Reads your file again and starts the run. While a run is going it says Restart; afterwards, Run again.'],
      ['**Pause** / **Resume**', 'Freeze the run and carry on.'],
      ['**Step**', 'Run until the program prints its next line, then pause. Press it again for the next line. Great for following a decision.'],
      ['**Reset**', 'Stop the run and put the rover back at the start.'],
      ['**Speed**', '1× is real time. Max runs as fast as the computer can.'],
    ], [0.25, 0.75]),
    gap(),
    P('Keyboard: **R** runs, **Space** pauses, **N** steps.'),
    H2('The status bar'),
    ...img('sim_hud', null, 460, 40),
    table(['Status', 'Meaning'], [
      ['READY', 'Python is loaded and waiting for you.'],
      ['RUNNING / PAUSED', 'A run is going, or paused.'],
      ['FINISHED', 'The program ended by itself.'],
      ['ERROR', 'The program stopped with an error. The Log shows the message, in red, with the line number.'],
      ['TIME LIMIT', 'The run went on for longer than the `timeLimit` parameter (900 s), so the simulator stopped it.'],
    ], [0.25, 0.75]),
    gap(),
    P('Next to it: the time in the run, the **steps** the autonomy made (and how many were blocked), the **looks** (distance measurements), and the **colours** found.'),
    ...img('sim_mismatch_hud', null, 560, 40),
    note('A red **Settings do not match the rover** badge means a setting in your file does not match the rover on the Rover tab. Fix it before you trust a run: chapter 7 shows where.', 'warn'),

    H1('5. Reading the map'),
    ...img('sim_logsel', 'After a run. A log line is selected, so a dashed rover shows where the rover was when it printed that line.', 640, 430),
    table(['On the map', 'What it shows'], [
      ['Brown boxes', 'Walls.'],
      ['Green, red and blue boxes', 'The colour patches.'],
      ['Yellow dashed box', 'The `COURSE_` limits from your code (Wall follower and Maze explorer). The rover never plans a move outside it.'],
      ['Dashed circle and START', 'Where the rover starts. It always starts facing up the screen (NORTH).'],
      ['The rover', 'Its outline, its wheels (dark = driven by a motor), the distance sensor (orange dot), the colour sensor (blue ring) and the turning point (+).'],
      ['Blue line (**Path**)', 'Where the rover’s turning point went.'],
      ['Orange dots (**Echoes**)', 'Where the distance sensor’s sound bounced back. An orange fan flashes each time it measures.'],
      ['Shaded squares, crosses and bars (**Map**)', 'The explorer’s map (Maze explorer only): shaded = visited, red cross = too close to a wall to stand in, red bar = move blocked by a wall, red circle = the square it is heading for.'],
      ['Dashed purple rover', 'Where the rover was when the selected Log line was printed.'],
    ], [0.32, 0.68]),
    gap(),
    P('Scroll to zoom in and out, towards the mouse pointer. With the **Look** tool, drag to move the view. **Fit course** zooms to the course; **Whole floor** shows the whole 10 m × 10 m floor. Untick **Echoes**, **Path** or **Map** to hide them.'),

    H1('6. The Log tab'),
    P('The Log shows every line the program printed, with the time it was printed, in seconds. A coloured square shows what kind of line it is:'),
    table(['Colour', 'Kind of line'], [
      ['Green', 'A colour was found'], ['Blue', 'A step was done'], ['Red', 'A step was blocked, or the run finished'],
      ['Purple', 'A decision (where the autonomy is heading next)'], ['Orange', 'A look with the distance sensor, or a wall check'],
      ['Grey', 'Any other message'],
    ], [0.3, 0.7]),
    gap(),
    ...bullets([
      '**Click a line** to see where the rover was when it printed it (a dashed rover on the map). Click it again to clear it.',
      '**Show drive and turn lines** also shows the detailed `drive:` and `turn:` lines. They are hidden at first, to keep the Log short.',
      '**Follow** keeps the newest line in view. It switches off when you click a line, so the Log stops jumping.',
      'Errors appear in red, with the line number in your file.',
    ]),

    H1('7. The Rover tab: describing your rover'),
    P('Here you tell the simulator what your rover looks like. The simulator drives **this** rover, whatever your file says, so make it match the rover you built.'),
    ...img('sim_rover_top', 'The top of the Rover tab: presets, name and the rover editor.', 330, 560),
    H2('Starting from a preset'),
    P('Choose the preset closest to your rover and click **Load preset**: two drive wheels and a caster; four or six wheels with two motors (skid steer); or rear drive with two free front wheels. Then give it your rover’s **Name** and change it to match.'),
    H2('The editor'),
    P('The editor shows the rover from above, front at the top, with grid lines every centimetre (bold every 5 cm). Below it, the pointer’s position is shown in cm.'),
    table(['Tool', 'How to use it'], [
      ['**Select**', 'Click a part to change it. Drag it to move it. Drag a corner of a selected box to resize it. Press Delete to remove it.'],
      ['**Box**', 'Drag to add a box to the body. Build the outline from boxes: one for the chassis, one for an arm sticking out, and so on.'],
      ['**Wheel**', 'Click to add a wheel. It is driven by the motor already driving that side.'],
      ['**Caster**', 'Click to add a caster or ball: a wheel that swivels.'],
      ['**Distance**, **Colour**', 'Click to add a sensor.'],
    ], [0.22, 0.78]),
    gap(),
    ...img('sim_rover_props', 'A wheel is selected: its settings appear under the editor.', 300, 520),
    P('Click a part to change it exactly:'),
    ...bullets([
      'Wheels: **Kind** (driven by a motor; free, which rolls but cannot swivel; or caster), diameter, position, and for a driven wheel the **motor port**, which way is **forward** and the **gear** ratio. **Copy to the other side** adds the matching wheel on the other side.',
      'Sensors: port, position, and for the distance sensor the angle (0 = straight ahead).',
      'Boxes: the positions of their four edges.',
    ]),
    P('The red **+** shows where the rover turns. If a change makes the rover unusable (for example, no driven wheel on one side), a message under the editor says what is missing, and the simulator keeps using the last working rover.'),
    ...img('sim_rover_bottom', 'The bottom of the Rover tab.', 330, 560),
    H2('The summary'),
    P('It says where the rover turns, how big a clear circle it needs to turn on the spot, how many motor degrees a quarter turn takes, and which ports drive which side.'),
    H2('Your program and this rover'),
    P('This compares the settings in your file with the rover you drew, and lists every setting that does not match. It also warns about things no setting can fix, such as two motors on one side, or wheels of different sizes on the same side.'),
    ...img('sim_mismatch_check', 'A four-wheel rover tested with the settings of a two-wheel rover.', 330, 200),
    P('**Copy settings for my program** copies the right settings for this rover. Paste them over the same lines in the SETTINGS part of your file.'),
    note('A rover that runs with the wrong settings drives the wrong distances, so it gets lost. In one test, a four-wheel rover exploring the course with the settings of a two-wheel rover was still searching after 15 minutes and had found only one of the two colours. With the right settings it found both in 7 minutes.', 'warn'),
    H2('Match my real rover'),
    P('For rovers with four or more wheels that cannot swivel, the simulator can only estimate how they turn. Enter two measurements from your real rover to make it turn the same way:'),
    ...bullets([
      '**Turning point, cm behind the front**: from `setup_check` test 6.',
      '**Motor degrees for a quarter turn**: `setup_check` test 5 prints it.',
    ]),
    P('Leave a box empty to use the estimate.'),
    H2('Saving and sharing your rover'),
    P('The simulator remembers your rover in this browser. To save it, or share it with your team, open **Rover as JSON**, click **Copy JSON** and paste it into a text file. To load it, paste it back and click **Apply JSON**.'),

    H1('8. The Parameters tab'),
    ...img('sim_params_file', 'The first settings from your file.', 340, 460),
    H2('From your file'),
    P('Every number and True/False setting in the SETTINGS and FINE TUNING parts of your file. Change one here to try a different value **in the simulator only**: your file is not changed. Changed values are marked “changed” and stay changed until you click **Clear all overrides**. Type in the filter box to find a setting.'),
    note('When you find a value that works, write it into your file. Otherwise the real rover will not use it.', 'warn'),
    ...img('sim_params_model', 'The sensor and motion model.', 300, 400),
    H2('Sensor and motion model'),
    P('How the pretend sensors and motors behave. Make them tougher to check your program copes with a less perfect world.'),
    table(['Parameter (default)', 'What it does'], [
      ['`coneHalf` (12)', 'Half the width of the distance sensor’s beam, in degrees.'],
      ['`maxIncidence` (40)', 'A wall seen more than this many degrees off square bounces the sound away: no echo.'],
      ['`sonarRange` (200)', 'The furthest the distance sensor can see, in cm.'],
      ['`dropoutPct` (0)', 'The percentage of readings that randomly get no echo. Try 10.'],
      ['`noiseCm` (0)', 'Random error added to each reading, in cm. Try 2.'],
      ['`turnMomentum` (0.08), `driveMomentum` (0.05)', 'How far the rover coasts after the motors stop, in seconds of movement.'],
      ['`timeLimit` (900)', 'The simulator stops a run after this many seconds.'],
    ], [0.38, 0.62]),

    H1('9. The Course tab: drawing your course'),
    ...img('sim_course_tools', 'The drawing tools.', 640, 40),
    table(['Tool', 'How to use it'], [
      ['**Look**', 'Drag to move the view (no drawing).'],
      ['**Wall**', 'Drag to draw a wall.'],
      ['**Green**, **Red**', 'Drag to draw the green or red patch. There is one of each: drawing a new one replaces the old one.'],
      ['**Start**', 'Click where the rover’s turning point starts. It always starts facing up the screen.'],
      ['**Erase**', 'Click a wall or a patch to remove it.'],
      ['**Snap 5 cm**', 'Keeps drawing on a 5 cm grid. Untick it for exact positions.'],
    ], [0.22, 0.78]),
    gap(),
    ...img('sim_course', 'The Course tab.', 300, 380),
    P('The **Course** tab has four ready-made courses (**Load preset**), including the real competition course, and **Remove all walls**. The course is also shown as JSON, in cm with y pointing up the screen: each wall is `[x0, x1, y0, y1]`. To build your competition course exactly, measure it, type the walls into the JSON and click **Apply JSON**. **Copy JSON** saves it to share.'),
    note('You cannot edit the course while a run is going: press Reset first.', 'tip'),

    H1('10. The Code tab'),
    ...img('sim_code', 'The Code tab.', 300, 300),
    ...bullets([
      '**File to run**: the program file the simulator reads, as a path from the simulator page. It only works when the page was started with `python sim/serve_sim.py`.',
      '**Choose a file instead**: pick your program file from the computer. Use this when you opened the page by double-clicking it.',
      '**Reload now**: read the file again without running it, for example to update the Parameters tab.',
      'The line below says which file was read, how many lines it has and when it was saved, so you can check it is the version you expect.',
    ]),

    H1('11. A good way to test'),
    ...steps([
      'Draw your rover on the **Rover** tab, and fix every setting in **Your program and this rover** until it says they match.',
      'Draw your competition course on the **Course** tab, as exactly as you can.',
      'Run `setup_check` (choose it in **Program**) to check the settings make sense.',
      'Run your program at **Max** speed to see the result, then at **5×** or with **Step** to watch the decisions.',
      'When something goes wrong, click the Log lines just before it to see where the rover was and what it saw.',
      'Make it harder: in **Parameters**, set `dropoutPct` to 10 and `noiseCm` to 2, and move the start a few cm. A program that still works is much more likely to work on the floor.',
      'Test on the real rover. If it behaves differently, measure it (setup_check tests 5 and 6) and enter the numbers on the Rover tab.',
    ]),

    H1('12. Troubleshooting'),
    table(['What you see', 'What to do'], [
      ['**Python failed** at the top left', 'The simulator could not download Python. Connect to the internet and reload the page.'],
      ['The Code tab says the page **cannot read files by path**, or **could not read** the file', 'Use **Choose a file instead** on the Code tab.'],
      ['`the file never calls runloop.run(...)`', 'Exactly one `runloop.run(...)` line at the bottom of your file must have no `#` in front.'],
      ['The red **Settings do not match the rover** badge', 'Open the Rover tab: it lists the settings that differ. Fix the rover drawing or your file.'],
      ['`A loop in your program reads sensors over and over but never waits`', 'In the simulator, the rover only moves while your program waits. Put `await runloop.sleep_ms(10)` inside the loop.'],
      ['`TypeError: motor speeds must be whole numbers`', 'Use `int(...)` around motor speeds. The hub stops with an error there too.'],
      ['`OSError ... no distance sensor on port ...`', 'The port in your file has no sensor on the Rover tab. Fix the port in one of them.'],
      ['**TIME LIMIT**', 'The run took longer than `timeLimit`. Raise it in Parameters, or make the program faster.'],
      ['The run does not match the real rover', 'Compare settings (Rover tab), and enter your real rover’s measurements in Match my real rover.'],
    ], [0.4, 0.6]),
  ];
  return writeDoc('Rover Simulator - User Manual.docx', 'Rover Simulator — User Manual', children);
}

/* ===================== Organiser guide ===================== */

function organiserGuide() {
  listInstance = 0;
  const children = [
    ...titlePage('Rover Software', 'Organiser Guide', [
      'Version ' + VERSION + ', ' + DATE + '.',
      'For the people who build the software packages and hand them out. Students do not need this guide.',
    ]),
    H1('1. What is in the folder'),
    table(['Path', 'What it is'], [
      ['`modules/`', 'The rover software, one file per part. **This is the source: change the software here, never in a built file.**'],
      ['`build.py`', 'Joins the modules into the one file a team gets (the SPIKE App runs a single file).'],
      ['`builds/`', 'Where built team files go (not kept in git).'],
      ['`spike_all_in_one.py`', 'A build with every module, for testing.'],
      ['`sim/`', 'The simulator: `rover_sim.html` (the simulator itself) and `serve_sim.py` (an optional launcher).'],
      ['`docs/`', 'These manuals, the script that makes them (`make_manuals.js`) and the screenshots.'],
    ], [0.3, 0.7]),
    H1('2. Building a team’s file', false),
    P('Each team buys one of three packages. Build their file with the package name and the team name:'),
    ...code(['python build.py basic --team "Rocket Rovers"', 'python build.py wall_follower --team "Rocket Rovers"', 'python build.py explorer --team "Rocket Rovers"']),
    P('This writes `builds/rocket_rovers.py`. The header names the team, the package, the version and the date it was built.'),
    table(['Package', 'Contains'], [
      ['`basic`', 'Setup and setup_check, Movement, Distance sensor, Colour sensor.'],
      ['`wall_follower`', 'Everything in basic, plus Grid moves and the Wall follower.'],
      ['`explorer`', 'Everything in basic, plus Grid moves and the Maze explorer.'],
      ['`all`', 'Everything (for testing only).'],
    ], [0.25, 0.75]),
    H2('Upgrading a team'),
    P('Build again with the **same team name**. If the file already exists, its **YOUR PROGRAM** section is kept, so the team does not lose its program. Two things are not carried over:'),
    ...bullets([
      'The “choose what runs” lines are the team’s old ones, so a team that upgrades to the explorer must add `runloop.run(run_program(explore))` itself (with a `#` in front).',
      'Their **SETTINGS** and their **`on_colour_found()`** go back to the defaults. Ask the team for their current file first, and copy those parts across.',
    ]),
    H1('3. What to give each team', false),
    ...bullets([
      'Their built `.py` file.',
      'The user manual for their package.',
      'The simulator folder (`sim/`) and the simulator manual. Everyone gets these, whichever package they bought. The simulator needs Chrome or Edge, and internet the first time it opens.',
      'Optionally, the competition course as simulator JSON (draw it once on the Course tab and use Copy JSON), so every team tests on the same course.',
    ]),
    H1('4. Before the event', false),
    ...steps([
      'Build all three packages and open each in the simulator. Run `setup_check` and the package’s main program on the competition course.',
      'Run each package on a real rover: `setup_check` first, then the main program. See the limits below.',
      'Print or share the manuals for the version you are handing out (the version is on every page).',
    ]),
    H2('Known limits'),
    ...bullets([
      'Hardware testing so far has used one rover with two drive wheels. `setup_check` has run on it; the autonomy programs have been tested mostly in the simulator.',
      'The explorer’s planning time and memory on the hub with large `COURSE_` limits have not been measured. Keep the limits close to the real course.',
      'For rovers with four or more wheels that cannot swivel, the simulator’s turning is an estimate until a team enters its own measurements.',
      'Rovers with car-style steering cannot use the turning functions or the autonomy.',
    ]),
    H1('5. Changing the software', false),
    ...steps([
      'Change the files in `modules/`. Each module has a description at the top (`#@about`), settings teams must set (`#@settings`), fine tuning (`#@tuning`) and code (`#@code`). Lines between `#@only explorer` and `#@end` only go into packages with the explorer.',
      'Raise `VERSION` at the top of `build.py`, so teams and helpers can tell versions apart.',
      'Rebuild `spike_all_in_one.py` (`python build.py all --out spike_all_in_one.py`) and check every program in the simulator still behaves as before.',
      'Update the manuals: change the text in `docs/make_manuals.js` and run `node make_manuals.js` in the `docs` folder. If the simulator’s look changed, retake the screenshots with `docs/tools/takeshots.py`.',
    ]),
  ];
  return writeDoc('Rover Software - Organiser Guide.docx', 'Rover Software — Organiser Guide', children);
}

(async () => {
  await packageManual('basic');
  await packageManual('wall');
  await packageManual('explorer');
  await simManual();
  await organiserGuide();
})().catch(e => { console.error(e); process.exit(1); });
