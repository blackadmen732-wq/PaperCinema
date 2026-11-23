# library/mocap: sources and licences

Every capture here records its source in its own `source` field. Only commercial-safe sources (CC0, CC-BY,
public domain, or the owner's own footage). CC-BY sources must be credited wherever the motion is used
(end credits or the video description).

| Capture | Source | Author | Licence | What we used / changed |
|---|---|---|---|---|
| `iaido-cut.json` | [Iaido 2.webm](https://commons.wikimedia.org/wiki/File:Iaido_2.webm), Wikimedia Commons (uploaded 2026-06-01; shows Maestro Kened Omar Bueno Rodríguez, Munazukushi, cutting bamboo) | Das Morton | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Seconds 59–66 of the 480p transcode; pose landmarks extracted with MediaPipe and turned into joint angles for our figure (tools/mocap.py). The video itself is not stored in the repo (download: see docs/MOCAP.md §6). |

Credit line for CC BY 4.0: *Motion reference: "Iaido 2" by Das Morton, Wikimedia Commons, CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/); landmarks extracted and retargeted.*

The pose estimator (MediaPipe Pose Landmarker, BlazePose GHUM 3D) is Apache-2.0 (code: github.com/google/mediapipe;
model: Google model card "BlazePose GHUM 3D", section *Licensed under Apache License, Version 2.0*; also stated on
huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full). Its output (landmarks) carries no extra terms.
