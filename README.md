# Listening Practice Companion

A program for your computer that makes **sound training sentences** for the [Listening Practice](https://github.com/mattias/anki-listening-practice) Android app (Japanese only).

Spoken Japanese runs together: 薬を is said *kusuryo*, これは *korya*, 食べている *tabeteru*, のだ *nda*. The app lets you practice hearing it. It needs sentences made from **the words you know**, with a translation and natural speech, and that takes a language model and a voice model. Those run on your computer, not on the phone, and this program is what ties them together:

```
 Listening Practice app (phone)  ──►  Companion (this program, your computer)  ──►  language model (Ollama, or another AI service)
        ▲   sentences + audio, kept on the phone                     │
        └──────────────────────────────────────────────────────────  └──────────►  Irodori voice server (speech)
```

1. The app sends the words you know and asks for, say, 20 sentences about *い-sound + を*.
2. The **language model** writes natural sentences with those words, built to show the phenomenon.
3. The program **checks every sentence** with a Japanese analyzer (the phenomenon is really there, the words are known) and a **proofreading** pass, and throws away what fails.
4. The sentences are **translated** into the language you read.
5. Each sentence is written the way it is **said** (これは → こりゃ) and spoken by the **Irodori** voice model.
6. The app downloads the sentences with their audio. From then on you can practice **without the computer**, for example when you are out walking. Only making new sentences needs the computer.

Everything stays on your own network. Nothing is sent anywhere unless you choose an online AI service for the sentences.

## What you need

| | |
|---|---|
| A computer | Windows 10 or 11 (the packaged program). Linux and macOS can run it from source. An NVIDIA graphics card with 16 GB is comfortable; the voice model and the language model share it. Without a good card, use an online AI service for the sentences (below); the voice then runs slowly on the processor. |
| The **Irodori voice server** | Set up by the [Irodori Audio add-on for Anki](https://github.com/mattias/anki-irodori-audio) (one click, about 8 GB), or by hand. **Required.** |
| A **language model** | [Ollama](https://ollama.com) with a model, the program downloads it for you. Or any service with the OpenAI API and a key. |
| The Android app | [Listening Practice](https://github.com/mattias/anki-listening-practice) 0.10.0 or newer. |
| A network | Phone and computer on the same Wi-Fi (or a VPN such as Tailscale) when you make sentences. |

## Setup, step by step

### 1. The voice server (Irodori)

The easy way: in Anki, install the *Irodori Audio* add-on (AnkiWeb code `2078760911`), restart Anki, and choose **Tools > Irodori Audio > Set up local server**. It installs everything (about 8 GB) and the six voices the Companion uses. You do not need to keep Anki open afterwards: the Companion starts the server by itself when it is installed that way.

If you already run an Irodori-TTS server, or set it up by hand, that works too: it needs the six voices `female_calm`, `female_bright`, `female_cool`, `male_calm`, `male_young` and `male_deep` in its `voices` folder (the add-on has the files). Put its address in the Companion (default `http://127.0.0.1:8088`).

### 2. The language model

Install [Ollama](https://ollama.com) (a normal installer) and start it. In the Companion, press **Download qwen3:8b** (about 5 GB). It is small enough to share the graphics card with the voice model, and it wrote the most natural sentences in tests. Any other model Ollama has works: type its name.

*Without a strong graphics card:* choose **Other service with the OpenAI API** and enter the service's address, a model name and your key. For example Google Gemini: address `https://generativelanguage.googleapis.com/v1beta/openai`, a Gemini model name and an API key from Google AI Studio. Then your known words and the sentences go to that service.

A translation model is optional. A `translategemma` model in Ollama is used automatically for the translations (they read more naturally); otherwise the language model translates.

### 3. The Companion

Download `ListeningPracticeCompanion.exe` from the [latest release](https://github.com/mattias/listening-practice-companion/releases/latest) and run it. It is one file, no installer. Windows may say it is an unknown program (it is not signed): choose *More info > Run anyway*.

The window shows what works: the voice server, the language model, and the service the phone connects to. Press **Save and start the service**. Tick *Start the program when I log in to Windows* if you want it always there.

### 4. The firewall

The phone connects to the computer over your network, so the Windows firewall has to allow it. The first time the service listens, Windows asks whether to allow the program: choose **Private networks**. If you missed it, or the phone cannot connect, open an administrator PowerShell and run:

```powershell
netsh advfirewall firewall add rule name="Listening Practice Companion" dir=in action=allow protocol=TCP localport=8089 profile=private
```

(Change `8089` if you changed the port.) If Windows earlier **blocked** the program, delete that block rule in *Windows Defender Firewall with Advanced Security > Inbound Rules*: block rules win over allow rules.

### 5. The app

In the app, with Japanese selected: **Settings > Library > Sound training**.

1. Enter the **address** the Companion shows (like `http://192.168.1.20:8089`) and the **token**.
2. Press **Test the connection**. You should see *Connected* and the language model's name.
3. Choose what to practice (one way, several, or *Everything*), how many sentences, and press **Make sentences**.
4. When it is done, choose **Sound training** in the source menu at the top of the practice screen. Reveal the text to see the translation and *Said as: …*, the way the voice was made to say it.

The settings page and the sound training source exist only for Japanese. The **sound filter** in the playback sheet also works on your Anki cards and videos, without the Companion.

### Offline

Making sentences needs the computer. **Practicing does not**: the sentences and their audio are stored on the phone. Make a batch (or two) at home and go for a walk. If the computer cannot be reached, the app says so and you can still practice what you have.

## The ways sounds run together

| | Written | Said |
|---|---|---|
| い-row + を | 薬を | *kusuryo* (not respelled) |
| ん + を / は | 本を, パンは | *honno*, *panna* (not respelled) |
| contractions with は | これは, では, ては, には | こりゃ, じゃ, ちゃ, にゃ |
| て-form + helper | 食べている, ておく, てしまう | 食べてる, とく, ちゃう |
| のだ / のです / ので | 行くのです | 行くんです |
| なければ / なくては | 行かなければ | 行かなきゃ |
| という | 来ないという話 | 来ないって話 |
| devoiced です / ます | です | *des* (not respelled) |
| devoiced vowels inside words | しました | *shmashta* (not respelled) |
| nasal が | 学校が | [ŋ] (not respelled) |
| shortened words | 本当, ところ | ほんと, とこ |

Where people really write the contraction (こりゃ, じゃ, ちゃ, にゃ, てる, とく, ちゃう, んだ, なきゃ, って, ほんと), the sentence is **written that way** before it goes to the voice, so the voice really says it that way; the app shows both, the written sentence and *Said as: …*. Where nobody writes it (薬を, 本を, です, devoiced vowels, nasal が) the text is left **as normal**: the Irodori voice says 薬を the way it is said by itself, and a made-up spelling like くすりょ could change the accent.

**About pitch accent:** the voice model has no way to be told the accent, it guesses it from the text. Spellings people really use are safe; that is why the others are not respelled. If a sentence sounds wrong, tell what it was.

## If something does not work

| | |
|---|---|
| *Can't reach …* in the app | The Companion must be running and the service started. The phone must be on the same network. Check the firewall (step 4). Try the address in the phone's browser: `http://…:8089/v1/sound/health` should show `{"service": "sound-training"…}`. |
| *The token is wrong* | Copy the token again from the Companion (*Copy*). A new token (*New*) must be entered in the app. |
| The window says the voice server is not running | Press *Start the voice server now*, or start it from the Irodori Audio add-on. The first start loads the model and takes about half a minute. |
| The language model is not installed | Press *Download qwen3:8b* (Ollama must be installed and running). |
| It makes fewer sentences than asked | The model had to throw some away (unknown words, unnatural). Make another batch. A small word list gives fewer valid sentences. |
| Some sentences are odd | The language model is small. Try a bigger one (Ollama `gemma3:12b`, `qwen3:14b`) if your card has room, or an online service. |
| It is slow | The sentences are written first (a few seconds), then spoken one by one (a few seconds each on a graphics card, much longer on the processor). |

The log is in `%APPDATA%\ListeningPracticeCompanion\companion.log` (*Open the log*).

## Running from source, headless

```powershell
git clone https://github.com/mattias/listening-practice-companion
cd listening-practice-companion
uv venv; uv pip install -e ".[dev]"
.venv\Scripts\python -m companion          # the window
.venv\Scripts\python -m companion serve    # no window: runs until Ctrl+C and prints the token
.venv\Scripts\python -m pytest             # tests
.venv\Scripts\python build.py              # dist\ListeningPracticeCompanion.exe
```

Settings are in `%APPDATA%\ListeningPracticeCompanion\config.json` (`~/.config/listening-practice-companion/config.json` on Linux). The service's API is in [`docs/api.md`](docs/api.md).

## Credits and licenses

Code: MIT. [Irodori-TTS](https://github.com/Aratako/Irodori-TTS) (MIT; see the model card for its usage restrictions), [Ollama](https://ollama.com), [Janome](https://github.com/mocobeta/janome) with IPADIC for the Japanese analysis, [FastAPI](https://fastapi.tiangolo.com).
