#!/usr/bin/env python3
"""Site build: stage and optimise website media from the game's asset pool.

Run from anywhere: `python3 build.py`. Reads the game checkout named by
$FF_GAME_REPO (default ~/code/faunafantasy: its Assets/, work/, Content/ and
docs/review/) and writes generated media into this repo's assets/, which is
committed and published as-is. No paid generations; vendor-pack art is not used.

Incremental: an output newer than its source is kept, so re-runs are quick.
FF_FORCE=1 re-encodes everything (do that after changing a clip's cut or the
encoder settings). Files under the generated dirs that this run did not produce
are deleted at the end, so the published set always matches this script.

Stills are AVIF (sips, macOS), each with a JPEG twin beside it (same name, .jpg)
that site.js swaps in on browsers without AVIF (Safari before 16, older Macs).
The two key-art JPEGs double as og:image.
Gameplay clips come from the App Store capture pipeline (work/store/captures,
tools/cinema/store.py in the game): H.264, muted, 30 fps, faststart, each with
an AVIF poster.
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


def h264(src, dst, width=None, crf=26, preset="slow", start=None, seconds=None,
         fps=None, vf=None, sound=False):
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
            "-preset", preset, "-profile:v", "high", *audio, "-sn", "-movflags", "+faststart", dst]
    sh(cmd)


def frame(src, at, dst, width=1280, q=58):
    """One frame of a movie as an AVIF poster plus its JPEG twin (via a temporary PNG)."""
    jdst = dst.with_suffix(".jpg")
    need_a = not fresh(dst, src)
    need_j = not fresh(jdst, src)
    if not (need_a or need_j):
        return
    tmp = dst.with_suffix(".tmp.png")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", src, "-frames:v", "1",
        "-vf", f"scale={width}:-2:flags=lanczos", tmp])
    if need_a:
        sh(["sips", "-s", "format", "avif", "-s", "formatOptions", str(q), tmp, "--out", dst])
    if need_j:
        sh(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "62", tmp, "--out", jdst])
    tmp.unlink()


def montage(segments, dst, width, fade=0.5, crf=26, zoom=0.72):
    """Cross-faded reel from (file, start, seconds) segments, all scaled to width x 16:9.
    zoom < 1 keeps the centre of each frame, so the corner HUD falls outside the
    background reel (the section clips keep the full frame)."""
    srcs = [s[0] for s in segments]
    if fresh(dst, *srcs):
        return
    h = width * 9 // 16
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f, start, secs in segments:
        cmd += ["-ss", f"{start:.3f}", "-t", f"{secs:.3f}", "-i", f]
    parts, offset = [], 0.0
    for i in range(len(segments)):
        parts.append(f"[{i}:v]crop=iw*{zoom}:ih*{zoom},scale={width}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
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


def main():
    if not (ROOT / "Content/heroes.json").exists():
        raise SystemExit(f"game checkout not found at {ROOT} (set FF_GAME_REPO)")
    print("game:", ROOT)
    for d in GENERATED:
        d.mkdir(parents=True, exist_ok=True)

    A = ROOT / "Assets"
    W = ROOT / "work"
    CAP = W / "store/captures"

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
    jpg(W / "brand/keyart_wide.png", IMG / "keyart_wide.jpg", 1600, 85)   # og:image
    jpg(W / "brand/keyart_tall.png", IMG / "keyart_tall.jpg", 1200, 85)   # og:image
    avif(W / "brand/keyart_wide.png", IMG / "keyart_wide.avif", 1600, 62)
    avif(W / "brand/keyart_tall.png", IMG / "keyart_tall.avif", 1200, 62)

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

    # ---- older dev captures still current (the Trail, camp, mini-games) ---------
    for rel in ("docs/review/trail_v2/00_overview.jpg", "docs/review/trail_v2/02_walking.jpg",
                "docs/review/trail_v2/03_camp.jpg", "docs/review/trail_v2/05_encounter.jpg",
                "docs/review/minigames_v2/brew_ipad_play.jpg",
                "docs/review/minigames_v2/grove_ipad_play.jpg"):
        src = ROOT / rel
        if src.exists():
            avif(src, IMG / "shots" / (Path(rel).stem + ".avif"), 1400, 60)
        else:
            print("  (missing shot)", rel)

    # ---- current-build stills from the App Store captures (uncaptioned) ---------
    print("store stills")
    stills = {
        "tv_battle_canyon": "tv/auto_canyon_s11.png",
        "tv_pack_legend": "tv/pack_s17.png",
        "tv_hub": "tv/hub_s00.png",
        "tv_gate": "tv/gate_s00.png",
        "tv_battle_plan": "tv/battle_coral_s08.png",
        "tv_coral": "tv/auto_coral_s03.png",
        "tv_binder": "tv/binder_s01.png",
        "tv_crawl": "tv/crawl_s03.png",
        "tv_arena_reveal": "tv/arena_reveal_s00.png",
        "tv_arena_battle": "tv/arena_battle_s03.png",
        "tv_shop": "tv/shop_s01.png",
        "ipad_hub": "ipad/hub_s00.png",
        "ipad_shop": "ipad/shop_s01.png",
        "ipad_crawl": "ipad/crawl_s04.png",
    }
    for name, rel in stills.items():
        src = CAP / rel
        if src.exists():
            avif(src, IMG / "shots" / (name + ".avif"), 1100 if name.startswith("ipad") else 1600, 60)
        else:
            print("  (missing still)", rel)

    # ---- gameplay clips: cut, scaled, muted, with posters ---------------------------
    # (name, capture, start s, seconds, width, poster at +s)
    print("gameplay clips")
    clips = [
        ("battle", "tv/auto_canyon.mov", 16.0, 10.0, 1280, 1.8),
        ("plan", "tv/battle_coral.mov", 10.5, 9.0, 1280, 3.0),
        ("pack", "tv/pack.mov", 2.6, 18.6, 1280, 15.6),   # poster: the Legendary face up, not the flip flash
        ("hub", "tv/hub.mov", 0.7, 9.0, 1280, 6.0),
        ("crawl", "iphone/crawl.mov", 1.5, 12.0, 1280, 2.0),
        ("arena", "tv/arena_battle.mov", 0.4, 13.6, 1280, 5.5),
        ("duel", "iphone/duel.mov", 0.0, 10.5, 1280, 4.6),
        ("coral", "tv/auto_coral.mov", 28.0, 10.0, 1280, 3.5),
        ("gloom", "iphone/battle_gloom.mov", 8.0, 10.0, 1280, 6.5),
        ("binder", "tv/binder.mov", 0.2, 6.2, 1280, 1.5),
    ]
    for name, rel, start, secs, width, poster in clips:
        src = CAP / rel
        if not src.exists():
            print("  (missing capture)", rel)
            continue
        h264(src, VID / "play" / (name + ".mp4"), width=width, crf=27, start=start,
             seconds=secs, fps=30)
        frame(src, start + poster, IMG / "play" / (name + ".avif"), width)

    # the home page's background reel: the store previews' beats, uncaptioned
    print("reel")
    reel = [
        (CAP / "tv/auto_canyon.mov", 17.4, 4.0),
        (CAP / "tv/pack.mov", 15.6, 4.4),
        (CAP / "tv/hub.mov", 1.0, 3.8),
        (CAP / "tv/battle_coral.mov", 12.4, 3.6),
        (CAP / "tv/crawl.mov", 2.5, 3.8),
        (CAP / "iphone/battle_gloom.mov", 9.6, 3.6),
        (CAP / "tv/arena_battle.mov", 3.0, 3.6),
    ]
    # 1280 wide: the montage's centre crop holds about 1380 px of real detail, so a
    # wider encode only adds weight (the 1600 version was 9 MB for 24 s)
    montage(reel, VID / "reel_1280.mp4", 1280, crf=27)
    h264(VID / "reel_1280.mp4", VID / "reel_960.mp4", width=960, crf=28)
    frame(VID / "reel_1280.mp4", 0.6, IMG / "reel_poster.avif", 1280)

    # ---- cinematics (in-app renders) ------------------------------------------------
    print("cinematics")
    for clip in ("attract_loop", "intro_fernwood", "boss_gloomroot_hollow", "finale"):
        src = A / "Cinematics" / (clip + ".mp4")
        if src.exists():
            h264(src, VID / (clip + "_h264.mp4"), crf=25, sound=True)   # "these play with sound"
            vtt = src.with_suffix(".vtt")
            if vtt.exists():
                copy(vtt, VID / (clip + ".vtt"))   # captions for the <track>
    frame(A / "Cinematics/attract_loop.mp4", 1.2, IMG / "attract_poster.avif", 1600)
    frame(A / "Cinematics/intro_fernwood.mp4", 4.0, IMG / "intro_poster.avif", 1280)
    frame(A / "Cinematics/boss_gloomroot_hollow.mp4", 3.0, IMG / "boss_poster.avif", 1280)
    frame(A / "Cinematics/finale.mp4", 6.0, IMG / "finale_poster.avif", 1600)

    heroes = json.loads((ROOT / "Content/heroes.json").read_text())["heroes"]
    jobs = {}
    for jf in (ROOT / "Content/jobs").glob("*.json"):
        jd = json.loads(jf.read_text())["job"]
        jobs[jd["id"]] = jd

    # ---- hero card art (480 w, used by the grid, the rails and the modal) ------------
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

    # "the card comes alive" loops: every hero that has one (Epic and Legendary)
    alive = []
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        mp4 = A / "Cards/alive" / (stem + ".mp4")
        if mp4.exists():
            h264(mp4, VID / "alive" / (stem + ".mp4"), width=520, crf=30, preset="fast")
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
    for f in A.glob("Fonts/*-OFL.txt"):
        copy(f, FONTS / f.name)

    # ---- data: heroes.js --------------------------------------------------------------------
    rows = []
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        job = jobs.get(h["job"], {})
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
