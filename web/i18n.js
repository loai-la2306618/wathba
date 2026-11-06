// Arabic / English interface switch. The app renders English; when Arabic is
// selected, visible text and accessible labels are translated in place
// (including content rendered later) and the layout switches to right-to-left.
// Switching back restores the original English exactly.
const KEY = 'wathba-lang';
const AR = {
  'Continue exercises': 'كمّل باقي التمارين',
  'Evaluate pain and effort across all exercises you just completed.': 'قيّم الألم والمجهود لكل التمارين اللي خلصتها في الجلسة.',
  'Answers cover all exercises in this session.': 'الإجابات تخص كل تمارين الجلسة.',
  'Did you feel pain during any exercise in this session?': 'هل شعرت بألم أثناء أي تمرين في الجلسة؟',
  'How much pain do you feel now, after the whole session?': 'ما شدة الألم الآن بعد انتهاء الجلسة كلها؟',
  'How hard was the whole session?': 'ما مدى صعوبة الجلسة كلها؟',
  'Back to Home': 'العودة للرئيسية',
  'Session evaluation': 'تقييم الجلسة',
  'Complete all exercises, then select Finish Session to evaluate the whole session.': 'أكمل كل التمارين، ثم اختر إنهاء الجلسة لتقييمها بالكامل.',
  'Reps at 60%+': 'تكرارات بتطابق 60% فأكثر',
  'Reps at 60%+ played': 'تكرارات معروضة بتطابق 60% فأكثر',
  'Repetition reached 60% reference match and was counted.': 'وصل التكرار إلى تطابق 60% مع المرجع وتم احتسابه.',
  'This repetition was not counted.': 'لم يُحتسب هذا التكرار.',
  'Test sound': 'اختبار الصوت',
  'Counting needs a matching therapist reference. Prepare the reference for the active pose model.': 'العد يحتاج مرجع معالج متوافقًا مع نموذج التتبع الحالي. أعد تجهيز المرجع.',
  'Check your movement': 'راجع حركتك', 'Get ready': 'استعد', 'Reference matched': 'مطابق للمرجع',
  'Sound alerts: on': 'التنبيه الصوتي: مفعّل', 'Sound alerts: muted': 'التنبيه الصوتي: مكتوم',
  'Matched reps': 'التكرارات المطابقة', 'Matched reps played': 'التكرارات المطابقة المعروضة',
  'Matched Reps / Target': 'التكرارات المطابقة / الهدف',
  'Counting paused: keep your whole body and feet visible.': 'العد متوقف: أبقِ جسمك بالكامل وقدميك ظاهرين.',
  'This movement differs from the guide. Check your knee and trunk position.': 'الحركة مختلفة عن المرجع. راجع وضع الركبة والجذع.',
  'This repetition was not counted: match the demonstrated movement range.': 'لم يُحتسب التكرار: اتبع مدى الحركة الموضح في فيديو المعالج.',
  'This repetition was not counted: follow the demonstrated pace.': 'لم يُحتسب التكرار: اتبع توقيت الحركة الموضح في فيديو المعالج.',
  'Hold the standing start position steady to begin counting.': 'اثبت واقفًا في وضع البداية ليبدأ العد.',
  'Repetition matched the reference and was counted.': 'التكرار مطابق للمرجع وتم احتسابه.',
  'Sound alerts are unavailable on this browser. Visual feedback remains active.': 'التنبيه الصوتي غير متاح في هذا المتصفح. الملاحظات المرئية تعمل.',
  'Sound could not start on this browser.': 'تعذر تشغيل الصوت في هذا المتصفح.',
  // Navigation and common
  'Home': 'الرئيسية', 'Programs': 'البرامج', 'Progress': 'التقدّم', 'Profile': 'الملف الشخصي', 'Back': 'رجوع', 'Done': 'تم',
  'Main navigation': 'التنقل الرئيسي', 'Close dialog': 'إغلاق', 'Open profile': 'فتح الملف الشخصي', 'Wathba logo': 'شعار وثبة',
  'Wathba': '', 'Wathba · وثبة': 'وثبة', 'Your recovery, connected.': 'تعافيك، متصل.',
  'AI-Powered': 'العلاج الطبيعي', 'Physiotherapy': 'بالذكاء الاصطناعي',
  'Guided exercises, real-time feedback,': 'تمارين موجّهة، وملاحظات فورية،', 'and progress your therapist can track.': 'وتقدّم يتابعه معالجك.',
  'Get Started': 'ابدأ الآن', 'I’m a Therapist': 'أنا أخصائي علاج طبيعي',
  // Home
  'Continue your recovery': 'تابع رحلة تعافيك', 'ACL Rehabilitation': 'تأهيل الرباط الصليبي الأمامي',
  'Therapist-guided movement practice': 'تمارين حركة بإشراف المعالج', 'Today’s Session': 'جلسة اليوم',
  '1 exercise · your assigned pace': 'تمرين واحد · بالوتيرة المحددة لك', '1 assigned exercise · your own pace': 'تمرين واحد مخصّص · بوتيرتك',
  'Squat': 'القرفصاء', 'Knee Raise': 'رفع الركبة', 'Glute Bridge': 'جسر الألوية', 'Heel Slide': 'انزلاق الكعب',
  'Hamstring Curl': 'ثني أوتار الركبة', 'Step Up': 'الصعود على الدرجة',
  'Explore the exercise library': 'استكشف مكتبة التمارين', 'Your movement. Your therapist. Connected.': 'حركتك. معالجك. متصلان.',
  'Start exercise': 'ابدأ التمرين', 'Start camera session': 'ابدأ جلسة بالكاميرا',
  'Latest reference match, not recovery progress': 'آخر نسبة تطابق مع المرجع، وليست مقياسًا للتعافي',
  'View session history': 'عرض سجل الجلسات', 'No sessions recorded on this day.': 'لا توجد جلسات مسجّلة في هذا اليوم.',
  // Workout
  'Exercise 1 · Squat': 'التمرين 1 · القرفصاء', 'Therapist reference': 'مرجع المعالج', 'Reference': 'المرجع', 'Sec': 'ث',
  'Movement guide': 'دليل الحركة', 'Let’s begin': 'لنبدأ', 'Keep going': 'استمر', 'Review together': 'لنراجع معًا',
  'Watch your therapist, then start your set.': 'شاهد معالجك، ثم ابدأ مجموعتك.',
  'Watch the movement. Get ready at your own pace.': 'شاهد الحركة واستعد بوتيرتك.',
  'Your set starts when you’re ready.': 'تبدأ مجموعتك عندما تكون مستعدًا.', 'You': 'أنت', 'You · Live': 'أنت · مباشر',
  'Your movement, ready to review': 'حركتك جاهزة للمراجعة', 'Your space to move': 'مساحتك للحركة',
  'Start your camera or upload your exercise video.': 'شغّل الكاميرا أو ارفع فيديو تمرينك.',
  'Reps': 'التكرارات', 'Last rep': 'آخر تكرار', 'Tracking': 'التتبّع', 'Reps played': 'التكرارات المعروضة', 'Analysed': 'تم تحليله',
  'I have permission to analyse this recording.': 'لدي إذن بتحليل هذا التسجيل.',
  'Use camera': 'استخدم الكاميرا', 'Upload video': 'ارفع فيديو', 'Use the provided patient video': 'استخدم فيديو المريض المرفق',
  'Start recording': 'ابدأ التسجيل', 'Analyse my video': 'حلّل الفيديو', 'Cancel analysis': 'إلغاء التحليل',
  'Back to results': 'العودة إلى النتائج', 'Follow your physiotherapist’s assigned limits.': 'التزم بالحدود التي حددها أخصائي العلاج الطبيعي.',
  'Finish set': 'إنهاء المجموعة', 'Switch to skeleton view': 'عرض الهيكل فقط', 'Switch to video view': 'عرض الفيديو',
  'Replay position': 'موضع الإعادة', 'Previous repetition': 'التكرار السابق', 'Play or pause replay': 'تشغيل أو إيقاف الإعادة',
  'Next repetition': 'التكرار التالي', 'Pause video': 'إيقاف الفيديو مؤقتًا', 'Play video': 'تشغيل الفيديو',
  'Pause session': 'إيقاف الجلسة مؤقتًا', 'Resume session': 'استئناف الجلسة', 'Session paused': 'الجلسة متوقفة مؤقتًا',
  'Repetition progress': 'تقدّم التكرارات', 'Therapist body landmarks': 'مفاصل جسم المعالج', 'Detected body landmarks': 'مفاصل الجسم المكتشفة',
  'Pause therapist demonstration': 'إيقاف عرض المعالج', 'Play therapist demonstration': 'تشغيل عرض المعالج',
  'Your therapist’s squat demonstration': 'عرض القرفصاء من معالجك', 'Back to exercises': 'العودة إلى التمارين',
  'Preparing demonstration': 'جارٍ تجهيز العرض', 'Camera ready': 'الكاميرا جاهزة', 'Patient video ready': 'فيديو المريض جاهز',
  'Keep your whole body and feet in view.': 'اجعل جسمك وقدميك بالكامل داخل الصورة.',
  'Ready to analyse your uploaded set.': 'جاهز لتحليل المجموعة التي رفعتها.', 'Live body tracking': 'تتبّع الجسم مباشرة',
  'Detected joints · original timing': 'المفاصل المكتشفة · التوقيت الأصلي', 'Analysing your movement': 'جارٍ تحليل حركتك',
  'Your recording': 'تسجيلك', 'Matched repetition phase': 'مرحلة التكرار المطابقة', 'Recording replay': 'إعادة التسجيل',
  'Compare the same stage of the movement.': 'قارن المرحلة نفسها من الحركة.',
  'The therapist replay follows the phase of your repetition.': 'تتبع إعادة المعالج مرحلة تكرارك.',
  'Tracking in this browser': 'التتبّع داخل هذا المتصفح', 'Analysing the uploaded movement…': 'جارٍ تحليل الحركة المرفوعة…',
  'Final repetition count appears after comparison.': 'يظهر العدد النهائي للتكرارات بعد المقارنة.',
  'Live count is provisional until full analysis.': 'العدّ المباشر مبدئي حتى اكتمال التحليل.',
  'Movement in progress. Follow your assigned range.': 'الحركة جارية. التزم بالمدى المحدد لك.',
  'Your last repetition was faster than the demonstration.': 'كان تكرارك الأخير أسرع من العرض.',
  'Counting paused: shoulders, hips and ankles must be clearly visible.': 'توقّف العدّ: يجب أن تظهر الكتفان والوركان والكاحلان بوضوح.',
  'Tracking lost. Move back until your body and feet are visible.': 'فُقد التتبّع. ابتعد حتى يظهر جسمك وقدماك.',
  'Tracking lost. Keep your whole body in view.': 'فُقد التتبّع. اجعل جسمك بالكامل داخل الصورة.',
  'Re-checking which person is being tracked.': 'جارٍ التحقق من الشخص الذي يتم تتبّعه.',
  'Several people of similar size are visible. Only the person being assessed should be in view.': 'يظهر عدة أشخاص بحجم متقارب. يجب أن يظهر الشخص الذي يتم تقييمه فقط.',
  'The selected person left the tracked region': 'خرج الشخص المحدد من منطقة التتبّع', 'No person detected': 'لم يُكتشف أي شخص',
  // Busy / toasts
  'Preparing your session': 'جارٍ تجهيز جلستك', 'Preparing the therapist reference': 'جارٍ تجهيز مرجع المعالج',
  'Preparing therapist reference': 'جارٍ تجهيز مرجع المعالج', 'Tracking the actual therapist recording in this browser.': 'جارٍ تتبّع تسجيل المعالج داخل هذا المتصفح.',
  'Learning movement and timing from the therapist’s recording.': 'جارٍ تعلّم الحركة والتوقيت من تسجيل المعالج.',
  'The reference was prepared with the previous pose engine and is being tracked again.': 'جُهّز المرجع بالمحرك السابق ويُعاد تتبّعه الآن.',
  'Tracking the demonstration in this browser.': 'جارٍ تتبّع العرض داخل هذا المتصفح.', 'Reading the uploaded demonstration.': 'جارٍ قراءة العرض المرفوع.',
  'Preparing your recording': 'جارٍ تجهيز تسجيلك', 'Reading the video and setting up browser tracking.': 'جارٍ قراءة الفيديو وتجهيز التتبّع.',
  'Building your report': 'جارٍ إعداد تقريرك', 'Comparing the patient’s movement with the therapist reference and extracting the actual clips.': 'جارٍ مقارنة حركة المريض بمرجع المعالج واستخراج المقاطع.',
  'Preparing live tracking': 'جارٍ تجهيز التتبّع المباشر', 'The pose models run on this device; video frames are not sent anywhere during tracking.': 'تعمل نماذج تتبّع الجسم على هذا الجهاز، ولا تُرسل إطارات الفيديو أثناء التتبّع.',
  'Saving your set': 'جارٍ حفظ مجموعتك', 'Preparing the recording for your report.': 'جارٍ تجهيز التسجيل لتقريرك.',
  'Checking selected frames with ViTPose': 'جارٍ فحص إطارات مختارة بنموذج ViTPose',
  'Running on the Wathba server with the tracked person boxes. The first run downloads the model.': 'يعمل على خادم وثبة باستخدام مربعات الشخص المتتبَّع. يُنزَّل النموذج في أول مرة.',
  'A therapist demonstration is needed before this session can start.': 'يلزم عرض من المعالج قبل بدء هذه الجلسة.',
  'Confirm permission before opening the camera.': 'أكّد الإذن قبل فتح الكاميرا.',
  'Confirm permission to use the provided patient recording.': 'أكّد الإذن باستخدام تسجيل المريض المرفق.',
  'Confirm permission before analysing a recording.': 'أكّد الإذن قبل تحليل التسجيل.', 'Confirm permission to analyse this recording.': 'أكّد الإذن بتحليل هذا التسجيل.',
  'Confirm permission before selecting your recording.': 'أكّد الإذن قبل اختيار تسجيلك.',
  'Confirm permission to use the therapist demonstration.': 'أكّد الإذن باستخدام عرض المعالج.', 'Choose a therapist demonstration first.': 'اختر عرض المعالج أولًا.',
  'Confirm that this recording may be re-analysed on the Wathba server.': 'أكّد السماح بإعادة تحليل هذا التسجيل على خادم وثبة.',
  'Camera permission was denied. Allow it in your browser or upload a video.': 'رُفض إذن الكاميرا. اسمح به في المتصفح أو ارفع فيديو.',
  'Analysis cancelled. You can start again.': 'أُلغي التحليل. يمكنك البدء من جديد.', 'Physiotherapist feedback refreshed.': 'تم تحديث ملاحظات أخصائي العلاج الطبيعي.',
  'Feedback saved to the patient report.': 'حُفظت الملاحظات في تقرير المريض.', 'Profile saved on this device.': 'حُفظ الملف الشخصي على هذا الجهاز.',
  'Enter your name.': 'أدخل اسمك.', 'Program saved. Future sessions use this repetition target.': 'حُفظ البرنامج. ستستخدم الجلسات القادمة هذا العدد من التكرارات.',
  'Session link copied. Available on this running Wathba server.': 'نُسخ رابط الجلسة. متاح على خادم وثبة الحالي.',
  'This video could not be played. Try an MP4 recording.': 'تعذّر تشغيل هذا الفيديو. جرّب تسجيلًا بصيغة MP4.',
  'Video seeking timed out. Try a shorter MP4.': 'انتهت مهلة التنقل في الفيديو. جرّب مقطع MP4 أقصر.',
  'Use a video between one second and three minutes.': 'استخدم فيديو مدته بين ثانية وثلاث دقائق.',
  'Body tracking stopped working on this device. Reload the page and try again.': 'توقف تتبّع الجسم على هذا الجهاز. أعد تحميل الصفحة وحاول مجددًا.',
  'The recording could not be processed. Please try again.': 'تعذّرت معالجة التسجيل. حاول مرة أخرى.',
  'Prepare the therapist reference before analysing the patient.': 'جهّز مرجع المعالج قبل تحليل المريض.',
  // Results
  'Exercise Complete': 'اكتمل التمرين', 'Reference match': 'التطابق مع المرجع', 'Reference Match': 'التطابق مع المرجع', 'Great effort!': 'مجهود رائع!',
  'About this comparison': 'عن هذه المقارنة', 'About the reference score': 'عن درجة المرجع',
  'Experimental movement similarity, not clinical accuracy, safety or recovery.': 'تشابه تجريبي في الحركة، وليس دقة سريرية أو سلامة أو تعافيًا.',
  'Movement': 'الحركة', 'Reviewing the movement pattern': 'مراجعة نمط الحركة', 'Measured landmark visibility': 'وضوح المفاصل المقاس',
  'Control': 'التحكم', 'Measured repetition timing': 'توقيت التكرار المقاس', 'Session Summary': 'ملخص الجلسة',
  'Replay with skeleton': 'إعادة مع الهيكل', 'View movement details': 'عرض تفاصيل الحركة', 'Duration': 'المدة',
  'Observed repetitions': 'التكرارات الملاحظة', 'Tracking coverage': 'نسبة التتبّع', 'Within reference thresholds': 'ضمن حدود المرجع',
  'Detailed breakdown': 'التفاصيل', 'Reference match by repetition': 'التطابق مع المرجع لكل تكرار', 'View full report': 'عرض التقرير الكامل',
  'Download report & clips': 'تنزيل التقرير والمقاطع', 'No differences exceeded comparison thresholds': 'لم تتجاوز أي فروق حدود المقارنة',
  'No complete repetition timing available': 'لا يتوفر توقيت لتكرار كامل', 'No complete repetitions were visible.': 'لم يظهر أي تكرار كامل.',
  'A different pace': 'وتيرة مختلفة', 'A smaller movement range': 'مدى حركة أصغر', 'A movement pattern to review': 'نمط حركة للمراجعة',
  'Part of the recording was unclear': 'جزء من التسجيل غير واضح', 'The movement could not be fully assessed': 'تعذّر تقييم الحركة بالكامل',
  'A moment to review': 'لحظة للمراجعة', 'Your recording is ready': 'تسجيلك جاهز',
  'No comparison differences exceeded the current thresholds. This does not establish clinical correctness.': 'لم تتجاوز فروق المقارنة الحدود الحالية. هذا لا يثبت الصحة السريرية.',
  'From your physiotherapist': 'من أخصائي العلاج الطبيعي',
  // Summary
  'Exercise': 'التمرين', 'Total Reps': 'إجمالي التكرارات', 'Exercise Breakdown': 'تفاصيل التمرين', 'Movement observations': 'ملاحظات الحركة',
  'Trackable samples': 'العينات القابلة للتتبّع', 'Your physiotherapist can review the measured differences and original clips.': 'يمكن لأخصائي العلاج الطبيعي مراجعة الفروق المقاسة والمقاطع الأصلية.',
  'View Report': 'عرض التقرير', 'Finish Session': 'إنهاء الجلسة', 'Share session report': 'مشاركة تقرير الجلسة',
  // Report
  'Session report': 'تقرير الجلسة', 'Open printable report': 'فتح التقرير للطباعة', 'Refresh physiotherapist feedback': 'تحديث ملاحظات أخصائي العلاج الطبيعي',
  'Squat · left leg': 'القرفصاء · الساق اليسرى', 'Moments to review': 'لحظات للمراجعة', 'No moments were flagged.': 'لا توجد لحظات للمراجعة.',
  'Physiotherapist feedback': 'ملاحظات أخصائي العلاج الطبيعي', 'Awaiting physiotherapist review.': 'بانتظار مراجعة أخصائي العلاج الطبيعي.',
  'Technical details': 'التفاصيل الفنية', 'Annotated recording': 'التسجيل مع التتبّع', 'Repetitions': 'التكرارات', 'Pain after': 'الألم بعد التمرين',
  'Movement analysis': 'تحليل الحركة', 'Median repetition': 'متوسط التكرار', 'Timing variation': 'تباين التوقيت', 'Excursion variation': 'تباين المدى',
  'Inspect a repetition': 'افحص تكرارًا', 'Your movement': 'حركتك', 'Therapist reference curve': 'منحنى مرجع المعالج',
  'Each complete repetition is compared with your therapist’s movement. Timing is measured separately from movement shape.': 'تُقارن كل حركة كاملة بحركة معالجك. يُقاس التوقيت بشكل منفصل عن شكل الحركة.',
  'No complete repetitions were assessable.': 'لم يكن أي تكرار كامل قابلًا للتقييم.', 'Repetition detail': 'تفاصيل التكرارات',
  'Rep': 'التكرار', 'Interval': 'الفترة', 'Excursion*': 'المدى*', 'Match': 'التطابق', 'How to interpret this': 'كيف تفهم هذه النتائج',
  'No comparison score was available.': 'لا تتوفر درجة مقارنة.', 'Pose models': 'نماذج تتبّع الجسم', 'Not measured with these models:': 'لا تقيسها هذه النماذج:',
  'ViTPose frame check': 'فحص الإطارات بنموذج ViTPose', 'Run ViTPose check': 'تشغيل فحص ViTPose', 'Run the ViTPose check again': 'إعادة فحص ViTPose',
  'Re-analyse selected frames of this already uploaded recording on the Wathba server. No third-party service is used.': 'أعد تحليل إطارات مختارة من هذا التسجيل المرفوع على خادم وثبة. لا تُستخدم أي خدمة خارجية.',
  'Measurement': 'القياس', 'Frames': 'الإطارات', 'Median |difference|': 'متوسط الفرق', 'Per-frame values (browser / ViTPose)': 'قيم كل إطار (المتصفح / ViTPose)',
  'Rep · phase': 'التكرار · المرحلة', 'Time': 'الوقت', 'Knee offset': 'انحراف الركبة', 'Trunk lean': 'ميل الجذع', 'Start': 'البداية', 'Return': 'العودة',
  'Left knee angle (2D, deg)': 'زاوية الركبة اليسرى (ثنائية الأبعاد، درجة)', 'Left hip angle (2D, deg)': 'زاوية الورك الأيسر (ثنائية الأبعاد، درجة)',
  'Trunk lean (2D, deg)': 'ميل الجذع (ثنائي الأبعاد، درجة)', 'Left knee offset (leg lengths)': 'انحراف الركبة اليسرى (بطول الساق)',
  'Hip height (torso lengths, per frame)': 'ارتفاع الورك (بطول الجذع، لكل إطار)',
  'Hip height relative to torso length': 'ارتفاع الورك نسبةً إلى طول الجذع', 'Projected knee offset from hip–ankle line': 'انحراف الركبة الظاهر عن خط الورك والكاحل',
  'Trunk inclination in the camera view': 'ميل الجذع في زاوية التصوير', 'Too few reliable observations in this repetition.': 'عدد الملاحظات الموثوقة في هذا التكرار قليل جدًا.',
  'Landmark depth / distance from camera': 'عمق المفاصل / البعد عن الكاميرا', 'Metric 3D world coordinates': 'إحداثيات ثلاثية الأبعاد',
  '3D knee flexion angle': 'زاوية ثني الركبة ثلاثية الأبعاد', 'Heel lift / toe contact': 'رفع الكعب / ملامسة الأصابع',
  'Foot progression angle': 'زاوية اتجاه القدم', 'Hand and finger position': 'وضع اليد والأصابع',
  'The COCO-17 models return 2D image coordinates only. No depth is estimated.': 'تعطي هذه النماذج إحداثيات ثنائية الأبعاد فقط، دون تقدير للعمق.',
  'None of the three models estimate 3D world coordinates.': 'لا يقدّر أي من النماذج الثلاثة إحداثيات ثلاثية الأبعاد.',
  'A true flexion angle needs 3D joint positions. Only 2D image-plane angles are available, and they change with camera position.': 'تحتاج زاوية الثني الحقيقية إلى مواضع مفاصل ثلاثية الأبعاد. المتاح زوايا ثنائية الأبعاد فقط وتتغير بتغير موضع الكاميرا.',
  'COCO-17 has ankles but no heel or toe landmarks, so foot contact cannot be assessed.': 'تتضمن النماذج الكاحلين دون الكعب أو الأصابع، لذا لا يمكن تقييم ملامسة القدم.',
  'Needs heel and toe landmarks, which these models do not provide.': 'تحتاج إلى نقاط الكعب والأصابع، ولا توفرها هذه النماذج.',
  'COCO-17 ends at the wrists.': 'تنتهي نقاط النماذج عند الرسغين.',
  // Backend findings and limitations
  'Movement was not visible reliably': 'لم تكن الحركة واضحة بشكل موثوق', 'Recording samples were interrupted': 'انقطعت عينات التسجيل',
  'Movement visibility was lost': 'فُقد وضوح الحركة', 'Movement could not be assessed': 'تعذّر تقييم الحركة',
  'The reference movement could not be assessed': 'تعذّر تقييم الحركة مقارنةً بالمرجع',
  'The required landmarks were uncertain. No movement correction is inferred across this interval.': 'كانت المفاصل المطلوبة غير مؤكدة. لا يُستنتج أي تصحيح للحركة خلال هذه الفترة.',
  'Keep the selected person and required joints in view, then record again.': 'أبقِ الشخص المحدد والمفاصل المطلوبة داخل الصورة، ثم سجّل مجددًا.',
  'No continuous movement was observed in this interval.': 'لم تُرصد حركة متصلة في هذه الفترة.', 'Review the recording quality.': 'راجع جودة التسجيل.',
  'Recording ended with uncertain landmarks.': 'انتهى التسجيل والمفاصل غير مؤكدة.', 'Keep the required joints visible.': 'أبقِ المفاصل المطلوبة ظاهرة.',
  'Required body joints were not reliably detected. No form judgment was made.': 'لم تُكتشف مفاصل الجسم المطلوبة بشكل موثوق. لم يُصدر أي حكم على أداء التمرين.',
  'Keep your entire body and feet visible, use a fixed camera, and record again.': 'أبقِ جسمك وقدميك ظاهرين بالكامل، واستخدم كاميرا ثابتة، ثم سجّل مجددًا.',
  'Compare this clip with your assigned reference and ask your physiotherapist about the difference.': 'قارن هذا المقطع بالمرجع المحدد لك واسأل أخصائي العلاج الطبيعي عن الفرق.',
  'No complete movement cycle was visible for the selected reference. This recording cannot establish whether the exercise matched the assigned movement.': 'لم تظهر دورة حركة كاملة للمرجع المختار، ولا يمكن لهذا التسجيل تحديد ما إذا كان التمرين مطابقًا للحركة المحددة.',
  'Check the selected exercise, leg, camera view, and whether the video includes complete repetitions.': 'تحقق من التمرين والساق وزاوية الكاميرا، ومن أن الفيديو يتضمن تكرارات كاملة.',
  '2D image-plane measurements are approximate and depend on camera placement; no depth is estimated.': 'القياسات ثنائية الأبعاد تقريبية وتعتمد على موضع الكاميرا، ولا يُقدّر العمق.',
  'A difference from a reference is not, by itself, proof of incorrect or unsafe exercise.': 'الاختلاف عن المرجع لا يعني بحد ذاته أن التمرين خاطئ أو غير آمن.',
  'No reference was selected; exercise correctness and corrective movement cues were not inferred.': 'لم يُختر مرجع، لذا لم يُستنتج صواب التمرين أو إرشادات تصحيحه.',
  'No complete repetitions were visible; partial movements were not counted.': 'لم تظهر تكرارات كاملة، ولم تُحتسب الحركات الجزئية.',
  'No reliable movement measurements. No corrective form feedback or score was inferred.': 'لا توجد قياسات حركة موثوقة، ولم تُستنتج ملاحظات أو درجة.',
  'Prototype similarity to the selected demonstration, not exercise safety, rehabilitation progress or a diagnosis.': 'تشابه تجريبي مع العرض المختار، وليس مقياسًا لسلامة التمرين أو تقدّم التأهيل أو تشخيصًا.',
  'A reference, complete repetitions and clear tracking are needed.': 'تلزم مرجعية وتكرارات كاملة وتتبّع واضح.',
  'Insufficient reliable tracking; recording saved for clinician review.': 'التتبّع الموثوق غير كافٍ؛ حُفظ التسجيل لمراجعة المختص.',
  'Reference comparison with separate timing and aligned movement features.': 'مقارنة بالمرجع مع توقيت منفصل وخصائص حركة متطابقة.',
  'A compatible reference and at least 70% trackable samples are needed for feature comparison.': 'تلزم مرجعية متوافقة ونسبة تتبّع لا تقل عن 70% لمقارنة الخصائص.',
  'Variation is the coefficient of variation across complete observed repetitions. Feature differences are 2D estimates after temporal alignment, not clinical severity. Pelvic excursion is not knee flexion range. The camera does not measure weight distribution, ligament healing, pain, or exercise safety.': 'التباين هو معامل الاختلاف بين التكرارات الكاملة. فروق الخصائص تقديرات ثنائية الأبعاد بعد المواءمة الزمنية، وليست شدة سريرية. مدى حركة الحوض ليس مدى ثني الركبة. لا تقيس الكاميرا توزيع الوزن أو التئام الأربطة أو الألم أو سلامة التمرين.',
  // Check-in questions
  'How did you feel?': 'كيف شعرت؟', 'Answer a few quick questions for your physiotherapist.': 'أجب عن بعض الأسئلة السريعة لأخصائي العلاج الطبيعي.',
  'Did you feel pain during the exercise?': 'هل شعرت بألم أثناء التمرين؟', 'How much pain do you feel now, after the exercise?': 'ما مقدار الألم الذي تشعر به الآن بعد التمرين؟',
  '0 = no pain · 10 = worst pain': '0 = لا ألم · 10 = أشد ألم', 'Where did you feel it?': 'أين شعرت بالألم؟',
  'How hard was the exercise?': 'ما مدى صعوبة التمرين؟', 'Did your knee feel unstable or give way?': 'هل شعرت بعدم ثبات في الركبة أو أنها تخونك؟',
  'Do you notice new swelling?': 'هل تلاحظ تورّمًا جديدًا؟', 'Anything else for your physiotherapist? (optional)': 'هل هناك شيء آخر لأخصائي العلاج الطبيعي؟ (اختياري)',
  'Yes': 'نعم', 'No': 'لا', 'Knee': 'الركبة', 'Hip': 'الورك', 'Lower back': 'أسفل الظهر', 'Ankle': 'الكاحل', 'Other': 'مكان آخر',
  'Easy': 'سهل', 'Moderate': 'متوسط', 'Hard': 'صعب', 'Save answers': 'حفظ الإجابات', 'Edit answers': 'تعديل الإجابات',
  'Answers saved. Your physiotherapist will see them in your report.': 'حُفظت الإجابات. سيراها أخصائي العلاج الطبيعي في تقريرك.',
  'Not answered': 'لم تتم الإجابة', 'Not specified': 'غير محدد', 'None': 'لا يوجد', 'Pain during': 'ألم أثناء التمرين',
  'Pain after (0–10)': 'الألم بعد التمرين (0–10)', 'Where': 'المكان', 'Difficulty': 'الصعوبة', 'Knee unstable': 'عدم ثبات الركبة',
  'New swelling': 'تورّم جديد', 'Notes': 'ملاحظات', 'You have not answered the questions yet.': 'لم تُجب عن الأسئلة بعد.',
  'Your answers mention pain, instability or swelling. Stop if it gets worse and contact your physiotherapist before your next session. This is not a diagnosis.': 'تشير إجاباتك إلى ألم أو عدم ثبات أو تورّم. توقّف إذا ازداد الأمر سوءًا وتواصل مع أخصائي العلاج الطبيعي قبل جلستك القادمة. هذا ليس تشخيصًا.',
  'Needs attention': 'يحتاج إلى متابعة', 'Answer the questions': 'أجب عن الأسئلة',
  // Portal / library / progress / profile
  'Therapist Portal': 'بوابة المعالج', 'ACL Rehabilitation · Left side': 'تأهيل الرباط الصليبي · الجانب الأيسر', 'Review ready': 'جاهز للمراجعة',
  'Overview': 'نظرة عامة', 'Sessions': 'الجلسات', 'Exercises': 'التمارين', 'Adjust Program': 'تعديل البرنامج',
  'Open detailed clinician workspace': 'فتح مساحة عمل المختص', 'Latest Session': 'آخر جلسة', 'To Review': 'للمراجعة',
  'Progress (Reference Match)': 'التقدّم (التطابق مع المرجع)', 'View session report': 'عرض تقرير الجلسة', 'Assigned movement': 'الحركة المحددة',
  'Squat · Left side · Front camera view': 'القرفصاء · الجانب الأيسر · كاميرا أمامية', 'Target repetitions': 'عدد التكرارات المستهدف',
  'Set therapist reference': 'تعيين مرجع المعالج', 'Set therapist demonstration': 'تعيين عرض المعالج', 'Feedback for the patient': 'ملاحظات للمريض',
  'Save Feedback': 'حفظ الملاحظات', 'Saved feedback appears in this session’s patient report.': 'تظهر الملاحظات المحفوظة في تقرير المريض لهذه الجلسة.',
  'A recorded session is needed before feedback can be saved.': 'يلزم وجود جلسة مسجّلة قبل حفظ الملاحظات.', 'No sessions recorded yet.': 'لا توجد جلسات مسجّلة بعد.',
  'Therapist workspace': 'مساحة عمل المعالج', 'Open detailed review workspace': 'فتح مساحة المراجعة التفصيلية', 'Save Program': 'حفظ البرنامج',
  'Assigned squat · left side · front camera view. Change the target for future sessions.': 'قرفصاء محددة · الجانب الأيسر · كاميرا أمامية. غيّر الهدف للجلسات القادمة.',
  'This hackathon prototype uses a shared demonstration workspace. Patient footage, feedback and reports are available to the team using this running app.': 'يستخدم هذا النموذج الأولي مساحة عرض مشتركة. التسجيلات والملاحظات والتقارير متاحة للفريق الذي يستخدم هذا التطبيق.',
  'Portal options': 'خيارات البوابة', 'Patient record': 'سجل المريض',
  'Exercise Library': 'مكتبة التمارين', 'Search exercises': 'ابحث في التمارين', 'Search exercises…': 'ابحث في التمارين…', 'Search exercise library': 'ابحث في مكتبة التمارين',
  'ACL': 'الرباط الصليبي', 'Strength': 'القوة', 'Mobility': 'المرونة', 'Exercise category': 'فئة التمرين',
  'Exercise illustrations. Follow your therapist’s prescription.': 'رسوم توضيحية للتمارين. اتبع وصفة معالجك.',
  'Squat movement assessment is available in this prototype.': 'تقييم حركة القرفصاء متاح في هذا النموذج الأولي.', 'No exercises match your search.': 'لا توجد تمارين مطابقة لبحثك.',
  'Beginner': 'مبتدئ', 'Intermediate': 'متوسط', 'Assigned': 'محدد لك', 'Start assigned exercise': 'ابدأ التمرين المحدد', 'Back to library': 'العودة إلى المكتبة',
  'Your actual therapist video is used during assessment.': 'يُستخدم فيديو معالجك الفعلي أثناء التقييم.',
  'Library illustration only. This movement is not currently assigned or automatically assessed.': 'رسم توضيحي فقط. هذه الحركة غير محددة لك حاليًا ولا تُقيَّم تلقائيًا.',
  'Use your own therapist’s demonstration. Keep the camera in front, with your entire body and feet visible.': 'استخدم عرض معالجك. ضع الكاميرا أمامك واجعل جسمك وقدميك ظاهرين بالكامل.',
  'A standing movement reference. Your therapist chooses the height, support and repetitions appropriate for your plan.': 'حركة مرجعية من الوقوف. يحدد معالجك الارتفاع والدعم والتكرارات المناسبة لخطتك.',
  'A floor exercise illustration. Your therapist determines whether it belongs in your rehabilitation plan.': 'رسم توضيحي لتمرين أرضي. يحدد معالجك إن كان جزءًا من خطة تأهيلك.',
  'A floor movement illustration. Follow your therapist’s prescribed range and progression.': 'رسم توضيحي لحركة أرضية. التزم بالمدى والتدرّج الذي يصفه معالجك.',
  'A standing exercise illustration. Support, resistance and range must come from your therapist.': 'رسم توضيحي لتمرين من الوقوف. يحدد معالجك الدعم والمقاومة والمدى.',
  'A step exercise illustration. Your therapist sets the step height, support and repetition target.': 'رسم توضيحي لتمرين الدرجة. يحدد معالجك ارتفاع الدرجة والدعم وعدد التكرارات.',
  'Your Progress': 'تقدّمك', 'Week': 'أسبوع', 'Month': 'شهر', 'All': 'الكل', 'History period': 'فترة السجل', 'Your recorded sessions': 'جلساتك المسجّلة',
  'recorded': 'مسجّلة', 'observed': 'ملاحظة', 'latest session': 'آخر جلسة', 'Latest measured reference match': 'آخر تطابق مقاس مع المرجع',
  'change across recorded sessions': 'التغيّر عبر الجلسات المسجّلة', 'Your rehabilitation': 'تأهيلك', 'Plan': 'الخطة', 'Practice': 'التمرين', 'Review': 'المراجعة',
  'Next steps': 'الخطوات التالية', 'Current: therapist-guided practice': 'الحالي: تمرين بإشراف المعالج',
  'Your clinician sets the recovery stage and progression.': 'يحدد المختص مرحلة التعافي والتدرّج.',
  'Complete a session to see your measured reference matches here.': 'أكمل جلسة لترى هنا نسب التطابق المقاسة.',
  'Recorded reference match scores, not recovery progress': 'درجات التطابق المسجّلة، وليست مقياسًا للتعافي',
  'Your Profile': 'ملفك الشخصي', 'Wathba · Home rehabilitation': 'وثبة · التأهيل المنزلي', 'Your name': 'اسمك', 'Save profile': 'حفظ الملف',
  'Welcome screen': 'شاشة الترحيب', 'Shared hackathon workspace · use demonstration recordings.': 'مساحة عمل مشتركة · استخدم تسجيلات العرض.',
  'Language': 'اللغة', 'AI coach': 'المساعد الذكي',
  'Written by a Qwen3 model running on the Wathba server, using only your measured results and answers. Every reply is checked automatically. Not medical advice.': 'يكتبه نموذج Qwen3 يعمل على خادم وثبة، باستخدام نتائجك المقاسة وإجاباتك فقط. تُفحص كل إجابة تلقائيًا. ليس نصيحة طبية.',
  'Allow the Qwen3 model on the Wathba server to process this session. Nothing is sent to other services.': 'أسمح لنموذج Qwen3 على خادم وثبة بمعالجة هذه الجلسة. لا يُرسل أي شيء إلى خدمات أخرى.',
  'Write my summary': 'اكتب ملخّصي', 'Write the summary again': 'أعد كتابة الملخّص', 'Ask about this session': 'اسأل عن هذه الجلسة',
  'For example: how many repetitions did I do?': 'مثلًا: كم تكرارًا أدّيت؟', 'Your question': 'سؤالك', 'Ask': 'اسأل', 'Thinking…': 'جارٍ التفكير…',
  'Type a question first.': 'اكتب سؤالًا أولًا.', 'The AI coach is not available on this server.': 'المساعد الذكي غير متاح على هذا الخادم.',
  "The model's summary did not pass the automatic checks, so it is not shown.": 'لم يجتز ملخّص النموذج الفحوصات التلقائية، لذا لا يُعرض.',
  'Confirm that this session may be processed by the Qwen3 model on the Wathba server.': 'أكّد السماح لنموذج Qwen3 على خادم وثبة بمعالجة هذه الجلسة.',
  'Writing your summary': 'جارٍ كتابة ملخّصك', 'The Qwen3 model is reading your session on the Wathba server. The first run loads the model.': 'يقرأ نموذج Qwen3 جلستك على خادم وثبة. يُحمَّل النموذج في المرة الأولى.',
  'Vision model review': 'مراجعة نموذج الرؤية', 'Describe the frames': 'صِف الإطارات', 'Describing the frames': 'جارٍ وصف الإطارات',
  'Experimental: a Qwen3-VL model describes the start and bottom of your first repetitions. It does not change your score.': 'تجريبي: يصف نموذج Qwen3-VL بداية وأسفل أول تكراراتك. لا يغيّر ذلك درجتك.',
  'The Qwen3-VL model is looking at your repetitions on the Wathba server. The first run loads the model.': 'ينظر نموذج Qwen3-VL إلى تكراراتك على خادم وثبة. يُحمَّل النموذج في المرة الأولى.',
  'The description did not pass the automatic checks, so it is not shown.': 'لم يجتز الوصف الفحوصات التلقائية، لذا لا يُعرض.', 'Training consistency': 'الانتظام في التدريب', 'All time': 'منذ البداية', 'Dismiss notification': 'إغلاق الإشعار', 'Training day': 'يوم تدريب', 'Training days': 'أيام التدريب', 'Training week': 'أسبوع تدريب',
  'Training weeks': 'أسابيع التدريب', 'Training month': 'شهر تدريب', 'Training months': 'أشهر التدريب',
  'Complete your first session to start counting.': 'أكمل جلستك الأولى ليبدأ العدّ.', 'Review the movement and add your feedback…': 'راجع الحركة وأضف ملاحظاتك…', 'To movement peak': 'حتى ذروة الحركة', 'Mean aligned difference:': 'متوسط الفرق بعد المواءمة:',
  '. Outside the comparison tolerance in': '. خارج هامش المقارنة في', 'of aligned observations.': 'من الملاحظات المتطابقة.',
  '*Frontal pelvic movement relative to torso length, measured in the 2D image plane; not calibrated clinical knee range.': '*حركة الحوض من الأمام نسبةً إلى طول الجذع، مقاسة في مستوى الصورة ثنائي الأبعاد؛ وليست مدى ثني الركبة السريري.',
  // Reference setup
  'Therapist demonstration': 'عرض المعالج', 'Prepare reference': 'تجهيز المرجع', 'Back to patient session': 'العودة إلى جلسة المريض',
  'Squat · left leg · front camera view. Upload a separate therapist-designated demonstration with at least two complete repetitions.': 'القرفصاء · الساق اليسرى · كاميرا أمامية. ارفع عرضًا منفصلًا يحدده المعالج يتضمن تكرارين كاملين على الأقل.',
  'I have permission to use this recording as the therapist reference.': 'لدي إذن باستخدام هذا التسجيل كمرجع للمعالج.',
};
const ltr = text => `⁦${text}⁩`;
const PARTS = {'Timing': 'التوقيت', 'Legs / pelvis': 'الساقان / الحوض', 'Trunk': 'الجذع', 'Left knee': 'الركبة اليسرى'};
const UNITS = {'torso lengths': 'من طول الجذع', 'leg lengths': 'من طول الساق', 'deg': 'درجة', 's': 'ث'};
const PATTERNS = [
  [/^Good (morning|afternoon|evening), (.+)$/, m => `${{morning: 'صباح الخير', afternoon: 'مساء الخير', evening: 'مساء الخير'}[m[1]]}، ${m[2]}`],
  [/^(\d+) reps?$/, m => `${m[1]} ${+m[1] === 1 ? 'تكرار' : 'تكرارات'}`],
  [/^(\d+) sec$/, m => `${m[1]} ث`], [/^([\d.]+) min$/, m => `${m[1]} د`],
  [/^1 set × (\d+) reps$/, m => `مجموعة واحدة × ${m[1]} تكرارات`],
  [/^Repetition (\d+) recorded\.$/, m => `سُجّل التكرار ${m[1]}.`],
  [/^Repetition (\d+)$/, m => `التكرار ${m[1]}`],
  [/^Repetition (\d+) · ([\d.]+)–([\d.]+)s$/, m => `التكرار ${m[1]} · ${ltr(`${m[2]}–${m[3]}`)} ث`],
  [/^Replay repetition (\d+)$/, m => `إعادة التكرار ${m[1]}`],
  [/^Previous set (\d+) · (\d+) reps · (.+)% reference match$/, m => `المجموعة السابقة ${m[1]} · ${m[2]} تكرارات · تطابق ${m[3]}%`],
  [/^(\d+) of (\d+) repetitions need review$/, m => `${m[1]} من ${m[2]} تكرارات تحتاج إلى مراجعة`],
  [/^(\d+)% of samples were trackable$/, m => `${m[1]}% من العينات قابلة للتتبّع`],
  [/^Median repetition ([\d.]+) sec$/, m => `متوسط التكرار ${m[1]} ث`],
  [/^Observed ([\d.]+)s · therapist reference ([\d.]+)s\. Live timing is provisional\.$/, m => `المرصود ${m[1]} ث · مرجع المعالج ${m[2]} ث. التوقيت المباشر مبدئي.`],
  [/^(\d+) moments to review\.$/, m => `${m[1]} لحظات للمراجعة.`],
  [/^Repetition (\d+): (.+)$/, m => `التكرار ${m[1]}: ${m[2].split(', ').map(p => PARTS[p] || p).join('، ')}`],
  [/^This repetition was (faster|slower) than the selected reference: ([\d.]+)s versus ([\d.]+)s \(tolerance ±([\d.]+)s\)\.$/,
    m => `كان هذا التكرار ${m[1] === 'faster' ? 'أسرع' : 'أبطأ'} من المرجع المختار: ${m[2]} ث مقابل ${m[3]} ث (هامش ±${m[4]} ث).`],
  [/^This repetition had a (smaller|larger) observed movement excursion than the selected reference: ([\d.]+) versus ([\d.]+) (.+?) \(tolerance ±([\d.]+)\)\.$/,
    m => `كان مدى الحركة في هذا التكرار ${m[1] === 'smaller' ? 'أصغر' : 'أكبر'} من المرجع المختار: ${m[2]} مقابل ${m[3]} ${UNITS[m[4]] || m[4]} (هامش ±${m[5]}).`],
  [/^(.+) differs from the selected reference across (\d+)% of aligned observations\.$/, m => `${tr(m[1])} يختلف عن المرجع المختار في ${m[2]}% من الملاحظات المتطابقة.`],
  [/^([\d.]+)–([\d.]+)s · (.+)$/, m => `${ltr(`${m[1]}–${m[2]}`)} ث · ${tr(m[3])}`],
  [/^([\d.]+)–([\d.]+)s$/, m => `${ltr(`${m[1]}–${m[2]}`)} ث`],
  [/^([\d.]+)s$/, m => `${m[1]} ث`],
  [/^([+-]?\d+) pts$/, m => `${m[1]} نقطة`],
  [/^(.+) · ([\d.]+) min$/, m => `${m[1]} · ${m[2]} د`],
  [/^(.+) · Squat$/, m => `${m[1]} · القرفصاء`],
  [/^(Control|Strength|Mobility) · (Beginner|Intermediate|Assigned)$/, m => `${{Control: 'تحكم', Strength: 'قوة', Mobility: 'مرونة'}[m[1]]} · ${AR[m[2]]}`],
  [/^(.+) keypoints \+ (.+) person selection · browser ONNX Runtime$/, m => `نقاط الجسم: ${m[1]} · تحديد الشخص: ${m[2]} · داخل المتصفح`],
  [/^(.+) keypoints · (.+) person selection( · degraded)?$/, m => `نقاط الجسم: ${m[1]} · تحديد الشخص: ${m[2]}${m[3] ? ' · وضع محدود' : ''}`],
  [/^(.+) keypoints( · degraded)?$/, m => `نقاط الجسم: ${m[1]}${m[2] ? ' · وضع محدود' : ''}`],
  [/^(.+?)\. Joints are 2D image-plane estimates \(17 COCO keypoints\); angles change with camera position\.$/, m => `${tr(m[1])}. المفاصل تقديرات ثنائية الأبعاد (17 نقطة)، وتتغير الزوايا بتغير موضع الكاميرا.`],
  [/^Your (trunk|left knee) differs from the demonstrated position\. (.+)$/, m => `${m[1] === 'trunk' ? 'جذعك' : 'ركبتك اليسرى'} مختلفة عن الوضع المعروض. ${tr(m[2])}`],
  [/^This demo supports videos up to (\d+) MB\. Use a short clip or the provided patient video\.$/, m => `يدعم هذا العرض فيديوهات حتى ${m[1]} ميغابايت. استخدم مقطعًا قصيرًا أو فيديو المريض المرفق.`],
  [/^Pain (\d+)\/10$/, m => `الألم ${m[1]}/10`],
  [/^Vertical scale: (\S+) to (\S+) (.+)\. Horizontal axis: repetition progress\.$/, m => `المحور الرأسي: من ${m[1]} إلى ${m[2]} ${UNITS[m[3]] || m[3]}. المحور الأفقي: تقدّم التكرار.`],
  [/^([-\d.]+) (torso lengths|leg lengths|deg)$/, m => `${m[1]} ${UNITS[m[2]]}`],
  [/^(\d+) recorded sessions? available for review\.$/, m => `${m[1]} جلسات مسجّلة متاحة للمراجعة.`],
  [/^(\d+) sessions? recorded since (.+)$/, m => `الجلسات المسجّلة: ${m[1]} · منذ ${m[2]}`],
  [/^Squat session · (\d+) reps$/, m => `جلسة قرفصاء · ${m[1]} تكرارات`],
];

let lang = 'en';
try { lang = localStorage.getItem(KEY) === 'ar' ? 'ar' : 'en'; } catch { /* storage blocked */ }
export const currentLang = () => lang;
const norm = s => s.replace(/\s+/g, ' ').trim();

/** Translate one English string for the current language (unknown text is returned unchanged). */
export function tr(text) {
  if (lang !== 'ar' || text == null) return text;
  const key = norm(String(text));
  if (!key) return text;
  if (Object.hasOwn(AR, key)) return AR[key];
  for (const [re, fn] of PATTERNS) { const m = key.match(re); if (m) return fn(m); }
  const lead = key.match(/^([:·–-]\s*)(.+)$/);
  if (lead) { const rest = tr(lead[2]); if (rest !== lead[2]) return lead[1] + rest; }
  // Longer messages join several sentences: translate each one that is known.
  const sentences = key.split(/(?<=[.!?])\s+(?=[A-Z0-9])/);
  if (sentences.length > 1) {
    const parts = sentences.map(s => tr(s));
    if (parts.some((p, i) => p !== sentences[i])) return parts.join(' ');
  }
  return text;
}

const ATTRS = ['aria-label', 'placeholder', 'title', 'alt'];
const textState = new WeakMap(), attrState = new WeakMap();
const skip = node => node.parentElement?.closest('script,style,textarea,[data-no-i18n]');

function translateTextNode(node) {
  if (skip(node)) return;
  const current = node.nodeValue, state = textState.get(node);
  const english = state && current === state.shown ? state.en : current;
  if (!/[A-Za-z]/.test(english)) return;
  let shown = english;
  if (lang === 'ar') {
    const key = norm(english), out = tr(key);
    if (out !== key) shown = english.replace(key, out);
  }
  textState.set(node, {en: english, shown});
  if (node.nodeValue !== shown) node.nodeValue = shown;
}

function translateAttrs(el) {
  if (el.closest('[data-no-i18n]')) return;
  let states = attrState.get(el);
  for (const name of ATTRS) {
    if (!el.hasAttribute(name)) continue;
    states ??= {};
    const current = el.getAttribute(name), state = states[name];
    const english = state && current === state.shown ? state.en : current;
    const shown = lang === 'ar' ? tr(english) : english;
    states[name] = {en: english, shown};
    if (current !== shown) el.setAttribute(name, shown);
  }
  if (states) attrState.set(el, states);
}

function translateTree(root) {
  if (root.nodeType === Node.TEXT_NODE) { translateTextNode(root); return; }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  translateAttrs(root);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) n.nodeType === Node.TEXT_NODE ? translateTextNode(n) : translateAttrs(n);
}

function applyDirection() {
  const html = document.documentElement;
  html.lang = lang; html.dir = lang === 'ar' ? 'rtl' : 'ltr';
  for (const b of document.querySelectorAll('.lang-toggle')) {
    b.textContent = lang === 'ar' ? 'English' : 'عربي';
    b.setAttribute('aria-label', lang === 'ar' ? 'Switch to English' : 'التبديل إلى العربية');
    b.lang = lang === 'ar' ? 'en' : 'ar';
  }
}

export function setLang(next) {
  lang = next === 'ar' ? 'ar' : 'en';
  try { localStorage.setItem(KEY, lang); } catch { /* not persisted */ }
  applyDirection();
  translateTree(document.body);
  window.dispatchEvent(new CustomEvent('wathba:lang', {detail: lang}));
}

function toggleButton() {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'lang-toggle'; b.dataset.noI18n = '';
  b.onclick = () => setLang(lang === 'ar' ? 'en' : 'ar');
  return b;
}

export function initI18n() {
  // Language buttons: home header, report header, welcome screen and profile.
  const spots = [['#home .greeting', 'before', '.avatar'], ['#report .results-top', 'append'], ['#welcome', 'prepend'], ['#profile .screen-heading', 'append-after']];
  for (const [selector, how, anchor] of spots) {
    const host = document.querySelector(selector);
    if (!host) continue;
    const b = toggleButton();
    if (how === 'before' && host.querySelector(anchor)) host.querySelector(anchor).before(b);
    else if (how === 'prepend') { b.classList.add('floating'); host.prepend(b); }
    else if (how === 'append-after') host.after(b);
    else host.append(b);
  }
  new MutationObserver(records => {
    if (lang !== 'ar') return;
    for (const r of records) {
      if (r.type === 'characterData') translateTextNode(r.target);
      else if (r.type === 'attributes') translateAttrs(r.target);
      else r.addedNodes.forEach(translateTree);
    }
  }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS});
  applyDirection();
  if (lang === 'ar') translateTree(document.body);
}
