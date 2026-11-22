// Traditional Japanese textile patterns, drawn by code onto the paper texture.
// Any cloth part can use one by data: { "color": "#2b4a6b", "pattern": "seigaiha", "fg": "#e8dcc4", "scale": 1 }
// Because patterns are generated (not image files), colour and size can change per video.
//
//   seigaiha  青海波  overlapping waves (calm sea, good fortune)
//   asanoha   麻の葉  hemp-leaf star (strength, growth)
//   kikko     亀甲    tortoise-shell hexagons (long life)
//   ichimatsu 市松    checkerboard (continuity)
//   yagasuri  矢絣    arrow feathers (resolve, no turning back)
//   uroko     鱗      triangle scales (protection from evil)
//   shippo    七宝    interlocking circles (harmony)
//   sakura    桜      falling cherry blossom (life's brevity, the samurai flower)
//   momiji    紅葉    maple leaves (autumn)
//   kumo      雲      stylised clouds

export const PATTERNS = ['seigaiha', 'asanoha', 'kikko', 'ichimatsu', 'yagasuri', 'uroko', 'shippo', 'sakura', 'momiji', 'kumo'];

export function drawPattern(g, size, p) {
  const type = p.pattern, fg = p.fg ?? '#efe6d4';
  const s = (size / 8) * (p.scale ?? 1);        // base cell size in pixels
  g.save();
  g.strokeStyle = fg; g.fillStyle = fg;
  g.lineWidth = Math.max(1.5, s * 0.07);
  g.lineJoin = g.lineCap = 'round';
  const cols = Math.ceil(size / s) + 2, rows = Math.ceil(size / s) + 2;

  if (type === 'seigaiha') {
    for (let r = rows * 2; r >= -1; r--) for (let c = -1; c < cols; c++) {
      const x = c * s + (r % 2 ? s / 2 : 0), y = r * s * 0.25;
      for (let k = 4; k >= 1; k--) {
        g.beginPath(); g.arc(x, y, (s / 2) * (k / 4), Math.PI, 0);
        k === 4 ? (g.save(), g.fillStyle = p.color, g.fill(), g.restore()) : 0;
        g.stroke();
      }
    }
  } else if (type === 'asanoha') {
    const h = s * Math.sqrt(3) / 2;
    for (let r = -1; r < rows; r++) for (let c = -1; c < cols; c++) {
      const cx = c * s + (r % 2 ? s / 2 : 0), cy = r * h;
      for (let a = 0; a < 6; a++) {
        const ang = (a / 6) * Math.PI * 2 + Math.PI / 6;
        g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(ang) * s / Math.sqrt(3), cy + Math.sin(ang) * s / Math.sqrt(3)); g.stroke();
        g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(ang - Math.PI / 6) * s / 2, cy + Math.sin(ang - Math.PI / 6) * s / 2); g.stroke();
      }
    }
  } else if (type === 'kikko') {
    const R = s / 2, h = R * Math.sqrt(3);
    for (let r = -1; r < rows; r++) for (let c = -1; c < cols; c++) {
      const cx = c * R * 3 + (r % 2 ? R * 1.5 : 0), cy = r * h / 2;
      for (const rr of [R, R * 0.7]) {
        g.beginPath();
        for (let a = 0; a <= 6; a++) { const ang = (a / 6) * Math.PI * 2; a ? g.lineTo(cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr) : g.moveTo(cx + rr, cy); }
        g.stroke();
      }
    }
  } else if (type === 'ichimatsu') {
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) if ((r + c) % 2 === 0) g.fillRect(c * s, r * s, s, s);
  } else if (type === 'yagasuri') {
    for (let c = -1; c < cols; c++) for (let r = -1; r < rows; r++) {
      const x = c * s, y = r * s * 1.2 + (c % 2 ? s * 0.6 : 0);
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + s / 2, y + s * 0.35); g.lineTo(x + s, y);
      g.lineTo(x + s, y + s * 0.6); g.lineTo(x + s / 2, y + s * 0.95); g.lineTo(x, y + s * 0.6); g.closePath(); g.fill();
    }
  } else if (type === 'uroko') {
    for (let r = 0; r < rows; r++) for (let c = -1; c < cols; c++) {
      const x = c * s + (r % 2 ? s / 2 : 0), y = r * s * 0.87;
      g.beginPath(); g.moveTo(x, y + s * 0.87); g.lineTo(x + s / 2, y); g.lineTo(x + s, y + s * 0.87); g.closePath(); g.fill();
    }
  } else if (type === 'shippo') {
    for (let r = -1; r < rows; r++) for (let c = -1; c < cols; c++) {
      g.beginPath(); g.arc(c * s, r * s, s / Math.SQRT2, 0, Math.PI * 2); g.stroke();
      g.beginPath(); g.arc(c * s + s / 2, r * s + s / 2, s / Math.SQRT2, 0, Math.PI * 2); g.stroke();
    }
  } else if (type === 'sakura' || type === 'momiji') {
    let seed = 99;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const n = Math.round((size / s) * (size / s) * 0.9);
    for (let i = 0; i < n; i++) {
      const x = rnd() * size, y = rnd() * size, rad = s * (0.25 + rnd() * 0.25), rot = rnd() * 6.28;
      g.save(); g.translate(x, y); g.rotate(rot);
      if (type === 'sakura') {
        for (let k = 0; k < 5; k++) {
          g.rotate((Math.PI * 2) / 5);
          g.beginPath(); g.moveTo(0, 0);
          g.bezierCurveTo(rad * 0.5, -rad * 0.3, rad * 1.1, -rad * 0.25, rad, 0);
          g.lineTo(rad * 0.85, rad * 0.08);
          g.bezierCurveTo(rad * 1.1, rad * 0.25, rad * 0.5, rad * 0.3, 0, 0); g.fill();
        }
      } else {
        for (let k = 0; k < 7; k++) {
          const ang = -Math.PI / 2 + (k - 3) * 0.42, len = rad * (1 - Math.abs(k - 3) * 0.13);
          g.beginPath(); g.moveTo(0, 0);
          g.lineTo(Math.cos(ang - 0.18) * len * 0.6, Math.sin(ang - 0.18) * len * 0.6);
          g.lineTo(Math.cos(ang) * len, Math.sin(ang) * len);
          g.lineTo(Math.cos(ang + 0.18) * len * 0.6, Math.sin(ang + 0.18) * len * 0.6); g.closePath(); g.fill();
        }
        g.fillRect(-1, 0, 2, rad * 0.5);
      }
      g.restore();
    }
  } else if (type === 'kumo') {
    for (let r = 0; r < rows / 2; r++) for (let c = -1; c < cols / 2; c++) {
      const x = c * s * 2 + (r % 2 ? s : 0), y = r * s * 2 + s;
      g.beginPath();
      g.arc(x, y, s * 0.35, Math.PI, 0); g.arc(x + s * 0.55, y, s * 0.25, Math.PI, 0); g.arc(x + s * 1.0, y, s * 0.2, Math.PI, 0);
      g.moveTo(x - s * 0.35, y); g.lineTo(x + s * 1.2, y); g.stroke();
    }
  }
  g.restore();
}
