# Moves: call a movement by name, get the same movement every time

A film never describes a movement joint by joint. It names one:

    { "t": 3.2, "move": "kesa-giri" }
    { "t": 0.4, "move": "sword-engage", "anime": 1.3 }

`library/moves.json` holds 26 of them. The fighter's position and facing at the moment of the call
decide where the move happens, so the same name works in any film, from any starting spot, facing
any direction. Call it twice, get the same movement twice.

## Two kinds of move, called the same way

| Kind | Looks like | Where it comes from |
|---|---|---|
| **Pose beats** | `[{ "dt": 0, "pose": "chudan" }, { "dt": 0.28, "pose": "chudan", "fwd": 0.4 }]` | authored by hand |
| **Recorded motion** | `{ "clip": "sword-a", "from": 1.0, "to": 4.0, "anime": 1.3 }` | a real person, captured |

A film cannot tell the difference and does not need to. `expandMoves()` turns either into ordinary
keys. Recorded moves read their frames from `library/mocap/<clip>.json`; `library/mocap-bonemap.json`
says which captured joint drives which of our bones.

## `anime`: deliberate unrealism, on a dial

Motion capture is a recording of a real person, and a real person is not an anime character. The
extremes are too small, the holds too short. That is the actual reason captured motion can look
*worse* than hand animation even though it is more accurate.

`anime` pushes every angle further from the clip's own average for that slice:

| Value | Result |
|---|---|
| `1` | the recording untouched |
| `1.2`–`1.4` | reads as animation: higher guard, deeper crouch, longer reach |
| `> 1.8` | limbs start to break |

**What it never touches:** position, timing, foot contacts and gait phase. Measured on
`sword-engage`, the travel is identical at `anime: 1` and `anime: 1.3` (x 0.098 m, z 0.034 m) while
the shoulder's range grows from 0.82 to 1.07 radians. Exaggerating a pose must never move the
fighter somewhere the film did not ask for, so the angle channels are scaled and nothing else is.

## What the recorded moves actually contain

Measured on `film/sword-mocap.json` (hero, 8 s, two recorded moves at `anime: 1.3`):

| | |
|---|---|
| right shoulder swing | 2.16 rad (124°) |
| right elbow | 1.13 rad (65°) |
| stride | 0.40 |
| **feet travel** | **x 0.16 m, z 0.30 m** |
| foot slide | 0.00 m on all four feet |

Read that last pair together and be honest about it: this capture is **swordplay in place**. The
arms do a great deal and the feet barely move, the way two fencers trade blows without crossing the
floor. So the zero slide is real but easy, and these clips are not where footwork comes from. For a
fighter who covers ground, keep the authored moves (`step-in`, `lunge-shomen`, `jump-back`) and use
the recorded ones for what they are good at: what the arms and blade do.

## Adding a recorded move

1. Convert a capture: `python3 tools/mocap_cmu.py assets/mocap/cmu/02_08.amc --out library/mocap/sword-b.json`
2. Add an entry to `library/moves.json` naming the clip and the slice you want
3. Call it from a film. `engine/validate.mjs` fails if the clip is missing or the slice is empty.
