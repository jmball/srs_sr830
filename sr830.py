"""Stanford Research Systems SR830 lock-in amplifier (LIA) control library."""
import logging
import sys

import visa


class sr830:
    """Stanford Research Systems SR830 LIA instrument."""

    sensitivities = (
        2e-9,
        5e-9,
        10e-9,
        20e-9,
        50e-9,
        100e-9,
        200e-9,
        500e-9,
        1e-6,
        2e-6,
        5e-6,
        10e-6,
        20e-6,
        50e-6,
        100e-6,
        200e-6,
        500e-6,
        1e-3,
        2e-3,
        5e-3,
        10e-3,
        20e-3,
        50e-3,
        100e-3,
        200e-3,
        500e-3,
        1,
    )

    time_constants = (
        10e-6,
        30e-6,
        100e-6,
        300e-6,
        1e-3,
        3e-3,
        10e-3,
        30e-3,
        100e-3,
        300e-3,
        1,
        3,
        10,
        30,
        100,
        300,
        1e3,
        3e3,
        10e3,
        30e3,
    )

    display_ch1 = ("X", "R", "X Noise", "Aux in 1", "Aux in 2")

    display_ch2 = ("Y", "Phase", "Y Noise", "Aux in 3", "Aux in 4")

    ratio_ch1 = ("none", "Aux in 1", "Aux in 2")

    ratio_ch2 = ("none", "Aux in 3", "Aux in 4")

    sample_rates = (
        62.5e-3,
        125e-3,
        250e-3,
        500e-3,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
        256,
        512,
        "Trigger",
    )

    end_of_buffer_modes = ("1 Shot", "Loop")

    trigger_start_modes = ("Off", "Start scan")

    data_transfer_modes = ("Off", "On (DOS)", "On (Windows)")

    local_modes = ("Local", "Remote", "Local lockout")

    gpib_overide_remote_conditions = ("No", "Yes")

    def __init__(self, addr, timeout=10000):
        """Open VISA resource for instr."""
        rm = visa.ResourceManager()
        self.instr = rm.open_resource(addr)
        self.instr.timeout = timeout

    # --- Reference and phase commands ---

    def set_ref_phase_shift(self, phase_shift):
        """Set the reference phase shift.

        Parameters
        ----------
        phase_shift : float
            phase shift in degrees, -360 =< phase_shift =< 720
        """
        self.instr.write(f"PHAS {phase_shift}")

    def get_ref_phase_shift(self):
        """Get the reference phase shift.

        Returns
        -------
        phase_shift : float
            phase shift in degrees, -360 =< phase_shift =< 720
        """
        return float(self.instr.query(f"PHAS?"))

    def set_ref_source(self, source):
        """Set the reference source.

        Parameters
        ----------
        source : int
            refernce source, 0 = external, 1 = internal
        """
        self.instr.write(f"FMOD {source}")

    def get_ref_source(self):
        """Get the reference source.

        Returns
        -------
        source : str
            refernce source
        """
        source = int(self.instr.query(f"FMOD?"))
        if source == 0:
            return "external"
        elif source == 1:
            return "internal"
        else:
            raise ValueError(f"Unknown reference source, {source}")

    def set_ref_freq(self, freq):
        """Set the frequency of the internal oscillator.

        Parameters
        ----------
        freq : float
            frequency in Hz, 0.001 =< freq =< 102000
        """
        self.instr.write(f"FREQ {freq}")

    def get_ref_freq(self):
        """Get the reference frequency.

        Returns
        -------
        freq : float
            frequency in Hz, 0.001 =< freq =< 102000
        """
        return float(self.instr.query(f"FREQ?"))

    def set_reference_trigger(self, trigger):
        """Set the reference trigger type when using external ref.

        Parameters
        ----------
        trigger : int
            trigger type: 0 = zero crossing, 1 = TTL rising egde, 2 = TTL falling edge
        """
        self.instr.write(f"RSLP {trigger}")

    def get_reference_trigger(self):
        """Get the reference trigger type when using external ref.

        Returns
        -------
        trigger : int
            trigger type: 0 = zero crossing, 1 = TTL rising egde, 2 = TTL falling edge
        """
        trigger = int(self.instr.query(f"RSLP?"))
        if trigger == 0:
            return "zero crossing"
        elif trigger == 1:
            return "rising edge"
        elif trigger == 2:
            return "falling edge"
        else:
            raise ValueError(f"Unknown trigger type, {trigger}")

    def set_harmonic(self, harmonic):
        """Set detection harmonic.

        Parameters
        ----------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        self.instr.write(f"HARM {harmonic}")

    def get_harmonic(self):
        """Get detection harmonic.

        Returns
        -------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        return int(self.instr.query(f"HARM?"))

    def set_sine_amplitude(self, amplitude):
        """Set the amplitude of the sine output.

        Parameters
        ----------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        self.instr.write(f"SLVL {amplitude}")

    def get_sine_amplitude(self):
        """Get the amplitude of the sine output.

        Returns
        -------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        return float(self.instr.query(f"SLVL?"))

    def set_input_configuration(self, config):
        """Set the input configuration.

        Parameters
        ----------
        config : int
            input configuration: 0 = A, 1 = A-B, 2 = I (1 MOhm), 3 = I (100 MOhm)
        """
        self.instr.write(f"ISRC {config}")

    def get_input_configuration(self):
        """Set the input configuration.

        Parameters
        ----------
        config : int
            input configuration: 0 = A, 1 = A-B, 2 = I (1 MOhm), 3 = I (100 MOhm)
        """
        config = int(self.instr.query(f"ISRC?"))
        if config == 0:
            return "A"
        elif config == 1:
            return "A-B"
        elif config == 2:
            return "I (1 MOhm)"
        elif config == 3:
            return "I (100 MOhm)"
        else:
            raise ValueError(f"Unknown input configuration, {config}")

    def set_input_shield_gnd(self, grounding):
        """Set input shield grounding.

        Parameters
        ----------
        grounding : int
            input shield grounding: 0 = Floating, 1 = Ground
        """
        self.instr.write(f"IGND {grounding}")

    def get_input_shield_gnd(self, grounding):
        """Get input shield grounding.

        Returns
        -------
        grounding : int
            input shield grounding: 0 = Floating, 1 = Ground
        """
        grounding = int(self.instr.query(f"IGND?"))
        if grounding == 0:
            return "Floating"
        elif grounding == 1:
            return "Ground"
        else:
            raise ValueError(f"Unknown input shield grounding, {grounding}")

    def set_input_coupling(self, coupling):
        """Set input coupling.

        Parameters
        ----------
        coupling : int
            input coupling: 0 = AC, 1 = DC
        """
        self.instr.write(f"ICPL {coupling}")

    def get_input_coupling(self):
        """Get input coupling.

        Returns
        -------
        coupling : int
            input coupling: 0 = AC, 1 = DC
        """
        coupling = int(self.instr.query(f"ICPL?"))
        if coupling == 0:
            return "AC"
        elif coupling == 1:
            return "DC"
        else:
            raise ValueError(f"Unknown input coupling, {coupling}")

    def set_line_notch_status(self, status):
        """Set input line notch filter status.

        Parameters
        ----------
        status : int
            input line notch filter status: 0 = none, 1 = line, 2 = 2 x line, 3 = both
        """
        self.instr.write(f"ILIN {status}")

    def get_line_notch_status(self, status):
        """Get input line notch filter status.

        Returns
        -------
        status : int
            input line notch filter status: 0 = none, 1 = line, 2 = 2 x line, 3 = both
        """
        status = int(self.instr.query(f"ILIN?"))
        if status == 0:
            return "none"
        elif status == 1:
            return "line"
        elif status == 2:
            return "2 x line"
        elif status == 3:
            return "both"
        else:
            raise ValueError(f"Unknown input line notch filter status, {status}")

    # --- Gain and time constant commands ---

    def set_sensitivity(self, sensitivity):
        """Set sensitivity.

        value   sensitivity (V/uA)
        0       2e-9
        1       5e-9
        2       10e-9
        3       20e-9
        4       50e-9
        5       100e-9
        6       200e-9
        7       500e-9
        8       1e-6
        9       2e-6
        10      5e-6
        11      10e-6
        12      20e-6
        13      50e-6
        14      100e-6
        15      200e-6
        16      500e-6
        17      1e-3
        18      2e-3
        19      5e-3
        20      10e-3
        21      20e-3
        22      50e-3
        23      100e-3
        24      200e-3
        25      500e-3
        26      1

        Parameters
        ----------
        sensitivity : int
            sensitivity in V/uA: see table above for mapping
        """
        self.instr.write(f"SENS {sensitivity}")

    def get_sensitivity(self):
        """Get sensitivity.

        value   sensitivity (V/uA)
        0       2e-9
        1       5e-9
        2       10e-9
        3       20e-9
        4       50e-9
        5       100e-9
        6       200e-9
        7       500e-9
        8       1e-6
        9       2e-6
        10      5e-6
        11      10e-6
        12      20e-6
        13      50e-6
        14      100e-6
        15      200e-6
        16      500e-6
        17      1e-3
        18      2e-3
        19      5e-3
        20      10e-3
        21      20e-3
        22      50e-3
        23      100e-3
        24      200e-3
        25      500e-3
        26      1

        Returns
        -------
        sensitivity : int
            sensitivity in V/uA: see table above for mapping
        """
        return str(self.sensitivities[int(self.instr.query(f"SENS?"))])

    def set_reserve_mode(self, mode):
        """Set reserve mode.

        Parameters
        ----------
        mode : int
            reserve mode: 0 = High reserve, 1 = Normal, 2 = Low noise
        """
        self.instr.write(f"RMOD {mode}")

    def get_reserve_mode(self):
        """Get reserve mode.

        Returns
        -------
        mode : int
            reserve mode: 0 = High reserve, 1 = Normal, 2 = Low noise
        """
        mode = int(self.instr.query(f"RMOD?"))
        if mode == 0:
            return "High reserve"
        elif mode == 1:
            return "Normal"
        elif mode == 2:
            return "Low noise"
        else:
            raise ValueError(f"Unknown reserve mode, {mode}")

    def set_time_constant(self, tc):
        """Set time constant.

        value   time constant (s)
        0       10e-6
        1       30e-6
        2       100e-6
        3       300e-6
        4       1e-3
        5       3e-3
        6       10e-3
        7       30e-3
        8       100e-3
        9       300e-3
        10      1
        11      3
        12      10
        13      30
        14      100
        15      300
        16      1e3
        17      3e3
        18      10e3
        19      30e3

        Parameters
        ----------
        tc : int
            time constant in s: see table above for mapping
        """
        self.instr.write(f"OFLT {tc}")

    def get_time_constant(self):
        """Get time constant.

        value   time constant (s)
        0       10e-6
        1       30e-6
        2       100e-6
        3       300e-6
        4       1e-3
        5       3e-3
        6       10e-3
        7       30e-3
        8       100e-3
        9       300e-3
        10      1
        11      3
        12      10
        13      30
        14      100
        15      300
        16      1e3
        17      3e3
        18      10e3
        19      30e3

        Returns
        -------
        tc : int
            time constant in s: see table above for mapping
        """
        return str(self.time_constants[int(self.instr.query(f"OFLT?"))])

    def set_lp_filter_slope(self, slope):
        """Set low pass filter slope.

        Parameters
        ----------
        slope : int
            low pass filter slope: 0 = 6 dB/oct, 1 = 12 dB/oct, 2 = 18 dB/oct, 3 = 24 dB/oct
        """
        self.instr.write(f"OFSL {slope}")

    def get_lp_filter_slope(self):
        """Get low pass filter slope.

        Parameters
        ----------
        slope : int
            low pass filter slope: 0 = 6 dB/oct, 1 = 12 dB/oct, 2 = 18 dB/oct, 3 = 24 dB/oct
        """
        slope = int(self.instr.query(f"OFSL?"))
        if slope == 0:
            return "6 dB/oct"
        elif slope == 1:
            return "12 dB/oct"
        elif slope == 2:
            return "18 dB/oct"
        elif slope == 3:
            return "24 dB/oct"
        else:
            raise ValueError(f"Unknown low pass filter slope, {slope}")

    def set_sync_status(self, status):
        """Set synchronous filter status.

        Parameters
        ----------
        status : int
            synchronous filter status: 0 = Off, 1 = below 200 Hz
        """
        self.instr.write(f"SYNC {status}")

    def get_sync_status(self, status):
        """Get synchronous filter status.

        Returns
        -------
        status : int
            synchronous filter status: 0 = Off, 1 = below 200 Hz
        """
        status = int(self.instr.query(f"SYNC?"))
        if status == 0:
            return "Off"
        elif status == 1:
            return "below 200 Hz"
        else:
            raise ValueError(f"Unknown synchronous filter status, {status}")

    # --- Display and output commands ---

    def set_display(self, channel, display=1, ratio=0):
        """Set a channel display configuration.

        Parameters
        ----------
        channel : int
            channel: 1 = CH1, 2 = CH2
        display : int
            display parameter CH1: 0 = X, 1 = R, 2 = X Noise, 3 = Aux in 1, 4 = Aux in 2;
            display parameter CH2: 0 = Y, 1 = Phase, 3 = Y Noise, 3 = Aux in 3, 4 = Aux in 4
        ratio : int
            ratio type CH1: 0 = none, 1 = Aux in 1, 2 = Aux in 2;
            ratio type CH2: 0 = none, 1 = Aux in 2, 2 = Aux in 4
        """
        self.instr.write(f"DDEF {channel}, {display}, {ratio}")

    def get_display(self, channel):
        """Get a channel display configuration.

        Parameters
        ----------
        channel : int
            channel: 1 = CH1, 2 = CH2
        
        Returns
        -------
        display : int
            display parameter CH1: 0 = X, 1 = R, 2 = X Noise, 3 = Aux in 1, 4 = Aux in 2;
            display parameter CH2: 0 = Y, 1 = Phase, 3 = Y Noise, 3 = Aux in 3, 4 = Aux in 4
        ratio : int
            ratio type CH1: 0 = none, 1 = Aux in 1, 2 = Aux in 2;
            ratio type CH2: 0 = none, 1 = Aux in 2, 2 = Aux in 4
        """
        resp = self.instr.write(f"DDEF? {channel}")
        display, ratio = resp.split(",")
        if channel == 1:
            return self.display_ch1[int(display)], self.ratio_ch1[(int(ratio))]
        elif channel == 2:
            return self.display_ch2[int(display)], self.ratio_ch2[(int(ratio))]

    def set_front_outp(self, channel, output=0):
        """Set front panel output sources.

        Parameters
        ----------
        channel : int
            channel: 1 = CH1, 2 = CH2
        output : int
            output quantity CH1: 0 = CH1 display, 1 = X;
            output quantity CH2: 0 = CH2 display, 1 = Y;
        """
        self.instr.write(f"FPOP {channel}, {output}")

    def get_front_outp(self, channel):
        """Get front panel output sources.

        Parameters
        ----------
        channel : int
            channel: 1 = CH1, 2 = CH2
        
        Returns
        -------
        output : int
            output quantity CH1: 0 = CH1 display, 1 = X;
            output quantity CH2: 0 = CH2 display, 1 = Y;
        """
        output = int(self.instr.query(f"FPOP? {channel}"))
        if channel == 1:
            if output == 0:
                return "CH1 display"
            elif output == 1:
                return "X"
            else:
                raise ValueError(f"Unknown output for channel {channel}, {output}")
        elif channel == 2:
            if output == 0:
                return "CH2 display"
            elif output == 1:
                return "Y"
            else:
                raise ValueError(f"Unknown output for channel {channel}, {output}")
        else:
            raise ValueError(f"Invalid channel, {channel}")

    def set_output_offset_expand(self, parameter, offset, expand):
        """Set the output offsets and expands.

        Parameters
        ----------
        parameter : int
            1 = X, 2 = Y, 3 = R
        offset : float
            %, -105.00 =< offset =< 105.00
        expand : int
            0 = no expand, 1 = 10, 2 = 100
        """
        self.instr.write(f"OEXP {parameter}, {offset}, {expand}")

    def get_output_offset_expand(self, parameter):
        """Get the output offsets and expands.

        Parameters
        ----------
        parameter : int
            1 = X, 2 = Y, 3 = R
        
        Returns
        -------
        offset : float
            %, -105.00 =< offset =< 105.00
        expand : int
            0 = no expand, 1 = 10, 2 = 100
        """
        resp = self.instr.query(f"OEXP? {parameter}")
        offset, expand = resp.split(",")
        offset = float(offset)
        expand = int(expand)
        if expand == 0:
            return offset, "no expand"
        elif expand == 1:
            return offset, "10"
        elif expand == 2:
            return offset, "100"
        else:
            raise ValueError(f"Unknown expand, {expand}")

    def auto_offset(self, parameter):
        """Set parameter offset to zero.

        Paramaters
        ----------
        parameter : int
            1 = X, 2 = Y, 3 = R
        """
        self.instr.write(f"AOFF {parameter}")

    # --- Aux input and output commands ---

    def get_aux_in(self, input):
        """Get voltage of auxiliary input.

        Parameter
        ---------
        input : int
            auxiliary input (1-4)
        """
        return float(self.instr.query(f"OAUX? {input}"))

    def set_aux_out(self, output, voltage):
        """Set voltage of auxiliary output.

        Parameters
        ----------
        output : int
            auxiliary output (1-4)
        voltage : float
            output voltage, -10.500 =< voltage =< 10.500
        """
        self.instr.write(f"AUXV {output}, {voltage}")

    def get_aux_out(self, output):
        """Get voltage of auxiliary output.

        Parameters
        ----------
        output : int
            auxiliary output (1-4)

        Returns
        -------
        voltage : float
            output voltage, -10.500 =< voltage =< 10.500
        """
        return float(self.instr.query(f"AUXV? {output}"))

    # --- Setup commands ---

    def set_output_interface(self, interface):
        """Set the output communication interface.
        
        This command should be sent before any query commands to direct the
        responses to the interface in use.

        Parameters
        ----------
        interface : int
            0 = RS232, 1 = GPIB
        """
        self.instr.write(f"OUTX {interface}")

    def get_output_interface(self):
        """Get the output communication interface.

        Returns
        -------
        interface : int
            0 = RS232, 1 = GPIB
        """
        interface = int(self.instr.query(f"OUTX?"))
        if interface == 0:
            return "RS232"
        elif interface == 1:
            return "GPIB"
        else:
            raise ValueError(f"Unknown communication interface, {interface}")

    def set_remote_status(self, status):
        """Set the remote status.
        
        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Parameters
        ----------
        status : int
            front panel behaviour: 0 = normal, 1 = front panel enabled
        """
        self.instr.write(f"OVRM {status}")

    def set_key_click(self, status):
        """Set key click status.

        Parameters
        ----------
        status : int
            0 = off, 1 = on
        """
        self.instr.write(f"KCLK {status}")

    def get_key_click(self):
        """Get key click status.

        Returns
        -------
        status : int
            0 = off, 1 = on
        """
        status = int(self.instr.query(f"KCLK?"))
        if status == 0:
            return "off"
        elif status == 1:
            return "on"
        else:
            raise ValueError(f"Unknown key click status, {status}")

    def set_alarm(self, status):
        """Set alarm status.

        Parameters
        ----------
        status : int
            0 = off, 1 = on
        """
        self.instr.write(f"ALRM {status}")

    def get_alarm(self):
        """Get alarm status.

        Returns
        -------
        status : int
            0 = off, 1 = on
        """
        status = int(self.instr.query(f"ALRM?"))
        if status == 0:
            return "off"
        elif status == 1:
            return "on"
        else:
            raise ValueError(f"Unknown alarm status, {status}")

    def save_setup(self, number):
        """Save lock-in setup in setting buffer.

        Parameters
        ----------
        number : int
            buffer number
        """
        self.instr.write(f"SSET {number}")

    def recall_setup(self, number):
        """Recall lock-in setup from setting buffer.

        Parameters
        ----------
        number : int
            buffer number
        """
        self.instr.write(f"RSET {number}")

    # --- Auto functions ---

    def auto_gain(self):
        """Automatically set gain."""
        self.instr.write(f"AGAN")
        # TODO: add read serial poll byte

    def auto_reserve(self):
        """Automatically set reserve."""
        self.instr.write(f"ARSV")
        # TODO: add read serial poll byte

    def auto_phase(self):
        """Automatically set phase."""
        self.instr.write(f"APHS")
        # TODO: add query phase shift to determine completion

    # --- Data storage commands ---

    def set_sample_rate(self, rate):
        """Set the data sample rate.
        
        value   sample rate (Hz)
        0       62.5e-3
        1       125e-3
        2       250e-3
        3       500e-3
        4       1
        5       2
        6       4
        7       8
        8       16
        8       32
        10      64
        11      128
        12      256
        13      512
        14      Trigger


        Paramters
        ---------
        rate : int
            sample rate in Hz: see table above for mapping
        """
        self.instr.write(f"SRAT {rate}")

    def get_sample_rate(self):
        """Get the data sample rate.

        value   sample rate (Hz)
        0       62.5e-3
        1       125e-3
        2       250e-3
        3       500e-3
        4       1
        5       2
        6       4
        7       8
        8       16
        8       32
        10      64
        11      128
        12      256
        13      512
        14      Trigger

        Returns
        ---------
        rate : float or str
            sample rate in Hz: see table above for mapping
        """
        return self.sample_rates[int(self.instr.query(f"SRAT?"))]

    def set_end_of_buffer_mode(self, mode):
        """Set the end of buffer mode.
        
        If Loop mode is used, make sure to pause data storage before reading the
        data to avoid confusion about which point is the most recent.

        Parameters
        ----------
        mode : int
            end of buffer mode: 0 = 1 Shot, 1 = Loop
        """
        self.instr.write(f"SEND {mode}")

    def get_end_of_buffer_mode(self):
        """Get the end of buffer mode.

        Returns
        ----------
        mode : int
            end of buffer mode: 0 = 1 Shot, 1 = Loop
        """
        return self.end_of_buffer_modes[int(self.instr.query(f"SEND?"))]

    def trigger(self):
        """Send software trigger."""
        self.instr.write(f"TRIG")

    def set_trigger_start_mode(self, mode):
        """Set the trigger start mode.

        Parameters
        ----------
        mode : int
            trigger start mode: 0 = Off, 1 = Start scan
        """
        self.instr.write(f"TSTR {mode}")

    def get_trigger_start_mode(self):
        """Get the trigger start mode.

        Returns
        -------
        mode : int
            trigger start mode: 0 = Off, 1 = Start scan
        """
        return self.trigger_start_modes[int(self.instr.query(f"TSTR?"))]

    def start(self):
        """Start or resume data storage.
        
        Ignored if storage already in progress.
        """
        self.instr.write(f"STRT")

    def pause(self):
        """Pause data storage.
        
        Ignored if storage is already paused or reset.
        """
        self.instr.write(f"PAUS")

    def reset_data_buffers(self):
        """Reset data buffers.
        
        This command will erase the data buffer.
        """
        self.instr.write(f"REST")

    # --- Data transfer commands ---

    def measure(self, parameter):
        """Read the value of X, Y, R, or phase.

        Parameters
        ----------
        parameter : int
            measured parameter: 1 = X, 2 = Y, 3 = R, 4 = phase
        
        Returns
        -------
        value : float
            value of measured parameter
        """
        return float(self.instr.query(f"OUTP? {parameter}"))

    def read_display(self, channel):
        """Read the value of a channel display.

        Parameters
        ----------
        channel : int
            channel display to read

        Returns
        -------
        value : float
            displayed value in display units
        """
        return float(self.instr.query(f"OUTR? {channel}"))

    def measure_multiple(self, parameters):
        """Read multiple (2-6) parameter values simultaneously.

        The values of X and Y are recorded at a single instant.
        The values of R and phase are also recorded at a single
        instant. Thus reading X,Y OR R,phase yields a coherent snapshot
        of the output signal. If X,Y,R and phase are all read, then the
        values of X,Y are recorded approximately 10µs apart from
        R,phase. Thus, the values of X and Y may not yield the exact
        values of R and phase from a single SNAP? query.

        The values of the Aux Inputs may have an uncertainty of up to
        32µs. The frequency is computed only every other period or 40 ms,
        whichever is longer. 

        value   parameter
        1       X
        2       Y
        3       R
        4       phase
        5       Aux in 1
        6       Aux in 2
        7       Aux in 3
        8       Aux in 4
        9       Ref frequency
        10      CH1 display
        11      CH2 display

        Paramters
        ---------
        paramters : list or tuple of int
            parameters to measure: see table above
        
        Returns
        -------
        values : tuple of float
            values of measured parameters
        """
        parameters = ",".join([str(i) for i in parameters])
        values = self.instr.query(f"SNAP? {parameters}").split(",")
        return (float(i) for i in values)

    def read_aux_in(self, aux_in):
        """Read an auxiliary input value in volts.

        Parameters
        ----------
        aux_in : int
            auxiliary input

        Returns
        -------
        voltage : float
            auxiliary input voltage
        """
        return float(self.instr.query(f"OAUX? {aux_in}"))

    def get_buffer_size(self):
        """Get the number of points stored in the buffer.

        Returns
        -------
        N : int
            number of points in the buffer
        """
        return int(self.instr.query(f"SPTS?"))

    def get_ascii_buffer_data(self, channel, start_bin, bins):
        """Get the points stored in a channel buffer range.

        The values are returned as ASCII floating point numbers with
        the units of the trace.

        Bins (or points) a labelled from 0 (oldest) to N-1 (newest)
        where N is the total number of bins.

        If data storage is set to Loop mode, make sure that
        storage is paused before reading any data. This is because
        the points are indexed relative to the most recent point
        which is continually changing.

        Parameters
        ----------
        channel : int
            channel 1 or 2
        start_bin : int
            starting bin to read where 0 is oldest
        bins : int
            number of bins to read
        
        Returns
        -------
        buffer : tuple of float
            data stored in buffer range
        """
        buffer = self.instr.query(f"TRCA? {channel},{start_bin},{bins}").split(",")
        return (float(i) for i in buffer)

    def get_binary_buffer_data(self, channel, start_bin, bins):
        """Get the points stored in a channel buffer range.

        The values are returned as IEEE format binary floating point
        numbers with the units of the trace.

        Bins (or points) a labelled from 0 (oldest) to N-1 (newest)
        where N is the total number of bins.

        If data storage is set to Loop mode, make sure that
        storage is paused before reading any data. This is because
        the points are indexed relative to the most recent point
        which is continually changing.

        Parameters
        ----------
        channel : int
            channel 1 or 2
        start_bin : int
            starting bin to read where 0 is oldest
        bins : int
            number of bins to read
        
        Returns
        -------
        buffer : tuple of float
            data stored in buffer range
        """
        # TODO: fix formatting
        buffer = self.instr.query(f"TRCB? {channel},{start_bin},{bins}").split(",")
        pass

    def get_non_norm_buffer_data(self, channel, start_bin, bins):
        """Get the points stored in a channel buffer range.

        The values are returned as non-normalised floating point
        numbers with the units of the trace.

        Bins (or points) a labelled from 0 (oldest) to N-1 (newest)
        where N is the total number of bins.

        If data storage is set to Loop mode, make sure that
        storage is paused before reading any data. This is because
        the points are indexed relative to the most recent point
        which is continually changing.

        Parameters
        ----------
        channel : int
            channel 1 or 2
        start_bin : int
            starting bin to read where 0 is oldest
        bins : int
            number of bins to read
        
        Returns
        -------
        buffer : tuple of float
            data stored in buffer range
        """
        # TODO: fix formatting
        buffer = self.instr.query(f"TRCL? {channel},{start_bin},{bins}").split(",")
        pass

    def set_data_transfer_mode(self, mode):
        """Get the data transfer mode.
        
        Parameters
        ----------
        mode : str
            0 = Off, 1 = On (DOS), 2 = On (Windows)
        """
        self.instr.write(f"FAST {mode}")

    def get_data_transfer_mode(self):
        """Get the data transfer mode.
        
        Returns
        -------
        mode : str
            0 = Off, 1 = On (DOS), 2 = On (Windows)
        """
        return self.data_transfer_modes[int(self.instr.query(f"FAST?"))]

    def start_scan(self):
        """Start scan.
        
        After turning on fast data transfer, this function starts
        the scan after a delay of 0.5 sec. This delay allows the
        controlling interface to place itself in the read mode before
        the first data points are transmitted. Do not use the STRT
        command to start the scan.
        """
        self.instr.write(f"STRD")

    # --- Interface commands ---
    # TODO: check differences between RS232 and GPIB. PyVISA might provide GPIB.

    def reset(self):
        """Reset the instrument to the default configuration."""
        self.instr.write(f"*RST")

    def get_idn(self):
        """Get the identity string."""
        self.instr.write(f"*IDN?")

    def set_local_mode(self, local):
        """Set the local/remote function.
        
        Parameters
        ----------
        local : int
            0 = Local, 1 = Remote, 2 = Local lockout
        """
        self.instr.write(f"LOCL {local}")

    def get_local_mode(self):
        """Get the local/remote function.

        Returns
        -------
        local : int
            0 = Local, 1 = Remote, 2 = Local lockout
        """
        return self.local_modes[int(self.instr.query("LOCL?"))]

    def set_gpib_overide_remote(self, condition):
        """Set the GPIB overide remote condition.

        Parameters
        ----------
        condition : int
            GPIB overide remote condition: 0 = No, 1 = Yes
        """
        self.instr.write(f"OVRM {condition}")

    def get_gpib_overide_remote(self):
        """Get the GPIB overide remote condition.

        Returns
        -------
        condition : int
            GPIB overide remote condition: 0 = No, 1 = Yes
        """
        return self.gpib_overide_remote_conditions[int(self.instr.write(f"OVRM?"))]

    # --- Status reporting commands ---
    # TODO: see if PyVISA implements these

    def clear_status_registers(self):
        """Clear all status registers."""
        self.instr.write("*CLS")


if __name__ == "__main__":
    console_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s|%(name)s|%(levelname)s|%(message)s",
        handlers=[console_handler],
    )
    logger = logging.getLogger()
else:
    logger = logging.getLogger(__name__)

