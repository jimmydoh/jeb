### 1. Root / Core Manager

*Note: In `core_manager.py`, several of these are called without folder paths (e.g., `self.audio.play("fail.wav")`), meaning they are expected to be in the absolute root directory of your SD card.*

* `system_reset.wav`
* `background_winddown.wav`
* `alarm_klaxon.wav`
* `voice_meltdown.wav`
* `link_restored.wav`
* `link_lost.wav`
* `fail.wav`

### 2. Common & Menu Elements

**`audio/common/`** *(Pre-loaded into RAM on boot)*

* `audio/common/menu_tick.wav`
* `audio/common/menu_select.wav`

**`audio/menu/`** *(Main Menu UI)*

* `audio/menu/open.wav`
* `audio/menu/close.wav`
* `audio/menu/tick.wav`
* `audio/menu/select.wav`
* `audio/menu/power.wav`

### 3. General Gameplay

**`audio/general/`** *(Shared across Emoji Reveal, Pong, etc.)*

* `audio/general/correct.wav`
* `audio/general/fail.wav`
* `audio/general/win.wav`

### 4. Industrial Startup Mode (`audio/ind/`)

**Atmosphere:**

* `audio/ind/atmo/hum_1.wav`
* `audio/ind/atmo/hum_2.wav`
* `audio/ind/atmo/hum_3.wav`
* `audio/ind/atmo/hum_alarm.wav`
* `audio/ind/atmo/hum_final.wav`

**Sound Effects:**

* `audio/ind/sfx/power_up.wav`
* `audio/ind/sfx/toggle_confirm.wav`
* `audio/ind/sfx/toggle_error.wav`
* `audio/ind/sfx/keypad_click.wav`
* `audio/ind/sfx/fail.wav`
* `audio/ind/sfx/success.wav`
* `audio/ind/sfx/target_shift.wav`
* `audio/ind/sfx/crash.wav`

**Voice Lines:**

* `audio/ind/voice/narration_0.wav`
* `audio/ind/voice/narration_1.wav`
* `audio/ind/voice/narration_2.wav`
* `audio/ind/voice/narration_3.wav`
* `audio/ind/voice/narration_4.wav`
* `audio/ind/voice/narration_balance.wav`
* `audio/ind/voice/narration_fail.wav`
* `audio/ind/voice/narration_success.wav`
* `audio/ind/voice/toggle_done.wav`
* `audio/ind/voice/keypad_go.wav`
* `audio/ind/voice/keypad_retry.wav`
* *Dynamic Voice Lines:*
* `audio/ind/voice/latch_0.wav` through `audio/ind/voice/latch_3.wav` (4 files)
* `audio/ind/voice/momentary_4_U.wav` and `audio/ind/voice/momentary_4_D.wav` (2 files)
* `audio/ind/voice/v_0.wav` through `audio/ind/voice/v_9.wav` (10 files)



### 5. Safe Cracker Mode (`audio/safe/`)

* `audio/safe/voice/welcome.wav`
* `audio/safe/sfx/crash.wav`
* `audio/safe/sfx/tick.wav`
* `audio/safe/sfx/thump.wav`

### 6. Simon Mode (`audio/simon/`)

* `audio/simon/tooslow.wav`

### 7. Rhythm Mode (`/sd/data/rhythm/`)

* `<song_name>.wav` *(This mode scans this directory dynamically, so you can drop any matching `.wav` / `.json` beatmap pairs here).*
