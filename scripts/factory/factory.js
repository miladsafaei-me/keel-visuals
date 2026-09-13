/*
 * The object factory: one procedural object per job, rendered on the stage's one camera.
 *
 * build_factory_objects.py loads this page in headless Chromium and calls
 * window.factory.render(job) once per object. Every object is modelled in stage
 * pixels, standing on the ground plane y = 0 with its contact point at the origin,
 * and the camera that frames it is the stage demo's own: CSS perspective 1400 px, the
 * eye 340 px above the ground, the image plane vertical. A sprite rendered here and a
 * floor drawn by the stage therefore agree about perspective by construction, which is
 * the whole lesson of the stage demo's PERSPECTIVE.md.
 */

import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/RoomEnvironment.js';
import { SVGLoader } from 'three/addons/SVGLoader.js';

/* The stage demo's camera (stage_scene.py): FOCAL, HORIZON_Y and GROUND_Y, in stage px. */
const FOCAL = 1400;
const HORIZON_Y = 560;
const GROUND_Y = 900;
const EYE_HEIGHT = GROUND_Y - HORIZON_Y;

/*
 * The stage's LIGHT is a screen-space vector, (-0.42, 1.0): shadows run down and to the
 * left, so the lamp is high and to the right. In world space that is a key light above
 * the object, to its right and a little in front, so the faces turned to the camera
 * still carry the highlight on their upper-right side.
 */
const LIGHT = [-0.42, 1.0];
const KEY_DIRECTION = new THREE.Vector3(0.42, 1.0, 0.24).normalize();

/* A virtual canvas far larger than any object, centred on the eye; each render window is cut from it. */
const VIRTUAL = 4000;
const PADDING = 0.05;

const canvas = document.createElement('canvas');
document.body.appendChild(canvas);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
/* Neutral tone mapping keeps hues where they are: gold stays gold and a brand's colour stays the brand's. */
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.setClearColor(0x000000, 0);

const linear = (r, g, b) => new THREE.Color().setRGB(r, g, b, THREE.LinearSRGBColorSpace);

/*
 * Reflectance of real metals, linear sRGB: what a metal looks like is mostly this colour
 * times what it reflects. Silver reflects nearly all of every channel, so the studio that
 * leaves gold its colour burns a silver face to white; silver sees that studio dimmer.
 */
const METALS = {
  gold: { color: linear(1.0, 0.71, 0.29), roughness: 0.16, environment: 1.0 },
  silver: { color: linear(0.94, 0.94, 0.95), roughness: 0.2, environment: 0.62 },
  gunmetal: { color: linear(0.13, 0.14, 0.16), roughness: 0.2, environment: 1.0 },
};

function metal(name, overrides = {}) {
  const spec = METALS[name];
  return new THREE.MeshPhysicalMaterial({
    color: spec.color.clone(),
    metalness: 1,
    roughness: spec.roughness,
    envMapIntensity: spec.environment,
    ...overrides,
  });
}

const environments = new Map();

/*
 * A dark photo studio built on three.js's RoomEnvironment: the room's walls are taken
 * down to a deep grey and softboxes are added where a product photographer puts them,
 * a tall strip on the key side, a large panel overhead, a kicker opposite and a low fill
 * behind the camera. Polished metal is almost entirely a picture of what it reflects;
 * a bright grey room makes gold read as brass, and hard-edged softboxes on a dark room
 * are what give a bar or a coin its crisp edge highlights.
 */
function studioEnvironment() {
  if (environments.has('studio')) return environments.get('studio');
  const room = new RoomEnvironment();
  room.traverse((object) => {
    if (object.isMesh && object.material.isMeshStandardMaterial) object.material.color.setScalar(0.1);
  });
  /* A diffused softbox is brightest at its centre and falls off toward its frame; that falloff is the gradient a polished face shows. */
  const falloff = document.createElement('canvas');
  falloff.width = 256;
  falloff.height = 256;
  const shade = falloff.getContext('2d');
  const gradient = shade.createRadialGradient(128, 128, 8, 128, 128, 181);
  gradient.addColorStop(0, '#ffffff');
  gradient.addColorStop(0.55, '#b8b8b8');
  gradient.addColorStop(1, '#3a3a3a');
  shade.fillStyle = gradient;
  shade.fillRect(0, 0, 256, 256);
  const falloffMap = new THREE.CanvasTexture(falloff);
  const box = new THREE.BoxGeometry();
  const panel = (intensity, position, scale) => {
    const material = new THREE.MeshLambertMaterial({ color: 0x000000, emissive: 0xffffff, emissiveIntensity: intensity, emissiveMap: falloffMap });
    const mesh = new THREE.Mesh(box, material);
    mesh.position.set(...position);
    mesh.scale.set(...scale);
    room.add(mesh);
  };
  /*
   * Room-local coordinates: the room sits 3.5 below the origin the environment is
   * captured from, so local y 3.5 is the camera's horizon. The camera looks down -z.
   * Each panel is placed where a face of the objects actually reflects: a face turned
   * to the camera mirrors the space behind the camera, a top face mirrors the low wall
   * behind the object, an end face mirrors the side walls near the horizon.
   */
  panel(30, [14.4, 9, 3], [0.1, 12, 3]);
  panel(12, [0, 21, 0], [12, 0.1, 10]);
  panel(6, [0, 5.5, -13], [18, 5, 0.1]);
  panel(3.6, [-9, 5.5, 13.8], [11, 8, 0.1]);
  panel(2.4, [9, 6, 14], [7, 6, 0.1]);
  panel(9, [14.4, 4.5, -9], [0.1, 5, 8]);
  panel(10, [-15.8, 8, -4], [0.1, 10, 2.2]);
  const generator = new THREE.PMREMGenerator(renderer);
  const texture = generator.fromScene(room, 0.02).texture;
  generator.dispose();
  environments.set('studio', texture);
  return texture;
}

/*
 * A block with every edge rounded, whose top is smaller than its base: the shape of a
 * bar cast in a mould. Each face is a grid whose points are pushed onto a rounded box
 * (clamp to the inner box, step out by the radius along the direction that clamp
 * removed), then the whole block is tapered with height. The normals are carried
 * through the taper exactly, through the inverse transpose of its Jacobian, so the
 * slanted sides shade as slanted sides rather than as a squashed box.
 */
function taperedBlock({ length, height, width, radius, topX = 1, topZ = 1, segments = 10 }) {
  const half = [length / 2, height / 2, width / 2];
  const inner = half.map((value) => value - radius);
  const coords = (axis) => {
    const h = inner[axis];
    const out = [];
    for (let i = segments; i >= 1; i--) out.push(-(h + radius * Math.tan((i / segments) * (Math.PI / 4))));
    out.push(-h, h);
    for (let i = 1; i <= segments; i++) out.push(h + radius * Math.tan((i / segments) * (Math.PI / 4)));
    return out;
  };
  const faces = [
    { n: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0] },
    { n: [0, 0, -1], u: [-1, 0, 0], v: [0, 1, 0] },
    { n: [1, 0, 0], u: [0, 0, -1], v: [0, 1, 0] },
    { n: [-1, 0, 0], u: [0, 0, 1], v: [0, 1, 0] },
    { n: [0, 1, 0], u: [1, 0, 0], v: [0, 0, -1] },
    { n: [0, -1, 0], u: [1, 0, 0], v: [0, 0, 1] },
  ];
  const kx = (topX - 1) / height;
  const kz = (topZ - 1) / height;
  const positions = [];
  const normals = [];
  const index = [];
  const axisOf = (vector) => vector.findIndex((component) => component !== 0);
  const normal = new THREE.Vector3();
  for (const face of faces) {
    const ua = axisOf(face.u);
    const va = axisOf(face.v);
    const na = axisOf(face.n);
    const us = coords(ua);
    const vs = coords(va);
    const start = positions.length / 3;
    for (const b of vs) {
      for (const a of us) {
        const p = [0, 0, 0];
        p[na] = face.n[na] * half[na];
        p[ua] = face.u[ua] * a;
        p[va] = face.v[va] * b;
        const c = p.map((value, i) => Math.max(-inner[i], Math.min(inner[i], value)));
        const d = p.map((value, i) => value - c[i]);
        const length3 = Math.hypot(d[0], d[1], d[2]);
        const n = length3 > 1e-9 ? d.map((value) => value / length3) : [...face.n];
        const q = c.map((value, i) => value + n[i] * radius);
        const lift = q[1] + half[1];
        const sx = 1 + kx * lift;
        const sz = 1 + kz * lift;
        positions.push(q[0] * sx, lift, q[2] * sz);
        normal.set(n[0] / sx, n[1] - (q[0] * kx * n[0]) / sx - (q[2] * kz * n[2]) / sz, n[2] / sz).normalize();
        normals.push(normal.x, normal.y, normal.z);
      }
    }
    const columns = us.length;
    for (let j = 0; j < vs.length - 1; j++) {
      for (let i = 0; i < columns - 1; i++) {
        const a = start + j * columns + i;
        index.push(a, a + 1, a + columns + 1, a, a + columns + 1, a + columns);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.setIndex(index);
  return geometry;
}

function roundRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

/*
 * The hallmark a refinery strikes into a bar, as two textures: a height map (white is
 * the polished surface, black is struck in) and a roughness map, because a struck
 * mark is matte against a mirror finish and that contrast is most of why it reads.
 * The wording is generic and names no refinery.
 */
function hallmark({ lines, aspect, roughness }) {
  const width = 2048;
  const height = Math.round(width / aspect);
  const draw = (ground, ink) => {
    const surface = document.createElement('canvas');
    surface.width = width;
    surface.height = height;
    const context = surface.getContext('2d');
    context.fillStyle = ground;
    context.fillRect(0, 0, width, height);
    context.filter = 'blur(2.5px)';
    context.strokeStyle = ink;
    context.fillStyle = ink;
    const inset = height * 0.09;
    context.lineWidth = height * 0.03;
    roundRect(context, inset, inset, width - 2 * inset, height - 2 * inset, height * 0.07);
    context.stroke();
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    for (const line of lines) {
      context.font = `800 ${Math.round(line.size * height)}px Montserrat, FreeSans, sans-serif`;
      context.letterSpacing = `${Math.round(line.tracking * height)}px`;
      context.fillText(line.text, width / 2, line.y * height);
    }
    const texture = new THREE.CanvasTexture(surface);
    texture.anisotropy = 8;
    return texture;
  };
  const grey = (value) => {
    const level = Math.round(Math.min(1, value) * 255);
    return `rgb(${level}, ${level}, ${level})`;
  };
  return { bump: draw('#ffffff', '#000000'), rough: draw(grey(roughness), grey(Math.max(roughness * 2.4, 0.42))) };
}

const GOLD_MARK = [
  { text: 'FINE GOLD', size: 0.17, tracking: 0.02, y: 0.36 },
  { text: '999.9', size: 0.27, tracking: 0.015, y: 0.66 },
];
const SILVER_MARK = [
  { text: 'FINE SILVER', size: 0.16, tracking: 0.02, y: 0.36 },
  { text: '999.0', size: 0.27, tracking: 0.015, y: 0.66 },
];

/* One cast bar, base on the ground, long axis along x, with its hallmark on the top face. */
function bar({ metalName, mark, length = 250, height = 60, width = 100 }) {
  const group = new THREE.Group();
  const radius = 6.5;
  const topX = 0.87;
  const topZ = 0.8;
  const body = new THREE.Mesh(taperedBlock({ length, height, width, radius, topX, topZ }), metal(metalName));
  group.add(body);
  const flatX = (length / 2 - radius) * topX * 2 * 0.97;
  const flatZ = (width / 2 - radius) * topZ * 2 * 0.95;
  const textures = hallmark({ lines: mark, aspect: flatX / flatZ, roughness: METALS[metalName].roughness });
  const material = metal(metalName, {
    bumpMap: textures.bump,
    bumpScale: 0.55,
    roughness: 1,
    roughnessMap: textures.rough,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(flatX, flatZ).rotateX(-Math.PI / 2), material);
  plate.position.y = height + 0.04;
  group.add(plate);
  return group;
}

/* A small pyramid of bars, three, two and one, each resting on the two below it. */
function barStack() {
  const group = new THREE.Group();
  const spec = { length: 220, height: 54, width: 92 };
  const gap = 4;
  const jitter = [0.012, -0.018, 0.009, -0.011, 0.016, -0.006];
  let n = 0;
  [3, 2, 1].forEach((count, level) => {
    for (let i = 0; i < count; i++) {
      const piece = bar({ metalName: 'gold', mark: GOLD_MARK, ...spec });
      piece.rotation.y = Math.PI / 2 + jitter[n];
      piece.position.set((i - (count - 1) / 2) * (spec.width + gap), level * spec.height, jitter[n] * 160);
      n += 1;
      group.add(piece);
    }
  });
  group.rotation.y = -0.52;
  return group;
}

/* A profile point list for LatheGeometry, with arcs, so round details stay round. */
function profile() {
  const points = [];
  return {
    points,
    to(r, y) {
      points.push(new THREE.Vector2(r, y));
      return this;
    },
    arc(cx, cy, radius, from, to, steps = 8) {
      for (let i = 0; i <= steps; i++) {
        const angle = THREE.MathUtils.degToRad(from + ((to - from) * i) / steps);
        points.push(new THREE.Vector2(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)));
      }
      return this;
    },
  };
}

/*
 * A 55-gallon steel drum, to its real proportions (height 1.49 x diameter): rolled
 * chimes top and bottom, two rolling hoops a third of the way up and down, a swage
 * bead near each end, a recessed lid, and the large and small bungs on the lid. Those
 * hoops and bungs are what make a cylinder an oil drum; the paint is a clear-coated
 * enamel over steel.
 */
function oilBarrel({ paint = '#15181d' }) {
  const R = 90;
  const H = 268;
  const hoop = (shape, y, rise, spread) => {
    shape.to(R, y - spread).to(R + rise * 0.25, y - spread * 0.62).to(R + rise * 0.8, y - spread * 0.3)
      .to(R + rise, y).to(R + rise * 0.8, y + spread * 0.3).to(R + rise * 0.25, y + spread * 0.62).to(R, y + spread);
  };
  const shape = profile();
  shape.to(0, 5).to(R - 9, 5).to(R - 8, 2.5).arc(R - 3, 3, 3, 250, 360, 6).arc(R - 1, 3.2, 3.2, 0, 90, 5);
  shape.to(R + 1.2, 7.8).to(R, 10);
  hoop(shape, 26, 1.3, 4);
  hoop(shape, H * 0.34, 3.4, 9);
  hoop(shape, H * 0.66, 3.4, 9);
  hoop(shape, H - 26, 1.3, 4);
  shape.to(R, H - 10).to(R + 1.2, H - 7.8).arc(R - 1, H - 3.2, 3.2, 270, 360, 5).arc(R - 3, H - 3, 3, 0, 110, 6);
  shape.to(R - 8, H - 2.5).to(R - 9, H - 7).to(R - 12, H - 7.6).to(0, H - 7.6);
  const enamel = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(paint),
    metalness: 0.35,
    roughness: 0.38,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
  });
  const group = new THREE.Group();
  group.add(new THREE.Mesh(new THREE.LatheGeometry(shape.points, 180), enamel));
  const zinc = metal('silver', { color: linear(0.55, 0.56, 0.58), roughness: 0.32 });
  const bung = (x, z, radius) => {
    const flange = new THREE.Mesh(new THREE.CylinderGeometry(radius + 3.2, radius + 3.8, 1.6, 48), zinc);
    flange.position.set(x, H - 7.6 + 0.8, z);
    const plug = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 3.2, 48), zinc);
    plug.position.set(x, H - 7.6 + 2.2, z);
    const boss = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.52, radius * 0.52, 5.2, 6), zinc);
    boss.position.set(x, H - 7.6 + 3.2, z);
    group.add(flange, plug, boss);
  };
  bung(-R * 0.56, -R * 0.2, 10.5);
  bung(R * 0.6, -R * 0.08, 6);
  group.rotation.y = 0.35;
  return group;
}

/*
 * A minted coin standing on its edge, facing the camera and turned so its edge shows:
 * a mirror-bright raised rim, a softer field inside it, a reeded edge, and a fine bead
 * ring where the rim meets the field. The duller field against the polished rim is the
 * proof finish that makes a disc read as struck metal rather than a token.
 */
function coin({ metalName = 'gold', svg = null, turn = -0.36 }) {
  const R = 100;
  const T = 19;
  const rimWidth = 11;
  const lip = 2.2;
  const recess = 0.5;
  const faceZ = T / 2 - recess;
  const body = new THREE.Group();
  let faceInfo = null;
  let chosen = metalName;
  let relief = null;
  if (svg) {
    relief = svgRelief(svg, R - rimWidth - 5, faceZ);
    faceInfo = relief.info;
    if (chosen === 'auto') chosen = relief.info.metal;
  } else if (chosen === 'auto') {
    chosen = 'gold';
  }
  const rim = metal(chosen, { roughness: METALS[chosen].roughness * 0.7 });
  const field = metal(chosen, { roughness: 0.26 });

  const front = profile();
  front.to(R, T / 2).arc(R - 1.6, T / 2 + lip - 1.6, 1.6, 0, 90, 5).to(R - rimWidth + 1.4, T / 2 + lip)
    .arc(R - rimWidth + 1.4, T / 2 + lip - 1.0, 1.0, 90, 180, 4).to(R - rimWidth - 0.9, faceZ);
  const rimFront = new THREE.Mesh(new THREE.LatheGeometry(front.points, 256), rim);
  const rimBack = new THREE.Mesh(new THREE.LatheGeometry(front.points.map((p) => new THREE.Vector2(p.x, -p.y)).reverse(), 256), rim);
  const fieldFront = new THREE.Mesh(new THREE.LatheGeometry([new THREE.Vector2(R - rimWidth - 0.9, faceZ), new THREE.Vector2(0, faceZ)], 256), field);
  const fieldBack = new THREE.Mesh(new THREE.LatheGeometry([new THREE.Vector2(0, -faceZ), new THREE.Vector2(R - rimWidth - 0.9, -faceZ)], 256), field);

  const reeds = document.createElement('canvas');
  reeds.width = 64;
  reeds.height = 4;
  const context = reeds.getContext('2d');
  for (let x = 0; x < 64; x++) {
    const level = Math.round(255 * (0.5 + 0.5 * Math.cos((2 * Math.PI * x) / 64)));
    context.fillStyle = `rgb(${level}, ${level}, ${level})`;
    context.fillRect(x, 0, 1, 4);
  }
  const reedMap = new THREE.CanvasTexture(reeds);
  reedMap.wrapS = THREE.RepeatWrapping;
  reedMap.repeat.set(220, 1);
  const edge = new THREE.Mesh(
    new THREE.CylinderGeometry(R, R, T, 512, 1, true),
    metal(chosen, { roughness: METALS[chosen].roughness * 1.3, bumpMap: reedMap, bumpScale: 0.9 }),
  );
  body.add(rimFront, rimBack, fieldFront, fieldBack, edge);

  for (const side of [1, -1]) {
    const bead = new THREE.Mesh(new THREE.TorusGeometry(R - rimWidth - 3.2, 0.6, 12, 256).rotateX(Math.PI / 2), rim);
    bead.position.y = side * faceZ;
    body.add(bead);
  }

  /* The coin was modelled lying flat, faces along y. Stand it up so its face looks down +z. */
  body.rotation.x = Math.PI / 2;
  const coinGroup = new THREE.Group();
  coinGroup.add(body);
  if (relief) coinGroup.add(relief.group);
  const stand = new THREE.Group();
  coinGroup.position.y = R;
  stand.add(coinGroup);
  stand.rotation.y = turn;
  return { root: stand, info: { metal: chosen, face: faceInfo } };
}

function parseTransform(text) {
  const matrix = new THREE.Matrix3();
  if (!text) return matrix;
  const pattern = /(matrix|translate|scale|rotate)\s*\(([^)]*)\)/g;
  let match;
  while ((match = pattern.exec(text))) {
    const v = match[2].split(/[\s,]+/).filter(Boolean).map(Number);
    const step = new THREE.Matrix3();
    if (match[1] === 'matrix') step.set(v[0], v[2], v[4], v[1], v[3], v[5], 0, 0, 1);
    else if (match[1] === 'translate') step.makeTranslation(v[0], v[1] ?? 0);
    else if (match[1] === 'scale') step.makeScale(v[0], v[1] ?? v[0]);
    else {
      const cx = v[1] ?? 0;
      const cy = v[2] ?? 0;
      step.makeTranslation(cx, cy)
        .multiply(new THREE.Matrix3().makeRotation(THREE.MathUtils.degToRad(v[0])))
        .multiply(new THREE.Matrix3().makeTranslation(-cx, -cy));
    }
    matrix.multiply(step);
  }
  return matrix;
}

/*
 * SVGLoader leaves a gradient fill as an unparsed url(#id), so a mark drawn with one
 * (Solana's is) would come out white. This reads the gradient itself, following href
 * inheritance, so the relief can be painted with it vertex by vertex.
 */
function gradientOf(root, fill) {
  const match = /url\(\s*['"]?#([^'")\s]+)['"]?\s*\)/.exec(fill || '');
  if (!match) return null;
  const byId = (id) => root.querySelector(`[id="${id}"]`);
  const node = byId(match[1]);
  if (!node) return null;
  const chain = [];
  for (let current = node; current && chain.length < 8; ) {
    chain.push(current);
    const href = current.getAttribute('href') || current.getAttribute('xlink:href');
    current = href && href.startsWith('#') ? byId(href.slice(1)) : null;
  }
  const attr = (name, fallback) => {
    for (const link of chain) if (link.hasAttribute(name)) return link.getAttribute(name);
    return fallback;
  };
  const holder = chain.find((link) => link.querySelector('stop'));
  if (!holder) return null;
  const stops = [...holder.querySelectorAll('stop')].map((stop) => {
    const style = Object.fromEntries(
      (stop.getAttribute('style') || '').split(';').map((pair) => pair.split(':').map((part) => part && part.trim())).filter((pair) => pair[0] && pair[1]),
    );
    const raw = stop.getAttribute('offset') || '0';
    const offset = raw.trim().endsWith('%') ? parseFloat(raw) / 100 : parseFloat(raw);
    const color = new THREE.Color().setStyle(style['stop-color'] || stop.getAttribute('stop-color') || '#000000', THREE.SRGBColorSpace);
    return { offset: THREE.MathUtils.clamp(Number.isFinite(offset) ? offset : 0, 0, 1), color };
  }).sort((a, b) => a.offset - b.offset);
  const units = attr('gradientUnits', 'objectBoundingBox');
  const kind = node.localName;
  const numbers = kind === 'linearGradient'
    ? { x1: attr('x1', '0%'), y1: attr('y1', '0%'), x2: attr('x2', '100%'), y2: attr('y2', '0%') }
    : { cx: attr('cx', '50%'), cy: attr('cy', '50%'), r: attr('r', '50%') };
  return { kind, units, numbers, stops, transform: parseTransform(attr('gradientTransform', '')) };
}

function sampleStops(stops, t) {
  if (t <= stops[0].offset) return stops[0].color.clone();
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i].offset) {
      const a = stops[i - 1];
      const b = stops[i];
      const span = b.offset - a.offset || 1;
      return new THREE.Color().lerpColors(a.color, b.color, (t - a.offset) / span);
    }
  }
  return stops[stops.length - 1].color.clone();
}

function paintGradient(geometry, gradient, box, viewBox) {
  const length = (value, span) => {
    const text = String(value).trim();
    if (text.endsWith('%')) return (parseFloat(text) / 100) * (gradient.units === 'objectBoundingBox' ? 1 : span);
    return parseFloat(text);
  };
  const g = gradient.numbers;
  const w = viewBox.width;
  const h = viewBox.height;
  const inverse = gradient.transform.clone().invert();
  const position = geometry.getAttribute('position');
  const colors = new Float32Array(position.count * 3);
  const p = new THREE.Vector2();
  for (let i = 0; i < position.count; i++) {
    p.set(position.getX(i), position.getY(i));
    if (gradient.units === 'objectBoundingBox') {
      p.set((p.x - box.min.x) / (box.max.x - box.min.x || 1), (p.y - box.min.y) / (box.max.y - box.min.y || 1));
    }
    p.applyMatrix3(inverse);
    let t;
    if (gradient.kind === 'linearGradient') {
      const x1 = length(g.x1, w);
      const y1 = length(g.y1, h);
      const dx = length(g.x2, w) - x1;
      const dy = length(g.y2, h) - y1;
      t = ((p.x - x1) * dx + (p.y - y1) * dy) / (dx * dx + dy * dy || 1);
    } else {
      t = Math.hypot(p.x - length(g.cx, w), p.y - length(g.cy, h)) / (length(g.r, Math.hypot(w, h) / Math.SQRT2) || 1);
    }
    const color = sampleStops(gradient.stops, THREE.MathUtils.clamp(t, 0, 1));
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
}

/* A mirror transform turns every triangle inside out; swapping two corners turns it back. */
function flipWinding(geometry) {
  for (const name of ['position', 'normal', 'uv', 'color']) {
    const attribute = geometry.getAttribute(name);
    if (!attribute) continue;
    const size = attribute.itemSize;
    const array = attribute.array;
    for (let i = 0; i < attribute.count; i += 3) {
      for (let k = 0; k < size; k++) {
        const a = (i + 1) * size + k;
        const b = (i + 2) * size + k;
        const swap = array[a];
        array[a] = array[b];
        array[b] = swap;
      }
    }
  }
}

function metalFor(color) {
  const hsl = color.getHSL({}, THREE.SRGBColorSpace);
  if (hsl.l < 0.2) return 'gunmetal';
  if (hsl.s > 0.35 && hsl.h >= 0.05 && hsl.h <= 0.17) return 'gold';
  return 'silver';
}

/* Relief heights in stage px: the first shape sits lowest and each later shape stands a step above the one it was painted over. */
const RELIEF_BASE = 1.2;
const RELIEF_STEP = 0.7;
const RELIEF_BEVEL = 0.32;
const RELIEF_SINK = 0.3;

/*
 * The brand's mark struck up out of the coin's face. Every filled path of the SVG is
 * extruded in the order the SVG paints it, each a little higher than the last, in its
 * own colour as a clear-coated enamel, and the whole mark is scaled so its farthest
 * point sits just inside the rim. The rim metal is chosen from the mark's largest
 * shape: warm and saturated takes gold, near black takes gunmetal, anything else silver.
 */
function svgRelief(svgText, faceRadius, faceZ) {
  const data = new SVGLoader().parse(svgText);
  const root = data.xml;
  const viewBoxText = (root.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
  const viewBox = viewBoxText.length === 4 && viewBoxText.every(Number.isFinite)
    ? { width: viewBoxText[2], height: viewBoxText[3] }
    : { width: parseFloat(root.getAttribute('width')) || 100, height: parseFloat(root.getAttribute('height')) || 100 };
  const layers = [];
  let strokesSkipped = 0;
  for (const path of data.paths) {
    const style = path.userData?.style ?? {};
    const fill = style.fill;
    const opacity = Number(style.fillOpacity ?? 1) * Number(style.opacity ?? 1);
    if (style.stroke && style.stroke !== 'none' && (!fill || fill === 'none')) strokesSkipped += 1;
    if (!fill || fill === 'none' || opacity <= 0 || style.visibility === 'hidden') continue;
    const shapes = path.toShapes();
    if (!shapes.length) continue;
    const gradient = gradientOf(root, fill);
    if (/^url\(/.test(fill) && !gradient) continue;
    layers.push({ shapes, gradient, color: gradient ? null : path.color.clone(), opacity });
  }
  if (!layers.length) throw new Error('the face SVG has no filled shape to strike into the coin');

  const everyPoint = [];
  for (const layer of layers) {
    const box = new THREE.Box2();
    let area = 0;
    for (const shape of layer.shapes) {
      const { shape: outline, holes } = shape.extractPoints(24);
      for (const point of outline) {
        everyPoint.push(point);
        box.expandByPoint(point);
      }
      area += Math.abs(THREE.ShapeUtils.area(outline)) - holes.reduce((sum, hole) => sum + Math.abs(THREE.ShapeUtils.area(hole)), 0);
    }
    layer.box = box;
    layer.area = area;
  }
  const bounds = new THREE.Box2().setFromPoints(everyPoint);
  const centre = bounds.getCenter(new THREE.Vector2());
  const reach = everyPoint.reduce((most, point) => Math.max(most, point.distanceTo(centre)), 0) || 1;
  const scale = faceRadius / reach;

  const group = new THREE.Group();
  layers.forEach((layer, order) => {
    const depth = (RELIEF_BASE + order * RELIEF_STEP) / scale;
    const bevel = RELIEF_BEVEL / scale;
    const geometry = new THREE.ExtrudeGeometry(layer.shapes, {
      depth,
      curveSegments: 32,
      bevelEnabled: true,
      bevelThickness: bevel,
      bevelSize: bevel,
      bevelOffset: -bevel,
      bevelSegments: 2,
    });
    if (layer.gradient) paintGradient(geometry, layer.gradient, layer.box, viewBox);
    geometry.translate(-centre.x, -centre.y, bevel);
    geometry.scale(scale, -scale, scale);
    flipWinding(geometry);
    geometry.translate(0, 0, faceZ - RELIEF_SINK);
    /* The enamel sees the studio dimmer than the metal around it, so its reflections gloss the brand's colour instead of bleaching it. */
    const material = new THREE.MeshPhysicalMaterial({
      color: layer.gradient ? 0xffffff : layer.color,
      vertexColors: Boolean(layer.gradient),
      metalness: 0,
      roughness: 0.3,
      clearcoat: 1,
      clearcoatRoughness: 0.06,
      envMapIntensity: 0.55,
      transparent: layer.opacity < 0.999,
      opacity: layer.opacity,
    });
    group.add(new THREE.Mesh(geometry, material));
  });

  const largest = layers.reduce((best, layer) => (layer.area > best.area ? layer : best), layers[0]);
  const dominant = largest.gradient
    ? largest.gradient.stops.reduce((sum, stop) => sum.add(stop.color), new THREE.Color(0, 0, 0)).multiplyScalar(1 / largest.gradient.stops.length)
    : largest.color;
  return {
    group,
    info: {
      layers: layers.length,
      gradients: layers.filter((layer) => layer.gradient).length,
      strokes_skipped: strokesSkipped,
      dominant: `#${dominant.getHexString(THREE.SRGBColorSpace)}`,
      metal: metalFor(dominant),
    },
  };
}

/*
 * A display podium: a short dark cylinder with a lacquered body, a dark top framed by
 * a thin polished inlay, and a lit rim. The rim is an emissive ring plus a soft halo
 * lying in the plane of the top, so the glow foreshortens with the podium instead of
 * floating in front of it as a flat ellipse would.
 */
function podium({ glow = '#eaf4ff' }) {
  const R = 230;
  const H = 58;
  const group = new THREE.Group();
  const shape = profile();
  shape.to(0, 0).to(R - 4, 0).arc(R - 4, 4, 4, 270, 360, 5).to(R, H - 4).arc(R - 4, H - 4, 4, 0, 90, 6).to(0, H);
  const lacquer = new THREE.MeshPhysicalMaterial({
    color: linear(0.012, 0.014, 0.018),
    metalness: 0.4,
    roughness: 0.32,
    clearcoat: 1,
    clearcoatRoughness: 0.05,
  });
  group.add(new THREE.Mesh(new THREE.LatheGeometry(shape.points, 256), lacquer));
  /* The stage sees the top at a grazing 13.65 degrees, where any gloss becomes a mirror of the room; a matte, low-specular top stays dark. */
  const finish = new THREE.MeshPhysicalMaterial({
    color: linear(0.01, 0.011, 0.014),
    metalness: 0,
    roughness: 0.62,
    specularIntensity: 0.25,
    envMapIntensity: 0.35,
  });
  const top = new THREE.Mesh(new THREE.CircleGeometry(R - 18, 256).rotateX(-Math.PI / 2), finish);
  top.position.y = H + 0.05;
  const inlay = new THREE.Mesh(new THREE.TorusGeometry(R - 18, 0.9, 12, 256).rotateX(Math.PI / 2), metal('gunmetal', { roughness: 0.12 }));
  inlay.position.y = H + 0.1;
  group.add(top, inlay);

  const tone = new THREE.Color(glow);
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(R - 2.6, 1.7, 16, 384).rotateX(Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: tone.clone().multiplyScalar(1.6), toneMapped: false }),
  );
  ring.position.y = H - 0.6;
  ring.userData.glow = true;
  const display = tone.clone().convertLinearToSRGB();
  const halo = new THREE.Mesh(
    new THREE.RingGeometry(R - 34, R + 30, 384, 1),
    new THREE.ShaderMaterial({
      uniforms: { tint: { value: new THREE.Vector3(display.r, display.g, display.b) }, radius: { value: R - 2.6 }, width: { value: 10 } },
      vertexShader: 'varying vec2 vPlane; void main() { vPlane = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: 'uniform vec3 tint; uniform float radius; uniform float width; varying vec2 vPlane; void main() { float d = (length(vPlane) - radius) / width; float a = 0.75 * exp(-d * d); gl_FragColor = vec4(tint * a, a); }',
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      premultipliedAlpha: true,
    }),
  );
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = H + 0.3;
  halo.userData.glow = true;
  group.add(ring, halo);
  return group;
}

function build(job) {
  const options = job.options || {};
  switch (job.object) {
    case 'gold-bar': {
      const root = bar({ metalName: 'gold', mark: GOLD_MARK });
      root.rotation.y = -0.4;
      return { root, info: { size: { length: 250, height: 60, width: 100 } } };
    }
    case 'silver-bar': {
      const root = bar({ metalName: 'silver', mark: SILVER_MARK });
      root.rotation.y = -0.4;
      return { root, info: { size: { length: 250, height: 60, width: 100 } } };
    }
    case 'gold-bar-stack':
      return { root: barStack(), info: { bars: 6 } };
    case 'oil-barrel':
      return { root: oilBarrel(options), info: { size: { diameter: 180, height: 268 } } };
    case 'coin-blank':
    case 'coin': {
      const made = coin({ metalName: options.metal || 'auto', svg: job.svg || null });
      return { root: made.root, info: { size: { diameter: 200, thickness: 15 }, ...made.info } };
    }
    case 'podium':
      return { root: podium(options), info: { size: { diameter: 460, height: 58 } } };
    default:
      throw new Error(`the factory has no object ${job.object}`);
  }
}

/* Every vertex projected through the stage camera, in virtual-canvas px, so the render window fits the object exactly. */
function projectedBounds(root) {
  root.updateMatrixWorld(true);
  const bounds = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
  const point = new THREE.Vector3();
  const instance = new THREE.Matrix4();
  const world = new THREE.Matrix4();
  root.traverse((object) => {
    if (!object.isMesh) return;
    const position = object.geometry.getAttribute('position');
    const copies = object.isInstancedMesh ? object.count : 1;
    for (let c = 0; c < copies; c++) {
      world.copy(object.matrixWorld);
      if (object.isInstancedMesh) {
        object.getMatrixAt(c, instance);
        world.multiply(instance);
      }
      for (let i = 0; i < position.count; i++) {
        point.fromBufferAttribute(position, i).applyMatrix4(world);
        const distance = FOCAL - point.z;
        const x = VIRTUAL / 2 + (FOCAL * point.x) / distance;
        const y = VIRTUAL / 2 - (FOCAL * (point.y - EYE_HEIGHT)) / distance;
        bounds.minX = Math.min(bounds.minX, x);
        bounds.maxX = Math.max(bounds.maxX, x);
        bounds.minY = Math.min(bounds.minY, y);
        bounds.maxY = Math.max(bounds.maxY, y);
      }
    }
  });
  return bounds;
}

/* Frees one job's geometry, materials and textures, but never the studio, which every job shares. */
function dispose(scene) {
  scene.traverse((object) => {
    if (!object.isMesh) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      for (const value of Object.values(material)) if (value && value.isTexture && value !== scene.environment) value.dispose();
      material.dispose();
    }
  });
}

async function render(job) {
  const scene = new THREE.Scene();
  scene.environment = studioEnvironment();
  scene.environmentIntensity = job.environmentIntensity ?? 1.0;
  const { root, info } = build(job);
  scene.add(root);
  root.traverse((object) => {
    if (!object.isMesh) return;
    if (!object.userData.glow) {
      object.castShadow = true;
      object.receiveShadow = true;
    }
    /*
     * envMapIntensity scales only an envMap the material holds itself, never
     * scene.environment, so a material that asks for a dimmer studio (silver, enamel,
     * the podium's top) is handed the studio directly or its request does nothing.
     */
    for (const material of [object.material].flat()) {
      if (material.isMeshStandardMaterial && material.envMapIntensity !== 1 && !material.envMap) material.envMap = scene.environment;
    }
  });

  const camera = new THREE.PerspectiveCamera(THREE.MathUtils.radToDeg(2 * Math.atan(VIRTUAL / 2 / FOCAL)), 1, 40, 6000);
  camera.position.set(0, EYE_HEIGHT, FOCAL);
  camera.lookAt(0, EYE_HEIGHT, 0);
  const bounds = projectedBounds(root);
  const side = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) * (1 + 2 * PADDING);
  const left = (bounds.minX + bounds.maxX) / 2 - side / 2;
  const top = (bounds.minY + bounds.maxY) / 2 - side / 2;
  camera.setViewOffset(VIRTUAL, VIRTUAL, left, top, side, side);
  camera.updateProjectionMatrix();

  const sphere = new THREE.Box3().setFromObject(root).getBoundingSphere(new THREE.Sphere());
  const key = new THREE.DirectionalLight(0xffffff, job.keyIntensity ?? 2.0);
  key.position.copy(sphere.center).addScaledVector(KEY_DIRECTION, 2000);
  key.target.position.copy(sphere.center);
  key.castShadow = true;
  key.shadow.mapSize.set(4096, 4096);
  const reach = sphere.radius * 1.15;
  Object.assign(key.shadow.camera, { left: -reach, right: reach, top: reach, bottom: -reach, near: 2000 - reach * 1.5, far: 2000 + reach * 1.5 });
  key.shadow.camera.updateProjectionMatrix();
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.6;
  key.shadow.radius = 3;
  scene.add(key, key.target);

  renderer.setSize(job.size, job.size, false);
  renderer.render(scene, camera);
  const png = canvas.toDataURL('image/png');
  dispose(scene);

  return {
    png,
    meta: {
      ground: { x: (VIRTUAL / 2 - left) / side, y: (VIRTUAL / 2 + EYE_HEIGHT - top) / side },
      stage_width_px: side,
      camera: {
        elevation_deg: THREE.MathUtils.radToDeg(Math.atan(EYE_HEIGHT / FOCAL)),
        focal_px: FOCAL,
        eye_height_px: EYE_HEIGHT,
        distance_px: FOCAL,
        image_plane: 'vertical',
      },
      light: LIGHT,
      light_direction: KEY_DIRECTION.toArray().map((value) => Number(value.toFixed(4))),
      object: info,
    },
  };
}

function info() {
  const gl = renderer.getContext();
  const debug = gl.getExtension('WEBGL_debug_renderer_info');
  return {
    three: THREE.REVISION,
    gl: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
    horizon_y: HORIZON_Y,
    ground_y: GROUND_Y,
  };
}

window.factory = { ready: true, render, info };
