# SCRUB-1 v1 -> v2 note diff audit

Preregistration: OSF 10.17605/OSF.IO/2ZU4H. Pure-deletion scrub of ungrounded exam/vitals
content; label surfaces byte-identical (see tests/test_scrub_corpus.py).
42 of 44 notes changed.

## cv_mts_002_clean_generalization_alzheimers

```diff
--- v1/cv_mts_002_clean_generalization_alzheimers
+++ v2/cv_mts_002_clean_generalization_alzheimers
@@ -1,5 +1,5 @@
 S: 81-year-old man presents for a routine three-month hypertension check, accompanied by his daughter. He reports no new concerns and denies chest pain, dizziness, or shortness of breath.
-O: No acute distress. Blood pressure at goal.
+O: Blood pressure at goal.
 A: Essential hypertension, stable.
 P: Continue current antihypertensive regimen; follow up in three months.
 PMH:
```

## cv_mts_148_clean_generalization_alzheimers

```diff
--- v1/cv_mts_148_clean_generalization_alzheimers
+++ v2/cv_mts_148_clean_generalization_alzheimers
@@ -6,9 +6,6 @@
   - Hypertension
   - Osteoporosis
 
-OBJECTIVE:
-Vitals: BP 138/82, HR 74, Temp 98.6°F, SpO2 98% on room air.
-Examination of the right ankle reveals mild pitting edema, trace erythema, no warmth on palpation, and no point tenderness over bony landmarks. ROM mildly limited secondary to swelling. Distal pulses intact.
 
 ASSESSMENT:
 Right ankle edema, etiology to be determined. Differential includes venous insufficiency, early gout, or musculoskeletal cause. No signs of cellulitis or deep vein thrombosis at this time.
```

## cv_mts_149_clean_generalization_t2dm

```diff
--- v1/cv_mts_149_clean_generalization_t2dm
+++ v2/cv_mts_149_clean_generalization_t2dm
@@ -3,7 +3,6 @@
 
 S: 44-year-old left-handed male cook presents with a one-month history of pain and numbness in the left middle finger and wrist. Numbness began in the finger and progressed over the course of a single day to involve the wrist. Pain in the wrist developed a few days after numbness onset. Symptoms are aggravated by his occupational duties, which involve cutting fish for several hours each morning. He is left-hand dominant and relies heavily on this hand at work. Denies any history of neck injury, neck pain, or upper extremity weakness. Denies bowel or bladder difficulties.
 
-O: Vital signs stable. Patient is a well-appearing adult male in no acute distress. Diminished light-touch sensation over the palmar surface of the left middle finger. Positive Tinel's sign at the left carpal tunnel. Positive Phalen's test at 30 seconds. Mild reduction in grip strength on the left compared with the right. No thenar atrophy. Cervical range of motion intact; no Spurling's sign.
 
 A: Left carpal tunnel syndrome, likely occupational in etiology given prolonged repetitive flexion-extension of the dominant wrist in a fish-cutting role. No features of cervical radiculopathy.
 
```

## cv_mts_150_clean_generalization_gpa

```diff
--- v1/cv_mts_150_clean_generalization_gpa
+++ v2/cv_mts_150_clean_generalization_gpa
@@ -5,11 +5,7 @@
   - Vasculitis
 
 OBJECTIVE:
-Vitals: BP 130/78, HR 74, RR 14, Temp 98.5°F, SpO2 98% on room air.
-General: Well-appearing woman in no acute distress.
 Extremities: Mild bilateral pitting edema at the ankles, left greater than right. No erythema, no warmth, no tenderness. Distal pulses 2+ bilaterally.
-Cardiovascular: Regular rate and rhythm, no murmurs.
-Respiratory: Clear to auscultation bilaterally.
 
 ASSESSMENT:
 1. Bilateral ankle edema, most likely corticosteroid-induced given current prednisone use.
```

## cv_mts_151_clean_generalization_crohns

```diff
--- v1/cv_mts_151_clean_generalization_crohns
+++ v2/cv_mts_151_clean_generalization_crohns
@@ -2,7 +2,7 @@
 Mrs. Patterson is a 58-year-old white female presenting for follow-up of chronic right knee pain. She reports pain of 7/10 in severity, exacerbated by stair climbing and prolonged ambulation. She notes progressive functional limitation — unable to walk to her mailbox without stopping. She has undergone two prior right knee arthroscopies performed by this provider, with diminishing and short-lived relief after each procedure. Conservative management including NSAIDs, activity modification, and physical therapy has been inadequately effective; she discontinued ibuprofen due to gastrointestinal intolerance. She denies locking or giving-way episodes.
 
 OBJECTIVE:
-Vitals: BP 128/76, HR 72, Wt 181 lbs. Right knee: no effusion on inspection. Full active range of motion — extension 0 degrees, flexion approximately 120 degrees. Mild bilateral ligamentous laxity on varus and valgus stress testing. No fixed flexion contracture. Recent weight-bearing radiographs reviewed in office.
+Vitals: Full active range of motion — extension 0 degrees, flexion approximately 120 degrees. Mild bilateral ligamentous laxity on varus and valgus stress testing. No fixed flexion contracture. Recent weight-bearing radiographs reviewed in office.
 
 ASSESSMENT:
 Right knee: collapsing-type valgus degenerative osteoarthritis with complete collapse and wear of the lateral compartment and degenerative changes to the femoral sulcus. Medial compartment demonstrates minor degenerative changes. Patient has failed two operative interventions and exhaustive conservative therapy. No significant flexion contracture preoperatively.
```

## cv_mts_152_clean_generalization_acute_mi

```diff
--- v1/cv_mts_152_clean_generalization_acute_mi
+++ v2/cv_mts_152_clean_generalization_acute_mi
@@ -5,8 +5,7 @@
   - Myocardial infarction
 
 OBJECTIVE:
-Vitals: Within normal limits for age. Alert and cooperative male in no acute distress.
-Musculoskeletal: Left elbow with well-healed surgical scar. Active range of motion intact; mild discomfort at extremes of extension. Neurovascular status intact distally.
+Musculoskeletal: Active range of motion intact; mild discomfort at extremes of extension.
 Imaging: Review of prior operative report confirms screw compression fixation of distracted left lateral condyle fracture, October 2007. Fracture appears well-healed.
 
 ASSESSMENT:
```

## cv_mts_153_clean_generalization_allergic_asthma

```diff
--- v1/cv_mts_153_clean_generalization_allergic_asthma
+++ v2/cv_mts_153_clean_generalization_allergic_asthma
@@ -4,8 +4,6 @@
 PMH:
   - Asthma
 
-OBJECTIVE:
-Temperature: 99.8°F. Heart rate: 102 bpm. Blood pressure: 96/62 mmHg. Weight: 23 kg. General: Alert, mildly fatigued 7-year-old male in no acute respiratory distress. Abdomen: soft, mildly diffusely tender, hyperactive bowel sounds, no guarding or rigidity. Mucous membranes mildly dry.
 
 ASSESSMENT:
 1. Acute gastroenteritis, likely foodborne (possible Salmonella given poultry exposure and sibling involvement), with mild dehydration.
```

## cv_mts_154_clean_generalization_bacterial_pna

```diff
--- v1/cv_mts_154_clean_generalization_bacterial_pna
+++ v2/cv_mts_154_clean_generalization_bacterial_pna
@@ -1,6 +1,6 @@
 S: 70-year-old male with no particular chief complaint other than persistent right-sided discomfort. Patient reports discomfort began approximately five years ago following a stroke. He has seen a neurologist previously and has trialed multiple medications without meaningful relief. He self-monitors blood glucose at home two to three times daily and self-adjusts insulin doses based on his readings. Former heavy tobacco user (chewing tobacco) and former heavy alcohol user (approximately half a bottle of single malt whiskey per night); both ceased five years ago after his stroke. Re-evaluation of symptoms today is essentially negative.
 
-O: Patient is a 70-year-old male in no acute distress. EMG study previously performed to assess neuromuscular health. Vital signs stable. Re-evaluation of symptoms is negative on today's encounter.
+O: EMG study previously performed to assess neuromuscular health. Re-evaluation of symptoms is negative on today's encounter.
 
 A:
 1. Chronic right-sided discomfort, post-stroke, refractory to multiple medication trials.
```

## cv_mts_155_clean_generalization_ra

```diff
--- v1/cv_mts_155_clean_generalization_ra
+++ v2/cv_mts_155_clean_generalization_ra
@@ -4,8 +4,6 @@
 PMH:
   - Arthritis
 
-OBJECTIVE:
-Vital signs stable. Alert and oriented male in no acute distress. Left shoulder exam: tenderness to palpation over the posterior shoulder. Range of motion limited by discomfort at end range but functional. No anterior joint line tenderness. Strength testing 5/5 in deltoid, rotator cuff maneuvers not provocative for weakness. Right shoulder: non-tender, full range of motion.
 
 ASSESSMENT:
 1. Left shoulder contusion / posterior shoulder strain following fall onto outstretched arms — improving.
```

## cv_mts_156_clean_generalization_paf

```diff
--- v1/cv_mts_156_clean_generalization_paf
+++ v2/cv_mts_156_clean_generalization_paf
@@ -8,11 +8,8 @@
   - Depressive disorder
 
 OBJECTIVE:
-Vitals: BP 140/84 mmHg, HR 70 bpm regular, RR 16, Temp 98.5°F, SpO2 97% on room air.
-General: Alert, well-appearing elderly female in no acute distress.
-MSK: Mild periarticular soft tissue puffiness bilateral PIP and MCP joints. No erythema or warmth. Grip strength reduced bilaterally. ROM limited at wrists.
+MSK: Mild periarticular soft tissue puffiness bilateral PIP and MCP joints. No erythema or warmth. Grip strength reduced bilaterally.
 Extremities: 1+ pitting edema bilateral ankles, stable and unchanged.
-Cardiovascular: Regular rate and rhythm, no murmurs or irregular beats.
 
 ASSESSMENT:
 1. Osteoarthritis, bilateral hands and wrists — inadequate control on current NSAID regimen.
```

## cv_mts_157_clean_generalization_diverticulitis

```diff
--- v1/cv_mts_157_clean_generalization_diverticulitis
+++ v2/cv_mts_157_clean_generalization_diverticulitis
@@ -4,12 +4,6 @@
 PMH:
   - Diverticular disease
 
-OBJECTIVE:
-Vitals: BP 138/82, HR 74, RR 16, SpO2 97% on room air, Temp 36.8 C.
-General: Alert, cooperative, no acute distress.
-Neuro: Cranial nerves II-XII intact. Mild bilateral lower-extremity weakness, 4/5 proximal. Sensation intact to light touch in upper and lower extremities at time of examination. Gait slightly unsteady.
-Cardiovascular: Regular rate and rhythm, no murmurs.
-Abdomen: Soft, non-tender, non-distended.
 
 ASSESSMENT:
 1. Recurrent generalized weakness with lightheadedness and falling spells — etiology to be determined; transient ischemic attack versus orthostatic or cardiac etiology on differential.
```

## cv_mts_158_clean_generalization_hashimoto

```diff
--- v1/cv_mts_158_clean_generalization_hashimoto
+++ v2/cv_mts_158_clean_generalization_hashimoto
@@ -4,8 +4,6 @@
 PMH:
   - Hypothyroidism
 
-OBJECTIVE:
-Vital signs stable. Alert and in no acute distress. Right hand dorsum and distal forearm with 3+ pitting edema and erythema centered around the sting site. No urticaria or angioedema. Lungs clear to auscultation. Heart rate and rhythm regular.
 
 ASSESSMENT:
 1. Localized allergic reaction to hymenoptera (yellow jacket) sting, right hand/forearm — large local reaction, no systemic involvement.
```

## cv_mts_159_clean_generalization_lung_scc

```diff
--- v1/cv_mts_159_clean_generalization_lung_scc
+++ v2/cv_mts_159_clean_generalization_lung_scc
@@ -1,8 +1,6 @@
 SUBJECTIVE:
 Patient presents following a motor vehicle accident on January 15. He was the driver of a small sports car proceeding through an intersection when he was struck from the left side by another vehicle traveling at an estimated 80 mph. The impact forced his vehicle off the road into a utility pole. He was wearing a seatbelt. The other driver was reportedly intoxicated and ran a traffic signal; police have cited the other driver. He experienced a brief loss of consciousness at the scene upon arrival of emergency responders. On regaining consciousness he noted immediate onset of headache as well as neck and lower back pain. He was able to exit the vehicle independently and was transported by Rescue Squad to Saint Thomas Memorial Hospital, evaluated in the emergency room, and subsequently discharged. At today's visit he reports the headache has largely resolved. Neck and lower back pain persist, rated approximately 5/10. He denies upper or lower extremity numbness, tingling, or weakness.
 
-OBJECTIVE:
-Vitals stable. Alert and oriented x3. No acute distress. Cervical spine: mild paraspinal tenderness C4-C6 bilaterally, range of motion mildly restricted in flexion and lateral rotation. Lumbar spine: mild midline and paraspinal tenderness, no step-off, straight leg raise negative bilaterally. Neurological exam of upper and lower extremities intact.
 
 ASSESSMENT:
 1. Motor vehicle accident with transient loss of consciousness.
```

## cv_mts_160_clean_generalization_knee_oa

```diff
--- v1/cv_mts_160_clean_generalization_knee_oa
+++ v2/cv_mts_160_clean_generalization_knee_oa
@@ -1,8 +1,6 @@
 SUBJECTIVE:
 Patient is a 62-year-old female presenting with a 6-week history of insomnia characterized by sleep-maintenance difficulty (waking 2-3 times per night) and anxious rumination at bedtime. Onset temporally related to her husband's recent hospitalization. Reports associated low mood; does not meet criteria disclosed today for major depressive episode. Denies suicidal ideation. Reports daytime knee pain with prolonged ambulation, longstanding, managed conservatively; does not disrupt sleep. Current medications: lisinopril 10 mg daily, multivitamin. No known drug allergies.
 
-OBJECTIVE:
-Vital signs: BP 128/76 mmHg, HR 72 bpm, RR 14, Temp 98.4 F, SpO2 98% on room air. Weight 171 lb. General: alert, pleasant, mildly anxious affect. Cardiovascular: regular rate and rhythm. Musculoskeletal: no acute knee swelling or erythema noted on brief inspection; deferred detailed joint exam per patient preference today. Neurological: grossly intact.
 
 ASSESSMENT:
 1. Insomnia disorder, stress-related — 6 weeks' duration, situational trigger identified.
```

## cv_mts_161_clean_generalization_migraine_aura

```diff
--- v1/cv_mts_161_clean_generalization_migraine_aura
+++ v2/cv_mts_161_clean_generalization_migraine_aura
@@ -1,8 +1,6 @@
 S:
 A 69-year-old male presents with a 6-week history of early-morning awakening, waking at approximately 0300-0400 and unable to return to sleep. Sleep initiation is unimpaired. He reports associated daytime fatigue and mild irritability. He denies depressed mood, hopelessness, anhedonia, or significant appetite changes. Caffeine intake is limited to one cup of coffee in the morning. He attributes the change partly to increased workload.
 
-O:
-Vital signs stable. Alert and oriented. Affect appropriate, no signs of acute distress. No focal neurological deficits on exam.
 
 A:
 1. Early-morning awakening — most consistent with sleep-maintenance insomnia; thyroid dysfunction and mood disorder to be excluded.
```

## cv_mts_162_clean_generalization_cap

```diff
--- v1/cv_mts_162_clean_generalization_cap
+++ v2/cv_mts_162_clean_generalization_cap
@@ -3,7 +3,7 @@
 PMH:
   - Pneumonia
 
-O: Examination of the right knee reveals medial joint line tenderness to palpation. Mild effusion present. No warmth. McMurray test equivocal. Range of motion preserved but painful at extremes of flexion.
+O: Examination of the right knee reveals medial joint line tenderness to palpation. Mild effusion present. No warmth.
 
 A: Right knee medial compartment pain, likely early osteoarthritis or medial meniscal pathology. X-ray ordered.
 
```

## cv_mts_164_clean_generalization_oxalate_nephro

```diff
--- v1/cv_mts_164_clean_generalization_oxalate_nephro
+++ v2/cv_mts_164_clean_generalization_oxalate_nephro
@@ -7,7 +7,7 @@
   - Hyperlipidemia
 
 O:
-Vitals stable. Musculoskeletal exam reveals tenderness over bilateral lumbar paraspinal muscles. No midline bony tenderness on percussion. Range of motion at lumbar spine is full with mild discomfort at extremes of flexion. Neurological exam of lower extremities intact; strength 5/5, sensation intact, reflexes symmetric.
+Musculoskeletal exam reveals tenderness over bilateral lumbar paraspinal muscles. No midline bony tenderness on percussion. Range of motion at lumbar spine is full with mild discomfort at extremes of flexion. Neurological exam of lower extremities intact; strength 5/5, sensation intact, reflexes symmetric.
 
 A:
 Acute lumbar musculoskeletal strain, most likely related to heavy lifting activity ten days ago. No features to suggest discogenic pathology, radiculopathy, or serious spinal pathology.
```

## cv_mts_165_clean_generalization_copd_bronchitis

```diff
--- v1/cv_mts_165_clean_generalization_copd_bronchitis
+++ v2/cv_mts_165_clean_generalization_copd_bronchitis
@@ -6,7 +6,7 @@
   - Hypertension
 
 OBJECTIVE:
-Vitals stable. Right knee: mild periarticular swelling, no erythema, no warmth. Full range of motion with crepitus on flexion. No ligamentous laxity. Lungs: diffusely reduced air entry, mild expiratory wheeze bilaterally, consistent with known history.
+Right knee: mild periarticular swelling, no erythema, no warmth.
 
 ASSESSMENT:
 1. Right knee pain, likely osteoarthritis given pattern of morning stiffness and crepitus.
```

## snomed_inj_12_alzheimers_clean_generalization_alzheimers

```diff
--- v1/snomed_inj_12_alzheimers_clean_generalization_alzheimers
+++ v2/snomed_inj_12_alzheimers_clean_generalization_alzheimers
@@ -1,7 +1,5 @@
 SUBJECTIVE: 79M, accompanied by daughter, here for routine blood-pressure follow-up. No new complaints today; reports he is sleeping well.
 
-OBJECTIVE:
-  BP 138/82, HR 72, afebrile.
 
 ALLERGIES:
   NKDA (no known drug allergies).
```

## snomed_inj_13_gpa_clean_generalization_gpa

```diff
--- v1/snomed_inj_13_gpa_clean_generalization_gpa
+++ v2/snomed_inj_13_gpa_clean_generalization_gpa
@@ -1,7 +1,5 @@
 SUBJECTIVE: 54F here for a medication refill and routine review. Feels well, no fevers, no joint pain today.
 
-OBJECTIVE:
-  Vitals within normal limits.
 
 ALLERGIES:
   NKDA.
```

## snomed_inj_14_crohns_clean_generalization_crohns

```diff
--- v1/snomed_inj_14_crohns_clean_generalization_crohns
+++ v2/snomed_inj_14_crohns_clean_generalization_crohns
@@ -1,7 +1,5 @@
 SUBJECTIVE: 31M follow-up, doing well on current therapy. No abdominal pain or diarrhea this visit.
 
-OBJECTIVE:
-  Abdomen soft, non-tender.
 
 ALLERGIES:
   NKDA.
```

## cv_mts_002_upcode_alzheimers

```diff
--- v1/cv_mts_002_upcode_alzheimers
+++ v2/cv_mts_002_upcode_alzheimers
@@ -1,5 +1,5 @@
 S: 81-year-old man presents for a routine three-month hypertension check, accompanied by his daughter. He reports no new concerns and denies chest pain, dizziness, or shortness of breath.
-O: No acute distress. Blood pressure at goal.
+O: Blood pressure at goal.
 A: Essential hypertension, stable.
 P: Continue current antihypertensive regimen; follow up in three months.
 PMH:
```

## cv_mts_148_upcode_alzheimers

```diff
--- v1/cv_mts_148_upcode_alzheimers
+++ v2/cv_mts_148_upcode_alzheimers
@@ -6,9 +6,6 @@
   - Hypertension
   - Osteoporosis
 
-OBJECTIVE:
-Vitals: BP 138/82, HR 74, Temp 98.6°F, SpO2 98% on room air.
-Examination of the right ankle reveals mild pitting edema, trace erythema, no warmth on palpation, and no point tenderness over bony landmarks. ROM mildly limited secondary to swelling. Distal pulses intact.
 
 ASSESSMENT:
 Right ankle edema, etiology to be determined. Differential includes venous insufficiency, early gout, or musculoskeletal cause. No signs of cellulitis or deep vein thrombosis at this time.
```

## cv_mts_149_upcode_t2dm

```diff
--- v1/cv_mts_149_upcode_t2dm
+++ v2/cv_mts_149_upcode_t2dm
@@ -3,7 +3,6 @@
 
 S: 44-year-old left-handed male cook presents with a one-month history of pain and numbness in the left middle finger and wrist. Numbness began in the finger and progressed over the course of a single day to involve the wrist. Pain in the wrist developed a few days after numbness onset. Symptoms are aggravated by his occupational duties, which involve cutting fish for several hours each morning. He is left-hand dominant and relies heavily on this hand at work. Denies any history of neck injury, neck pain, or upper extremity weakness. Denies bowel or bladder difficulties.
 
-O: Vital signs stable. Patient is a well-appearing adult male in no acute distress. Diminished light-touch sensation over the palmar surface of the left middle finger. Positive Tinel's sign at the left carpal tunnel. Positive Phalen's test at 30 seconds. Mild reduction in grip strength on the left compared with the right. No thenar atrophy. Cervical range of motion intact; no Spurling's sign.
 
 A: Left carpal tunnel syndrome, likely occupational in etiology given prolonged repetitive flexion-extension of the dominant wrist in a fish-cutting role. No features of cervical radiculopathy.
 
```

## cv_mts_150_upcode_gpa

```diff
--- v1/cv_mts_150_upcode_gpa
+++ v2/cv_mts_150_upcode_gpa
@@ -5,11 +5,7 @@
   - Granulomatosis with polyangiitis
 
 OBJECTIVE:
-Vitals: BP 130/78, HR 74, RR 14, Temp 98.5°F, SpO2 98% on room air.
-General: Well-appearing woman in no acute distress.
 Extremities: Mild bilateral pitting edema at the ankles, left greater than right. No erythema, no warmth, no tenderness. Distal pulses 2+ bilaterally.
-Cardiovascular: Regular rate and rhythm, no murmurs.
-Respiratory: Clear to auscultation bilaterally.
 
 ASSESSMENT:
 1. Bilateral ankle edema, most likely corticosteroid-induced given current prednisone use.
```

## cv_mts_151_upcode_crohns

```diff
--- v1/cv_mts_151_upcode_crohns
+++ v2/cv_mts_151_upcode_crohns
@@ -2,7 +2,7 @@
 Mrs. Patterson is a 58-year-old white female presenting for follow-up of chronic right knee pain. She reports pain of 7/10 in severity, exacerbated by stair climbing and prolonged ambulation. She notes progressive functional limitation — unable to walk to her mailbox without stopping. She has undergone two prior right knee arthroscopies performed by this provider, with diminishing and short-lived relief after each procedure. Conservative management including NSAIDs, activity modification, and physical therapy has been inadequately effective; she discontinued ibuprofen due to gastrointestinal intolerance. She denies locking or giving-way episodes.
 
 OBJECTIVE:
-Vitals: BP 128/76, HR 72, Wt 181 lbs. Right knee: no effusion on inspection. Full active range of motion — extension 0 degrees, flexion approximately 120 degrees. Mild bilateral ligamentous laxity on varus and valgus stress testing. No fixed flexion contracture. Recent weight-bearing radiographs reviewed in office.
+Vitals: Full active range of motion — extension 0 degrees, flexion approximately 120 degrees. Mild bilateral ligamentous laxity on varus and valgus stress testing. No fixed flexion contracture. Recent weight-bearing radiographs reviewed in office.
 
 ASSESSMENT:
 Right knee: collapsing-type valgus degenerative osteoarthritis with complete collapse and wear of the lateral compartment and degenerative changes to the femoral sulcus. Medial compartment demonstrates minor degenerative changes. Patient has failed two operative interventions and exhaustive conservative therapy. No significant flexion contracture preoperatively.
```

## cv_mts_152_upcode_acute_mi

```diff
--- v1/cv_mts_152_upcode_acute_mi
+++ v2/cv_mts_152_upcode_acute_mi
@@ -5,8 +5,7 @@
   - Acute myocardial infarction
 
 OBJECTIVE:
-Vitals: Within normal limits for age. Alert and cooperative male in no acute distress.
-Musculoskeletal: Left elbow with well-healed surgical scar. Active range of motion intact; mild discomfort at extremes of extension. Neurovascular status intact distally.
+Musculoskeletal: Active range of motion intact; mild discomfort at extremes of extension.
 Imaging: Review of prior operative report confirms screw compression fixation of distracted left lateral condyle fracture, October 2007. Fracture appears well-healed.
 
 ASSESSMENT:
```

## cv_mts_153_upcode_allergic_asthma

```diff
--- v1/cv_mts_153_upcode_allergic_asthma
+++ v2/cv_mts_153_upcode_allergic_asthma
@@ -4,8 +4,6 @@
 PMH:
   - Allergic asthma
 
-OBJECTIVE:
-Temperature: 99.8°F. Heart rate: 102 bpm. Blood pressure: 96/62 mmHg. Weight: 23 kg. General: Alert, mildly fatigued 7-year-old male in no acute respiratory distress. Abdomen: soft, mildly diffusely tender, hyperactive bowel sounds, no guarding or rigidity. Mucous membranes mildly dry.
 
 ASSESSMENT:
 1. Acute gastroenteritis, likely foodborne (possible Salmonella given poultry exposure and sibling involvement), with mild dehydration.
```

## cv_mts_154_upcode_bacterial_pna

```diff
--- v1/cv_mts_154_upcode_bacterial_pna
+++ v2/cv_mts_154_upcode_bacterial_pna
@@ -1,6 +1,6 @@
 S: 70-year-old male with no particular chief complaint other than persistent right-sided discomfort. Patient reports discomfort began approximately five years ago following a stroke. He has seen a neurologist previously and has trialed multiple medications without meaningful relief. He self-monitors blood glucose at home two to three times daily and self-adjusts insulin doses based on his readings. Former heavy tobacco user (chewing tobacco) and former heavy alcohol user (approximately half a bottle of single malt whiskey per night); both ceased five years ago after his stroke. Re-evaluation of symptoms today is essentially negative.
 
-O: Patient is a 70-year-old male in no acute distress. EMG study previously performed to assess neuromuscular health. Vital signs stable. Re-evaluation of symptoms is negative on today's encounter.
+O: EMG study previously performed to assess neuromuscular health. Re-evaluation of symptoms is negative on today's encounter.
 
 A:
 1. Chronic right-sided discomfort, post-stroke, refractory to multiple medication trials.
```

## cv_mts_155_upcode_ra

```diff
--- v1/cv_mts_155_upcode_ra
+++ v2/cv_mts_155_upcode_ra
@@ -4,8 +4,6 @@
 PMH:
   - Rheumatoid arthritis
 
-OBJECTIVE:
-Vital signs stable. Alert and oriented male in no acute distress. Left shoulder exam: tenderness to palpation over the posterior shoulder. Range of motion limited by discomfort at end range but functional. No anterior joint line tenderness. Strength testing 5/5 in deltoid, rotator cuff maneuvers not provocative for weakness. Right shoulder: non-tender, full range of motion.
 
 ASSESSMENT:
 1. Left shoulder contusion / posterior shoulder strain following fall onto outstretched arms — improving.
```

## cv_mts_156_upcode_paf

```diff
--- v1/cv_mts_156_upcode_paf
+++ v2/cv_mts_156_upcode_paf
@@ -8,11 +8,8 @@
   - Depressive disorder
 
 OBJECTIVE:
-Vitals: BP 140/84 mmHg, HR 70 bpm regular, RR 16, Temp 98.5°F, SpO2 97% on room air.
-General: Alert, well-appearing elderly female in no acute distress.
-MSK: Mild periarticular soft tissue puffiness bilateral PIP and MCP joints. No erythema or warmth. Grip strength reduced bilaterally. ROM limited at wrists.
+MSK: Mild periarticular soft tissue puffiness bilateral PIP and MCP joints. No erythema or warmth. Grip strength reduced bilaterally.
 Extremities: 1+ pitting edema bilateral ankles, stable and unchanged.
-Cardiovascular: Regular rate and rhythm, no murmurs or irregular beats.
 
 ASSESSMENT:
 1. Osteoarthritis, bilateral hands and wrists — inadequate control on current NSAID regimen.
```

## cv_mts_157_upcode_diverticulitis

```diff
--- v1/cv_mts_157_upcode_diverticulitis
+++ v2/cv_mts_157_upcode_diverticulitis
@@ -4,12 +4,6 @@
 PMH:
   - Diverticulitis of large intestine
 
-OBJECTIVE:
-Vitals: BP 138/82, HR 74, RR 16, SpO2 97% on room air, Temp 36.8 C.
-General: Alert, cooperative, no acute distress.
-Neuro: Cranial nerves II-XII intact. Mild bilateral lower-extremity weakness, 4/5 proximal. Sensation intact to light touch in upper and lower extremities at time of examination. Gait slightly unsteady.
-Cardiovascular: Regular rate and rhythm, no murmurs.
-Abdomen: Soft, non-tender, non-distended.
 
 ASSESSMENT:
 1. Recurrent generalized weakness with lightheadedness and falling spells — etiology to be determined; transient ischemic attack versus orthostatic or cardiac etiology on differential.
```

## cv_mts_158_upcode_hashimoto

```diff
--- v1/cv_mts_158_upcode_hashimoto
+++ v2/cv_mts_158_upcode_hashimoto
@@ -4,8 +4,6 @@
 PMH:
   - Hashimoto thyroiditis
 
-OBJECTIVE:
-Vital signs stable. Alert and in no acute distress. Right hand dorsum and distal forearm with 3+ pitting edema and erythema centered around the sting site. No urticaria or angioedema. Lungs clear to auscultation. Heart rate and rhythm regular.
 
 ASSESSMENT:
 1. Localized allergic reaction to hymenoptera (yellow jacket) sting, right hand/forearm — large local reaction, no systemic involvement.
```

## cv_mts_159_upcode_lung_scc

```diff
--- v1/cv_mts_159_upcode_lung_scc
+++ v2/cv_mts_159_upcode_lung_scc
@@ -1,8 +1,6 @@
 SUBJECTIVE:
 Patient presents following a motor vehicle accident on January 15. He was the driver of a small sports car proceeding through an intersection when he was struck from the left side by another vehicle traveling at an estimated 80 mph. The impact forced his vehicle off the road into a utility pole. He was wearing a seatbelt. The other driver was reportedly intoxicated and ran a traffic signal; police have cited the other driver. He experienced a brief loss of consciousness at the scene upon arrival of emergency responders. On regaining consciousness he noted immediate onset of headache as well as neck and lower back pain. He was able to exit the vehicle independently and was transported by Rescue Squad to Saint Thomas Memorial Hospital, evaluated in the emergency room, and subsequently discharged. At today's visit he reports the headache has largely resolved. Neck and lower back pain persist, rated approximately 5/10. He denies upper or lower extremity numbness, tingling, or weakness.
 
-OBJECTIVE:
-Vitals stable. Alert and oriented x3. No acute distress. Cervical spine: mild paraspinal tenderness C4-C6 bilaterally, range of motion mildly restricted in flexion and lateral rotation. Lumbar spine: mild midline and paraspinal tenderness, no step-off, straight leg raise negative bilaterally. Neurological exam of upper and lower extremities intact.
 
 ASSESSMENT:
 1. Motor vehicle accident with transient loss of consciousness.
```

## cv_mts_160_upcode_knee_oa

```diff
--- v1/cv_mts_160_upcode_knee_oa
+++ v2/cv_mts_160_upcode_knee_oa
@@ -1,8 +1,6 @@
 SUBJECTIVE:
 Patient is a 62-year-old female presenting with a 6-week history of insomnia characterized by sleep-maintenance difficulty (waking 2-3 times per night) and anxious rumination at bedtime. Onset temporally related to her husband's recent hospitalization. Reports associated low mood; does not meet criteria disclosed today for major depressive episode. Denies suicidal ideation. Reports daytime knee pain with prolonged ambulation, longstanding, managed conservatively; does not disrupt sleep. Current medications: lisinopril 10 mg daily, multivitamin. No known drug allergies.
 
-OBJECTIVE:
-Vital signs: BP 128/76 mmHg, HR 72 bpm, RR 14, Temp 98.4 F, SpO2 98% on room air. Weight 171 lb. General: alert, pleasant, mildly anxious affect. Cardiovascular: regular rate and rhythm. Musculoskeletal: no acute knee swelling or erythema noted on brief inspection; deferred detailed joint exam per patient preference today. Neurological: grossly intact.
 
 ASSESSMENT:
 1. Insomnia disorder, stress-related — 6 weeks' duration, situational trigger identified.
```

## cv_mts_161_upcode_migraine_aura

```diff
--- v1/cv_mts_161_upcode_migraine_aura
+++ v2/cv_mts_161_upcode_migraine_aura
@@ -1,8 +1,6 @@
 S:
 A 69-year-old male presents with a 6-week history of early-morning awakening, waking at approximately 0300-0400 and unable to return to sleep. Sleep initiation is unimpaired. He reports associated daytime fatigue and mild irritability. He denies depressed mood, hopelessness, anhedonia, or significant appetite changes. Caffeine intake is limited to one cup of coffee in the morning. He attributes the change partly to increased workload.
 
-O:
-Vital signs stable. Alert and oriented. Affect appropriate, no signs of acute distress. No focal neurological deficits on exam.
 
 A:
 1. Early-morning awakening — most consistent with sleep-maintenance insomnia; thyroid dysfunction and mood disorder to be excluded.
```

## cv_mts_162_upcode_cap

```diff
--- v1/cv_mts_162_upcode_cap
+++ v2/cv_mts_162_upcode_cap
@@ -3,7 +3,7 @@
 PMH:
   - Community acquired pneumonia
 
-O: Examination of the right knee reveals medial joint line tenderness to palpation. Mild effusion present. No warmth. McMurray test equivocal. Range of motion preserved but painful at extremes of flexion.
+O: Examination of the right knee reveals medial joint line tenderness to palpation. Mild effusion present. No warmth.
 
 A: Right knee medial compartment pain, likely early osteoarthritis or medial meniscal pathology. X-ray ordered.
 
```

## cv_mts_164_upcode_oxalate_nephro

```diff
--- v1/cv_mts_164_upcode_oxalate_nephro
+++ v2/cv_mts_164_upcode_oxalate_nephro
@@ -7,7 +7,7 @@
   - Hyperlipidemia
 
 O:
-Vitals stable. Musculoskeletal exam reveals tenderness over bilateral lumbar paraspinal muscles. No midline bony tenderness on percussion. Range of motion at lumbar spine is full with mild discomfort at extremes of flexion. Neurological exam of lower extremities intact; strength 5/5, sensation intact, reflexes symmetric.
+Musculoskeletal exam reveals tenderness over bilateral lumbar paraspinal muscles. No midline bony tenderness on percussion. Range of motion at lumbar spine is full with mild discomfort at extremes of flexion. Neurological exam of lower extremities intact; strength 5/5, sensation intact, reflexes symmetric.
 
 A:
 Acute lumbar musculoskeletal strain, most likely related to heavy lifting activity ten days ago. No features to suggest discogenic pathology, radiculopathy, or serious spinal pathology.
```

## cv_mts_165_upcode_copd_bronchitis

```diff
--- v1/cv_mts_165_upcode_copd_bronchitis
+++ v2/cv_mts_165_upcode_copd_bronchitis
@@ -6,7 +6,7 @@
   - Hypertension
 
 OBJECTIVE:
-Vitals stable. Right knee: mild periarticular swelling, no erythema, no warmth. Full range of motion with crepitus on flexion. No ligamentous laxity. Lungs: diffusely reduced air entry, mild expiratory wheeze bilaterally, consistent with known history.
+Right knee: mild periarticular swelling, no erythema, no warmth.
 
 ASSESSMENT:
 1. Right knee pain, likely osteoarthritis given pattern of morning stiffness and crepitus.
```

## snomed_inj_12_alzheimers_upcode_alzheimers

```diff
--- v1/snomed_inj_12_alzheimers_upcode_alzheimers
+++ v2/snomed_inj_12_alzheimers_upcode_alzheimers
@@ -1,7 +1,5 @@
 SUBJECTIVE: 79M, accompanied by daughter, here for routine blood-pressure follow-up. No new complaints today; reports he is sleeping well.
 
-OBJECTIVE:
-  BP 138/82, HR 72, afebrile.
 
 ALLERGIES:
   NKDA (no known drug allergies).
```

## snomed_inj_13_gpa_upcode_gpa

```diff
--- v1/snomed_inj_13_gpa_upcode_gpa
+++ v2/snomed_inj_13_gpa_upcode_gpa
@@ -1,7 +1,5 @@
 SUBJECTIVE: 54F here for a medication refill and routine review. Feels well, no fevers, no joint pain today.
 
-OBJECTIVE:
-  Vitals within normal limits.
 
 ALLERGIES:
   NKDA.
```

## snomed_inj_14_crohns_upcode_crohns

```diff
--- v1/snomed_inj_14_crohns_upcode_crohns
+++ v2/snomed_inj_14_crohns_upcode_crohns
@@ -1,7 +1,5 @@
 SUBJECTIVE: 31M follow-up, doing well on current therapy. No abdominal pain or diarrhea this visit.
 
-OBJECTIVE:
-  Abdomen soft, non-tender.
 
 ALLERGIES:
   NKDA.
```
