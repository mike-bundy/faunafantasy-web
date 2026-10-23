# The Fauna Fantasy website

A static, dependency-free marketing site for the game — six pages, no framework, no build
step needed to browse. It is written to be staged and deployed as-is.

## Layout
- `*.html` — the six pages (index, world, heroes, play, arena, media). All paths are relative.
- `assets/css/style.css`, `assets/js/*` — shared styles and behaviour.
- `build.py` — stages generated media and data into `assets/` from the project's asset pool
  (card art, backgrounds, cinematics, music, fonts, `Content/*.json`). `assets/` is generated;
  do not hand-edit it. Run `python3 site/build.py` after media or `Content/` changes.
- `deploy.sh` — stages this folder (plus generated `assets/`) into the `faunafantasy-web`
  repo and pushes to GitHub Pages.

## Conventions
- Page copy is marketing copy; canon lives in `docs/design/STORY.md` and the `Content/` data.
  When lore changes there, this site follows.
- No vendor-pack art (LoaD/Quaternius/Mixamo) goes on the site. Card art and backgrounds are
  forge-generated (`gpt_image`); cinematic clips and hero "alive" loops are our own renders;
  fonts are OFL (Fraunces, Lilita One, Atkinson Hyperlegible Next) and their licences ship
  with them in `assets/fonts/`.
- The hero roster and world data are data-driven from `Content/heroes.json`,
  `Content/biomes.json` and `Content/jobs/*.json` via `build.py`.

## Preview
`cd site && python3 -m http.server 8123` → http://localhost:8123

## Deploy (GitHub Pages)
One-time: create the `faunafantasy-web` repo (public; Pages needs public on the free plan),
enable Pages from the `main` branch root. Then `site/deploy.sh` stages and pushes. The live
URL is `https://mike-bundy.github.io/faunafantasy-web/`.

Open before any public *launch* push: the attract-loop clip and a couple of gameplay shots
show LoaD-derived 3D models; swap them for forge-only art or clear the vendor licence first
(Needs-Mike 1).
