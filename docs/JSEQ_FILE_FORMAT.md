# `.jseq` Audio Sequence Format Specification

The `.jseq` (JEB Sequence) file is a lightweight, custom binary format designed for the JEB Audio Studio. It stores multi-channel, variable-duration chiptune sequences for playback on the hardware synthesizer.

**Endianness:** All multi-byte integers (16-bit) are stored in **Little-Endian** format.
**Encoding:** Raw Binary (No text encoding)

---

## 1. Global Header (8 Bytes)

Every `.jseq` file begins with an 8-byte global header that defines the sequence parameters.

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `0x00` - `0x03` | `char[]` | 4 bytes | **Magic Bytes:** `JSEQ` (`0x4A`, `0x53`, `0x45`, `0x51`) |
| `0x04`      | `uint8` | 1 byte  | **Format Version:** `0x01` (v1) or `0x02` (v2) |
| `0x05` - `0x06` | `uint16`| 2 bytes | **BPM:** Playback speed in Beats Per Minute |
| `0x07`      | `uint8` | 1 byte  | **Channel Count:** Number of audio channels (typically `3`) |

The `SynthManager` reads byte `0x04` at load time and routes the file to the
appropriate parser — v1 files continue to work unchanged.

---

## 2. V1 Channel Data Blocks

*(Used when Format Version = `0x01`.)*

Immediately following the global header are the channel data blocks. There will be exactly `Channel Count` blocks appended consecutively.

### 2.1 V1 Channel Header (3 Bytes)

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Patch Index:** The synthesizer instrument map (See Patch Table) |
| `+0x01` - `0x02`| `uint16`| 2 bytes | **Step Count (`N`):** The number of note/rest events in this channel |

### 2.2 V1 Sequence Steps (`N` × 2 Bytes)

Following each Channel Header is an array of steps. Every step consists of a 2-byte pair defining the pitch and the exact duration of the event.

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Pitch Index:** `0` = Rest, `1-255` = MIDI Note Offset |
| `+0x01`     | `uint8` | 1 byte  | **Duration:** Time value measured in `1/32nd` beat units |

*(Note: If a channel has 16 steps, its Sequence Steps block will be 32 bytes long).*

---

## 3. V2 Channel Data Blocks

*(Used when Format Version = `0x02`.)*

V2 extends the channel header to support **Track Types** and **Inline ADSR Overrides**, while keeping the 2-byte step pair format.

### 3.1 V2 Channel Header (5–9 Bytes)

The first byte (`+0x00`) has a **dual purpose** depending on Track Type:

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Audio:** Patch Index (see §4.1). **Automation:** Target Scope — `0x00`–`0x0F` targets a specific Audio channel by index (0-based); `0xFF` targets the Global Master Bus |
| `+0x01`     | `uint8` | 1 byte  | **Track Type:** `0x00` = Audio, `0x01` = Automation |
| `+0x02`     | `uint8` | 1 byte  | **Override Flag:** `0x00` = no override, `0x01` = ADSR multipliers follow *(Audio only; always `0x00` for Automation)* |
| `+0x03`–`+0x06` | `uint8[4]` | 4 bytes | *(only if Override Flag = `0x01`)* **ADSR Multipliers:** `[Attack, Decay, Sustain, Release]` — each value ÷ 100 = float multiplier (e.g. `100` = 1.0×, `200` = 2.0×, `50` = 0.5×) |
| `+N, +N+1`  | `uint16` | 2 bytes | **Step Count:** Number of step pairs (little-endian) |

> **Global Channel Count:** The `num_channels` byte in the Global Header is the
> total of all tracks — Audio **and** Automation combined.  The `SynthManager`
> assigns a `channel_idx` (0-based, Audio tracks only) to each Audio channel as
> they are parsed, so that Automation channels with a matching `Target Scope` can
> apply per-channel filters or amplitude changes without touching other outputs.

### 3.2 V2 Audio Track Steps (`N` × 2 Bytes)

Audio tracks use the same 2-byte step pair as v1, extended with a **Meta-Event** marker:

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Pitch Index:** `0` = Rest, `1`–`254` = MIDI Note Offset, `255` = **Meta-Event** |
| `+0x01`     | `uint8` | 1 byte  | **Duration / Command Payload:** duration units for normal notes; new BPM value when Pitch Index = `255` |

#### Meta-Events (Pitch Index = `0xFF`)

When byte `+0x00` of a step is `0xFF`, the step is a **Meta-Event** rather than a
note.  The second byte (`+0x01`) is interpreted as a **Command Payload**:

| Payload value | Meaning |
| :--- | :--- |
| `1`–`255` | **BPM Change** — sets playback speed to this new BPM for all subsequent notes |

The parser converts meta-events to `(None, new_bpm)` tuples in the sequence
list so that `play_sequence()` can update `beat_duration` on the fly without
any structural changes to the playback loop.

### 3.3 V2 Automation Track Steps (`N` × 2 Bytes)

For **Automation** channels (`Track Type = 0x01`), the step payload is
re-purposed as a parameter modulation value:

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Target Parameter ID** |
| `+0x01`     | `uint8` | 1 byte  | **Modulation Value** (0–255) |

Each automation step fires at a **1/32-beat interval** (matching the finest
audio note resolution), so 32 automation steps cover exactly 1 beat.

#### Target Scope Routing (Header Byte `+0x00`)

| Scope value | Effect |
| :---------- | :----- |
| `0x00`–`0x0F` | Apply to a **specific Audio channel** (index = value).  For LPF, the Biquad filter is stored per-note via `synthio.Note.filter`.  For Amplitude, envelope levels are scaled for that channel only. |
| `0xFF` | Apply to the **Global Master Bus** via `synth.filter` (LPF) or `_automation_amplitude` (Amplitude).  All audio output is affected. |

#### Automation Parameter IDs

| ID     | Symbol                  | Mapping |
| :----- | :---------------------- | :------ |
| `0x00` | `JSEQ_PARAM_LPF_CUTOFF` | Low-Pass Filter cutoff: `value / 255 × 20 000 Hz` |
| `0x01` | `JSEQ_PARAM_AMPLITUDE`  | Note amplitude: `value / 255` (0.0–1.0) |

---

## 4. Data Value Mappings

### 4.1 Patch Index Table
The `uint8` Patch Index maps to the following string constants in the synth engine:
* `0` = `RETRO_LEAD`
* `1` = `RETRO_BASS`
* `2` = `RETRO_NOISE`
* `3` = `BEEP`
* `4` = `BEEP_SQUARE`
* `5` = `PAD`
* `6` = `PUNCH`
* `7` = `ALARM`
* `8` = `SCANNER`
* `9` = `CLICK`
* `10` = `NOISE`
* `11` = `SELECT`
* `12` = `DATA_STREAM`
* `13` = `ETHEREAL`
* `14` = `ENGINE_HUM`
* `15` = `TEXT_SCROLL`
* `16` = `SUCCESS`
* `17` = `ERROR`

### 4.2 Pitch Math (MIDI Offset)
To save space and align with standard MIDI numbering, pitch is calculated using standard octaves (`C-1` to `G9`).
* **Rest:** A pitch value of `0` is always a Rest (silence).
* **Note Formula:** `Pitch Index = ((Octave + 1) * 12) + Semitone + 1`
* *Example (C4):* Octave `4`, Semitone `0` (C). `((4 + 1) * 12) + 0 + 1 = 61`.
* **V2 Meta-Event:** Pitch value `255` (`0xFF`) is reserved as a meta-event marker.

### 4.3 Duration Math
To support sub-beat timing (like 1/16th and 1/32nd notes) as an integer, the duration byte represents units of `1/32nd` of a beat.
* **Max Value:** `255` (approx 7.96 beats). Gaps larger than this are split into consecutive rest blocks.
* **Beat Formula:** `Total Beats = Duration Byte / 32.0`
* *Examples:* * `1` beat (Quarter note) = `32`
  * `0.5` beats (Eighth note) = `16`
  * `0.25` beats (Sixteenth note) = `8`
  * `4.0` beats (Whole note / Chunked rest) = `128`

### 4.4 V2 ADSR Multiplier Math
The four override bytes each represent a **floating-point multiplier** encoded as an integer.
* **Formula:** `float_multiplier = byte_value / 100.0`
* `100` = no change (1.0×)
* `200` = double (2.0×)
* `50`  = halve (0.5×)
* `0`   = zero out (0.0×) — e.g. removes attack ramp entirely

Sustain level is additionally clamped to `[0.0, 1.0]` after multiplication.

---

## 5. Backwards Compatibility

Because the Format Version is explicitly declared at byte `0x04`, migration is
completely non-destructive:

1. `SynthManager.load_jseq()` reads the 8-byte global header.
2. If `version == 1`, it executes the legacy byte-parsing logic (`_load_jseq_v1`).
3. If `version == 2`, it utilises the expanded feature set (`_load_jseq_v2`).
4. Any other version raises `ValueError`.

All existing `.jseq` v1 files continue to play correctly without modification.
