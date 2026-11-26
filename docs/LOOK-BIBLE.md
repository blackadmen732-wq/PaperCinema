# The Paper Cinema look bible (Mark's 14 posters, Nov 26)

Mark made 14 AI posters for the channel on 26 Nov and handed them over as the look to follow. The images are not in
this repository yet (it is public: they go in only after Mark says so). This page is the breakdown, numbered #1–#14 in
the order he sent them.

## The system: what is the same in all 14
- **Palette:** white paper, black ink, ONE red (the sun, the seal, petals, cords, banners). Pink only on some
  blossoms. No orange anywhere. Red is also the story bible's colour of the curse (`docs/STORY-BIBLE.md`).
- **Layout:** the name 紙の映画 huge, brush-written, top to bottom down the left third; the hero upper centre-right,
  seen from low, looking up or away; the katana diagonal across the lower right, handle toward the viewer; a red sun
  or a red brush ring (ensō) behind the head; a cherry branch in a corner; ink splashes and smoke.
- **The bottom band:** PAPER CINEMA in wide-spaced serif capitals between thin lines, `紙の映画 • a paper sword-duel
  series` under it, and the red square seal 映画 (Mark's signature: *eiga*, "cinema"; white characters carved into red,
  the hakubun style) centred, or at the left in #11.
- **Signature props:** a katana with a diamond-wrapped handle; a guard of cherry blossom over waves (seigaiha); the
  oni-mask charm on a chain with a kanji tag (鬼神 "demon god", 刀影 "sword shadow", 浪人 "ronin", 桜 "cherry
  blossom", 紙の映画) plus a kunai and tassels; red cords and ribbons; tag earrings.

## The cast
| who | posters | look |
|---|---|---|
| **The hero: the dreadlocked samurai** | #2, #4, #7, #8, #9, #11, #12, #13 | locs with metal cuffs, a shaved line or cornrows, a scar, tag earrings, sometimes a headband; dark kimono with a white cherry crest |
| young samurai, wild hair | #1, #5 | scar, headband |
| swordswoman with curly locs | #10 | white rope belt with tassels, cherry kimono |
| masked swordswoman | #3 | oni half-mask, hairpins with a red tassel |
| blindfolded swordswoman | #6 | white blindfold, hairpins |

## The worlds
A castle on cliffs with waterfalls, bridges and red banners carrying a cherry crest (#12, #13, #14); a torii gate
with stone stairs (#14); glowing stone lanterns (#13); mist and clouds; the red sun.

## The one that IS the name: #14
The sword is wrapped in torn paper strips with a red cord: literally *paper cinema*. That idea (paper strips, torn
paper edges, the seal) is the brand in one picture.

## What gets built from this (when Mark says go)
1. **The hero as our paper character:** a dreadlocks part with metal cuffs, tag earrings, a scar, the headband;
   data on the existing skeleton, like `kojiro.json` and `musashi.json`.
2. **Props:** the oni-mask charm set (mask, chain, kanji tag, kunai, tassels), the cherry-over-waves guard on
   `blender/props/katana_hero.py`, red cords, the torn-paper wrap of #14.
3. **World kit:** the castle on cliffs with waterfalls, banners with our crest, torii and stairs, stone lanterns.
4. **Cover maker 2.0** (`tools/cover.py`) in this look: a brush title, red sun or ensō, a cherry branch, ink
   splashes, this bottom band; the kanji always typeset from a real font.

## Open decisions (Mark's)
1. **Red or orange?** All 14 are red; the first cover (`tools/cover.py`) is orange.
2. **2D posters, 3D videos.** These are flat ink drawings and the films are 3D paper. A cover has to look like the
   video it opens. Options: covers in this look made from our 3D renders (ink outline, this palette); these AI posters
   as covers (only if the tool's terms allow commercial use); or move the films toward this ink look.
3. **Where the 14 images live:** this repo once it is private, or somewhere else.
