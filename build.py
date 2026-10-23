#!/usr/bin/env python3
"""Site build: stage and optimise website media from the project's asset pool.

Run from anywhere: `python3 site/build.py` (repo root inferred). Writes generated
media into site/assets/ (gitignored in the game repo; shipped by deploy.sh).
Idempotent; safe to re-run. No paid generations; vendor-pack art is not used.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = SITE / "assets"
IMG = OUT / "img"
VID = OUT / "vid"
DATA = OUT / "data"
FONTS = OUT / "fonts"

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL:", " ".join(map(str, cmd)))
        print(r.stderr[:600])
        raise SystemExit(1)

def jpg(src, dst, width=None, q=82):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q)]
    if width:
        cmd += ["--resampleWidth", str(width)]
    cmd += [str(src), "--out", str(dst)]
    sh(cmd)

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def h264(src, dst, scale=None, crf=26, preset="slow"):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "libx264",
           "-crf", str(crf), "-preset", preset]
    if scale:
        cmd += ["-vf", f"scale={scale}:-2"]
    cmd += ["-an", "-movflags", "+faststart", str(dst)]
    sh(cmd)

def main():
    for d in (IMG, VID, DATA, FONTS):
        if d.exists():
            shutil.rmtree(d)
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    (OUT / "vid").mkdir(parents=True, exist_ok=True)
    (DATA).mkdir(parents=True, exist_ok=True)
    (FONTS).mkdir(parents=True, exist_ok=True)

    A = ROOT / "Assets"
    W = ROOT / "work"

    # ---- brand -------------------------------------------------------------
    copy(A / "Brand/logo.png", IMG / "logo.png")
    jpg(W / "brand/keyart_wide.png", IMG / "keyart_wide.jpg", 1600, 85)
    jpg(W / "brand/keyart_tall.png", IMG / "keyart_tall.jpg", 1200, 85)

    # ---- menu / world backgrounds ------------------------------------------
    for f in (A / "Backgrounds/menu").glob("*.jpg"):
        jpg(f, IMG / "menu" / f.name, 1600, 85)
    for f in (A / "Backgrounds/battle").glob("*_vista.jpg"):
        jpg(f, IMG / "battle" / f.name, 1600, 85)
    for f in (A / "Backgrounds/battle").glob("*_mid.png"):
        jpg(f, IMG / "battle" / (f.stem + ".jpg"), 1600, 85)
    for f in (A / "Backgrounds/runmap").glob("*.jpg"):
        jpg(f, IMG / "battle" / f.name, 1600, 85)

    # ---- gameplay screenshots (hand-picked for the media + play pages) ----
    shots = [
        "docs/review/hero_trials/05_battle_hud.jpg",
        "docs/review/hero_trials/08_ipad_battle.jpg",
        "docs/review/trail_v2/00_overview.jpg",
        "docs/review/trail_v2/02_walking.jpg",
        "docs/review/trail_v2/03_camp.jpg",
        "docs/review/trail_v2/05_encounter.jpg",
        "docs/review/trail_v2/06_duel_hand.jpg",
        "docs/review/minigames_v2/brew_ipad_play.jpg",
        "docs/review/minigames_v2/grove_ipad_play.jpg",
        "docs/review/vfx/battle_contact_iphone_fernwood.jpg",
        "docs/review/vfx/battle_contact_iphone_emberforge.jpg",
        "docs/review/p1303b_pack_opening/sealed_tell.jpg",
    ]
    for rel in shots:
        src = ROOT / rel
        if src.exists():
            jpg(src, IMG / "shots" / Path(rel).name, 1400, 84)
        else:
            print("  (missing shot)", rel)

    # ---- video: attract loop + hero alive loops -----------------------------
    print("video: cinematic clips")
    for clip in ("attract_loop", "intro_fernwood", "boss_gloomroot_hollow",
                 "finale"):
        src = A / "Cinematics" / (clip + ".mp4")
        if src.exists():
            h264(src, VID / (clip + "_h264.mp4"), crf=25)
    # poster from a calm early frame
    sh(["ffmpeg", "-y", "-v", "error", "-ss", "1.2", "-i",
        str(A / "Cinematics/attract_loop.mp4"), "-frames:v", "1",
        "-vf", "scale=1600:-2", "-q:v", "3", str(IMG / "attract_poster.jpg")])

    heroes = json.loads((ROOT / "Content/heroes.json").read_text())["heroes"]
    jobs = {}
    for jf in (ROOT / "Content/jobs").glob("*.json"):
        jd = json.loads(jf.read_text())["job"]
        jobs[jd["id"]] = jd

    # ---- hero card art: thumb (160w) + full (480w) -------------------------
    print("hero card art: 100 faces")
    n_t = 0
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        src = None
        for cand in (stem + ".heic", stem + ".jpg", stem + "_face.heic"):
            p = A / "Cards/hero" / cand
            if p.exists():
                src = p
                break
        if not src:
            print("  (no art)", h["id"])
            continue
        stem = h["id"].removeprefix("hero.")
        jpg(src, IMG / "heroes/t" / (stem + ".jpg"), 160, 80); n_t += 1
        jpg(src, IMG / "heroes/f" / (stem + ".jpg"), 480, 82)
    print(f"  {n_t} pairs")

    # alive loops: featured only (legendaries), half-size, crf 30
    print("alive loops (legendaries only)")
    alive = []
    for h in heroes:
        stem = h["id"].removeprefix("hero.")
        mp4 = A / "Cards/alive" / (stem + ".mp4")
        if mp4.exists() and h["rarity"] == "legendary":
            h264(mp4, VID / "alive" / (stem + ".mp4"), scale=520, crf=30,
                 preset="fast")
            alive.append(stem)
    print(f"  {len(alive)} loops")

    # ---- audio: eight score excerpts ----------------------------------------
    print("audio: score excerpts")
    AUD = OUT / "audio"
    AUD.mkdir(parents=True, exist_ok=True)
    for t in ("title", "hub", "biome_fernwood", "biome_coral_shallows",
              "biome_emberforge_caldera", "battle", "boss", "blightheart"):
        copy(A / "Audio/Music" / (t + ".m4a"), AUD / (t + ".m4a"))

    # ---- fonts ---------------------------------------------------------------
    fontmap = {
        "LilitaOne-Regular.ttf": "lilita-one.ttf",
        "Fraunces[SOFT,WONK,opsz,wght].ttf": "fraunces.ttf",
        "AtkinsonHyperlegibleNext[wght].ttf": "atkinson.ttf",
    }
    for src, dst in fontmap.items():
        copy(A / "Fonts" / src, FONTS / dst)
    for f in A.glob("Fonts/*-OFL.txt"):
        copy(f, FONTS / f.name)

    # ---- data: heroes.js ------------------------------------------------------
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
    (DATA / "heroes.js").write_text(
        "window.HEROES = " + json.dumps(rows, ensure_ascii=False,
                                        separators=(",", ":")) + ";\n")

    # ---- data: biomes.js -------------------------------------------------------
    biomes = json.loads((ROOT / "Content/biomes.json").read_text())["biomes"]
    (DATA / "biomes_raw.js").write_text(
        "window.BIOMES_RAW = " + json.dumps(biomes, ensure_ascii=False,
                                            separators=(",", ":")) + ";\n")
    print("done. sizes:")
    subprocess.run(["du", "-sh", str(OUT)])
    for sub in (IMG, VID, DATA, FONTS):
        subprocess.run(["du", "-sh", str(sub)])

if __name__ == "__main__":
    main()