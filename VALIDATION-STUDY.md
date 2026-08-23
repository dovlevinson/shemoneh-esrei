# Rapid two-bracha adult validation study

## Purpose and limit

This study tests whether the vowel evidence separates known-correct and
deliberately changed readings across adult voices. Each person records Brachot
9 and 10 of Shemoneh Esrei. The browser collector is at `/study`.

This is an exploratory adult study. It can help decide whether the current model
and evidence method are worth testing on children. It cannot validate automatic
student pass, retry, or mastery decisions.

## Balanced assignment

Alternate assignments as people arrive. Keep reading ability and pronunciation
tradition reasonably balanced between the two groups.

| Assignment | Bracha 9, Barech Aleinu | Bracha 10, Teka Beshofar |
|---|---|---|
| A | Read correctly | Read four displayed vowel changes |
| B | Read four displayed vowel changes | Read correctly |

Use A for the first person, B for the second, A for the third, and so on. Aim
for at least four people, with at least two in each assignment. Six or eight
balanced speakers are more informative.

This crossover gives every tested vowel position a correct adult control group
and a separate adult error group without requiring anyone to repeat a bracha.

The selected non-winter texts contain 48 words after splitting maqaf-linked
words, 129 mapped vowel slots, all five core vowel sounds, all 19 consonant
phones represented by the current mapper, and 12 of the 13 written vowel
categories found in the current ordinary-weekday prayer text. The missing
category is hataf kamatz. These counts describe test coverage, not demonstrated
model accuracy.

## Exact guided changes

The page inserts and highlights these changes automatically.

### Bracha 9

| Correct form | Form to say |
|---|---|
| אֱלֹהֵינוּ | אֲלֹהֵינוּ |
| הַזֹּאת | הַזֵּאת |
| מִינֵי | מֵינֵי |
| הָאֲדָמָה | הָאֱדָמָה |

### Bracha 10

| Correct form | Form to say |
|---|---|
| בְּשׁוֹפָר | בְּשׁוּפָר |
| לְחֵרוּתֵנוּ | לְחִרוּתֵנוּ |
| גָּלֻיּוֹתֵינוּ | גָּלִיּוֹתֵינוּ |
| בָּרוּךְ | בָּרוֹךְ |

## Recording procedure

1. Open `/study` in current Chrome or Edge.
2. Enter a code such as `A01`. Do not enter the speaker's name.
3. Choose the next alternating assignment and record the displayed brachot.
4. Keep the microphone about 15 to 30 cm from the speaker. Avoid Bluetooth,
   music, television, or another voice in the room.
5. Let the speaker practice the four changed words before the guided recording.
6. Record only the displayed bracha. Do not announce the recording or add words.
7. Play back each recording immediately. Confirm it only if the correct script
   was followed. If uncertain, discard it and record again.
8. Select **Download recordings** before the speaker leaves.

The two recordings should take about five minutes including setup and playback.
Natural reading is more useful than slow over-enunciation.

Use the exact displayed non-winter text for Bracha 9, including `וְתֵן בְּרָכָה`.
Do not substitute the seasonal `טַל וּמָטָר` wording during this
collection, because every package must have the same expected word sequence.

## Privacy and analysis

Raw and analyzed packages contain base64-encoded audio. Keep them in an approved
private location and never commit them to this public repository.

The model does not need to be ready while people are present. After collection:

1. Import each raw package back into `/study`.
2. Select **Analyze both recordings**.
3. Download the analyzed package.
4. Combine the analyzed packages with:

```bash
python -m evaluation.rapid_validation_study \
  /private/kriah-rapid-analyzed-A01.json \
  /private/kriah-rapid-analyzed-A02.json \
  --output /private/kriah-rapid-summary.json
```

The aggregate report removes audio. It reports sensitivity, false alarms,
unmeasured targets, assignment balance, and the correct-versus-error evidence
distribution for each identical vowel position. It tests several absolute
competitor-margin thresholds because same-speaker reference recordings are not
available in this shortened design.

## Interpretation

The report marks a threshold as an exploratory pass only if all of these hold:

- at least four speakers;
- at least two speakers in each assignment;
- at least 90% of planned targets measured;
- at least 80% sensitivity;
- no more than 2% observed false alarms.

Even a pass only nominates an approach for a larger child study. Child speech
has been reported to produce wider pronunciation-score distributions than adult
speech: [Cao et al., Interspeech
2023](https://www.isca-archive.org/interspeech_2023/cao23_interspeech.pdf). The
phoneme model is a general multilingual recognizer, not a validated Hebrew child
assessment model: [model
card](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft).
