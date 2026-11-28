# The asset library (Supabase)

Mark, 28 Nov: "the test we did with the bucket, put it in and transform it to paper: that's what I want the library
for." Existing free models (Poly Haven, CC0) and our generated parts, the PAPER version our pipeline makes of each, a
still of it, and one catalogue row per asset, so any session on any machine can find a part, fetch it and build a scene.

- **Project**: Supabase org "Paper Cinema" (free plan), project `papercinema`, ref `pkqbqlhgffqatgryofxt`, us-east-1.
- **Files**: private bucket `pc-library` (50 MB a file on the free plan; 1 GB in all).
- **Catalogue**: table `public.pc_library`: `id` (`poly-haven/wooden_bucket_01`, `tripo/ronin-model-1`, `set/edo-village`),
  `kind` (prop, building, tree, plant, rock, character-part, character, set, texture), `source`, `licence`, `title`,
  `tags`, `original_path`, `paper_path`, `preview_path` (paths in the bucket), `size_m`, `tris`, `credits`, `checked`
  (the proof), `used_in`.
- **Access**: the edge function `library` (`supabase/functions/library/index.ts`) holds the service role; the pipeline
  holds only the library token (`$PC_LIBRARY_TOKEN` or `~/.pc-library-token`, never in the repo). The environment's
  network allows `pkqbqlhgffqatgryofxt.supabase.co`.

```bash
python3 tools/library.py selftest
python3 tools/library.py put assets/polyhaven/wooden_bucket_01/wooden_bucket_01_1k.gltf poly-haven/wooden_bucket_01/original/wooden_bucket_01_1k.gltf
python3 tools/library.py rows --kind prop
```
