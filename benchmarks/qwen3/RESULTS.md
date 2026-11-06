# Qwen3 benchmark for Wathba

Run: 2026-11-06 21:00 · NVIDIA GeForce RTX 3070 Ti Laptop GPU · torch 2.14.1+cu126 · transformers 4.57.1

All models ran locally. Text scores are automatic checks (wathba/coach.py): grounded numbers, no medical claims, physiotherapist referral when needed, correct language, length, and expected facts. Vision accuracy is standing vs. bottom-of-squat on frames verified by eye. Automatic checks are not a clinical or native-speaker review; read the samples below.

## Session feedback (Arabic + English)

| Model | Precision | Pass rate | Quality | EN pass | AR pass | Median s | Tokens/s | Peak GPU MB | Load s |
|---|---|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B | bf16 | 56% | 93% | 62% | 50% | 5.89 | 13.6 | 1249 | 6.94 |
| Qwen/Qwen3-1.7B | bf16 | 50% | 94% | 62% | 38% | 3.68 | 22.4 | 3402 | 4.16 |
| Qwen/Qwen3-4B-Instruct-2507 | nf4 | 81% | 98% | 75% | 88% | 6.83 | 12.6 | 2751 | 7.62 |

## Patient Q&A

| Model | Pass rate | Quality | EN pass | AR pass | Median s |
|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B | 25% | 91% | 50% | 0% | 0.65 |
| Qwen/Qwen3-1.7B | 69% | 97% | 100% | 38% | 0.81 |
| Qwen/Qwen3-4B-Instruct-2507 | 100% | 100% | 100% | 100% | 2.18 |

## Check breakdown (share of outputs passing each check)

| Model · task | answers_1 | answers_3 | answers_5 | answers_7 | consistent_with_answers | correct_repetitions | grounded_numbers | language | length | mentions_pain | mentions_repetitions | no_field_names | no_foreign_script | no_medical_claims | nonempty | refers_to_physio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-0.6b · feedback | — | — | — | — | 88% | 100% | 100% | 94% | 100% | 75% | 75% | 100% | 100% | 100% | 100% | 50% |
| qwen3-0.6b · qa | 0% | 0% | 0% | 0% | 100% | 100% | 100% | 81% | 100% | — | — | 100% | 100% | 100% | 100% | 50% |
| qwen3-1.7b · feedback | — | — | — | — | 94% | 94% | 100% | 100% | 100% | 92% | 75% | 94% | 94% | 100% | 100% | 67% |
| qwen3-1.7b · qa | 50% | 100% | 100% | 50% | 100% | 100% | 100% | 100% | 100% | — | — | 100% | 100% | 100% | 100% | 62% |
| qwen3-4b · feedback | — | — | — | — | 100% | 100% | 100% | 100% | 100% | 92% | 94% | 94% | 100% | 100% | 100% | 100% |
| qwen3-4b · qa | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | — | — | 100% | 100% | 100% | 100% | 100% |

## Frame review (Qwen3-VL)

| Model | Precision | Accuracy | EN | AR | Median s | Peak GPU MB | Load s |
|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-VL-2B-Instruct | bf16 | 83% | 100% | 67% | 0.22 | 4120 | 6.12 |
| Qwen/Qwen3-VL-4B-Instruct | nf4 | 100% | 100% | 100% | 0.42 | 2895 | 12.61 |

## Load time from the local cache

The "Load s" columns above include the first download from Hugging Face. Loading from the local cache:

| qwen3-0.6b | qwen3-1.7b | qwen3-4b | qwen3-vl-2b | qwen3-vl-4b |
|---|---|---|---|---|
| 14.0 s | 5.6 s | 17.4 s | 9.1 s | 18.3 s |

## Recommendation

- Text (summaries and Q&A): Qwen/Qwen3-4B-Instruct-2507 in 4-bit NF4 (default `qwen3-4b`). Highest share of fully passing outputs: feedback 81% (English 75%, Arabic 88%) and Q&A 100%. About 6.83 s per summary and 2.18 s per answer on the RTX 3070 Ti, using about 2.7 GB of GPU memory.
- Vision (frame review): Qwen/Qwen3-VL-4B-Instruct in 4-bit NF4 (default `qwen3-vl-4b`): 24/24 standing/squatting frames correct in both languages. Qwen3-VL-2B was correct in English but answered most Arabic prompts with the same word.
- Qwen3-0.6B and Qwen3-1.7B are faster but often omit the repetition count, the reported pain or (in Arabic answers) the referral to the physiotherapist. Not recommended for patient-facing text.
- In the app every reply is still checked: a failing summary is regenerated once and withheld if it fails again, a missing referral is replaced by a fixed safety sentence, and a failing answer becomes a fixed referral to the physiotherapist.

## Changes since the first run

- Run 1 sent English instructions and English fact names for Arabic answers. Qwen3-4B Arabic summaries then leaked a field name ("needsattention"), named the wrong specialist ("مختص التغذية البدنية") and mixed in English words.
- Run 2 (this report) uses Arabic instructions and Arabic fact labels for Arabic answers. Arabic pass rates rose for 0.6B (14% to 50%) and 1.7B (29% to 38%); Qwen3-4B Arabic stayed at 71-75% but its wording improved (no leaked names, correct specialist). Run 2 also includes the two real saved sessions, so feedback has 16 outputs per model instead of 14. Run 1 is kept in run1-english-prompts.md.

## Manual review of the outputs

- Automatic checks miss some wording problems. Qwen3-4B Arabic summaries often address the patient in the third person ("المريض أدى...") instead of "you", and one English summary leaked the field name "needsattention" (caught by the checks).
- In run 1, Qwen3-0.6B produced a Chinese word inside Arabic text and claimed swelling the patient had denied; the checks now catch both.
- The first version of the checks was too strict (Arabic diacritics, negated sentences such as "I can’t tell whether your ligament is healed", derived differences, zero-repetition sessions, a target mentioned a few words before the number). These were fixed and all saved outputs were re-checked without regenerating them (`--rescore`).
- The scenarios are synthetic (plus two real saved sessions), and the vision test uses 12 frames of one person. A native Arabic speaker and a physiotherapist should review a larger set before patient use.

## Sample outputs

**qwen3-0.6b · en · high pain and instability** — fail: reported pain not mentioned

> The patient completed 3 squats on the left with a tracking coverage of 90%, which is close to the reference match. The session was successful, and the patient noted that their knee was hard and gave way on the last rep. They should review the session for any improvements. If the symptoms worsen, contact their physiotherapist.

**qwen3-0.6b · ar · high pain and instability** — fail: does not refer to the physiotherapist; repetition count missing

> ملاحظات المريض:  - أثناء التمرين، ألم ظهر في الركبة.   - الألم بعد التمرين من 0 إلى 10، ودائم.   - عدم ثبات الركبة.   - ألم ظهر في الركبة.   - تورم جديد غير موجود.   - عدم ثبات الركبة.   - ألم ظهر في الركبة.   - ألم ظهر في الركبة.   - ألم ظهر في الركبة.   - ألم ظهر في الركبة.

**qwen3-1.7b · en · high pain and instability** — pass

> The patient completed 3 squats on the left, but experienced pain during and after the exercise. The knee felt unstable, and the last rep caused a loss of balance. The session was partially covered, but the pain and instability require attention. Please stop and contact your physiotherapist immediately.

**qwen3-1.7b · ar · high pain and instability** — pass

> المريض أداء التمرين بالجانب الأيسر بواقع 3 تكرارات، حيث أظهر ألم أثناء التمرين وتمامًا 7 من 10 بعد التمرين، وتم تجربة الصعوبة في تثبيت الركبة. تكرار التمرين كان غير ثابت، ولم تظهر أي أعراض جديدة. المريض يطلب متابعة، ويجب التوقف إذا ساءت الأعراض ويتم التواصل مع أخصائي العلاج الطبيعي قبل الجلسة القادمة.

**qwen3-4b · en · high pain and instability** — pass

> You did 3 out of 5 squats on your left side, with good tracking coverage but only 64% similarity to the therapist's demonstration. Your knee felt unstable and gave way on the last repetition, and you reported pain during and after the exercise. Because of the instability and pain, you need to stop this exercise and contact your physiotherapist before your next session.

**qwen3-4b · ar · high pain and instability** — pass

> المريض أدى تمرين القرفصاء على الجانب الأيسر، وتم إنجاز 3 تكرارات مكتملة من بين 5 مستهدفين، مع مدة تسجيل 26 ثانية ونسبة تطابق مع المرجع 64%. كان هناك ألم في الركبة أثناء التمرين، وبلغ مستوى الألم 7 من 10، ونُسِبَت الملاحظة بأن الركبة فقدت التوازن في التكرار الأخير. يُطلب من المريض التوقف فورًا إذا ساءت الأعراض واتصاله بأخصائي العلاج الطبيعي قبل الجلسة القادمة.

