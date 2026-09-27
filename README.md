# Exam Buddy: an Alexa quiz skill for ICSE class 9 and 10

An Alexa skill that quizzes students on the ICSE class 9 and 10 syllabus in
**Maths, Physics, Chemistry and Biology** with spoken multiple choice
questions. It runs as an Alexa-hosted skill written in Python.

```
Student: Alexa, open exam buddy
Alexa:   Welcome to Exam Buddy... What would you like to practise?
Student: Class 10 physics, refraction
Alexa:   Here are 5 questions on class 10 physics, Refraction of Light and Lenses.
         Question 1. A convex lens is also called a:
         A: diverging lens. B: converging lens. C: plane lens. D: cylindrical mirror.
Student: B
Alexa:   Correct! A convex lens brings parallel rays together at its focus.
         Question 2. ...
         ...
         That's the end of the round. You scored 4 out of 5. Good effort.
         Would you like another round of class 10 physics, Refraction of Light and Lenses?
```

## What it does

- **Choose what to practise:** class, subject, and optionally a chapter.
  - "class 9 maths" mixes questions from every class 9 maths chapter.
  - "class 10 science" mixes physics, chemistry and biology.
  - "genetics" works on its own, because the chapter is only in class 10 biology.
    For a chapter in both classes, like "trigonometry", Alexa asks which class.
  - Alexa asks for whatever is missing.
- **Rounds:** each round has 5 questions. The four options are shuffled every time,
  so the answer letter keeps changing.
- **Answering:** say A, B, C or D, or "option B", "I think C", and so on. After each
  answer you hear right or wrong and a one-line explanation.
- **Commands:** at any time you can say *repeat*, *skip* ("I don't know"), *help*,
  *what chapters are there in class 10 chemistry*, or *stop*.
- **More rounds:** after a round, say *yes* for another round of the same selection.
  It avoids questions you have already had in this session. Or name a new subject
  or chapter; whatever you don't say (for example the class) carries over.
- **State:** progress lasts only for the session, so no database is used.

## Question bank

**290 questions across 58 chapters, 5 per chapter.**

| Class | Maths | Physics | Chemistry | Biology |
|---|---|---|---|---|
| 9 | 12 chapters, 60 Qs | 5 chapters, 25 Qs | 5 chapters, 25 Qs | 5 chapters, 25 Qs |
| 10 | 16 chapters, 80 Qs | 5 chapters, 25 Qs | 5 chapters, 25 Qs | 5 chapters, 25 Qs |

Maths covers most of the syllabus. Each science subject covers 5 core chapters
so far; see [QUESTION_BANK.md](QUESTION_BANK.md) for the full list.

> **Please review the questions before students use them.** They were written
> carefully against the CISCE syllabus, but a teacher should check the answers
> and wording. [QUESTION_BANK.md](QUESTION_BANK.md) lists every question with
> the correct option in bold, for easy review.

### Adding or editing questions

Questions live in `lambda/data/class{9,10}_{maths,physics,chemistry,biology}.json`:

```json
{
  "key": "trigonometry",
  "name": "Trigonometry",
  "synonyms": ["trigonometric ratios", "trig"],
  "questions": [
    {
      "question": "What is the value of tan 45 degrees?",
      "answer": "1",
      "distractors": ["0", "root 3", "1 by root 3"],
      "explanation": "At 45 degrees the opposite and adjacent sides are equal, so tan is 1."
    }
  ]
}
```

Rules, all enforced by `scripts/validate_bank.py`:

- **Written to be spoken.** Use "x squared", "root 2", "3 by 5", "plus",
  "minus", "degrees", "percent". Symbols like `^ / = + √ °` are rejected
  because Alexa reads them inconsistently. Formulas are spaced out, like "C O 2".
- **Answer and distractors.** Give the correct `answer` and three `distractors`.
  Options are shuffled, so never use "all of the above" or mention an option
  letter in the explanation.
- **Chapter size.** Each chapter needs at least 5 questions, so a chapter-only
  round is full.
- **Keys.** A chapter `key` is shared across classes when the same chapter exists
  in both (for example `trigonometry`). Names and synonyms must not clash
  between different keys.

After editing, run:

```bash
python scripts/validate_bank.py    # check the questions
python scripts/build.py            # regenerate the interaction model and QUESTION_BANK.md
python -m pytest -q
```

`build.py` puts new chapters into the Alexa `TOPIC` slot, so the interaction
model must be rebuilt and redeployed whenever chapters or synonyms change.
Adding questions to an existing chapter only needs a code deploy.

## Project layout

```
lambda/                     deployed to the Alexa-hosted Lambda
  lambda_function.py        Alexa handlers (thin: slots in, engine call, response out)
  quiz/engine.py            conversation logic and session state (no SDK dependency)
  quiz/bank.py              loads the JSON question bank, picks questions
  data/*.json               the questions
  requirements.txt
skill-package/
  skill.json                manifest (name, description, example phrases)
  interactionModels/custom/en-IN.json   generated by scripts/build.py
scripts/
  validate_bank.py          question bank checks
  build.py                  generates the interaction model and QUESTION_BANK.md
  play.py                   play the quiz in a terminal
deploy.bat                  copy to the Alexa-hosted repo and push (Windows)
tests/                      pytest: bank, engine flows, full Alexa request/response
```

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
python scripts/play.py      # type "class 10 physics", then a, b, c or d
```

`play.py` uses a very rough stand-in for Alexa's language understanding. It is
for trying the questions and flow, not for testing phrasing.

CI (`.github/workflows/ci.yml`) runs the validator, checks the generated files
are up to date, and runs the tests on Python 3.9 and 3.12. The code avoids
newer syntax so it runs on whatever Python version the Alexa-hosted
environment provides.

## Deploying as an Alexa-hosted skill

### Cost

Alexa-hosted skills are **free**. Amazon provides the Lambda function, S3 and
DynamoDB for you within AWS Free Tier limits, and you don't need an AWS
account. A text-only quiz with no database uses a tiny fraction of those limits.

### One-time setup

1. Sign in to the [Alexa developer console](https://developer.amazon.com/alexa/console/ask)
   and click **Create Skill**:
   - **Name:** Exam Buddy
   - **Primary locale:** English (IN)
   - **Type:** Other, then Custom
   - **Hosting:** Alexa-hosted (Python)
   - **Template:** Start from scratch
2. Wait for the skill to be created. You'll get a skill ID starting `amzn1.ask.skill...`.

Then deploy with either option below.

### Option A: developer console only

1. **Interaction model:** go to Build, then Interaction Model, then JSON Editor.
   Paste the contents of `skill-package/interactionModels/custom/en-IN.json`,
   then click **Save** and **Build skill**.
2. **Code:** zip the *contents* of `lambda/` (`lambda_function.py`,
   `requirements.txt`, `quiz/`, `data/`). On the Code tab, click
   **Import Code**, choose the zip, then click **Deploy**.
3. **Manifest text:** copy the description, example phrases and keywords from
   `skill-package/skill.json` into the Distribution tab.
4. **Test:** on the Test tab, set testing to *Development* and type
   `open exam buddy`.

### Option B: ASK CLI (recommended for ongoing updates)

Alexa-hosted skills keep their code in an Amazon-managed git repository. The
CLI clones it, and pushing to it deploys.

```bash
npm install -g ask-cli
ask configure                                    # sign in with your Amazon developer account
ask init --hosted-skill-id amzn1.ask.skill.xxxx  # clones the hosted repo into a new folder
```

Name the folder `ExamBuddy` and create it next to this repo's clone.
Then, on Windows, deploy with:

```bat
deploy.bat                       REM or: deploy.bat C:\path\to\hosted-repo
```

The script does the following:

1. Pulls the latest code from GitHub.
2. Validates the question bank, if Python is installed.
3. Copies `lambda\` and `skill-package\interactionModels\` into the hosted repo.
4. Commits and pushes. The push builds the model and deploys the code to the
   development stage.

It leaves the hosted repo's own `skill.json` alone, because that file holds the
managed Lambda endpoint. Copy the `publishingInformation` text across by hand
if you want it. GitHub (this repo) stays the source of truth;
the hosted repo is just the deployment target.

## Notes before publishing

- **Audience:** the manifest sets `isChildDirected: false`, because ICSE class
  9 and 10 students are typically 14 to 16. Amazon's certification asks this
  directly, so confirm it matches your intended audience. Skills directed at
  children under 13 have extra requirements.
- **Voice model:** the voice model uses some adjacent slots, such as
  "class {grade} {subject}". Alexa supports this, but test the phrasings
  students actually use on the Test tab or a device, and add more sample
  utterances in `scripts/build.py` if needed.
- **Locale:** only English (IN) is configured.
