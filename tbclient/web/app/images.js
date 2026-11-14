// TBClient web GUI - images in the chat (CR12).
// Part of app.js, split by sections (Refactoring R11); index.html loads the parts in order.
"use strict";

// ---------------------------------------------------------------- images (CR12)
/* Over the air only "~#<hash 16 hex><size 2 hex><blurhash>" (36-42 bytes, no
 * separators) and, after a space, the caption. The size is in steps of 64
 * bytes. The picture itself is fetched from the TinyBox on a tap (/api/image/get)
 * and then served by the client as /img/<hash>. */
const IMG_RE = /^~#([0-9a-f]{16})([0-9a-f]{2})/;              // CR86/CR96: 16 hex (was 6)
const IMG_SHRINK_MAX = 8192;            // fallback if the board says nothing
/* Three sizes to choose from (CR34): the target in bytes decides the time on
 * air, the long side in px keeps the picture sharp enough for that size.
 * "normal" is [images] target_bytes of the client (4 kB), "small" half of it,
 * "large" the board's limit; the choice is remembered in the browser.
 * The picture is shown in the chat at its own pixel size (CR36), so the
 * three sizes differ on the screen as well: 108 / 192 / 320 px. */
const IMG_SIZES = { small: { px: 108, of: 0.5 }, normal: { px: 192, of: 1 }, large: { px: 320, of: 0 } };
/* Width in px for the blurred placeholder - the pixels are not on the wire,
 * only the bytes, so guess the size step from them. */
function imgGuessPx(bytes) {
  const normal = imgTarget("normal"), small = imgTarget("small");
  return bytes <= (small + normal) / 2 ? IMG_SIZES.small.px
       : bytes <= (normal + imgTarget("large")) / 2 ? IMG_SIZES.normal.px : IMG_SIZES.large.px;
}
function imgTarget(size) {
  const limit = (S && S.board && S.board.img) || IMG_SHRINK_MAX;
  const normal = Math.min(limit, (S && S.img && S.img.target) || 4096);
  const f = IMG_SIZES[size] || IMG_SIZES.normal;
  return f.of ? Math.round(normal * f.of) : limit;
}

/* Parse the reference at the start of a (quote-free) wire text:
 * {hash, size, bh, caption} or null. */
function imageRef(wire) {
  const m = (wire || "").match(IMG_RE);
  if (!m) return null;
  const rest = wire.slice(m[0].length), n = blurhashLen(rest[0] || "");
  if (!n || rest.length < n) return null;
  const bh = rest.slice(0, n);
  if (!blurhashShape(bh)) return null;
  if (rest.length > n && rest[n] !== " ") return null;
  return { hash: m[1], size: parseInt(m[2], 16) * 64, bh, caption: rest.slice(n + 1) };
}

const kbText = (n) => `${(n / 1024).toFixed(1)} KB`;
function secText(s) {
  if (s < 50) return `~${Math.max(5, Math.round(s / 5) * 5)} s`;
  const m = Math.round(s / 60);
  return `~${Math.max(1, m)} min`;
}
/* Time over the air: net rate of the link (the picture goes in one go, the
 * AX.25 window paces it) plus the turnarounds: //IMGPUT - //IMGGO, the last
 * acknowledgement and //IMGOK when sending, request and answer when loading. */
function imgTime(size, sending) {
  const c = (S && S.img) || { rate: 100 };
  return size / c.rate + (sending ? 8 : 5);
}

/* Draw a blurhash into a canvas the shape of its components (3x2 = landscape). */
function blurCanvas(bh, cls, bytes) {
  const sh = blurhashShape(bh);
  const c = el("canvas", cls);
  if (bytes) {                            // CR36: placeholder about as big as the picture
    const px = imgGuessPx(bytes);
    c.style.width = (sh.nx >= sh.ny ? px : Math.round((px * sh.nx) / sh.ny)) + "px";
  }
  const w = 32, h = Math.max(4, Math.round((32 * sh.ny) / sh.nx));
  c.width = w; c.height = h;
  const px = blurhashDecode(bh, w, h);
  if (px) c.getContext("2d").putImageData(new ImageData(px, w, h), 0, 0);
  c.style.aspectRatio = `${sh.nx} / ${sh.ny}`;
  return c;
}

/* The image part of a bubble: the picture if it is here, else the blurred
 * placeholder with size, load time and the state of a running download. */
function imageBlock(ref, own, get) {   // get: how to fetch it (CR78: from a TBClient)
  const box = el("div", "imgbox");
  const I = S.images || { have: [], loading: {} };
  if (I.have.includes(ref.hash)) {
    const img = el("img");
    img.src = "/img/" + ref.hash; img.alt = "image";
    img.onclick = (ev) => { ev.stopPropagation(); window.open(img.src, "_blank", "noopener"); };
    box.append(img);
    return box;
  }
  box.append(blurCanvas(ref.bh, "blur", ref.size));
  const ov = el("div", "imgov");
  const ld = I.loading[ref.hash];
  if (ld && ld.error) {
    ov.append(el("div", "", `⚠ ${ld.error}`), el("div", "small", "tap to try again"));
    box.classList.add("err");
  } else if (ld) {
    const bar = el("div", "bar"), fill = el("div", "fill");
    const total = ld.total || ref.size;
    fill.style.width = Math.min(100, Math.round((100 * ld.done) / total)) + "%";
    bar.append(fill);
    ov.append(el("div", "", `${kbText(ld.done)} / ${kbText(total)}`), bar);
    box.classList.add("busy");
  } else {
    ov.append(el("div", "", `🖼 ${kbText(ref.size)} · ${secText(imgTime(ref.size, false))}`),
              el("div", "small", "tap to load"));
  }
  box.append(ov);
  if (!ld || ld.error) {
    box.onclick = (ev) => { ev.stopPropagation(); (get || (() => api("image/get", { hash: ref.hash })))(); };
  } else box.onclick = (ev) => ev.stopPropagation();
  return box;
}

/* CR30: another station is sending a picture. The TinyBox announces it once
 * ("^OE1ABC 50"); the bar shows what we hear of those frames on the channel.
 * A station we cannot hear directly (digipeater, too weak) gives no bytes -
 * then the bar runs over the expected time instead. */
function uploadRow(u) {
  const li = el("li", "sys uprow");
  const bar = el("div", "bar"), fill = el("div", "fill");
  const heard = u.got > 0;
  li.append(el("div", "uptxt", `🖼 ${u.call} uploading picture · ` +
    (heard ? `${kbText(u.got)} / ${kbText(u.size)}` : kbText(u.size))));
  if (heard) {
    fill.style.width = Math.min(100, Math.round((100 * u.got) / u.size)) + "%";
  } else {
    const secs = Math.max(5, imgTime(u.size, true));
    fill.style.animation = `upgrow ${secs}s linear ${-Math.max(0, Date.now() / 1000 - u.at)}s forwards`;
  }
  bar.append(fill);
  li.append(bar);
  return li;
}

/* The own upload under way (or failed): a bubble of its own until the chat
 * line with the reference comes back from the TinyBox. */
// CR86: a file in a board - kept by the TinyBox, fetched on a tap
function boardFileBlock(m) {
  const [, hash, size, air, name] = m;
  const F = S.bfiles || { have: [], loading: {} };
  const box = el("div", "fbox");
  box.append(el("div", "fname", "📎 " + name));
  const ld = F.loading[hash];
  if (F.have.includes(hash)) {
    const a = el("a", "fsave", `Save · ${Number(size)} bytes`);
    a.href = `/file/${hash}/${encodeURIComponent(name)}`;
    a.download = name;
    a.onclick = (ev) => ev.stopPropagation();
    box.append(a);
  } else if (ld && !ld.error) {
    const bar = el("div", "bar"), fill = el("div", "fill");
    const total = ld.total || Number(air);
    fill.style.width = Math.min(100, Math.round((100 * ld.done) / total)) + "%";
    bar.append(fill);
    box.append(el("div", "small", `${ld.done} / ${total} bytes on air`), bar);
  } else {
    box.append(el("div", "small", (ld && ld.error ? `⚠ ${ld.error} · ` : "")
      + `${Number(size)} bytes, ${Number(air)} on air · ${secText(imgTime(Number(air), false))} · tap to load`));
    box.classList.add("tap");
    box.onclick = (ev) => { ev.stopPropagation(); api("bfile/get", { hash, name }); };
  }
  return box;
}
function fileUploadBubble(up) {
  const li = el("li", "msg own");
  const col = el("div", "col");
  const b = el("div", "bubble fileb pending");
  const box = el("div", "fbox");
  box.append(el("div", "fname", "📎 " + (up.name || "file")));
  if (up.state === "error") {
    box.append(el("div", "small", `⚠ not sent: ${up.error}`));
    const again = el("button", "sm", "Try again"), x = el("button", "sm", "Discard");
    again.onclick = () => api("bfile/retry"); x.onclick = () => api("bfile/dismiss");
    box.append(again, " ", x);
  } else {
    const bar = el("div", "bar"), fill = el("div", "fill");
    fill.style.width = Math.min(100, Math.round((100 * up.sent) / up.size)) + "%";
    bar.append(fill);
    box.append(el("div", "small", up.state === "waiting" ? "waiting…" : `${up.sent} / ${up.size} bytes on air`), bar);
  }
  b.append(box);
  col.append(b, el("div", "meta", up.state === "error" ? "failed" : "sending…"));
  li.append(col);
  return li;
}
async function boardSendFile(file) {
  $("bfilein").value = "";
  if (!file || !S.board || !S.board.file) return;
  const hint = $("hint");
  const say = (t) => { hint.className = "hint"; hint.classList.remove("hidden"); hint.textContent = t; };
  if (file.size > 64 * 1024) { say(`Too big: ${file.size} bytes (max. 64 KB).`); return; }
  const max = S.board.file;
  if (!window.confirm(`Send "${file.name}" (${file.size} bytes) to ${S.board.name}?\n` +
      `Packed it goes up once (max. ${max} bytes on air, about ${secText(imgTime(Math.min(file.size, max), true))} at most); ` +
      `the others fetch it from the TinyBox when they tap it.`)) return;
  const buf = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 4096) bin += String.fromCharCode(...buf.subarray(i, i + 4096));
  const r = await postJson("bfile", { name: file.name, data: btoa(bin), quote: quotePrefix() });
  if (!r.ok) say(`Not sent: too large for this board (max. ${max} bytes on air, packed), or a program file.`);
  else if (quoteTo) setQuote(null);
}

function uploadBubble(up) {
  const li = el("li", "msg own");
  const col = el("div", "col");
  const b = el("div", "bubble img pending");
  const ref = imageRef(stripQuote(up.line));
  const box = el("div", "imgbox");
  if (ref && (S.images.have || []).includes(ref.hash)) {
    const img = el("img"); img.src = "/img/" + ref.hash; img.alt = "image"; box.append(img);
  } else if (ref) box.append(blurCanvas(ref.bh, "blur", up.size || ref.size));
  const ov = el("div", "imgov");
  if (up.state === "error") {
    ov.append(el("div", "", `⚠ not sent: ${up.error}`));
    const row = el("div", "row");
    const again = el("button", "sm", "Try again");
    again.onclick = (ev) => { ev.stopPropagation(); api("image/retry"); };
    const x = el("button", "sm", "Discard");
    x.onclick = (ev) => { ev.stopPropagation(); api("image/dismiss"); };
    row.append(again, x);
    ov.append(row);
    box.classList.add("err");
  } else {
    const bar = el("div", "bar"), fill = el("div", "fill");
    fill.style.width = Math.min(100, Math.round((100 * up.sent) / up.size)) + "%";
    bar.append(fill);
    ov.append(el("div", "", up.state === "waiting" ? "waiting…" : `${kbText(up.sent)} / ${kbText(up.size)}`), bar);
    box.classList.add("busy");
  }
  box.append(ov);
  b.append(box);
  if (ref && ref.caption) { const cap = el("div", "cap"); richText(cap, wireToText(ref.caption)); b.append(cap); }
  col.append(b, el("div", "meta", up.state === "error" ? "failed" : "sending…"));
  li.append(col);
  return li;
}

/* Shrink a chosen file: WebP (JPEG where the browser cannot make WebP), long
 * side at most longPx, quality then size down until it fits maxBytes.
 * -> {blob, w, h, bh} or null. */
async function shrinkImage(file, maxBytes, longPx = 320) {
  let src;
  try { src = await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch (e) {
    src = await new Promise((ok, no) => {
      const im = new Image();
      im.onload = () => ok(im); im.onerror = no;
      im.src = URL.createObjectURL(file);
    });
  }
  const W = src.width || src.naturalWidth, H = src.height || src.naturalHeight;
  if (!W || !H) return null;
  const canvas = document.createElement("canvas");
  const toBlob = (type, q) => new Promise((ok) => canvas.toBlob(ok, type, q));
  let scale = Math.min(1, longPx / Math.max(W, H));
  let best = null;
  for (let round = 0; round < 8; round++) {
    const w = Math.max(8, Math.round(W * scale)), h = Math.max(8, Math.round(H * scale));
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(src, 0, 0, w, h);
    let type = "image/webp";
    for (const q of [0.8, 0.65, 0.5, 0.4, 0.3, 0.2]) {
      let blob = await toBlob(type, q);
      if (!blob || blob.type !== type) { type = "image/jpeg"; blob = await toBlob(type, q); }
      if (!blob) return null;
      if (!best || blob.size < best.blob.size) best = { blob, w, h };
      if (blob.size <= maxBytes) { best = { blob, w, h }; round = 99; break; }
    }
    scale *= 0.75;
    if (w <= 64 && h <= 64) break;
  }
  if (!best || best.blob.size > maxBytes) return null;
  // the blurhash from a tiny copy; the component counts follow the shape
  const ratio = best.w / best.h;
  const [nx, ny] = ratio >= 1.25 ? [3, 2] : ratio <= 0.8 ? [2, 3] : [3, 3];
  const tw = 24, th = Math.max(4, Math.round(24 / ratio));
  canvas.width = tw; canvas.height = th;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(src, 0, 0, tw, th);
  const bh = blurhashEncode(ctx.getImageData(0, 0, tw, th).data, tw, th, nx, ny);
  return { ...best, bh };
}

let imgPick = null;                      // {blob, bh} waiting for OK in the dialog
let imgFile = null;                      // the chosen file, shrunk again on a size change
let imgAspect = null;                    // width / height of the chosen file
let imgSize = "normal";
try { imgSize = localStorage.getItem("tb.imgsize") || "normal"; } catch (e) { /* no storage */ }
if (!IMG_SIZES[imgSize]) imgSize = "normal";

/* CR36: the three size buttons carry their numbers: pixels (from the shape
 * of the chosen file), bytes and the time to upload. */
function imgSizeButtons() {
  for (const b of document.querySelectorAll("#imgdlg-size button")) {
    const size = b.dataset.size, px = IMG_SIZES[size].px, bytes = imgTarget(size);
    b.classList.toggle("on", size === imgSize);
    let dims = `${px} px`;
    if (imgAspect) {
      const w = imgAspect >= 1 ? px : Math.round(px * imgAspect);
      const h = imgAspect >= 1 ? Math.round(px / imgAspect) : px;
      dims = `${w}×${h}`;
    }
    b.textContent = "";
    b.append(el("b", "", size), el("span", "", ` (${dims}), ~${kbText(bytes)}, ${secText(imgTime(bytes, true))}`));
  }
}
async function pickImageSize(size) {
  if (!IMG_SIZES[size] || size === imgSize) return;
  imgSize = size;
  try { localStorage.setItem("tb.imgsize", size); } catch (e) { /* no storage */ }
  imgSizeButtons();
  if (imgFile) await shrinkForDialog();
}
async function chooseImage(file) {
  if (!file || !S) return;
  if (view !== "peer" && !(S.board && S.board.img)) return;   // CR78: to a TBClient always
  imgFile = file; imgAspect = null;
  $("imgdlg-caption").value = view === "peer" ? $("term-input").value : $("input").value;
  $("imgdlg").classList.remove("hidden");
  imgSizeButtons();
  await shrinkForDialog();
}
async function shrinkForDialog() {
  const file = imgFile, limit = (S.board && S.board.img) || IMG_SHRINK_MAX;
  const target = imgTarget(imgSize), px = IMG_SIZES[imgSize].px;
  $("imgdlg-text").textContent = "Shrinking the picture…";
  $("imgdlg-ok").disabled = true;
  imgPick = null;
  let r = null;
  try { r = await shrinkImage(file, target, px); } catch (e) { r = null; }
  if (file !== imgFile) return;           // dialog closed or another file chosen meanwhile
  if (!r || r.blob.size > limit) {
    $("imgdlg-text").textContent = `Sorry, this picture cannot be made small enough (max. ${kbText(limit)}).`;
    return;
  }
  imgPick = r;
  if (!imgAspect) { imgAspect = r.w / r.h; imgSizeButtons(); }
  $("imgdlg-text").textContent = "";      // the numbers are in the buttons (CR36)
  $("imgdlg-ok").disabled = false;
}
function closeImageDialog() { $("imgdlg").classList.add("hidden"); imgPick = imgFile = imgAspect = null; $("imgfile").value = ""; }
async function sendImage() {
  if (!imgPick) return;
  const { wire, bad } = textToWire($("imgdlg-caption").value);
  if (bad.length) { $("imgdlg-text").textContent = `Not sendable over radio: ${bad.join(" ")}`; return; }
  const buf = new Uint8Array(await imgPick.blob.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 4096) bin += String.fromCharCode(...buf.subarray(i, i + 4096));
  if (view === "peer") {                          // CR78: straight to the TBClient
    const bh = imgPick.bh;
    closeImageDialog();
    $("term-input").value = ""; peerHint();
    const r = await postJson("peer/img", { ch: activeCh, data: btoa(bin), blurhash: bh, caption: wire });
    if (!r.ok) { $("peer-hint").className = "hint"; $("peer-hint").textContent = "The picture was not accepted."; $("peer-hint").classList.remove("hidden"); }
    return;
  }
  const body = { data: btoa(bin), blurhash: imgPick.bh, caption: wire, quote: quotePrefix() };
  closeImageDialog();
  $("input").value = ""; updateHint();
  if (quoteTo) setQuote(null);
  const r = await postJson("image", body);
  if (!r.ok) { $("hint").className = "hint"; $("hint").textContent = "The picture was not accepted."; $("hint").classList.remove("hidden"); }
}
