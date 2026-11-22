# 3D assets

Generated from your reference images with **Microsoft TRELLIS** (MIT licence, commercial use OK) on a rented RunPod RTX 4090.

| File | From | Notes |
|---|---|---|
| `models/ronin_base.glb` | Straw-hat samurai (your base image) | Clean. Inner glow baked into the texture. |
| `models/samurai_front.glb` | Front-facing samurai with sword | Clean, full body |
| `models/gold_armor.glb` | Gold origami armored samurai | Red paint splash from the background got included. Needs cleanup. |
| `models/kimono_swordswoman.glb` | Red/teal kimono swordswoman | The red sun disc behind her became a disc shape. Needs cleanup. |
| `models/kasa_hat.glb` | Straw hat on its own | Clean accessory for the library |

`previews/*_turntable.mp4` show each model spinning.

Regenerate: `python3 gpu/pod.py start` → upload images to `/workspace/in` → run `gpu/gen_trellis.py` → `python3 gpu/pod.py stop`.
