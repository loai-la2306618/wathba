> **Historical record.** This page describes the earlier MediaPipe preview deployment. The current source uses YOLOv8n-pose + MoveNet in the browser and an optional backend ViTPose check (see README). The preview has not been redeployed with it.

# Wathba shared preview

Production preview: https://wathba-demo.vercel.app

This preview runs independently of the laptop on the user's existing Vercel Hobby account. The original Hugging Face Space `JustViping/wathba-app` remains paused; creation of a second compute Space and a change to free CPU were rejected by Hugging Face with HTTP 402. No subscription or paid runtime was started.

The user explicitly authorized inclusion of the staged demonstration clips. Only the chosen therapist reference and one patient demonstration, with their measured tracks and evidence clips, were uploaded to the private dataset `JustViping/wathba-shared-demo-data`. Other recordings, QA sessions, local filesystem paths and API credentials are excluded. New demo sessions and feedback persist through the same private storage.

The preview requires an access code or its recipient access link. The access value is kept locally in the ignored `.wathba/share-access.json` and in sensitive Vercel environment variables. It is not in this source or the deployment's client code. Change `WATHBA_DEMO_PASSWORD` and `WATHBA_COOKIE_SECRET` in Vercel and redeploy to revoke existing access. A recipient link is intentionally shareable and should be sent only to intended viewers.

The backend's authenticated media route issues temporary object-storage URLs. The private media directory is not mounted as a deployable static directory. The browser loads open MediaPipe runtime/model assets from the deployment CDN. No inference-provider API or GPU is used.

Serverless preview limits: 4 MB uploads and 20-second camera recordings. The supplied demonstration video bypasses the upload limit because it is already in private storage. The local development app keeps its existing larger limits. The in-app Therapist Portal is included; `/physio` redirects to it in this lightweight deployment.

Deployment source is staged under the ignored `.wathba/deploy/wathba-demo`. Its entrypoint imports `wathba.serverless:app`, uses writable `/tmp` caches, and omits the large Gradio/ViTPose server stack. The original local `app.py` continues to provide the detailed Gradio clinician workspace.

This is a friend/team preview, not a completed hackathon submission.

Verified production deployment: `dpl_J9qnTEtxnsR3jLJs5xkXwhxcABEs` (READY). An external browser checked actual MediaPipe inference, a new upload, three repetitions, skeleton replay, report measurements and playable clips. A separate fresh client verified the recipient access link, blocked anonymous media, a 20-repetition seeded session, ranged video playback and an exported ZIP containing all 17 evidence clips. Forty-two Python tests pass. The current deployment’s runtime log scan found no tracebacks.

Program/live update (6 November): production deployment `dpl_6Kn6N7AkUkzm1o2RXNPz3bWsgFmv` adds the Demo program (Squats + Jump, Mon/Tue/Thu/Sat), persisted completion and next due dates, selectors, full-viewport capture, reference-relative per-part colours, and explicit report evidence. Staged Jump guide/patient footage is in the same private dataset. The seeded squat report now contains paired stills and annotated evidence clips. New failed-tracking attempts are retained without scores. No InfiniteRep or exercise-recognition dataset was added. Jump form comparison is withheld until its own compatible therapist reference is fitted. HF paid compute remains paused.

Fresh production verification: Program selection and real Jump guide playback passed. The updated seeded squat report exposes 17 timestamped findings with playable clips and paired stills; anonymous media requests remain blocked. Local 50-test suite, eight colour/visibility assertions, real MediaPipe camera capture/save/reload/review, separate Jump upload/review and mobile/tablet/desktop overflow checks passed.
