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
| `0x04`      | `uint8` | 1 byte  | **Format Version:** Currently `0x01` |
| `0x05` - `0x06` | `uint16`| 2 bytes | **BPM:** Playback speed in Beats Per Minute |
| `0x07`      | `uint8` | 1 byte  | **Channel Count:** Number of audio channels (typically `3`) |

---

## 2. Channel Data Blocks

Immediately following the global header are the channel data blocks. There will be exactly `Channel Count` blocks appended consecutively.

### 2.1 Channel Header (3 Bytes)

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Patch Index:** The synthesizer instrument map (See Patch Table) |
| `+0x01` - `0x02`| `uint16`| 2 bytes | **Step Count (`N`):** The number of note/rest events in this channel |

### 2.2 Sequence Steps (`N` × 2 Bytes)

Following each Channel Header is an array of steps. Every step consists of a 2-byte pair defining the pitch and the exact duration of the event.

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00`     | `uint8` | 1 byte  | **Pitch Index:** `0` = Rest, `1-255` = MIDI Note Offset |
| `+0x01`     | `uint8` | 1 byte  | **Duration:** Time value measured in `1/32nd` beat units |

*(Note: If a channel has 16 steps, its Sequence Steps block will be 32 bytes long).*

---

## 3. Data Value Mappings

### 3.1 Patch Index Table
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

### 3.2 Pitch Math (MIDI Offset)
To save space and align with standard MIDI numbering, pitch is calculated using standard octaves (`C-1` to `G9`).
* **Rest:** A pitch value of `0` is always a Rest (silence).
* **Note Formula:** `Pitch Index = ((Octave + 1) * 12) + Semitone + 1`
* *Example (C4):* Octave `4`, Semitone `0` (C). `((4 + 1) * 12) + 0 + 1 = 61`.

### 3.3 Duration Math
To support sub-beat timing (like 1/16th and 1/32nd notes) as an integer, the duration byte represents units of `1/32nd` of a beat.
* **Max Value:** `255` (approx 7.96 beats). Gaps larger than this are split into consecutive rest blocks.
* **Beat Formula:** `Total Beats = Duration Byte / 32.0`
* *Examples:* * `1` beat (Quarter note) = `32`
  * `0.5` beats (Eighth note) = `16`
  * `0.25` beats (Sixteenth note) = `8`
  * `4.0` beats (Whole note / Chunked rest) = `128`
