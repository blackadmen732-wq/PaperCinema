#!/usr/bin/env bash
# Our own synthesised sword sounds (no licence needed: made here with ffmpeg).
# Layered clash = tink (transient) + ring (steel partials) + low body + paper crinkle (our style).
#   bash tools/synth_sfx.sh   → assets/sfx/clash-steel.mp3, clash-light.mp3, steel-scrape.mp3, whoosh-a/b/c.mp3, draw-shing.mp3
set -euo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d); O=assets/sfx
f() { ffmpeg -y -loglevel error "$@"; }
f -f lavfi -i "anoisesrc=d=0.06:c=white:a=0.9:r=44100" -af "highpass=f=3500,lowpass=f=11000,afade=t=out:st=0.004:d=0.05:curve=exp" $T/tink.wav
f -f lavfi -i "aevalsrc='0.35*sin(2*PI*2093*t)*exp(-7*t)+0.28*sin(2*PI*3271*t)*exp(-9*t)+0.22*sin(2*PI*4733*t)*exp(-12*t)+0.16*sin(2*PI*6947*t)*exp(-16*t)+0.1*sin(2*PI*9211*t)*exp(-22*t)':d=1.4:s=44100" -af "vibrato=f=11:d=0.12,aecho=0.8:0.5:23|41:0.25|0.15" $T/ring.wav
f -f lavfi -i "aevalsrc='0.9*sin(2*PI*(55+90*exp(-30*t))*t)*exp(-14*t)':d=0.35:s=44100" -af "lowpass=f=180" $T/body.wav
f -f lavfi -i "anoisesrc=d=0.25:c=pink:a=0.8:r=44100" -af "highpass=f=1800,lowpass=f=7000,tremolo=f=37:d=0.9,tremolo=f=61:d=0.7,afade=t=out:st=0.02:d=0.22" $T/crinkle.wav
# full clash: tink 0 dB-ish, ring +5 ms, body, crinkle +20 ms
f -i $T/tink.wav -i $T/ring.wav -i $T/body.wav -i $T/crinkle.wav -filter_complex \
 "[0]volume=0.7[a];[1]adelay=5|5,volume=0.45[b];[2]volume=0.55[c];[3]adelay=20|20,volume=0.2[d];[a][b][c][d]amix=inputs=4:normalize=0:duration=longest,alimiter=limit=0.95,aformat=channel_layouts=stereo" -ar 44100 -b:a 192k $O/clash-steel.mp3
# light contact (blades meeting in a bind): higher, shorter, no body
f -i $T/tink.wav -i $T/ring.wav -filter_complex "[0]volume=0.5[a];[1]asetrate=44100*1.2,aresample=44100,atrim=0:0.6,afade=t=out:st=0.3:d=0.3,volume=0.3[b];[a][b]amix=inputs=2:normalize=0:duration=longest,aformat=channel_layouts=stereo" -ar 44100 -b:a 192k $O/clash-light.mp3
f -f lavfi -i "anoisesrc=d=1.6:c=white:a=0.5:r=44100" -af "bandpass=f=5200:t=h:w=1800,vibrato=f=6:d=0.4,tremolo=f=23:d=0.6,afade=t=in:d=0.05,afade=t=out:st=1.2:d=0.4,aformat=channel_layouts=stereo" -b:a 192k $O/steel-scrape.mp3
# three different whooshes: noise through a band that sweeps up then down (different speeds/centres)
w() { f -f lavfi -i "anoisesrc=d=$2:c=pink:a=0.9:r=44100" -af "highpass=f=$3,lowpass=f=$4,vibrato=f=$5:d=0.3,afade=t=in:st=0:d=$6:curve=exp,afade=t=out:st=$6:d=$(python3 -c "print($2-$6)"):curve=exp,volume=2.2,aformat=channel_layouts=stereo" -b:a 192k $O/$1.mp3; }
w whoosh-a 0.42 300 3200 7 0.16
w whoosh-b 0.34 450 4500 9 0.12
w whoosh-c 0.55 220 2400 5 0.22
# draw "shing": a rising chirp into the ring
f -f lavfi -i "aevalsrc='0.3*sin(2*PI*(1800*t+2600*t*t))*exp(-2*t)':d=0.45:s=44100" -i $T/ring.wav -filter_complex "[0]highpass=f=900[a];[1]adelay=380|380,volume=0.35[b];[a][b]amix=inputs=2:normalize=0:duration=longest,aformat=channel_layouts=stereo" -ar 44100 -b:a 192k $O/draw-shing.mp3
rm -rf $T
python3 - <<'PY'
import json
p='assets/sfx/credits.json'; c=json.load(open(p))
for k in ['clash-steel','clash-light','steel-scrape','whoosh-a','whoosh-b','whoosh-c','draw-shing']:
    c[k]={"title":k,"creator":"Paper Cinema (synthesised with ffmpeg, tools/synth_sfx.sh)","license":"own","source":"synth"}
json.dump(c,open(p,'w'),indent=2)
PY
echo done
