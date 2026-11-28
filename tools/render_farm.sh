#!/usr/bin/env bash
# RENDER FARM: more machines on one render (Mark, 28 Nov: "can you get even more workers"). This machine has 4 cores and
# two render workers fill them; each helper is another cloud session of this environment (another 4-core machine with
# Blender installed by the environment's setup script) that renders a stretch of the same film with tools/film.sh.
#
# The frames come back through git, the only channel the sessions share, WITHOUT publishing them (the repo is public):
# the helper packs its frames losslessly (FFV1 in Matroska, every pixel and the alpha exact), encrypts the pack
# (AES-256, openssl, PBKDF2) with a passphrase that travels only in the sessions' private messages, splits it under
# GitHub's 100 MB file limit and pushes only that to its own throwaway branch.
#
#   helper:  PCF_PASS=... tools/render_farm.sh pack <film> <A> <B> [--no-push]
#              frames A..B (0-based, file number = frame + 1) of output/blender/<film>/ -> farm/<film>-<A>-<B>.mkv.enc.NN
#              committed on the current branch and pushed (git push -u origin HEAD)
#   main:    PCF_PASS=... tools/render_farm.sh unpack <film> <branch-or-ref>
#              every farm/<film>-*.enc.NN on that branch -> output/blender/<film>/fNNNN.png, each pack checked against
#              the helper's checksum before a single frame is written
#   either:  tools/render_farm.sh selftest      # pack + unpack 12 frames of a scratch copy, compare every pixel
set -euo pipefail
cd "$(dirname "$0")/.."
die() { echo "render_farm: $*" >&2; exit 1; }
need_pass() { [ -n "${PCF_PASS:-}" ] || die "set PCF_PASS (the passphrase from the main session's message)"; }
PART=45m

pack() {
  local film=$1 A=$2 B=$3 push=${4:-}
  need_pass
  local D=output/blender/$film n=$(( B - A + 1 )) i
  for i in $(seq $(( A + 1 )) $(( B + 1 ))); do [ -f "$D/f$(printf %04d "$i").png" ] || die "missing $D/f$(printf %04d "$i").png"; done
  mkdir -p farm
  local base=farm/$film-$A-$B.mkv
  ffmpeg -v error -y -framerate 30 -start_number $(( A + 1 )) -i "$D/f%04d.png" -frames:v "$n" -c:v ffv1 -level 3 -pix_fmt bgra "$base"
  sha256sum "$base" | cut -d' ' -f1 > "farm/$film-$A-$B.sha256"
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:PCF_PASS -in "$base" -out "$base.enc"
  rm -f "$base" "$base".enc.[0-9][0-9]
  split -b "$PART" -d -a 2 "$base.enc" "$base.enc."
  rm -f "$base.enc"
  echo "packed $n frames ($A-$B) -> $(ls "$base".enc.* | wc -l) part(s), $(du -ch "$base".enc.* | tail -1 | cut -f1)"
  git add -f "$base".enc.* "farm/$film-$A-$B.sha256"
  git commit -q -m "render farm: $film frames $A-$B (encrypted, lossless)"
  if [ "$push" != "--no-push" ]; then
    local k
    for k in 1 2 3 4; do git push -q -u origin HEAD && break; sleep $(( k * 5 )); done
    echo "pushed to $(git rev-parse --abbrev-ref HEAD)"
  fi
}

unpack() {
  local film=$1 ref=$2 tmp jobs job A B n parts got want
  need_pass
  if ! git rev-parse -q --verify "$ref^{commit}" >/dev/null; then
    git fetch -q origin "$ref" || die "cannot fetch $ref"
    ref=FETCH_HEAD
  fi
  tmp=$(mktemp -d)
  jobs=$(git ls-tree -r --name-only "$ref" farm/ 2>/dev/null | grep -E "^farm/$film-[0-9]+-[0-9]+\.mkv\.enc\.[0-9]{2}$" | sed -E 's/\.mkv\.enc\.[0-9]{2}$//' | sort -u)
  [ -n "$jobs" ] || die "no packs of $film on $ref"
  mkdir -p "output/blender/$film"
  for job in $jobs; do
    A=$(echo "$job" | sed -E 's/.*-([0-9]+)-([0-9]+)$/\1/'); B=$(echo "$job" | sed -E 's/.*-([0-9]+)-([0-9]+)$/\2/')
    n=$(( B - A + 1 ))
    : > "$tmp/pack.enc"
    for parts in $(git ls-tree -r --name-only "$ref" farm/ | grep -E "^$job\.mkv\.enc\.[0-9]{2}$" | sort); do
      git show "$ref:$parts" >> "$tmp/pack.enc"
    done
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:PCF_PASS -in "$tmp/pack.enc" -out "$tmp/pack.mkv" \
      || die "$job: cannot decrypt (wrong PCF_PASS?)"
    want=$(git show "$ref:$job.sha256" 2>/dev/null || true)
    got=$(sha256sum "$tmp/pack.mkv" | cut -d' ' -f1)
    [ -n "$want" ] && [ "$got" = "$want" ] || die "$job: checksum mismatch (got $got, the helper wrote ${want:-nothing})"
    rm -rf "$tmp/frames"; mkdir -p "$tmp/frames"
    ffmpeg -v error -i "$tmp/pack.mkv" -start_number $(( A + 1 )) "$tmp/frames/f%04d.png"
    [ "$(ls "$tmp/frames" | wc -l)" = "$n" ] || die "$job: decoded $(ls "$tmp/frames" | wc -l) frames, expected $n"
    mv -f "$tmp/frames"/f*.png "output/blender/$film/"
    echo "unpacked $film frames $A-$B ($n) into output/blender/$film/"
  done
  rm -rf "$tmp"
}

selftest() {
  local src film=_farmtest D
  src=output/blender/ganryujima-ep1
  [ -d "$src" ] || { src=$(ls -d output/blender/*/ | head -1); src=${src%/}; }
  D=output/blender/$film
  rm -rf "$D" farm/$film-*; mkdir -p "$D"
  local f k=0
  for f in "$src"/f*.png; do cp "$f" "$D/"; k=$(( k + 1 )); [ "$k" -ge 12 ] && break; done
  local first; first=$(for f in "$D"/f*.png; do basename "$f"; break; done | sed -E 's/f0*([0-9]+)\.png/\1/')
  local A=$(( first - 1 )) B=$(( first + 10 ))
  mkdir -p "$D.orig"; cp "$D"/*.png "$D.orig/"
  export PCF_PASS=selftest-$$
  local br; br=$(git rev-parse --abbrev-ref HEAD)
  git checkout -q -b "_farmtest-$$"
  pack "$film" "$A" "$B" --no-push
  rm -f "$D"/*.png
  unpack "$film" "_farmtest-$$"
  git checkout -q "$br"; git branch -q -D "_farmtest-$$"; rm -rf farm/$film-*
  python3 - "$D" "$D.orig" <<'EOF'
import sys, os
from PIL import Image, ImageChops
a, b = sys.argv[1], sys.argv[2]
bad = [f for f in sorted(os.listdir(b)) if ImageChops.difference(Image.open(os.path.join(a, f)), Image.open(os.path.join(b, f))).getbbox()]
print('selftest: %d frames, %d differ' % (len(os.listdir(b)), len(bad)))
sys.exit(1 if bad else 0)
EOF
  rm -rf "$D" "$D.orig"
}

case "${1:-}" in
  pack) shift; [ $# -ge 3 ] || die "usage: pack <film> <A> <B> [--no-push]"; pack "$@" ;;
  unpack) shift; [ $# -ge 2 ] || die "usage: unpack <film> <branch>"; unpack "$@" ;;
  selftest) selftest ;;
  *) die "usage: tools/render_farm.sh pack|unpack|selftest (see the top of this file)" ;;
esac
