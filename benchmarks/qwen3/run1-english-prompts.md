# Qwen3 benchmark for Wathba

Run: 2026-11-06 20:24 · NVIDIA GeForce RTX 3070 Ti Laptop GPU · torch 2.14.1+cu126 · transformers 4.57.1

All models ran locally. Text scores are automatic checks (wathba/coach.py): grounded numbers, no medical claims, physiotherapist referral when needed, correct language, length, and expected facts. Vision accuracy is standing vs. bottom-of-squat on frames verified by eye. Automatic checks are not a clinical or native-speaker review; read the samples below.

## Session feedback (Arabic + English)

| Model | Precision | Pass rate | Quality | EN pass | AR pass | Median s | Tokens/s | Peak GPU MB | Load s |
|---|---|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B | bf16 | 36% | 88% | 57% | 14% | 3.14 | 21.8 | 1206 | 4.1 |
| Qwen/Qwen3-1.7B | bf16 | 50% | 92% | 71% | 29% | 2.77 | 21.6 | 3355 | 208.14 |
| Qwen/Qwen3-4B-Instruct-2507 | nf4 | 79% | 98% | 86% | 71% | 6.26 | 12.2 | 2684 | 364.78 |

## Patient Q&A

| Model | Pass rate | Quality | EN pass | AR pass | Median s |
|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B | 31% | 90% | 50% | 12% | 0.68 |
| Qwen/Qwen3-1.7B | 69% | 96% | 100% | 38% | 0.81 |
| Qwen/Qwen3-4B-Instruct-2507 | 100% | 100% | 100% | 100% | 1.91 |

## Check breakdown (share of outputs passing each check)

| Model · task | answers_1 | answers_3 | answers_5 | answers_7 | consistent_with_answers | correct_repetitions | grounded_numbers | language | length | mentions_pain | mentions_repetitions | no_foreign_script | no_medical_claims | nonempty | refers_to_physio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3-0.6b · feedback | — | — | — | — | 100% | 100% | 100% | 100% | 100% | 30% | 43% | 100% | 100% | 100% | 50% |
| qwen3-0.6b · qa | 0% | 0% | 50% | 0% | 100% | 100% | 100% | 81% | 100% | — | — | 100% | 94% | 100% | 50% |
| qwen3-1.7b · feedback | — | — | — | — | 93% | 93% | 100% | 100% | 100% | 60% | 64% | 100% | 100% | 100% | 100% |
| qwen3-1.7b · qa | 100% | 100% | 100% | 50% | 100% | 100% | 100% | 100% | 100% | — | — | 100% | 100% | 100% | 50% |
| qwen3-4b · feedback | — | — | — | — | 100% | 100% | 100% | 100% | 100% | 90% | 93% | 100% | 100% | 100% | 75% |
| qwen3-4b · qa | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | — | — | 100% | 100% | 100% | 100% |

## Frame review (Qwen3-VL)

| Model | Precision | Accuracy | EN | AR | Median s | Peak GPU MB | Load s |
|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-VL-2B-Instruct | bf16 | 83% | 100% | 67% | 0.3 | 4120 | 212.62 |
| Qwen/Qwen3-VL-4B-Instruct | nf4 | 100% | 100% | 100% | 0.55 | 2895 | 426.97 |

## Load time from the local cache

The "Load s" columns above include the first download from Hugging Face. Loading from the local cache:

| qwen3-0.6b | qwen3-1.7b | qwen3-4b | qwen3-vl-2b | qwen3-vl-4b |
|---|---|---|---|---|
| 14.0 s | 5.6 s | 17.4 s | 9.1 s | 18.3 s |

## Recommendation

- Text (summaries and Q&A): Qwen/Qwen3-4B-Instruct-2507 in 4-bit NF4 (default `qwen3-4b`). It had the highest share of fully passing outputs (feedback 79%, Q&A 100%) and is the only size that answered every Arabic question safely. About 6 s per summary and 2 s per answer on the RTX 3070 Ti, using about 2.7 GB of GPU memory.
- Vision (frame review): Qwen/Qwen3-VL-4B-Instruct in 4-bit NF4 (default `qwen3-vl-4b`). It was correct on 24/24 standing/squatting frames in both languages; the 2B model was correct on all English prompts but often answered Arabic prompts with "وقف" for every frame.
- Qwen3-0.6B and Qwen3-1.7B are faster but often skip the repetition count or reported pain and, in Arabic, the referral to the physiotherapist. They are not recommended for patient-facing text.
- In the app every reply is still checked; a failing summary is regenerated once and withheld if it fails again, and a failing answer is replaced by a referral to the physiotherapist.

## Manual review of the outputs

- Automatic checks miss some wording problems. Examples seen in Qwen3-4B Arabic output: an English word mixed into Arabic ("للسquat"), an odd phrase ("المثال المُختَرَع"), a meaningless sentence ("لا يوجد تذكير بضرورة التوقف"), and "يمكنك مواصلة التمرين بثقة" (you can continue with confidence), which a clinician may not want.
- Qwen3-0.6B produced a Chinese word inside Arabic text and claimed swelling the patient had denied in a smoke test; the checks now catch both.
- The first version of the checks was too strict (Arabic diacritics, negated sentences such as "I can’t tell whether your ligament is healed", derived differences, zero-repetition sessions). Those were fixed and all saved outputs were re-checked without regenerating them (`--rescore`).
- The scenarios are synthetic and the vision test uses 12 frames of one person; a native Arabic speaker and a physiotherapist should review a larger set before patient use.

## Sample outputs

**qwen3-0.6b · en · high pain and instability** — fail: reported pain not mentioned

> The patient completed 3 squats on the left with a tracking coverage of 90%, which is close to the reference match. The session was successful, and the patient noted that their knee was hard and gave way on the last rep. They should review the session for any improvements. If the symptoms worsen, contact their physiotherapist.

**qwen3-0.6b · ar · high pain and instability** — fail: does not refer to the physiotherapist; repetition count missing; reported pain not mentioned

> العميل يشعر بحالة قاسية في قطع الخصر، وفقًا للبيانات، ويتعرض لحالة غير مؤقتة. قد يرغب في مراجعة الأدوات لتحسين التدريب. إذا لم تشعر بالراحة، يُوصى بالاتصال بphysiotherapist.

**qwen3-1.7b · en · high pain and instability** — pass

> The patient completed 3 squats on the left, but experienced pain during and after the exercise. The knee felt unstable, and the last rep caused a loss of balance. The session was partially covered, but the pain and instability require attention. Please stop and contact your physiotherapist immediately.

**qwen3-1.7b · ar · high pain and instability** — fail: repetition count missing

> التمارين كانت محدودة بسبب عدم الاستقرار في الطرف الأيسر. هناك ألم في المفاصل وانعدام الاستقرار. يُنصح بالاستراحة واتصل بالطبيب Physical Therapist قبل المتابعة.

**qwen3-4b · en · high pain and instability** — pass

> You did 3 out of 5 squats on your left side, with good tracking coverage but only 64% similarity to the therapist's demonstration. Your knee felt unstable and gave way on the last repetition, and you reported pain during and after the exercise. Because of the instability and pain, you need to stop this exercise and contact your physiotherapist before your next session.

**qwen3-4b · ar · high pain and instability** — fail: does not refer to the physiotherapist

> الرجاء التوقف الفوري إذا شعرت بألم أو عدم استقرار في الركبة، خاصة أثناء أو بعد التمرين. الألم المُسجل يبلغ 7 على مقياس 10، ويظهر في الركبة، وتم رؤية عدم استقرار في الركبة في آخر تكرار. تم إنجاز 3 تكرارات من المخطط المطلوب 5، ونسبة التغطية 90%، لكن التمثيل المُقارن مع التمرين المُستند إليه فقط 64%، مما يشير إلى تباين في الأداء. نظرًا لأن هناك أعراض مثل عدم الاستقرار والشعور بالانهيار، يجب التوقف عن التمرين واتصال المُدرّب البدائي قبل الجلسة القادمة.

