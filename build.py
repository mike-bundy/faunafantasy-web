#!/usr/bin/env python3
"""Site build: stage and optimise website media from the game's asset pool.

Run from anywhere: `python3 build.py`. Reads the game checkout named by
$FF_GAME_REPO (default ~/code/faunafantasy: its Assets/, work/ and Content/)
and writes generated media into this repo's assets/, which is
committed and published as-is. No paid generations; vendor-pack art is not used.

Incremental: an output newer than its source is kept, so re-runs are quick.
FF_FORCE=1 re-encodes everything (do that after changing a clip's cut or the
encoder settings). Files under the generated dirs that this run did not produce
are deleted at the end, so the published set always matches this script.

Stills are AVIF (sips, macOS), each with a JPEG twin beside it (same name, .jpg)
that site.js swaps in on browsers without AVIF (Safari before 16, older Macs).
The two key-art JPEGs double as og:image.
Gameplay clips come from the App Store capture pipeline (work/store/captures,
tools/cinema/store.py in the game), this site's own captures made with the same
machinery (work/store/captures_web) and the trailer's Rootdelve footage
(work/marketing/hype_v2/footage/delve): H.264, muted, 30 fps, faststart, each
with an AVIF poster. Every clip's window is measured smooth first (no repeated
frames holding motion for over 100 ms; Apple TV simulator recordings often do).
The trailer (work/marketing/hype_v2) keeps its sound and gets captions from its
edit list.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FF_GAME_REPO", "~/code/faunafantasy")).expanduser().resolve()
FORCE = os.environ.get("FF_FORCE") == "1"
OUT = SITE / "assets"
IMG = OUT / "img"
VID = OUT / "vid"
AUD = OUT / "audio"
DATA = OUT / "data"
FONTS = OUT / "fonts"
GENERATED = (IMG, VID, AUD, DATA, FONTS)
made = set()


def sh(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL:", " ".join(map(str, cmd)))
        print(r.stderr[-1200:])
        out = Path(str(cmd[-1]))   # never leave a partial output that looks fresh
        if out.suffix in (".mp4", ".avif", ".jpg", ".png") and out.exists():
            out.unlink()
        raise SystemExit(1)


def fresh(dst, *srcs):
    """True when dst can be kept: it exists and is newer than every source."""
    made.add(dst.resolve())
    if FORCE or not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        return False
    return all(dst.stat().st_mtime >= Path(s).stat().st_mtime for s in srcs)


def jpg(src, dst, width=None, q=82):
    if fresh(dst, src):
        return
    cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q)]
    if width:
        cmd += ["--resampleWidth", str(width)]
    sh(cmd + [src, "--out", dst])


INK = "0x0b110d"   # the page colour; transparent stills are flattened onto it for JPEG


def twin_jpg(src, dst, tw, th, q=62):
    """The JPEG twin of an AVIF still, for browsers without AVIF. sips flattens alpha
    onto white, so transparent sources are composited onto the page colour by ffmpeg."""
    alpha = "yes" in subprocess.run(["sips", "-g", "hasAlpha", str(src)],
                                    capture_output=True, text=True).stdout
    if alpha:
        sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex",
            f"color=c={INK}:s={tw}x{th}[bg];[0]scale={tw}:{th}:flags=lanczos[fg];"
            f"[bg][fg]overlay=shortest=1,format=yuvj420p",
            "-frames:v", "1", "-q:v", "5", dst])
    else:
        sh(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q),
            "-z", str(th), str(tw), src, "--out", dst])


def avif(src, dst, width=None, q=60, twin=True):
    """AVIF still via sips, plus its JPEG twin. Never upscales. Width and height always
    come out even: Chrome draws nothing for sips' 4:2:0 AVIFs with an odd dimension."""
    jdst = dst.with_suffix(".jpg")
    twin = twin and jdst.resolve() not in made   # key art: jpg() already made it
    need_a = not fresh(dst, src)
    need_j = twin and not fresh(jdst, src)
    if not (need_a or need_j):
        return
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(src)],
                         capture_output=True, text=True).stdout.split()
    w, h = int(out[-3]), int(out[-1])
    tw = min(width or w, w)
    th = round(h * tw / w)
    tw, th = tw - tw % 2, th - th % 2
    if need_a:
        sh(["sips", "-s", "format", "avif", "-s", "formatOptions", str(q),
            "-z", str(th), str(tw), src, "--out", dst])
    if need_j:
        twin_jpg(src, jdst, tw, th)


def copy(src, dst):
    if fresh(dst, src):
        return
    shutil.copy2(src, dst)


def share_card(art, logo, dst, w=1200, h=630):
    """The link-preview card (og:image, twitter:image) at the 1.91:1 size Open Graph and X
    expect: the wide key art cropped to keep the heroes' heads, darkened toward the foot,
    with the logo there. Kept small (under 300 KB) so every messenger shows it."""
    if fresh(dst, art, logo):
        return
    lw = round(w * 0.5)
    sh(["ffmpeg", "-y", "-v", "error", "-i", art, "-i", logo, "-filter_complex",
        f"[0]scale={w}:-2:flags=lanczos,crop={w}:{h}:0:(ih-{h})*0.30,format=rgba[bg];"
        f"color=c=black:s={w}x{h},format=rgba,"
        f"geq=r=0:g=0:b=0:a='if(gt(Y,H*0.6),pow((Y-H*0.6)/(H*0.4),1.4)*215,0)'[shade];"
        f"[1]scale={lw}:-2:flags=lanczos[logo];"
        f"[bg][shade]overlay[a];[a][logo]overlay=(W-w)/2:H-h-24,format=yuvj420p",
        "-frames:v", "1", "-q:v", "3", dst])


def h264(src, dst, width=None, crf=26, preset="slow", start=None, seconds=None,
         fps=None, vf=None, sound=False, x264=None):
    """H.264 web clip (yuv420p, faststart). Muted unless sound=True, which keeps the
    first audio track as AAC (the cinematics' dialogue and score)."""
    if fresh(dst, src):
        return
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if seconds is not None:
        cmd += ["-t", f"{seconds:.3f}"]
    cmd += ["-i", src]
    filters = []
    if vf:
        filters.append(vf)
    if width:
        filters.append(f"scale={width}:-2:flags=lanczos")
    if fps:
        filters.append(f"fps={fps}")
    filters.append("format=yuv420p")
    audio = ["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", "128k"] if sound else ["-an"]
    cmd += ["-vf", ",".join(filters), "-c:v", "libx264", "-crf", str(crf),
            "-preset", preset, "-profile:v", "high", *(["-x264-params", x264] if x264 else []),
            *audio, "-sn", "-movflags", "+faststart", dst]
    sh(cmd)


def trailer(src, dst, width=1280, kbps=1600, audio="160k"):
    """The trailer: a finished film with its score and narrator, so sound is kept (AAC) and the
    size is held by a two-pass bitrate target (about 13 MB a minute at the defaults) rather than
    a CRF, which would let a minute of fast cuts and particles run past 20 MB."""
    if fresh(dst, src):
        return
    log = dst.with_suffix(".2pass")
    vf = f"scale={width}:-2:flags=lanczos,format=yuv420p"
    common = ["-vf", vf, "-c:v", "libx264", "-b:v", f"{kbps}k", "-maxrate", f"{kbps * 2}k",
              "-bufsize", f"{kbps * 2}k", "-preset", "slow", "-profile:v", "high", "-passlogfile", log]
    sh(["ffmpeg", "-y", "-v", "error", "-i", src, *common, "-pass", "1", "-an", "-f", "mp4", os.devnull])
    sh(["ffmpeg", "-y", "-v", "error", "-i", src, *common, "-pass", "2",
        "-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", audio, "-sn", "-movflags", "+faststart", dst])
    for f in dst.parent.glob(log.name + "*"):
        f.unlink()


def trailer_vtt(edl, dst):
    """Captions for the trailer from its edit list's voice lines: each line's text (the part
    before the editor's note in brackets), from its cue time to `end_by` or the end of its audio."""
    if fresh(dst, edl):
        return
    def ts(t):
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"
    lines = []
    for v in sorted(json.loads(Path(edl).read_text())["vo"], key=lambda v: v["at"]):
        text = v["text"].split(" (")[0].strip()
        wav = ROOT / v["file"]
        if not wav.exists() and v.get("fallback"):
            wav = ROOT / v["fallback"]["file"]
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout or 2.5)
        lines.append([v["at"], min(v.get("end_by", 1e9), v["at"] + secs + 0.25), text])
    for a, b in zip(lines, lines[1:]):
        a[1] = min(a[1], b[0] - 0.05)          # one caption at a time
    cues = [f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(lines, 1)]
    dst.write_text("WEBVTT\n\n" + "\n".join(cues))


def frame(src, at, dst, width=1280, q=58, vf=None):
    """One frame of a movie as an AVIF poster plus its JPEG twin (via a temporary PNG).
    vf runs before the scale (the iPhone pack capture is stored on its side: transpose=2)."""
    jdst = dst.with_suffix(".jpg")
    need_a = not fresh(dst, src)
    need_j = not fresh(jdst, src)
    if not (need_a or need_j):
        return
    tmp = dst.with_suffix(".tmp.png")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", src, "-frames:v", "1",
        "-vf", (vf + "," if vf else "") + f"scale={width}:-2:flags=lanczos", tmp])
    if need_a:
        sh(["sips", "-s", "format", "avif", "-s", "formatOptions", str(q), tmp, "--out", dst])
    if need_j:
        sh(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "62", tmp, "--out", jdst])
    tmp.unlink()


def montage(segments, dst, width, fade=0.5, crf=26, zoom=0.72):
    """Cross-faded reel from (file, start, seconds[, vf]) segments, all scaled to width x 16:9.
    zoom < 1 keeps the centre of each frame, so the corner HUD falls outside the
    background reel (the section clips keep the full frame). A segment's vf runs first."""
    srcs = [s[0] for s in segments]
    if fresh(dst, *srcs):
        return
    h = width * 9 // 16
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f, start, secs, *_ in segments:
        cmd += ["-ss", f"{start:.3f}", "-t", f"{secs:.3f}", "-i", f]
    parts, offset = [], 0.0
    for i, seg in enumerate(segments):
        pre = seg[3] + "," if len(seg) > 3 and seg[3] else ""
        parts.append(f"[{i}:v]{pre}crop=iw*{zoom}:ih*{zoom},scale={width}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
                     f"crop={width}:{h},fps=30,format=yuv420p,setsar=1,settb=AVTB[s{i}]")
    last = "s0"
    for i in range(1, len(segments)):
        offset += segments[i - 1][2] - fade
        out = f"x{i}"
        parts.append(f"[{last}][s{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{out}]")
        last = out
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]", "-pix_fmt", "yuv420p", "-c:v", "libx264",
            "-crf", str(crf), "-preset", "slow", "-profile:v", "high", "-an",
            "-movflags", "+faststart", dst]
    sh(cmd)


def brand_take(brand, name):
    """The take of a forge.brand piece that forge itself uses (its source()): the one named in selected.json,
    else the newest reroll, else the first."""
    sel = brand / "selected.json"
    pick = json.loads(sel.read_text()).get(name) if sel.exists() else None
    if pick and (brand / pick).exists():
        return brand / pick
    takes = sorted(brand.glob(f"{name}_r*.png"), key=lambda p: int(p.stem.rsplit("_r", 1)[1]))
    return takes[-1] if takes else brand / f"{name}.png"


# The Legendaries the site shows (moving, unnamed) on the Heroes page and the home rail.
TEASED = ("agnes_valor", "wolfgang_wildmane", "kuzunoha_ninetails",
          "aurora_frostbrew", "leonhart_sunmane", "amara")


def main():
    if not (ROOT / "Content/heroes.json").exists():
        raise SystemExit(f"game checkout not found at {ROOT} (set FF_GAME_REPO)")
    print("game:", ROOT)
    for d in GENERATED:
        d.mkdir(parents=True, exist_ok=True)

    A = ROOT / "Assets"
    W = ROOT / "work"
    CAP = W / "store/captures"          # the App Store captures (late October; the Binder 2 November)
    WEB = W / "store/captures_web"      # this site's own captures (9 November: Grovehaven, Rootdelve, Trail, Shop)
    DELVE = W / "marketing/hype_v2/footage/delve"   # Rootdelve on Apple TV at 60 fps (9 November)
    SIDEWAYS = "transpose=2"            # the iPhone pack capture is stored on its side, with no rotation flag

    # ---- brand ---------------------------------------------------------------
    copy(A / "Brand/logo.png", IMG / "logo.png")
    # home-screen and tab icons at the site root: the shipping app icon's layers, flattened,
    # and the SVG favicon as a 32 px .ico for browsers that ask for /favicon.ico
    icon = ROOT / "App/Shared/AppIcon.icon/Assets"
    touch = SITE / "apple-touch-icon.png"
    if not fresh(touch, icon / "back.png", icon / "middle.png", icon / "front.png"):
        sh(["ffmpeg", "-y", "-v", "error", "-i", icon / "back.png", "-i", icon / "middle.png",
            "-i", icon / "front.png", "-filter_complex",
            "[0][1]overlay[a];[a][2]overlay,scale=180:180:flags=lanczos,format=rgb24",
            "-frames:v", "1", touch])
    ico = SITE / "favicon.ico"
    if not fresh(ico, SITE / "favicon.svg"):
        sh(["sips", "-s", "format", "ico", "-z", "32", "32", SITE / "favicon.svg", "--out", ico])
    # the Starter Set key art (forge.brand's newest take: Rowan, Ember, Hazel and Clover, 9 November)
    keyart = brand_take(W / "brand", "keyart_wide")
    jpg(keyart, IMG / "keyart_wide.jpg", 1600, 85)   # og:image
    avif(keyart, IMG / "keyart_wide.avif", 1600, 62)
    share_card(keyart, A / "Brand/logo.png", IMG / "share_1200x630.jpg")

    # ---- menu / world backgrounds ----------------------------------------------
    print("backgrounds")
    for f in (A / "Backgrounds/menu").glob("*.jpg"):
        avif(f, IMG / "menu" / (f.stem + ".avif"), 1600, 58)
    for f in (A / "Backgrounds/battle").glob("*_vista.jpg"):
        avif(f, IMG / "battle" / (f.stem + ".avif"), 1600, 58)
    for f in (A / "Backgrounds/battle").glob("*_mid.png"):
        avif(f, IMG / "battle" / (f.stem + ".avif"), 1600, 58)
    for f in (A / "Backgrounds/runmap").glob("*.jpg"):
        avif(f, IMG / "battle" / (f.stem + ".avif"), 1600, 58)

    # ---- current-build stills (uncaptioned): the store captures where the screen hasn't
    # changed since, and this site's own captures where it has (WEB.shots, 9 November:
    # Grovehaven's new street and menu, the dressed Rootdelve, the straight Trail and Infusions)
    print("stills")
    stills = {
        "tv_battle_canyon": CAP / "tv/auto_canyon_s11.png",
        "tv_pack_legend": CAP / "tv/pack_s17.png",
        "tv_hub": WEB / "tv/hub_s03.png",
        "tv_gate": CAP / "tv/gate_s00.png",
        "tv_battle_plan": WEB / "tv/battle_coral_s00.png",
        "tv_coral": CAP / "tv/auto_coral_s03.png",
        "tv_binder": CAP / "tv/binder_s01.png",
        "tv_crawl": WEB / "tv/crawl_s04.png",
        "tv_arena_reveal": CAP / "tv/arena_reveal_s00.png",
        "tv_arena_battle": CAP / "tv/arena_battle_s03.png",
        "tv_shop": WEB / "tv/shop_s00.png",
        "tv_trail": WEB / "tv/trail_s07.png",
        "tv_victory": WEB / "tv/trail_s03.png",
        "tv_chest": WEB / "tv/trail_s06.png",
        "tv_camp": WEB / "tv/trail_s13.png",
        "ipad_binder": CAP / "ipad/binder_s01.png",
        "ipad_pack": CAP / "ipad/pack_s17.png",
        "ipad_shop": CAP / "ipad/shop_s01.png",
    }
    for name, src in stills.items():
        rel = src.relative_to(W)
        if src.exists():
            avif(src, IMG / "shots" / (name + ".avif"), 1100 if name.startswith("ipad") else 1600, 60)
        else:
            print("  (missing still)", rel)

    # ---- gameplay clips: cut, scaled, muted, with posters ---------------------------
    # (name, capture, start s, seconds, width, poster at +s[, vf])
    # WEB.smooth: every window is measured smooth (no motion gap over 100 ms at 30 fps; the
    # numbers are on _review/smooth.html). The Apple TV simulator repeats frames under load, so
    # the TV pack opening and battle planning come from the iPhone captures instead.
    print("gameplay clips")
    clips = [
        ("battle", CAP / "tv/auto_canyon.mov", 16.0, 10.0, 1280, 1.8),
        ("plan", CAP / "iphone/battle_coral.mov", 2.5, 9.0, 1280, 1.5),
        ("pack", CAP / "iphone/pack.mov", 3.0, 17.0, 1280, 15.2, SIDEWAYS),   # poster: Agnes Valor face up
        ("hub", WEB / "tv/hub.mov", 5.45, 6.9, 1280, 3.0),   # from 5.45 s: the staged journal's "Sets complete" toast has gone, the heroes are landing
        ("crawl", DELVE / "delve_agnes.mov", 13.4, 13.6, 1280, 6.6),   # Stormspire, then down to Gloomroot
        ("arena", CAP / "tv/arena_battle.mov", 0.4, 13.6, 1280, 5.5),
        ("duel", CAP / "iphone/duel.mov", 0.0, 10.5, 1280, 4.6),
        ("coral", CAP / "tv/auto_coral.mov", 28.0, 10.0, 1280, 3.5),
        ("gloom", CAP / "iphone/battle_gloom.mov", 8.0, 10.0, 1280, 6.5),
        ("binder", CAP / "tv/binder.mov", 0.2, 6.2, 1280, 1.5),
    ]
    for name, src, start, secs, width, poster, *vf in clips:
        if not src.exists():
            print("  (missing capture)", src.relative_to(W))
            continue
        vf = vf[0] if vf else None
        h264(src, VID / "play" / (name + ".mp4"), width=width, crf=27, start=start,
             seconds=secs, fps=30, vf=vf)
        frame(src, start + poster, IMG / "play" / (name + ".avif"), width, vf=vf)

    # the home page's background reel: the store previews' beats, uncaptioned, every
    # segment from a smooth window
    print("reel")
    reel = [
        (CAP / "tv/auto_canyon.mov", 17.4, 4.0),
        (CAP / "iphone/pack.mov", 15.6, 4.4, SIDEWAYS),
        (WEB / "tv/hub.mov", 5.45, 3.8),
        (CAP / "iphone/battle_coral.mov", 3.0, 3.6),
        (DELVE / "delve_agnes.mov", 19.0, 3.8),
        (CAP / "iphone/battle_gloom.mov", 9.6, 3.6),
        (CAP / "tv/arena_battle.mov", 3.0, 3.6),
    ]
    # 1280 wide: the montage's centre crop holds about 1380 px of real detail, so a
    # wider encode only adds weight (the 1600 version was 9 MB for 24 s)
    montage(reel, VID / "reel_1280.mp4", 1280, crf=27)
    h264(VID / "reel_1280.mp4", VID / "reel_960.mp4", width=960, crf=28)
    frame(VID / "reel_1280.mp4", 0.6, IMG / "reel_poster.avif", 1280)

    # ---- the trailer (MKT.hype2): the Media page's feature and the home page's Watch button --
    # A finished minute with its score and narrator: sound kept, captions from its edit list,
    # the poster from the logo end card before the platform ribbon comes in (0:55)
    print("trailer")
    hype = W / "marketing/hype_v2/fauna_hype_v2.mp4"
    if hype.exists():
        trailer(hype, VID / "trailer_1280.mp4")
        frame(hype, 1.2, IMG / "trailer_poster.avif", 1280)   # the young Wyrms over the great oak: bright, no text
        edl = ROOT / "tools/marketing/hype_v2_edl.json"
        if edl.exists():
            trailer_vtt(edl, VID / "trailer.vtt")
    else:
        print("  (missing trailer)", hype.relative_to(ROOT))

    # ---- cinematics (in-app renders) ------------------------------------------------
    print("cinematics")
    for clip in ("attract_loop", "intro_fernwood", "boss_gloomroot_hollow", "finale"):
        src = A / "Cinematics" / (clip + ".mp4")
        if src.exists():
            # "these play with sound"; the v5 renders are 1920 wide, the web copies 1280
            h264(src, VID / (clip + "_h264.mp4"), width=1280, crf=25, sound=True)
            vtt = src.with_suffix(".vtt")
            if vtt.exists():
                copy(vtt, VID / (clip + ".vtt"))   # captions for the <track>
    frame(A / "Cinematics/attract_loop.mp4", 1.2, IMG / "attract_poster.avif", 1600)
    frame(A / "Cinematics/intro_fernwood.mp4", 4.0, IMG / "intro_poster.avif", 1280)
    frame(A / "Cinematics/boss_gloomroot_hollow.mp4", 3.0, IMG / "boss_poster.avif", 1280)
    frame(A / "Cinematics/finale.mp4", 6.0, IMG / "finale_poster.avif", 1600)

    heroes = json.loads((ROOT / "Content/heroes.json").read_text())["heroes"]
    # The site introduces the four starters and teases a few Legendaries without names; everyone
    # else is met in the packs, so their art and data never ship (WEB.tease, 9 November).
    heroes = [h for h in heroes if h.get("starter") or h["id"].removeprefix("hero.") in TEASED]
    jobs = {}
    for jf in (ROOT / "Content/jobs").glob("*.json"):
        jd = json.loads(jf.read_text())["job"]
        jobs[jd["id"]] = jd

    # ---- hero card art (480 w, used by the starters, the rails and the modal) ----------
    print("hero card art")
    n = 0
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        src = next((A / "Cards/hero" / c for c in (stem + ".heic", stem + ".jpg", stem + "_face.heic")
                    if (A / "Cards/hero" / c).exists()), None)
        if not src:
            print("  (no art)", h["id"])
            continue
        avif(src, IMG / "heroes/f" / (stem + ".avif"), 480, 60)
        n += 1
    print(f"  {n} cards")

    # "the card comes alive" loops: the teased Legendaries
    alive = []
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        mp4 = A / "Cards/alive" / (stem + ".mp4")
        if mp4.exists():
            # WEB.smooth: crf 30 / preset fast froze these gentle loops for up to 41 frames, then
            # jumped; preset slow with a smaller dead zone keeps the slow motion moving
            h264(mp4, VID / "alive" / (stem + ".mp4"), width=520, crf=28, preset="slow",
                 x264="deadzone-inter=4:deadzone-intra=4")
            alive.append(stem)
    print(f"  {len(alive)} alive loops")

    # ---- audio: score excerpts ----------------------------------------------------------
    for t in ("title", "hub", "biome_fernwood", "biome_coral_shallows",
              "biome_emberforge_caldera", "battle", "boss", "blightheart"):
        copy(A / "Audio/Music" / (t + ".m4a"), AUD / (t + ".m4a"))

    # ---- fonts ---------------------------------------------------------------------------
    fontmap = {
        "LilitaOne-Regular.ttf": "lilita-one.ttf",
        "Fraunces[SOFT,WONK,opsz,wght].ttf": "fraunces.ttf",
        "AtkinsonHyperlegibleNext[wght].ttf": "atkinson.ttf",
    }
    for src, dst in fontmap.items():
        copy(A / "Fonts" / src, FONTS / dst)
    # only the licences of the three fonts the site ships (the game's Assets/Fonts also holds
    # its localization fonts, which this site doesn't use)
    for lic in ("LilitaOne-OFL.txt", "Fraunces-OFL.txt", "AtkinsonHyperlegibleNext-OFL.txt"):
        copy(A / "Fonts" / lic, FONTS / lic)

    # ---- data: heroes.js --------------------------------------------------------------------
    rows = []
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        job = jobs.get(h["job"], {})
        if not h.get("starter"):
            # a teased Legendary: its card and nothing that says who it is
            rows.append({"id": stem, "el": h["element"], "rarity": h["rarity"], "starter": False,
                         "alive": (stem + ".mp4") if stem in alive else None})
            continue
        rows.append({
            "n": h["number"], "id": stem, "name": h["name"],
            "title": h.get("title"), "job": h["job"],
            "jobName": job.get("name", h["job"]), "role": job.get("role", ""),
            "el": h["element"], "rarity": h["rarity"],
            "sp": h.get("species", ""), "hook": h.get("hook", ""),
            "flav": h.get("flavour", ""), "sig": h.get("signatureAction", ""),
            "pal": (h.get("palette") or {}).get("words", ""),
            "palc": [(h.get("palette") or {}).get("primary"),
                     (h.get("palette") or {}).get("secondary"),
                     (h.get("palette") or {}).get("accent")],
            "starter": bool(h.get("starter")),
            "alive": (stem + ".mp4") if stem in alive else None,
        })
    heroes_js = DATA / "heroes.js"
    made.add(heroes_js.resolve())
    heroes_js.write_text("window.HEROES = " + json.dumps(rows, ensure_ascii=False,
                                                         separators=(",", ":")) + ";\n")

    biomes = json.loads((ROOT / "Content/biomes.json").read_text())["biomes"]
    biomes_js = DATA / "biomes_raw.js"
    made.add(biomes_js.resolve())
    biomes_js.write_text("window.BIOMES_RAW = " + json.dumps(biomes, ensure_ascii=False,
                                                             separators=(",", ":")) + ";\n")

    # ---- prune anything this run did not produce ----------------------------------------
    for d in GENERATED:
        for f in sorted(d.rglob("*"), reverse=True):
            if f.is_file() and f.resolve() not in made:
                f.unlink()
                print("  pruned", f.relative_to(SITE))
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()

    print("done. sizes:")
    subprocess.run(["du", "-sh", str(OUT)])
    for sub in GENERATED:
        subprocess.run(["du", "-sh", str(sub)])


if __name__ == "__main__":
    main()
