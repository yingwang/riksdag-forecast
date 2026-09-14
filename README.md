# Riksdag 2026 forecast

Sweden voted on 13 September 2026. On election night the preliminary count gave the four parties behind Magdalena Andersson (S, V, C, MP) 176 seats and the four behind Ulf Kristersson (M, SD, KD, L) 173, with 175 needed for a majority. About 3–4 % of the votes are only counted from the Wednesday after the election, and the whole count is then redone as the final count during the week. This repository forecasts what the final seat distribution will be, re-runs itself every two hours from Valmyndigheten's live result files, and scores itself against the certified result when it arrives.

Live page: **https://yingwang.github.io/riksdag-forecast/**

<!-- forecast:start -->
**Latest run** 2026-09-14 16:05 UTC · count updated 2026-09-14T17:57:59 · 6311/6626 districts

- P(S + V + C + MP ≥ 175) = **99.3 %** (median 176, 90 % range 175–176)
- P(M + SD + KD + L ≥ 175) = **0.7 %** (median 173, 90 % range 173–174)
- Expected votes still to count: 230,207

| Party | Seats now | Forecast mean | 90 % range |
|---|---:|---:|---:|
| S | 100 | 99.0 | 98–100 |
| M | 70 | 70.4 | 70–71 |
| SD | 62 | 61.9 | 61–62 |
| V | 29 | 29.6 | 29–30 |
| C | 25 | 25.0 | 25–25 |
| KD | 22 | 22.0 | 22–22 |
| MP | 22 | 22.0 | 22–22 |
| L | 19 | 19.0 | 19–19 |
<!-- forecast:end -->

## How it works

1. `riksdag/fetch.py` downloads the current preliminary and final-count result files (zip of JSON per polling district) from `resultat.val.se`.
2. `riksdag/data.py` reads them: votes per party per constituency, which of the 6 626 districts have reported, and which of the 314 collection districts (`uppsamlingsdistrikt`, the votes counted from Wednesday) are still pending.
3. `riksdag/model.py` takes the counted votes as given and simulates the rest, 4 000 times:
   - unreported ordinary districts get their 2022 result moved by the constituency's 2022→2026 swing;
   - the collection districts get, per constituency, their 2022 size (scaled by the growth in counted votes, lognormal uncertainty shared nationally and locally) and their 2022 party mix moved by the local swing, with a correlated national perturbation and constituency-level Dirichlet noise;
   - a small jitter stands in for the final recount (in 2022 it moved shares by at most 0.02 points).
4. `riksdag/seats.py` allocates the 349 seats exactly as vallagen 14 kap. prescribes: 310 fixed constituency seats by the adjusted odd-number method (first divisor 1.2), the 4 % national and 12 % constituency thresholds, return of surplus seats, and 39 levelling seats placed by comparison number (with the full vote count as comparison number where a party holds no fixed seat). `tests/test_seats.py` checks that it reproduces Valmyndigheten's own seat tables for all 29 constituencies from the same votes.
5. `riksdag/run.py` writes `forecast/latest.json`, appends `forecast/history.jsonl`, saves a compact snapshot of the count in `data/snapshots/`, renders `docs/index.html` and updates the block above.
6. When the final count covers every district, `riksdag/verify.py` scores every earlier run (Brier score on the majority question, seat error per party) into `forecast/verification.md`.

The prior in `data/prior_2022.json` comes from the 2022 result files: the collection districts held 3.4 % of the votes and voted differently from the polling stations (S 26.6 % against 30.5 %, V 9.1 % against 6.7 %, M 20.1 % against 19.1 %, SD 18.5 % against 20.6 %).

Sensitivity: with the default uncertainty the left bloc's majority is near-certain; doubling the uncertainty on the size and mix of the late votes still leaves it above 95 %, because flipping two seats needs a net swing of roughly 37 000 votes out of some 226 000 that remain, and the late votes have leaned left.

The step from "who has 175 seats" to "who becomes prime minister" is a judgement, not a model; its weights are in `config.json` and shown on the page as such.

## Run it

```
pip install numpy
python -m riksdag.run                         # live data
python -m riksdag.run data/samples/<file>.zip # a saved snapshot
python tests/test_seats.py
```

The GitHub Actions workflow in `.github/workflows/forecast.yml` runs the same command every two hours and commits the results.

## 中文说明

瑞典 2026 年 9 月 13 日大选，选举夜的初步计票是安德松一方（S、V、C、MP）176 席对克里斯特松一方（M、SD、KD、L）173 席，过半需要 175 席。约 3% 到 4% 的选票（提前投票的晚到部分、海外票、跨市投票）要到周三起才点，之后整周还要做一遍正式复点。这个仓库每两小时从选举局的实时结果文件重新预测最终席位，并在正式结果出来后自动给自己打分。

做法：把已点的票当作已知，对剩下的票做四千次模拟（用 2022 年同类票的规模与党派构成作先验，按各选区今年的摆动修正，再加上相关的不确定性），每一次模拟都按选举法第十四章的规则分配 349 席（固定席位、4% 与 12% 门槛、超额席位回收、调整席位），席位分配算法已用官方的 29 个选区席位表逐一核对。
