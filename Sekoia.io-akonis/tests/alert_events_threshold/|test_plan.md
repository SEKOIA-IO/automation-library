| Area               | Coverage                                 |
| ------------------ | ---------------------------------------- |
| Config validation  | ✔ full                                   |
| Rule filters       | ✔ full                                   |
| Retry logic        | ✔ full (success + max failure)           |
| Count events API   | ✔ success + fail open                    |
| Threshold logic    | covered through happy-path & concurrency |
| Malformed payloads | ✔ invalid alert, invalid notification    |
| Concurrency        | ✔ multi-await on correlated state        |


needed?

 - test for _cleanup_old_states
 - test for next_batch (with a fake async generator)
 - test for run() main-loop restart logic
 - snapshot-based golden test for large fixtures (valid JSON payloads)