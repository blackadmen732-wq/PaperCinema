# Regression report

Branch head `c032307` against base `4a8c4cb` (origin/claude/relaxed-dirac-m3lm7k), 2026-11-28T08:17Z.
Reproduce: `bash tools/regression-report.sh` (needs Node 18+, Python 3 with numpy and OpenCV, ffmpeg).

| Check | Result | Verdict |
|---|---|---|
| npm test (Node, new-film, VYRN, Aethern) | # pass 27 # fail 0 Ran 10 tests in 6.577s Ran 28 tests in 1.679s # pass 6 # fail 0  in 15s | PASS |
| dash-test mix, Sonic off: 4a8c4cb vs head | 51b50249bddbca2bfdeda2df37197b6f / 51b50249bddbca2bfdeda2df37197b6f | PASS |
| dash-test mix, Sonic sonic: 824a2e1 vs head | 31d5ab4c8b2bedda2237badf90b5e042 / 31d5ab4c8b2bedda2237badf90b5e042 | PASS |
| version-1 events still read and upgraded | v1 line valid; merged as file:v1  | PASS |

Overall: PASS
