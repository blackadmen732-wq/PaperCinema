# Research: Musashi and the Yoshioka school at Ichijō-ji (1604)

Episode 2 (`film/ichijoji-ep2.json`, written by `film/src/ichijoji-ep2.py`). The fight is part of the Musashi story
everyone tells, but almost every detail comes from accounts written 50 to 170 years later. The film marks which is which.
Confidence marks as in `research/ganryujima.md`: **Documented** (sources agree, not seriously disputed),
**Tradition** (classic accounts; late sources, or they disagree), **Our choice** (an artistic decision, not from a source).

## Facts and how the film uses them

| What | Status | Notes | In the film |
|---|---|---|---|
| Musashi fought the Yoshioka, Kyoto's leading sword school (masters of the Ashikaga shōguns), and they lost | **Documented** (as far as anything here is) | The *Kokura hibun*, a stone inscription put up in 1654 by Musashi's adopted son Iori, nine years after his death, tells it. It is a family monument, so it is on Musashi's side. | The whole film |
| Three fights: Seijūrō, then his brother Denshichirō, then the boy Matashichirō at Ichijō-ji | **Tradition** | The *Kokura hibun* and the *Nitenki* (1776) both have the sequence. The Yoshioka side's own record (*Yoshioka-den*) tells the first bout differently (a draw), so the score depends on whose account you read. | Title: "Twice the Yoshioka had lost to him" |
| Date: 1604 (Keichō 9) | **Tradition** | The year usually given (Nitenki; Yoshikawa's novel follows it). Musashi wrote that he went to Kyoto at 21 and fought famous swordsmen there (*Gorin no sho*, about 1645), which fits 1604 for a man born 1584, but he names nobody. | Title: "1604 (traditional date)" |
| The place: the "hanging pine" (*sagari-matsu*) at Ichijō-ji, a crossroads outside Kyoto on the road north-east | **Tradition** for the fight; **Documented** for the place | The *Kokura hibun* says Matashichirō gathered his students "around the Sagarimatsu outside the capital". The pine and its crossroads still exist (Ichijō-ji Sagarimatsu-chō, Sakyō-ku, Kyoto) with a stone "site of the Miyamoto-Yoshioka duel"; the tree standing now is said to be the 4th generation (one source: tabi-mag). | The set `library/sets/ichijoji-crossroads.json`: two roads crossing, a big leaning pine on the corner |
| Matashichirō was a boy, put up as the nominal head of the school | **Tradition** | The *Nitenki* makes him Seijūrō's son and young; other accounts make him Denshichirō's son. His age is not reliably known. We do not state an age. | "Their new head was a boy." Played by the armoured `samurai-ai` figure (the figures cannot be made smaller without code: see `docs/EPISODE-2.md`) |
| The Yoshioka came in numbers | **Tradition** | The *Kokura hibun* says "several hundred" students; later retellings give dozens, some armed with bows and guns. Every number is a late, partisan count. | Title says "and all his school" with no number; on screen, three men (the cast we have) |
| This time Musashi came early and waited | **Tradition** | The reverse of the lateness of Ganryūjima (and of the first two Yoshioka bouts, in the classic telling). | S1-S3: he is already under the pine, in the dark, when they arrive |
| He cut down the boy first, then fought his way out | **Tradition** | The core of every telling (*Nitenki*). Killing the nominal leader first is told as the tactic that broke them. | S4-S5 |
| He used two swords here | **Tradition** (late) | Some retellings put the origin of his two-sword style at Ichijō-ji. Not in the film: the rig holds one sword (`docs/EPISODE-2.md`, "What needed code"). | Not shown |
| On the way he stopped at the Hachidai shrine to pray, and decided not to | **Tradition / popular fiction** | Mostly Yoshikawa Eiji's novel *Miyamoto Musashi* (1935-39). The shrine is real and stands just above the pine. | Not shown; a torii on the slope above the pine is set dressing (Our choice) |
| "Respect the Buddhas and the gods without counting on their help." (*Busshin wa tattoshi, busshin wo tanomazu*) | **Documented** (the words) | Precept 19 of the *Dokkōdō* ("The Path of Aloneness"), which Musashi wrote a week before he died, in 1645. The link to Ichijō-ji is the novel's, so the film quotes it as "Musashi later wrote" and draws no connection. | Closing title |
| The duel happened before dawn | **Tradition** | The classic telling has him arrive in the dark and wait. | Night set: moon low, ground mist (Our choice for the look) |
| Matashichirō's armour, the retainers' costumes | **Our choice** | The available cast: `samurai-ai` (the boy), `ronin-ai-kabuto` and `assassin-ai` (two retainers). | The cast |
| Paint and paper shards, never blood | **Our choice** (project rule 4) | | Every cut |

## Main sources and their limits

- **Kokura hibun (小倉碑文), 1654.** The earliest account; a memorial by Musashi's adopted son, so not neutral.
- **Nitenki (二天記), 1776.** The fullest story, 130 years after Musashi's death, from retainer interviews; tradition.
- **Gorin no sho (五輪書), about 1645.** Musashi's own: Kyoto at 21, famous swordsmen, never lost. No names, no Ichijō-ji.
- **Dokkōdō (獨行道), 1645.** The 21 precepts; precept 19 is the closing title.
- **Yoshikawa Eiji, *Miyamoto Musashi* (novel, 1935-39)** and the film *Samurai II: Duel at Ichijōji Temple* (1955):
  where most of the popular detail (the shrine, the boy's age, the fight's choreography) comes from. Fiction.

## Web sources consulted (28 Nov 2026)

- Wikipedia: [Yoshioka-ryū](https://en.wikipedia.org/wiki/Yoshioka-ry%C5%AB), [Miyamoto Musashi](https://en.wikipedia.org/wiki/Miyamoto_Musashi), [Samurai II: Duel at Ichijoji Temple](https://en.wikipedia.org/wiki/Samurai_II)
- [tabi-mag: 一乗寺下り松](https://tabi-mag.jp/ky0032/) (the pine now standing is the 4th; the Kokura hibun line "又七郎…洛外下松邊…門生数百人")
- [Light in the Clouds: Final Chapters of Kyōhachi-ryū: Yoshioka-ryū](https://lightinthecloudsblog.com/tag/yoshioka-ryu/)
- [Japanese Wiki Corpus: Miyamoto Musashi](https://japanese-wiki-corpus.github.io/person/Musashi%20MIYAMOTO.html) (Kokura hibun, 1654)
