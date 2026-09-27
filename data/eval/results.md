# ClaimLens replay evaluation (hindsight)

- Claims replayed: 215 (scored: 70), model `openai/gpt-oss-120b`, flag threshold 61

| | Without memory | With Hindsight |
|---|---|---|
| Fraud recall | 0% (0/33) | 42% (14/33) |
| Precision | 0% | 100% |
| Genuine claims flagged | 0 | 0 |
| ROC AUC | 0.46 | 0.79 |
| Fraud value flagged | Rs 0 | Rs 3,674,500 |

## By fraud ring

| Ring | Claims | Caught without memory | Caught with memory |
|---|---|---|---|
| R1 | 13 | 0 | 6 |
| R2 | 11 | 0 | 5 |
| R3 | 7 | 0 | 3 |
| R4 | 2 | 0 | 0 |

## By month

| Month | Scored | Fraud | Recall without | Recall with | False flags without | False flags with |
|---|---|---|---|---|---|---|
| Jan | 5 | 0 |  |  | 0 | 0 |
| Feb | 6 | 0 |  |  | 0 | 0 |
| Mar | 7 | 4 | 0% | 0% | 0 | 0 |
| Apr | 5 | 2 | 0% | 0% | 0 | 0 |
| May | 8 | 5 | 0% | 0% | 0 | 0 |
| Jun | 7 | 3 | 0% | 0% | 0 | 0 |
| Jul | 12 | 7 | 0% | 43% | 0 | 0 |
| Aug | 9 | 5 | 0% | 100% | 0 | 0 |
| Sep | 11 | 7 | 0% | 86% | 0 | 0 |
