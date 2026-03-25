# File: src/managers/synth_manager.py
"""
Manager for Generative Audio using synthio.
"""

import asyncio
import random
import synthio
from utilities.logger import JEBLogger
from utilities.synth_registry import Patches, Waveforms
from utilities.tones import note

# Ordered patch name list for .jseq file encoding.
# Index must stay in sync with the Audio Studio web UI.
JSEQ_PATCH_NAMES = [
    'RETRO_LEAD', 'RETRO_BASS', 'RETRO_NOISE',
    'BEEP', 'BEEP_SQUARE', 'PAD', 'PUNCH',
    'ALARM', 'SCANNER', 'CLICK', 'NOISE', 'SELECT',
    'DATA_STREAM', 'ETHEREAL', 'ENGINE_HUM',
    'TEXT_SCROLL', 'SUCCESS', 'ERROR',
]


def _jseq_midi_to_freq(midi_note):
    """Convert a MIDI note number (0-127) to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))

# JSEQ v2 Automation parameter IDs.
JSEQ_PARAM_LPF_CUTOFF = 0x00   # Low-pass filter cutoff (0-255 → 0–20 000 Hz)
JSEQ_PARAM_AMPLITUDE  = 0x01   # Note amplitude        (0-255 → 0.0–1.0)

# JSEQ v2 meta-event pitch marker.
JSEQ_META_EVENT = 0xFF  # pitch_idx value that marks a meta-event step

class SynthManager:
    """
    A reusable SynthIO engine.
    Can be instantiated for Hi-Fi (I2S) or Lo-Fi (PWM/Piezo).
    """

    def __init__(self, sample_rate=22050, channel_count=1, waveform_override=None, root_data_dir="/"):
        JEBLogger.info("SYNTH", f"[INIT] SynthManager - sample_rate: {sample_rate}, channel_count: {channel_count}, waveform_override: {waveform_override}")
        self.override = waveform_override
        self.root_data_dir = root_data_dir

        # Create the synthesizer object
        # mode=synthio.Mode.POLYPHONIC allows multiple notes at once
        self.synth = synthio.Synthesizer(sample_rate=sample_rate, channel_count=channel_count)

        # Background chiptune sequencer task handle
        self._chiptune_task = None

        # RAM cache for explicitly preloaded .jseq files
        self._jseq_cache = {}

        # V2 automation state: global and per-channel amplitude/filter values.
        # These are updated by _apply_automation() and consumed when new notes
        # are pressed via play_sequence().
        self._automation_amplitude = 1.0           # global amplitude scale (0xFF scope)
        self._channel_filters = {}                 # audio_ch_idx → synthio.Biquad or None
        self._channel_amplitudes = {}              # audio_ch_idx → float 0.0–1.0

    @property
    def source(self):
        """Returns the synth object to be fed into AudioMixer."""
        return self.synth

    def preload(self, files):
        """
        Reads a .jseq file from the SD card and stores the parsed sequence in RAM.
        Call this during system boot for UI sounds to prevent SD card read latency.
        """
        for filename in files:
            filepath = f"{self.root_data_dir}{filename}"
            try:
                if filepath not in self._jseq_cache:
                    # load_jseq will handle the file I/O and parsing
                    channels_data = self.load_jseq(filepath)
                    if channels_data:
                        self._jseq_cache[filepath] = channels_data
                        JEBLogger.info("SYNTH", f"Preloaded JSEQ to RAM: {filepath}")
            except Exception as e:
                JEBLogger.error("SYNTH", f"Failed to preload JSEQ '{filepath}': {e}")

    def play_note(self, frequency, patch=None, duration=None):
        """
        Trigger a note.

        Args:
            frequency (float): Frequency in Hz.
            patch (dict): The synth patch to use.
            duration (float): If set, note auto-releases after seconds.
                              If None, note holds until stop_note is called.
        """
        active_patch = patch or Patches.SELECT

        if isinstance(active_patch, str):
            active_patch = getattr(Patches, active_patch, Patches.SELECT)

        JEBLogger.debug("SYNTH", f"Playing note - Frequency: {frequency}, Duration: {duration}, Patch: {active_patch['name']}")

        wave = self.override if self.override else active_patch["wave"]

        # Create the note object
        # We assume standard amplitude; ADSR handles the rest
        n = synthio.Note(
            frequency=frequency,
            waveform=wave,
            envelope=active_patch["envelope"]
        )

        # Press the note (start playing)
        self.synth.press(n)

        if duration:
            # If duration is provided, schedule the release
            asyncio.create_task(self._auto_release(n, duration))

        return n

    def stop_note(self, note_obj):
        """Stops a specific note object."""
        self.synth.release(note_obj)

    def release_all(self):
        """Immediately stops all playing notes."""
        self.synth.release_all()

    async def _auto_release(self, note_obj, duration):
        """Background task to release a note after duration."""
        await asyncio.sleep(duration)
        self.synth.release(note_obj)

    async def play_sequence(self, sequence_data, patch=None):
        """
        Play a sequence of notes defined in Tones format.

        Supports JSEQ v2 features:
        - ``envelope_override``: a pre-built synthio.Envelope in the channel dict
          that replaces the patch's default ADSR envelope.
        - Meta-events: a step of ``(None, new_bpm)`` signals a real-time BPM change
          mid-sequence (Pitch Index 255 in the binary format).
        - Per-channel automation routing: if the channel dict carries a
          ``'channel_idx'`` key, per-channel filters (``_channel_filters``) and
          per-channel amplitude overrides (``_channel_amplitudes``) are applied
          in addition to — or instead of — the global automation state.

        Args:
            sequence_data (dict): Dict with 'bpm' and 'sequence' list.
            patch (dict): The synth patch to use.
        """
        bpm = sequence_data.get('bpm', 120)
        beat_duration = 60.0 / bpm

        # channel_idx is set by _load_jseq_v2 for per-channel automation routing.
        channel_idx = sequence_data.get('channel_idx', None)

        # LOGIC UPDATE:
        # sequence_data.get('patch') -> Returns Patch Object or None
        # patch -> Returns Patch Object or None
        # Patches.SELECT -> The guaranteed fallback
        active_patch = patch or sequence_data.get('patch') or Patches.SELECT

        if isinstance(active_patch, str):
            active_patch = getattr(Patches, active_patch, Patches.SELECT)

        JEBLogger.debug("SYNTH", f"Playing sequence - BPM: {bpm}, Patch: {active_patch['name']}, Override Waveform: {self.override}")

        wave = self.override if self.override else active_patch["wave"]

        # V2: use inline ADSR override envelope if provided, else patch default.
        envelope = sequence_data.get('envelope_override') or active_patch["envelope"]

        for item in sequence_data['sequence']:
            # Handle both (freq, dur) and ('NoteName', dur) formats
            tone_val, duration_beats = item

            # V2 meta-event: (None, new_bpm) signals a dynamic BPM change.
            if tone_val is None:
                bpm = duration_beats
                beat_duration = 60.0 / bpm
                JEBLogger.debug("SYNTH", f"Meta-event: BPM changed to {bpm}")
                continue

            if isinstance(tone_val, (int, float)):
                freq = tone_val
            else:
                freq = note(tone_val)
            duration_sec = duration_beats * beat_duration

            if freq > 0:
                # V2: determine effective amplitude.
                # Per-channel amplitude (from automation targeting this channel)
                # takes precedence over the global _automation_amplitude.
                if channel_idx is not None and channel_idx in self._channel_amplitudes:
                    amplitude = self._channel_amplitudes[channel_idx]
                else:
                    amplitude = self._automation_amplitude

                # Scale the envelope if automation has changed the amplitude.
                # Use a threshold rather than exact float equality to avoid
                # floating-point precision issues.
                active_envelope = envelope
                if abs(amplitude - 1.0) > 0.001 and hasattr(envelope, 'attack_time'):
                    active_envelope = synthio.Envelope(
                        attack_time=envelope.attack_time,
                        decay_time=envelope.decay_time,
                        sustain_level=envelope.sustain_level * amplitude,
                        release_time=envelope.release_time,
                        attack_level=envelope.attack_level * amplitude,
                    )

                n = synthio.Note(
                    frequency=freq,
                    waveform=wave,
                    envelope=active_envelope
                )

                # V2: apply per-channel Biquad filter to the note object if one
                # has been set by a concurrent automation task targeting this
                # specific channel index.
                if channel_idx is not None and channel_idx in self._channel_filters:
                    try:
                        n.filter = self._channel_filters[channel_idx]
                    except AttributeError:
                        pass  # Graceful degradation for CircuitPython versions without per-note filter

                self.synth.press(n)
                await asyncio.sleep(duration_sec)
                self.synth.release(n)
            else:
                # Rest
                await asyncio.sleep(duration_sec)

            # Small gap between notes for articulation
            await asyncio.sleep(0.01)

    async def start_generative_drone(self):
        """Creates an infinite, shifting background drone."""
        # Frequencies for a C Minor chord (C3, Eb3, G3)
        # We detune them slightly for a 'chorus' effect
        freqs = [130.81, 155.56, 196.00]

        while True:
            # Pick a random note from the chord
            f = random.choice(freqs)

            # Jitter the frequency slightly (+/- 2 Hz) for analog realism
            f_jitter = f + random.uniform(-2, 2)

            # Play it using the ENGINE_HUM patch
            # Duration is random between 3 and 6 seconds
            duration = random.uniform(3.0, 6.0)

            # Fire and forget (the auto_release handles cleanup)
            self.play_note(f_jitter, Patches.ENGINE_HUM, duration)

            # Wait a bit before layering the next note
            # Overlapping notes creates chords
            await asyncio.sleep(random.uniform(2.0, 4.0))

    async def _run_chiptune_channel(self, sequence_data, patch=None):
        """Runs a single chiptune channel in a loop until cancelled."""
        try:
            while True:
                await self.play_sequence(sequence_data, patch=patch)
        except asyncio.CancelledError:
            raise

    async def _run_chiptune_sequencer(self, channels):
        """Runs all chiptune channels concurrently using asyncio.gather."""
        tasks = []
        if 'melody' in channels:
            tasks.append(self._run_chiptune_channel(channels['melody'], Patches.RETRO_LEAD))
        if 'bass' in channels:
            tasks.append(self._run_chiptune_channel(channels['bass'], Patches.RETRO_BASS))
        if 'noise' in channels:
            tasks.append(self._run_chiptune_channel(channels['noise'], Patches.get_retro_noise_patch()))
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.release_all()
            raise

    def start_chiptune_sequencer(self, channels):
        """Starts a 3-channel chiptune sequencer as a background asyncio task.

        Args:
            channels (dict): Channel data with optional keys:
                'melody': sequence_data dict (Square wave lead, RETRO_LEAD patch)
                'bass':   sequence_data dict (Triangle wave bass, RETRO_BASS patch)
                'noise':  sequence_data dict (Noise percussion, RETRO_NOISE patch)

        Returns:
            asyncio.Task: The running task, which can be cancelled to stop playback.
        """
        self.stop_chiptune()
        self._chiptune_task = asyncio.create_task(self._run_chiptune_sequencer(channels))
        return self._chiptune_task

    def stop_chiptune(self):
        """Stops the chiptune sequencer and silences all active notes."""
        if self._chiptune_task and not self._chiptune_task.done():
            self._chiptune_task.cancel()
        self._chiptune_task = None
        self.release_all()

    def load_jseq(self, filepath):
        """Load a .jseq binary sequence file and return a list of channel dicts.

        Supports both JSEQ v1 and v2 format files.  The format version is read
        from byte ``0x04`` of the global header and the appropriate parser is
        selected automatically, preserving full backwards compatibility with all
        existing v1 files.

        Each returned dict has at minimum a ``'type'`` key:

        * **Audio channel** (``type == 'audio'``): also contains ``'bpm'``,
          ``'patch'``, ``'sequence'``, and (v2 only) an optional
          ``'envelope_override'`` key.
        * **Automation channel** (``type == 'automation'``): contains ``'bpm'``
          and ``'steps'`` — a list of ``(param_id, value)`` tuples.

        Args:
            filepath (str): Path to the .jseq file.

        Returns:
            list: List of channel dicts.

        Raises:
            ValueError: If the file has an invalid format or unsupported version.
        """
        # Return instantly if the sequence is cached in RAM
        if filepath in self._jseq_cache:
            return self._jseq_cache[filepath]

        # Otherwise, perform the standard SD card read
        with open(filepath, 'rb') as f:
            data = f.read()

        if len(data) < 8 or data[:4] != b'JSEQ':
            raise ValueError("Invalid or unsupported .jseq file format")

        version = data[4]
        if version == 1:
            return self._load_jseq_v1(data)
        elif version == 2:
            return self._load_jseq_v2(data)
        else:
            raise ValueError("Invalid or unsupported .jseq file format")

    def _load_jseq_v1(self, data):
        """Parse a JSEQ v1 binary payload and return a list of channel dicts."""
        bpm = data[5] | (data[6] << 8)
        num_channels = data[7]

        channels = []
        pos = 8
        for _ in range(num_channels):
            if pos + 3 > len(data):
                break
            patch_idx = data[pos]
            note_count = data[pos + 1] | (data[pos + 2] << 8)
            pos += 3

            patch_name = JSEQ_PATCH_NAMES[patch_idx] if 0 <= patch_idx < len(JSEQ_PATCH_NAMES) else 'SELECT'
            patch = getattr(Patches, patch_name, Patches.SELECT)

            sequence = []
            for _ in range(note_count):
                if pos + 2 > len(data):
                    break
                note_idx = data[pos]
                dur_units = data[pos + 1]
                pos += 2

                freq = 0 if note_idx == 0 else _jseq_midi_to_freq(note_idx - 1)
                duration_beats = dur_units / 32.0
                sequence.append((freq, duration_beats))

            channels.append({'bpm': bpm, 'patch': patch, 'sequence': sequence, 'type': 'audio'})

        return channels

    def _load_jseq_v2(self, data):
        """Parse a JSEQ v2 binary payload and return a list of channel dicts.

        V2 channel header layout (variable size):

        +---------+-----------------+-------------------------------------------+
        | Byte(s) | Field           | Description                               |
        +=========+=================+===========================================+
        | 0       | scope_or_patch  | Audio: patch index.                       |
        |         |                 | Automation: target scope                  |
        |         |                 |   0x00–0x0F = specific audio channel idx  |
        |         |                 |   0xFF      = Global Master Bus           |
        | 1       | track_type      | 0x00 = Audio, 0x01 = Automation           |
        | 2       | ovr_flag        | 0x01 = ADSR multiplier bytes follow (Audio|
        |         |                 | only), else 0                             |
        | 3–6     | adsr_mult       | (only if ovr_flag=1) Attack/Decay/Sustain |
        |         |                 | /Release multipliers, each ÷100 = scale   |
        | N, N+1  | step_count      | Number of step pairs (little-endian u16)  |
        +---------+-----------------+-------------------------------------------+

        Audio step (2 bytes):  ``[pitch_idx, dur_units]``
          * ``pitch_idx == 0``   → rest
          * ``pitch_idx == 255`` → meta-event; ``dur_units`` = new BPM value
          * otherwise            → MIDI note = ``pitch_idx - 1``

        Automation step (2 bytes):  ``[param_id, value]``
          * param_id ``0x00`` = LPF cutoff  (0–255 → 0–20 000 Hz)
          * param_id ``0x01`` = amplitude   (0–255 → 0.0–1.0)

        The total channel count in the global header includes all tracks
        (Audio + Automation combined).  Audio channels receive a
        ``'channel_idx'`` key (0-based count among Audio tracks only) so
        that concurrent Automation tasks can target them by index.
        """
        bpm = data[5] | (data[6] << 8)
        num_channels = data[7]

        channels = []
        pos = 8
        audio_channel_idx = 0   # counts Audio channels only; used as channel_idx key
        for _ in range(num_channels):
            # Minimum channel header: patch(1) + track_type(1) + ovr_flag(1) + step_count(2)
            if pos + 5 > len(data):
                break

            scope_or_patch = data[pos]            # reinterpreted per track_type below
            track_type     = data[pos + 1]        # 0=audio, 1=automation
            ovr_flag       = data[pos + 2]        # 0=no override, 1=ADSR multipliers follow
            pos += 3

            # Optional inline ADSR override bytes
            envelope_override = None
            if ovr_flag == 1:
                if pos + 4 > len(data):
                    break
                adsr = (data[pos], data[pos + 1], data[pos + 2], data[pos + 3])
                pos += 4
                patch_name = JSEQ_PATCH_NAMES[scope_or_patch] if 0 <= scope_or_patch < len(JSEQ_PATCH_NAMES) else 'SELECT'
                base_patch = getattr(Patches, patch_name, Patches.SELECT)
                envelope_override = self._apply_adsr_multipliers(base_patch['envelope'], adsr)

            # Step count (2 bytes LE)
            if pos + 2 > len(data):
                break
            step_count = data[pos] | (data[pos + 1] << 8)
            pos += 2

            if track_type == 0x01:
                # Automation channel: scope_or_patch byte is the target_scope.
                #   0x00–0x0F → target a specific audio channel by index
                #   0xFF      → target the global master bus
                target_scope = scope_or_patch
                steps = []
                for _ in range(step_count):
                    if pos + 2 > len(data):
                        break
                    param_id = data[pos]
                    value    = data[pos + 1]
                    pos += 2
                    steps.append((param_id, value))
                channels.append({
                    'bpm': bpm,
                    'type': 'automation',
                    'target_scope': target_scope,
                    'steps': steps,
                })
            else:
                # Audio channel (default): scope_or_patch byte is the patch index.
                patch_name = JSEQ_PATCH_NAMES[scope_or_patch] if 0 <= scope_or_patch < len(JSEQ_PATCH_NAMES) else 'SELECT'
                patch = getattr(Patches, patch_name, Patches.SELECT)
                sequence = []
                for _ in range(step_count):
                    if pos + 2 > len(data):
                        break
                    note_idx  = data[pos]
                    dur_units = data[pos + 1]
                    pos += 2

                    if note_idx == JSEQ_META_EVENT:
                        # Meta-event: second byte = new BPM value
                        sequence.append((None, dur_units))
                    else:
                        freq = 0 if note_idx == 0 else _jseq_midi_to_freq(note_idx - 1)
                        duration_beats = dur_units / 32.0
                        sequence.append((freq, duration_beats))

                ch = {
                    'bpm': bpm,
                    'patch': patch,
                    'sequence': sequence,
                    'type': 'audio',
                    'channel_idx': audio_channel_idx,  # used by _apply_automation per-channel routing
                }
                if envelope_override is not None:
                    ch['envelope_override'] = envelope_override
                channels.append(ch)
                audio_channel_idx += 1

        return channels

    def _apply_adsr_multipliers(self, base_envelope, multipliers):
        """Return a new synthio.Envelope with ADSR values scaled by *multipliers*.

        Each multiplier is an integer in the range 0–255 where ``100`` equals
        1.0× (no change).  Attack, Decay, and Release times are multiplied
        directly; Sustain level is multiplied and clamped to [0.0, 1.0].

        Args:
            base_envelope: The ``synthio.Envelope`` whose values are the base.
            multipliers (tuple): Four integers ``(attack, decay, sustain, release)``.

        Returns:
            A new ``synthio.Envelope`` with the adjusted ADSR values.
        """
        a_mult = multipliers[0] / 100.0
        d_mult = multipliers[1] / 100.0
        s_mult = multipliers[2] / 100.0
        r_mult = multipliers[3] / 100.0
        return synthio.Envelope(
            # Time values are not clamped to a maximum: synthio accepts any
            # non-negative float, so arbitrarily long attack/decay/release times
            # are valid. A multiplier of 0 produces an instant (0-second) stage.
            attack_time=base_envelope.attack_time * a_mult,
            decay_time=base_envelope.decay_time * d_mult,
            # Sustain level is a 0.0–1.0 amplitude fraction; cap it to avoid
            # over-driving the synthesizer output.
            sustain_level=min(1.0, base_envelope.sustain_level * s_mult),
            release_time=base_envelope.release_time * r_mult,
            attack_level=base_envelope.attack_level,
        )

    def _apply_automation(self, param_id, value, target_channel=0xFF):
        """Apply a single automation step to the live synth engine.

        Routes the parameter change to either a specific audio channel or the
        global synthesizer output depending on *target_channel*:

        * ``target_channel == 0xFF`` (255) — Global Master Bus.  The Biquad
          filter is applied to ``self.synth.filter`` (all output); the
          amplitude is stored in ``self._automation_amplitude``.
        * ``target_channel 0–15`` — Per-channel scope.  The Biquad filter is
          stored in ``self._channel_filters[target_channel]`` so that the next
          note pressed by the matching ``play_sequence`` task picks it up via
          ``n.filter``.  The amplitude is stored in
          ``self._channel_amplitudes[target_channel]``.

        Args:
            param_id (int):       Target parameter identifier (0x00 or 0x01).
            value (int):          Raw modulation value (0–255).
            target_channel (int): Audio channel index (0–15) or 0xFF for global.
        """
        if param_id == JSEQ_PARAM_LPF_CUTOFF:
            cutoff_hz = (value / 255.0) * 20000.0
            JEBLogger.debug("SYNTH", f"Automation LPF: {cutoff_hz:.1f} Hz -> scope={target_channel:#04x}")
            try:
                lpf = synthio.Biquad(synthio.FilterMode.LOW_PASS, cutoff_hz, 0.7071)
                if target_channel == 0xFF:
                    # Global master bus filter
                    self.synth.filter = lpf
                else:
                    # Per-channel: stored and applied when notes are pressed
                    self._channel_filters[target_channel] = lpf
            except AttributeError:
                JEBLogger.debug("SYNTH", "Biquad filter not available; skipping LPF automation")
        elif param_id == JSEQ_PARAM_AMPLITUDE:
            level = value / 255.0
            JEBLogger.debug("SYNTH", f"Automation amplitude: {level:.3f} -> scope={target_channel:#04x}")
            if target_channel == 0xFF:
                self._automation_amplitude = level
            else:
                self._channel_amplitudes[target_channel] = level
        else:
            JEBLogger.debug("SYNTH", f"Automation: unknown param_id={param_id:#04x}, scope={target_channel:#04x}")

    async def _play_automation(self, channel_data):
        """Play a v2 Automation channel by advancing through its steps.

        Each step fires at 1/32-beat intervals (the finest note resolution),
        matching the timing grid of concurrent audio channels.

        The ``'target_scope'`` key in *channel_data* determines routing:
        ``0xFF`` applies changes globally; ``0``–``15`` targets a specific
        audio channel (per-note ``filter`` / ``_channel_amplitudes``).

        Args:
            channel_data (dict): Channel dict with ``'bpm'``, ``'steps'``, and
                optional ``'target_scope'`` keys, as returned by
                ``_load_jseq_v2``.
        """
        bpm = channel_data.get('bpm', 120)
        target_scope = channel_data.get('target_scope', 0xFF)
        step_duration = (60.0 / bpm) / 32.0   # 1/32 of a beat in seconds

        for param_id, value in channel_data.get('steps', []):
            self._apply_automation(param_id, value, target_scope)
            await asyncio.sleep(step_duration)

    async def play_jseq(self, filepath):
        """Load and play a .jseq file, running all channels concurrently.

        Supports both JSEQ v1 and v2 files.  For v2 files, Automation channels
        are played via :meth:`_play_automation` while Audio channels use the
        standard :meth:`play_sequence` path.

        Args:
            filepath (str): Path to the .jseq file on the filesystem.
        """
        channels_data = self.load_jseq(filepath)
        if not channels_data:
            return
        tasks = []
        for ch in channels_data:
            if ch.get('type') == 'automation':
                tasks.append(asyncio.create_task(self._play_automation(ch)))
            else:
                tasks.append(asyncio.create_task(self.play_sequence(ch)))
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.release_all()
            raise

    def start_jseq(self, filepath):
        """Non-blocking playback of a .jseq file, managed as the active chiptune task."""
        self.stop_chiptune()
        self._chiptune_task = asyncio.create_task(self.play_jseq(filepath))
        return self._chiptune_task

    def preview_channels(self, channels_data):
        """Start a one-shot playback of multichannel sequence data.

        Non-blocking: creates an asyncio task and returns immediately.
        Any currently running chiptune or preview is stopped first.

        Supports JSEQ v2 channel dicts: channels with ``type='automation'``
        are routed to :meth:`_play_automation`; all others use
        :meth:`play_sequence` as before.

        Args:
            channels_data (list): List of channel dicts.  Audio channel dicts
                must have ``'bpm'``, ``'patch'`` (name or Patches dict), and
                ``'sequence'`` keys.  Automation channel dicts must have
                ``'type': 'automation'``, ``'bpm'``, and ``'steps'`` keys.

        Returns:
            asyncio.Task: The running playback task.
        """
        self.stop_chiptune()

        async def _run_once():
            tasks = []
            for ch in channels_data:
                if ch.get('type') == 'automation':
                    tasks.append(asyncio.create_task(self._play_automation(ch)))
                else:
                    p = ch.get('patch', Patches.SELECT)
                    if isinstance(p, str):
                        p = getattr(Patches, p, Patches.SELECT)
                    tasks.append(asyncio.create_task(self.play_sequence(dict(ch, patch=p))))
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                self.release_all()
                raise

        self._chiptune_task = asyncio.create_task(_run_once())
        return self._chiptune_task
