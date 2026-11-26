# Fix order: what gets fixed before any paid 3D (Mark, 26 Nov)

Mark: "before we start to be able to do the 3D, start fixing all this problem." One item at a time, in this
order; each is done when its check passes and Mark has seen the clip. Older detailed notes: `FIX-LIST.md`.

| # | Problem (Mark's words) | Root cause found | Fix | Status |
|---|---|---|---|---|
| 1 | "The blade have to be real, like real metal ... the one that hold the blade have to be real 3D. The blade cannot just pull out like that." | The film's sword was three boxes; the scabbard was glued inside the hakama (0% visible); the hands were posed by angles, never on the handle; the blade slid in a straight line | `blender/props/katana_real.py` (real curved steel blade, wrapped handle, motif guard, curved lacquer scabbard), `blender/props/sword_draw.py` (scabbard outside the clothes, left hand holds/levels/turns it, right hand on the handle by IK: 0 mm / 0 deg, blade slides along its own curve) | test clip done and **seen by Mark, 26 Nov: "it got much better ... I like it"** (`output/draw-hip/`, `output/draw-test/`, 30 fps); next: wire into `film_modular.py` and the scabbard throw |
| 1b | "Give it a real articulation of a hand ... the wrist to be able to turn around ... that hand switch" (Mark, 26 Nov) | The hand had no finger joints (one flat sheet); the sword was glued to one hand for the whole film, so no hand switch, reverse grip or spin was possible | done: gripping hands (fingers folded round the handle and the scabbard, `sword_draw.build_grip_hand`). Next: a per-finger CURL channel (open 0 to closed 1, 3 joints per finger) so hands open and close on camera; a GRIP TRACK in the film data (which hand holds, normal or reverse grip, both hands) so the sword can be handed from one hand to the other, flipped to a reverse grip or spun about the grip point while the fingers open and close; wrist limits so the turns stay human | grip shape done; curl + grip track open |
| 2 | "Why doesn't the fight look good?" | No contact (swords pass through each other); hit-stop, smear, impact punch only in the browser preview; Blender bakes every move linear | blade contact + hit-stop + anticipation/snap in the Blender film, the same arm IK for two-handed grips | open |
| 3 | "We don't have really that much of effect" | 42 effects listed, only the slash reaches the final render | wire glint, ink impact frame, paper shards, dust, petals, embers into the Blender film | open |
| 4 | "Camera control is extremely bad" | the Blender camera copies a path, nothing keeps the action in frame (the first draw test lost the blade off the edge); no depth of field, no motion blur | a framing check (blade + hands in frame), blade-follow, DOF and motion blur in Blender | open |
| 5 | "The paper movement" | clothes are stiff panels on bones | follow-through: sleeves, hakama, headband and tassels lag and overshoot | open |
| 6 | "Our characters ... are bad and ugly" | every part is boxes and rings placed by math; 32 parts in 16 slots | redesign against Mark's posters; more parts per slot; rigid hero pieces later from Tripo | open |

Rule for every item: measure first (a number or a frame), fix, show the 30 fps clip. Our own judgement is not a
score; Fable reviews when usage credits are on (AGENTS.md rule 01).
