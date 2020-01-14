"""Stanford Research Systems SR830 lock-in amplifier (LIA) control library.

The full instrument manual, including the programming guide, can be found at
https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf.
"""

import logging
import sys

import visa

rm = visa.ResourceManager()


class sr830:
    """Stanford Research Systems SR830 LIA instrument.

    Some instrument commands and responses map parameter values to integers. For
    example, to set the sensitivity to 10e-9 V/um the argument of the command
    string sent to the instrument should be 2; the instrument response string to the
    parameter query is an integer corresponding to a human readable sensitivity.
    When setting the value of parameter, the integer mapping the value should be provided
    as the argument to the function. However, when reading/getting the value of a parameter
    either the human readable version (of type str, default) or corresponding integer
    (of type int) can optionally be returned. Internally, valid instrument parameters in
    human readable format are stored in tuples as class variables. The index of a
    parameter in a tuple is its corresponding integer value used by the instrument.
    """

    reference_sources = ("external", "internal")

    triggers = ("zero crossing", "TTL rising egde", "TTL falling edge")

    input_configurations = ("A", "A-B", "I (1 MOhm)", "I (100 MOhm)")

    groundings = ("Float", "Ground")

    input_couplings = ("AC", "DC")

    input_line_notch_filter_statuses = (
        "no filters",
        "Line notch in",
        "2 x Line notch in",
        "Both notch filters in",
    )

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
        1.0,
    )

    reserve_modes = ("High reserve", "Normal", "Low noise")

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
        1.0,
        3.0,
        10.0,
        30.0,
        100.0,
        300.0,
        1e3,
        3e3,
        10e3,
        30e3,
    )

    low_pass_filter_slopes = (6, 12, 18, 24)

    synchronous_filter_statuses = ("Off", "below 200 Hz")

    display_ch1 = ("X", "R", "X Noise", "Aux In 1", "Aux In 2")

    display_ch2 = ("Y", "Phase", "Y Noise", "Aux In 3", "Aux In 4")

    ratio_ch1 = ("none", "Aux In 1", "Aux In 2")

    ratio_ch2 = ("none", "Aux In 3", "Aux In 4")

    front_panel_output_sources_ch1 = ("CH1 display", "X")

    front_panel_output_sources_ch2 = ("CH2 display", "Y")

    expands = (0, 10, 100)

    communication_interfaces = ("RS232", "GPIB")

    key_click_states = ("Off", "On")

    alarm_statuses = ("Off", "On")

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

    def __init__(self, address, output_interface, timeout=10000, return_int=False):
        """Initialise VISA resource for instrument.

        The following operations are performed for the initial setup in order:

        1. Open a VISA connection to the instrument.
        2. Set the communication timeout.
        3. Set whether to return integer or human readable parameters from responses.
        4. Send a command to the instrument to set its output communication interface,
        i.e. set what communication interface is being used on the rear panel of the
        instrument itself.
        5. Query the identity string and set corresponding attributes.
        
        Parameters
        ----------
        address: str
            Full VISA resource address, e.g. "ASRL2::INSTR", "GPIB0::14::INSTR" etc.
        output_interface: str
            Communication interface on the lock-in amplifier rear panel used to read
            instrument responses. This does not need to match the VISA resource interface
            type if, for example, an interface adapter is used between the control
            computer and the instrument.
        timeout: int or float, optional
            Communication timeout in ms.
        return_int: bool, optional
            When instrument response strings for a parameter are integers corresponding
            to a value, choose whether to return the integer (True) or the human
            readable value (False).
        """
        self.instr = rm.open_resource(address)
        self.instr.timeout = timeout
        # TODO: add return_int option to methods, make sure docstrings are consistent
        self.return_int = return_int
        self.set_output_interface(output_interface)
        self._add_idn()
        logger.info(
            f"{self.manufacturer} {self.model} {self.serial_number} {self.firmware_version} connected!"
        )

    def _add_idn(self):
        """Add identity info attributes from identity string."""
        idn = self.get_id()
        idn = idn.split(",")
        self.manufacturer = idn[0]
        self.model = idn[1]
        self.serial_number = idn[2]
        self.firmware_version = idn[3]

    # --- Reference and phase commands ---

    def set_ref_phase_shift(self, phase_shift):
        """Set the reference phase shift.

        Parameters
        ----------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        cmd = f"PHAS {phase_shift}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_ref_phase_shift(self):
        """Get the reference phase shift.

        Returns
        -------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        cmd = f"PHAS?"
        phase_shift = float(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return phase_shift

    def set_ref_source(self, source):
        """Set the reference source.

        Parameters
        ----------
        source : {0, 1}
            Refernce source:
                
                * 0 : external
                * 1 : internal
        """
        cmd = f"FMOD {source}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_ref_source(self):
        """Get the reference source.

        Returns
        -------
        source : {0, 1}
            Refernce source:
                
                * 0 : external
                * 1 : internal
        """
        cmd = f"FMOD?"
        source = self.reference_sources[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return source

    def set_ref_freq(self, freq):
        """Set the frequency of the internal oscillator.

        Parameters
        ----------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        cmd = f"FREQ {freq}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_ref_freq(self):
        """Get the reference frequency.

        Returns
        -------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        cmd = f"FREQ?"
        freq = float(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return freq

    def set_reference_trigger(self, trigger):
        """Set the reference trigger type when using external ref.

        Parameters
        ----------
        trigger : {0, 1, 2}
            Trigger type:
            
                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        cmd = f"RSLP {trigger}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_reference_trigger(self):
        """Get the reference trigger type when using external ref.

        Returns
        -------
        trigger : {0, 1, 2}
            Trigger type:
            
                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        cmd = f"RSLP?"
        trigger = self.triggers[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return trigger

    def set_harmonic(self, harmonic):
        """Set detection harmonic.

        Parameters
        ----------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        cmd = f"HARM {harmonic}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_harmonic(self):
        """Get detection harmonic.

        Returns
        -------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        cmd = f"HARM?"
        harmonic = int(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return harmonic

    def set_sine_amplitude(self, amplitude):
        """Set the amplitude of the sine output.

        Parameters
        ----------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        cmd = f"SLVL {amplitude}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_sine_amplitude(self):
        """Get the amplitude of the sine output.

        Returns
        -------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        cmd = f"SLVL?"
        amplitude = float(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return amplitude

    def set_input_configuration(self, config):
        """Set the input configuration.

        Parameters
        ----------
        config : {0, 1, 2, 3}
            Input configuration:
                
                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        cmd = f"ISRC {config}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_input_configuration(self):
        """Set the input configuration.

        Returns
        -------
        config : {0, 1, 2, 3}
            Input configuration:
                
                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        cmd = f"ISRC?"
        config = self.input_configurations[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return config

    def set_input_shield_gnd(self, grounding):
        """Set input shield grounding.

        Parameters
        ----------
        grounding : {0, 1}
            Input shield grounding:
            
                * 0 : Float
                * 1 : Ground
        """
        cmd = f"IGND {grounding}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_input_shield_gnd(self, grounding):
        """Get input shield grounding.

        Returns
        -------
        grounding : {0, 1}
            Input shield grounding:
            
                * 0 : Float
                * 1 : Ground
        """
        cmd = f"IGND?"
        grounding = self.groundings[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return grounding

    def set_input_coupling(self, coupling):
        """Set input coupling.

        Parameters
        ----------
        coupling : {0, 1}
            Input coupling:
            
                * 0 : AC
                * 1 : DC
        """
        cmd = f"ICPL {coupling}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_input_coupling(self):
        """Get input coupling.

        Returns
        -------
        coupling : {0, 1}
            Input coupling:
            
                * 0 : AC
                * 1 : DC
        """
        cmd = f"ICPL?"
        coupling = self.input_couplings[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return coupling

    def set_line_notch_status(self, status):
        """Set input line notch filter status.

        Parameters
        ----------
        status : {0, 1, 2, 3}
            Input line notch filter status:
            
                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        cmd = f"ILIN {status}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_line_notch_status(self, status):
        """Get input line notch filter status.

        Returns
        -------
        status : {0, 1, 2, 3}
            Input line notch filter status:
            
                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        cmd = f"ILIN?"
        status = self.input_line_notch_filter_statuses[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return status

    # --- Gain and time constant commands ---

    def set_sensitivity(self, sensitivity):
        """Set sensitivity.

        Parameters
        ----------
        sensitivity : {0 - 26}
            Sensitivity in V/uA:
            
                * 0 : 2e-9
                * 1 : 5e-9
                * 2 : 10e-9
                * 3 : 20e-9
                * 4 : 50e-9
                * 5 : 100e-9
                * 6 : 200e-9
                * 7 : 500e-9
                * 8 : 1e-6
                * 9 : 2e-6
                * 10 : 5e-6
                * 11 : 10e-6
                * 12 : 20e-6
                * 13 : 50e-6
                * 14 : 100e-6
                * 15 : 200e-6
                * 16 : 500e-6
                * 17 : 1e-3
                * 18 : 2e-3
                * 19 : 5e-3
                * 20 : 10e-3
                * 21 : 20e-3
                * 22 : 50e-3
                * 23 : 100e-3
                * 24 : 200e-3
                * 25 : 500e-3
                * 26 : 1
        """
        cmd = f"SENS {sensitivity}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_sensitivity(self):
        """Get sensitivity.

        Returns
        -------
        sensitivity : {0 - 26}
            Sensitivity in V/uA:
            
                * 0 : 2e-9
                * 1 : 5e-9
                * 2 : 10e-9
                * 3 : 20e-9
                * 4 : 50e-9
                * 5 : 100e-9
                * 6 : 200e-9
                * 7 : 500e-9
                * 8 : 1e-6
                * 9 : 2e-6
                * 10 : 5e-6
                * 11 : 10e-6
                * 12 : 20e-6
                * 13 : 50e-6
                * 14 : 100e-6
                * 15 : 200e-6
                * 16 : 500e-6
                * 17 : 1e-3
                * 18 : 2e-3
                * 19 : 5e-3
                * 20 : 10e-3
                * 21 : 20e-3
                * 22 : 50e-3
                * 23 : 100e-3
                * 24 : 200e-3
                * 25 : 500e-3
                * 26 : 1
        """
        cmd = f"SENS?"
        sensitivity = self.sensitivities[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return sensitivity

    def set_reserve_mode(self, mode):
        """Set reserve mode.

        Parameters
        ----------
        mode : {0, 1, 2}
            Reserve mode:
            
                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        cmd = f"RMOD {mode}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_reserve_mode(self):
        """Get reserve mode.

        Returns
        -------
        mode : {0, 1, 2}
            Reserve mode:
            
                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        cmd = f"RMOD?"
        mode = self.reserve_modes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return mode

    def set_time_constant(self, tc):
        """Set time constant.

        Parameters
        ----------
        tc : {0 - 19}
            Time constant in s:

                * 0 : 10e-6
                * 1 : 30e-6
                * 2 : 100e-6
                * 3 : 300e-6
                * 4 : 1e-3
                * 5 : 3e-3
                * 6 : 10e-3
                * 7 : 30e-3
                * 8 : 100e-3
                * 9 : 300e-3
                * 10 : 1
                * 11 : 3
                * 12 : 10
                * 13 : 30
                * 14 : 100
                * 15 : 300
                * 16 : 1e3
                * 17 : 3e3
                * 18 : 10e3
                * 19 : 30e3
        """
        cmd = f"OFLT {tc}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_time_constant(self):
        """Get time constant.

        Returns
        -------
        tc : {0 - 19}
            Time constant in s:

                * 0 : 10e-6
                * 1 : 30e-6
                * 2 : 100e-6
                * 3 : 300e-6
                * 4 : 1e-3
                * 5 : 3e-3
                * 6 : 10e-3
                * 7 : 30e-3
                * 8 : 100e-3
                * 9 : 300e-3
                * 10 : 1
                * 11 : 3
                * 12 : 10
                * 13 : 30
                * 14 : 100
                * 15 : 300
                * 16 : 1e3
                * 17 : 3e3
                * 18 : 10e3
                * 19 : 30e3
        """
        cmd = f"OFLT?"
        tc = self.time_constants[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return tc

    def set_lp_filter_slope(self, slope):
        """Set the low pass filter slope.

        Parameters
        ----------
        slope : {0, 1, 2, 3}
            Low pass filter slope in dB/oct:
                
                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        cmd = f"OFSL {slope}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_lp_filter_slope(self):
        """Get the low pass filter slope.

        Parameters
        ----------
        slope : {0, 1, 2, 3}
            Low pass filter slope in dB/oct:
                
                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        cmd = f"OFSL?"
        slope = self.low_pass_filter_slopes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return slope

    def set_sync_status(self, status):
        """Set synchronous filter status.

        Parameters
        ----------
        status : {0, 1}
            Synchronous filter status:
            
                * 0 : Off
                * 1 : below 200 Hz
        """
        cmd = f"SYNC {status}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_sync_status(self, status):
        """Get synchronous filter status.

        Returns
        -------
        status : {0, 1}
            Synchronous filter status:
            
                * 0 : Off
                * 1 : below 200 Hz
        """
        cmd = f"SYNC?"
        status = self.synchronous_filter_statuses[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return status

    # --- Display and output commands ---

    def set_display(self, channel, display=1, ratio=0):
        """Set a channel display configuration.

        Parameters
        ----------
        channel : {1, 2}
            Channel:
                
                * 1 : CH1
                * 2 : CH2

        display : {0, 1, 2, 3, 4}
            Display parameter for CH1:
            
                * 0 : X
                * 1 : R
                * 2 : X Noise
                * 3 : Aux In 1
                * 4 : Aux In 2;

            Display parameter for CH2:
            
                * 0 : Y
                * 1 : Phase
                * 2 : Y Noise
                * 3 : Aux In 3
                * 4 : Aux In 4

        ratio : {0, 1, 2}
            Ratio type for CH1:
                
                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2
                
            Ratio type for CH2: 
                
                * 0 : none
                * 1 : Aux In 2
                * 2 : Aux In 4
        """
        cmd = f"DDEF {channel}, {display}, {ratio}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_display(self, channel):
        """Get a channel display configuration.

        Parameters
        ----------
        channel : {1, 2}
            Channel:
                
                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        display : {0, 1, 2, 3, 4}
            Display parameter for CH1:
            
                * 0 : X
                * 1 : R
                * 2 : X Noise
                * 3 : Aux In 1
                * 4 : Aux In 2;

            Display parameter for CH2:
            
                * 0 : Y
                * 1 : Phase
                * 2 : Y Noise
                * 3 : Aux In 3
                * 4 : Aux In 4

        ratio : {0, 1, 2}
            Ratio type for CH1:
                
                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2
                
            Ratio type for CH2: 
                
                * 0 : none
                * 1 : Aux In 2
                * 2 : Aux In 4
        """
        cmd = f"DDEF? {channel}"
        resp = self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        display, ratio = resp.split(",")
        if channel == 1:
            return self.display_ch1[int(display)], self.ratio_ch1[(int(ratio))]
        elif channel == 2:
            return self.display_ch2[int(display)], self.ratio_ch2[(int(ratio))]
        else:
            raise ValueError(f"Invalid channel, {channel}")

    def set_front_output(self, channel, output=0):
        """Set front panel output sources.

        Parameters
        ----------
        channel : {1, 2}
            Channel:
                
                * 1 : CH1
                * 2 : CH2

        output : {0, 1}
            Output quantity for CH1:
            
                * 0 : CH1 display
                * 1 : X

            Output quantity for CH2:
            
                * 0 : CH2 display
                * 1 : Y
        """
        cmd = f"FPOP {channel}, {output}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_front_output(self, channel):
        """Get front panel output sources.

        Parameters
        ----------
        channel : {1, 2}
            Channel:
                
                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        output : {0, 1}
            Output quantity for CH1:
            
                * 0 : CH1 display
                * 1 : X

            Output quantity for CH2:
            
                * 0 : CH2 display
                * 1 : Y
        """
        cmd = f"FPOP? {channel}"
        output = int(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        if channel == 1:
            return self.front_panel_output_sources_ch1[output]
        elif channel == 2:
            return self.front_panel_output_sources_ch2[output]
        else:
            raise ValueError(f"Invalid channel, {channel}")

    def set_output_offset_expand(self, parameter, offset, expand):
        """Set the output offsets and expands.

        Setting an offset to zero turns the offset off.

        Parameters
        ----------
        parameter : {1, 2, 3}
            Measurement parameter:
            
                * 1 : X
                * 2 : Y
                * 3 : R

        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : {0, 1, 2}
            Expand:

                * 0 : 0
                * 1 : 10
                * 2 : 100
        """
        cmd = f"OEXP {parameter}, {offset}, {expand}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_output_offset_expand(self, parameter):
        """Get the output offsets and expands.

        Parameters
        ----------
        parameter : {1, 2, 3}
            Measurement parameter:
            
                * 1 : X
                * 2 : Y
                * 3 : R

        Returns
        -------
        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : {0, 1, 2}
            Expand:

                * 0 : 0
                * 1 : 10
                * 2 : 100
        """
        cmd = f"OEXP? {parameter}"
        resp = self.instr.query(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        offset, expand = resp.split(",")
        offset = float(offset)
        expand = self.expands[int(expand)]
        return offset, expand

    def auto_offset(self, parameter):
        """Set parameter offset to zero.

        Paramaters
        ----------
        parameter : {1, 2, 3}
            Measurement parameter:
            
                * 1 : X
                * 2 : Y
                * 3 : R
        """
        cmd = f"AOFF {parameter}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    # --- Aux input and output commands ---

    def get_aux_in(self, aux_in):
        """Get voltage of auxiliary input.

        The resolution is 1/3 mV.

        Parameter
        ---------
        aux_in : {1, 2, 3, 4}
            Auxiliary input (1, 2, 3, or 4).
        
        Returns
        -------
        voltage : float
            Auxiliary input voltage.
        """
        cmd = f"OAUX? {aux_in}"
        voltage = self.instr.query(cmd)
        voltage = float(voltage.decode("ascii"))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return voltage

    def set_aux_out(self, aux_out, voltage):
        """Set voltage of auxiliary output.

        Parameters
        ----------
        aux_out : {1, 2, 3, 4}
            Auxiliary output (1, 2, 3, or 4).
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        cmd = f"AUXV {aux_out}, {voltage}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_aux_out(self, aux_out):
        """Get voltage of auxiliary output.

        Parameters
        ----------
        aux_out : {1, 2, 3, 4}
            Auxiliary output (1, 2, 3, or 4).

        Returns
        -------
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        cmd = f"AUXV? {aux_out}"
        voltage = float(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return voltage

    # --- Setup commands ---

    def set_output_interface(self, interface):
        """Set the output communication interface.

        This command should be sent before any query commands to direct the
        responses to the interface in use.

        Parameters
        ----------
        interface : {0, 1}
            Output communication interface:
                
                * 0 : RS232
                * 1 : GPIB
        """
        cmd = f"OUTX {interface}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_output_interface(self):
        """Get the output communication interface.

        Returns
        -------
        interface : {0, 1}
            Output communication interface:
                
                * 0 : RS232
                * 1 : GPIB
        """
        cmd = f"OUTX?"
        interface = self.communication_interfaces[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return interface

    def set_remote_status(self, status):
        """Set the remote status.

        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Parameters
        ----------
        status : {0, 1}
            Front panel behaviour:
                
                * 0 : normal
                * 1 : front panel activated
        """
        cmd = f"OVRM {status}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def set_key_click_state(self, state):
        """Set key click state.

        Parameters
        ----------
        state : {0, 1}
            Key click state:
                
                * 0 : Off
                * 1 : On
        """
        cmd = f"KCLK {state}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_key_click_state(self):
        """Get key click state.

        Returns
        -------
        state : {0, 1}
            Key click state:
                
                * 0 : Off
                * 1 : On
        """
        cmd = f"KCLK?"
        state = self.key_click_states[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return state

    def set_alarm(self, status):
        """Set the alarm status.

        Parameters
        ----------
        status : {0, 1}
            Alarm status:
            
                * 0 : Off
                * 1 : On
        """
        cmd = f"ALRM {status}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_alarm(self):
        """Get the alarm status.

        Returns
        -------
        status : {0, 1}
            Alarm status:
            
                * 0 : Off
                * 1 : On
        """
        cmd = f"ALRM?"
        status = self.alarm_statuses[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return status

    def save_setup(self, number):
        """Save the lock-in setup in a settings buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        cmd = f"SSET {number}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def recall_setup(self, number):
        """Recall lock-in setup from setting buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        cmd = f"RSET {number}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    # --- Auto functions ---

    def auto_gain(self):
        """Automatically set the gain.
        
        Does nothing if the time constant is greater than 1 second.
        """
        cmd = f"AGAN"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        # TODO: add read serial poll byte

    def auto_reserve(self):
        """Automatically set reserve."""
        cmd = f"ARSV"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        # TODO: add read serial poll byte

    def auto_phase(self):
        """Automatically set phase."""
        cmd = f"APHS"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        # TODO: add query phase shift to determine completion

    # --- Data storage commands ---

    def set_sample_rate(self, rate):
        """Set the data sample rate.

        Paramters
        ---------
        rate : {0 - 14}
            Sample rate in Hz:

                * 0 : 62.5e-3
                * 1 : 125e-3
                * 2 : 250e-3
                * 3 : 500e-3
                * 4 : 1
                * 5 : 2
                * 6 : 4
                * 7 : 8
                * 8 : 16
                * 9 : 32
                * 10 : 64
                * 11 : 128
                * 12 : 256
                * 13 : 512
                * 14 : Trigger
        """
        cmd = f"SRAT {rate}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_sample_rate(self):
        """Get the data sample rate.

        Returns
        ---------
        rate : {0 - 14} or float or int or "Trigger"
            Sample rate in Hz:

                * 0 : 62.5e-3
                * 1 : 125e-3
                * 2 : 250e-3
                * 3 : 500e-3
                * 4 : 1
                * 5 : 2
                * 6 : 4
                * 7 : 8
                * 8 : 16
                * 9 : 32
                * 10 : 64
                * 11 : 128
                * 12 : 256
                * 13 : 512
                * 14 : Trigger
        """
        cmd = f"SRAT?"
        rate = self.sample_rates[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return rate

    def set_end_of_buffer_mode(self, mode):
        """Set the end of buffer mode.

        If Loop mode is used, make sure to pause data storage before reading the
        data to avoid confusion about which point is the most recent.

        Parameters
        ----------
        mode : {0, 1}
            End of buffer mode:
                
                * 0 : 1 Shot
                * 1 : Loop
        """
        cmd = f"SEND {mode}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_end_of_buffer_mode(self):
        """Get the end of buffer mode.

        Returns
        ----------
        mode : {0, 1} or str
            End of buffer mode:
                
                * 0 : 1 Shot
                * 1 : Loop
        """
        cmd = f"SEND?"
        mode = self.end_of_buffer_modes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return mode

    def trigger(self):
        """Send software trigger."""
        cmd = f"TRIG"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def set_trigger_start_mode(self, mode):
        """Set the trigger start mode.

        Parameters
        ----------
        mode : {0, 1}
            Trigger start mode:
            
                * 0 : Off
                * 1 : Start scan
        """
        cmd = f"TSTR {mode}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_trigger_start_mode(self):
        """Get the trigger start mode.

        Returns
        -------
        mode : {0, 1} or str
            Trigger start mode:
            
                * 0 : Off
                * 1 : Start scan
        """
        cmd = f"TSTR?"
        mode = self.trigger_start_modes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return mode

    def start(self):
        """Start or resume data storage.

        Ignored if storage already in progress.
        """
        cmd = f"STRT"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def pause(self):
        """Pause data storage.

        Ignored if storage is already paused or reset.
        """
        cmd = f"PAUS"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def reset_data_buffers(self):
        """Reset data buffers.

        This command will erase the data buffer.
        """
        cmd = f"REST"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    # --- Data transfer commands ---

    def measure(self, parameter):
        """Read the value of X, Y, R, or phase.

        Parameters
        ----------
        parameter : {1, 2, 3, 4}
            Measured parameter:
            
                * 1 : X
                * 2 : Y
                * 3 : R
                * 4 : Phase

        Returns
        -------
        value : float
            Value of measured parameter in volts or degrees.
        """
        cmd = f"OUTP? {parameter}"
        value = self.instr.query(cmd)
        value = float(value.decode("ascii"))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return value

    def read_display(self, channel):
        """Read the value of a channel display.

        Parameters
        ----------
        channel : {1, 2}
            Channel display to read:
                
                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        value : float
            Displayed value in display units.
        """
        cmd = f"OUTR? {channel}"
        value = self.instr.query(cmd)
        value = float(value.decode("ascii"))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return value

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

        Paramters
        ---------
        paramters : list or tuple of int
            Parameters to measure:

                * 1 : X
                * 2 : Y
                * 3 : R
                * 4 : Phase
                * 5 : Aux In 1
                * 6 : Aux In 2
                * 7 : Aux In 3
                * 8 : Aux In 4
                * 9 : Ref Frequency
                * 10 : CH1 display
                * 11 : CH2 display

        Returns
        -------
        values : tuple of float
            Values of measured parameters.
        """
        parameters = ",".join([str(i) for i in parameters])
        cmd = f"SNAP? {parameters}"
        values = self.instr.query(cmd).split(",")
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return (float(i) for i in values)

    def read_aux_in(self, aux_in):
        """Read an auxiliary input value in volts.

        Parameters
        ----------
        aux_in : {1, 2, 3, 4}
            Auxiliary input (1-4).

        Returns
        -------
        voltage : float
            Auxiliary input voltage.
        """
        cmd = f"OAUX? {aux_in}"
        voltage = self.instr.query(cmd)
        voltage = float(voltage.decode("ascii"))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return voltage

    def get_buffer_size(self):
        """Get the number of points stored in the buffer.

        Returns
        -------
        N : int
            Number of points in the buffer.
        """
        cmd = f"SPTS?"
        N = int(self.instr.query(cmd))
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return N

    def get_ascii_buffer_data(self, channel, start_bin, bins):
        """Get the points stored in a channel buffer range.

        The values are returned as ASCII floating point numbers with
        the units of the trace.

        Bins (or points) a labelled from 0 (oldest) to N-1 (newest)
        where N is the total number of bins.

        If data storage is set to Loop mode, storage is paused before
        reading any data. This is because the points are indexed relative
        to the most recent point which is continually changing.

        Parameters
        ----------
        channel : {1, 2}
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest.
        bins : int
            Number of bins to read.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        cmd = f"TRCA? {channel},{start_bin},{bins}"

        # pause storage if loop mode
        buffer_mode = self.get_end_of_buffer_mode()
        if buffer_mode == "Loop":
            self.pause()

        buffer = self.instr.query_ascii_values(cmd, container=tuple())

        # restart loop storage if previously set
        if buffer_mode == "Loop":
            self.set_end_of_buffer_mode(mode=1)

        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

        return buffer

    def get_binary_buffer_data(self, channel, start_bin, bins):
        """Get the points stored in a channel buffer range.

        The values are returned as IEEE format binary floating point
        numbers with the units of the trace.

        Bins (or points) a labelled from 0 (oldest) to N-1 (newest)
        where N is the total number of bins.

        If data storage is set to Loop mode, storage is paused before
        reading any data. This is because the points are indexed relative
        to the most recent point which is continually changing.

        Parameters
        ----------
        channel : {1, 2}
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest.
        bins : int
            Number of bins to read.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        cmd = f"TRCB? {channel},{start_bin},{bins}"

        output_interface = self.get_output_interface()
        if output_interface == "RS232":
            # TODO: When using the RS232 interface, the word length must be 8 bits
            expect_termination = False
            logger.warning(
                f"SRS recommends not using binary transfers over serial interfaces."
            )
        elif output_interface == "GPIB":
            expect_termination = True

        # pause storage if loop mode
        buffer_mode = self.get_end_of_buffer_mode()
        if buffer_mode == "Loop":
            self.pause()

        # TODO: When using GPIB, make sure that the software is configured to NOT
        # terminate reading upon receipt of a CR or LF
        buffer = self.instr.query_binary_values(
            cmd,
            container=tuple(),
            expect_termination=expect_termination,
            data_points=bins,
        )

        # restart loop storage if previously set
        if buffer_mode == "Loop":
            self.set_end_of_buffer_mode(mode=1)

        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

        return buffer

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
        channel : {1, 2}
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest.
        bins : int
            Number of bins to read.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        cmd = f"TRCL? {channel},{start_bin},{bins}"
        # TODO: fix formatting
        buffer = self.instr.query(cmd).split(",")
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return buffer

    def set_data_transfer_mode(self, mode):
        """Set the data transfer mode.

        GPIB only.

        Parameters
        ----------
        mode : {0, 1, 2}
            Data transfer mode:
                
                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        cmd = f"FAST {mode}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_data_transfer_mode(self):
        """Get the data transfer mode.

        Returns
        -------
        mode : {0, 1, 2}
            Data transfer mode:
                
                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        cmd = f"FAST?"
        mode = self.data_transfer_modes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return mode

    def start_scan(self):
        """Start scan.

        After turning on fast data transfer, this function starts
        the scan after a delay of 0.5 sec. Do not use the STRT command to start the
        scan with fast mode enabled.
        """
        cmd = f"STRD"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    # --- Interface commands ---
    # TODO: check differences between RS232 and GPIB. PyVISA might provide GPIB.

    def reset(self):
        """Reset the instrument to the default configuration."""
        cmd = f"*RST"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_id(self):
        """Get the device identification string.

        The string is in the format "Stanford_Research_Systems,SR830,s/n00111,ver1.000",
        where, for example, the serial number is 00111 and the firmware version is 1.000.
        
        Returns
        -------
        idn : str
            identification string
        """
        cmd = f"*IDN?"
        idn = self.instr.query(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return idn

    def set_local_mode(self, local):
        """Set the local/remote function.

        Parameters
        ----------
        local : {0, 1, 2}
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        cmd = f"LOCL {local}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_local_mode(self):
        """Get the local/remote function.

        Returns
        -------
        local : {0, 1, 2}
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        cmd = "LOCL?"
        local = self.local_modes[int(self.instr.query(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return local

    def set_gpib_overide_remote(self, condition):
        """Set the GPIB overide remote condition.

        Parameters
        ----------
        condition : int
            GPIB overide remote condition:
                
                * 0 : No
                * 1 : Yes
        """
        cmd = f"OVRM {condition}"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")

    def get_gpib_overide_remote(self):
        """Get the GPIB overide remote condition.

        Returns
        -------
        condition : int
            GPIB overide remote condition:
                
                * 0 : No
                * 1 : Yes
        """
        cmd = f"OVRM?"
        condition = self.gpib_overide_remote_conditions[int(self.instr.write(cmd))]
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")
        return condition

    # --- Status reporting commands ---
    # TODO: see if PyVISA implements these

    def clear_status_registers(self):
        """Clear all status registers."""
        cmd = "*CLS"
        self.instr.write(cmd)
        logger.info(f"{self.serial_number}, cmd: '{cmd}'")


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
