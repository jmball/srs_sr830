"""Virtual Stanford Research Systems SR830 lock-in amplifier (LIA) control library.

Returns dummy responses for testing instrument commands wihtout access to the
instrument.
"""
import logging


logging.captureWarnings(True)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class sr830:
    """Virtual Stanford Research Systems SR830 LIA instrument.

    All get methods return 0, an empty dictionary, or a list/tuple of 0's of length
    determined by method arguments. Set methods all `pass` without returning a
    status.
    """

    # --- class variables ---

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

    # --- private class variables ---

    _enable_register_cmd_dict = {
        "standard_event": "*ESE",
        "serial_poll": "*SRE",
        "error": "ERRE",
        "lia_status": "LIAE",
    }

    _status_byte_cmd_dict = {
        "standard_event": "*ESR?",
        "serial_poll": "*STB?",
        "error": "ERRS?",
        "lia": "LIAS?",
    }

    # Meaning of status bits. Indices of outer list are same are bit numbers.
    # Indices of inner lists give description of event or state.
    _serial_poll_status_bit_names = [
        "SCN",
        "IFC",
        "ERR",
        "LIA",
        "MAV",
        "ESB",
        "SRQ",
        "Unused",
    ]
    _serial_poll_status_byte = [
        ["", "No scan in progress"],
        ["", "No command execution in progress"],
        ["", "An enabled bit in error status byte has been set"],
        ["", "An enabled bit in LIA status byte has been set"],
        ["", "Interface output buffer is non-empty"],
        ["", "An enabled bit in standard status byte has been set"],
        ["", "A service request has occured"],
        ["", ""],
    ]

    _standard_event_status_bit_names = [
        "INP",
        "Unused",
        "QRY",
        "Unused",
        "EXE",
        "CMD",
        "URQ",
        "PON",
    ]
    _standard_event_status_byte = [
        ["", "Input queue overflow"],
        ["", ""],
        ["", "Output queue overflow"],
        ["", ""],
        ["", "Command cannot execute/parameter out of range"],
        ["", "Received illegal command"],
        ["", "Key pressed/knob rotated"],
        ["", "Power-on"],
    ]

    _lia_status_bit_names = [
        "INPUT/RESRV",
        "FILTR",
        "OUTPUT",
        "UNLK",
        "RANGE",
        "TC",
        "TRIG",
        "Unused",
    ]
    _lia_status_byte = [
        ["", "Input or amplifier overload"],
        ["", "Time constant filter overload"],
        ["", "Output overload"],
        ["", "Reference unlock detected"],
        ["", "Detection frequency switched range"],
        ["", "Time constant changed indirectly"],
        ["", "Data storage triggered"],
        ["", ""],
    ]

    _error_status_bit_names = [
        "Unused",
        "Backup error",
        "RAM error",
        "Unused",
        "ROM error",
        "GPIB error",
        "DSP error",
        "Math error",
    ]
    _error_status_byte = [
        ["", ""],
        ["", "Battery backup has failed"],
        ["", "RAM memory test found error"],
        ["", ""],
        ["", "ROM memory test found error"],
        ["", "GPIB fast data transfer mode aborted"],
        ["", "DSP test found error"],
        ["", "Internal math error"],
    ]

    def __init__(self, return_int=False, check_errors=True):
        """Initialise object.

        Parameters
        ----------
        return_int : bool, optional
            The raw instrument response to a parameter query where the parameter values
            are elements of a limited set is an integer that maps to a human-readable
            value. If True, the raw integer is returned by the query method. If False,
            the human-readable value that the integer maps to is returned by the query
            method.
        check_errors : bool, optional
            Check instrument error status after every command.
        """
        self.return_int = return_int
        self.check_errors = check_errors

    def __del__(self):
        """Ensure front panel unlocked if class instance is destroyed before disconnect."""
        self.disconnect()

    def connect(
        self,
        resource_name,
        output_interface,
        reset=True,
        set_default_configuration=True,
        local_lockout=False,
        **resource_kwargs,
    ):
        """Conntect to the instrument.

        Parameters
        ----------
        resource_name : str
            Full VISA resource name, e.g. "ASRL2::INSTR", "GPIB0::14::INSTR" etc. See
            https://pyvisa.readthedocs.io/en/latest/introduction/names.html for more
            info on correct formatting for resource names.
        output_interface : {0, 1}
            Communication interface on the lock-in amplifier rear panel used to read
            instrument responses. Although the SR830 can read commands from both
            interfaces at any time, it can only send responses over one. This does not
            need to match the VISA resource interface type if, for example, an
            interface adapter is used between the control computer and the instrument.
            Valid output communication interfaces:

                * 0 : RS232
                * 1 : GPIB

        reset : bool, optional
            Reset the instrument to the built-in default configuration.
        set_default_configuration : bool, optional
            If True, set all configuration settings to defaults defined in the
            `set_configuraiton` method.
        local_lockout : bool, optional
            If True all front panel keys are disabled, including the 'Local' key. If
            False all keys except the 'Local' key are disabled, which the user may
            press to manually return the instrument to local control.
        resource_kwargs : dict
            Keyword arguments to be used to change instrument attributes after
            construction.
        """
        # self.instr = rm.open_resource(resource_name, **resource_kwargs)
        # if reset is True:
        #     self.reset()
        # self.enable_all_status_bytes()
        # if local_lockout is True:
        #     self.set_local_mode(2)
        # else:
        #     self.set_local_mode(1)
        # self.set_output_interface(output_interface)
        # logger.info(f"{','.join(self.get_id())} connected!")
        # if set_default_configuration is True:
        #     self.set_configuration()
        logger.info(f"Virtual SRS SR830 connected!")

    def disconnect(self):
        """Disconnect the instrument after returning to local mode."""
        # self.set_local_mode(0)
        # self.instr.close()
        pass

    def set_configuration(
        self,
        input_configuration=0,
        input_coupling=0,
        ground_shielding=1,
        line_notch_filter_status=3,
        ref_source=0,
        detection_harmonic=1,
        ref_trigger=1,
        ref_freq=1000,
        sensitivity=26,
        reserve_mode=1,
        time_constant=8,
        low_pass_filter_slope=1,
        sync_status=0,
        ch1_display=1,
        ch2_display=1,
        ch1_ratio=0,
        ch2_ratio=0,
    ):
        """Set the instrument configuration.

        Parameters
        ----------
        input_configuration : {0, 1, 2, 3}
            Input configuration:

                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)

        input_coupling : {0, 1}
            Input coupling:

                * 0 : AC
                * 1 : DC

        ground_shielding : {0, 1}
            Input shield grounding:

                * 0 : Float
                * 1 : Ground

        line_notch_filter_status : {0, 1, 2, 3}
            Input line notch filter status:

                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in

        ref_source : {0, 1}
            Refernce source:

                * 0 : external
                * 1 : internal

        detection_harmonic : int
            Detection harmonic, 1 =< harmonic =< 19999.
        ref_trigger : {0, 1, 2}
            Trigger type:

                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge

        ref_freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
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

        reserve_mode : {0, 1, 2}
            Reserve mode:

                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise

        time_constant : {0 - 19}
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

        low_pass_filter_slope : {0, 1, 2, 3}
            Low pass filter slope in dB/oct:

                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24

        sync_status : {0, 1}
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz

        ch1_display : {0, 1, 2, 3, 4}
            Display parameter for CH1:

                * 0 : X
                * 1 : R
                * 2 : X Noise
                * 3 : Aux In 1
                * 4 : Aux In 2

        ch2_display : {0, 1, 2, 3, 4}
            Display parameter for CH2:

                * 0 : Y
                * 1 : Phase
                * 2 : Y Noise
                * 3 : Aux In 3
                * 4 : Aux In 4

        ch1_ratio : {0, 1, 2}
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2

        ch2_ratio : {0, 1, 2}
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 3
                * 2 : Aux In 4
        """
        # self.set_input_configuration(input_configuration)
        # self.set_input_coupling(input_coupling)
        # self.set_input_shield_gnd(ground_shielding)
        # self.set_line_notch_status(line_notch_filter_status)
        # self.set_ref_source(ref_source)
        # self.set_harmonic(detection_harmonic)
        # self.set_reference_trigger(ref_trigger)
        # self.set_ref_freq(ref_freq)
        # self.set_sensitivity(sensitivity)
        # self.set_reserve_mode(reserve_mode)
        # self.set_time_constant(time_constant)
        # self.set_lp_filter_slope(low_pass_filter_slope)
        # self.set_sync_status(sync_status)
        # self.set_display(1, ch1_display, ch1_ratio)
        # self.set_display(2, ch2_display, ch2_ratio)
        pass

    def get_configuration(self):
        """Get the instrument configuration.

        Returns
        -------
        configuration : dict
            Configuration dictionary with the following keys:

                * input_configuration
                * input_coupling
                * ground_shielding
                * line_notch_filter_status
                * ref_source
                * detection_harmonic
                * ref_trigger
                * ref_freq
                * sensitivity
                * reserve_mode
                * time_constant
                * low_pass_filter_slope
                * sync_status
                * ch1_display
                * ch2_display
                * ch1_ratio
                * ch2_ratio
        """
        # input_configuration = self.get_input_configuration()
        # input_coupling = self.get_input_coupling()
        # ground_shielding = self.get_input_shield_gnd()
        # line_notch_filter_status = self.get_line_notch_status()
        # ref_source = self.get_ref_source()
        # detection_harmonic = self.get_harmonic()
        # ref_trigger = self.get_reference_trigger()
        # ref_freq = self.get_ref_freq()
        # sensitivity = self.get_sensitivity()
        # reserve_mode = self.get_reserve_mode()
        # time_constant = self.get_time_constant()
        # low_pass_filter_slope = self.get_low_pass_filter_slope()
        # sync_status = self.get_sync_status()
        # ch1_display, ch1_ratio = self.get_display(1)
        # ch2_display, ch2_ratio = self.get_display(2)

        # configuration = {
        #     "input_configuration": input_configuration,
        #     "input_coupling": input_coupling,
        #     "ground_shielding": ground_shielding,
        #     "line_notch_filter_status": line_notch_filter_status,
        #     "ref_source": ref_source,
        #     "detection_harmonic": detection_harmonic,
        #     "ref_trigger": ref_trigger,
        #     "ref_freq": ref_freq,
        #     "sensitivity": sensitivity,
        #     "reserve_mode": reserve_mode,
        #     "time_constant": time_constant,
        #     "low_pass_filter_slope": low_pass_filter_slope,
        #     "sync_status": sync_status,
        #     "ch1_display": ch1_display,
        #     "ch1_ratio": ch1_ratio,
        #     "ch2_display": ch2_display,
        #     "ch2_ratio": ch2_ratio,
        # }

        # return configuration
        return {}

    def enable_all_status_bytes(self):
        """Enable all status bytes."""
        # registers = ["standard_event", "serial_poll", "error", "lia_status"]
        # for register in registers:
        #     self.set_enable_register(register, 255, decimal=True)
        pass

    def error_check(self):
        """Check for errors."""
        # sp = self.get_status_byte("serial_poll")
        # sp = format(sp, "b")
        # errors = []

        # # check if the interface output buffer is non-empty
        # if sp[4] == "1":
        #     errors.append(self._serial_poll_status_byte[4][1])

        # # if any bits in error status byte are enabled check if they constitute an error
        # if sp[2] == "1":
        #     esb = self.get_status_byte("error")
        #     esb = format(esb, "b")
        #     for i, bit in enumerate(esb):
        #         if bit == "1":
        #             errors.append(self._error_status_byte[i][1])

        # # if any bits in LIA status byte are enabled check if they constitute an error
        # if sp[3] == "1":
        #     lsb = self.get_status_byte("lia")
        #     lsb = format(lsb, "b")
        #     for i, bit in enumerate(lsb[:4]):
        #         if bit == "1":
        #             errors.append(self._lia_status_byte[i][1])

        # # if any bits in standard event status byte are enabled check if they
        # # constitute an error
        # if sp[5] == "1":
        #     sesb = self.get_status_byte("standard_event")
        #     sesb = format(sesb, "b")
        #     sesb_error_bits = [0, 2, 4, 5]
        #     for i in sesb_error_bits:
        #         if sesb[i] == "1":
        #             errors.append(self._standard_event_status_byte[i][1])

        # if len(errors) != 0:
        #     warnings.warn(f"Instrument reported errors: {', '.join(errors)}.")
        pass

    # --- Reference and phase commands ---

    def set_ref_phase_shift(self, phase_shift):
        """Set the reference phase shift.

        Parameters
        ----------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        # cmd = f"PHAS {phase_shift}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_ref_phase_shift(self):
        """Get the reference phase shift.

        Returns
        -------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        # cmd = f"PHAS?"
        # phase_shift = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return phase_shift
        return 0.0

    def set_ref_source(self, source):
        """Set the reference source.

        Parameters
        ----------
        source : {0, 1}
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        # cmd = f"FMOD {source}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_ref_source(self):
        """Get the reference source.

        Returns
        -------
        source : {0, 1}
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        # cmd = f"FMOD?"
        # source = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return source
        # else:
        #     return self.reference_sources[source]
        return 0

    def set_ref_freq(self, freq):
        """Set the frequency of the internal oscillator.

        Parameters
        ----------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        # cmd = f"FREQ {freq}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_ref_freq(self):
        """Get the reference frequency.

        Returns
        -------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        # cmd = f"FREQ?"
        # freq = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return freq
        return 0.0

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
        # cmd = f"RSLP {trigger}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()

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
        # cmd = f"RSLP?"
        # trigger = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return trigger
        # else:
        #     return self.triggers[trigger]
        return 0

    def set_harmonic(self, harmonic):
        """Set detection harmonic.

        Parameters
        ----------
        harmonic : int
            Detection harmonic, 1 =< harmonic =< 19999.
        """
        # cmd = f"HARM {harmonic}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_harmonic(self):
        """Get detection harmonic.

        Returns
        -------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        # cmd = f"HARM?"
        # harmonic = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return harmonic
        return 0

    def set_sine_amplitude(self, amplitude):
        """Set the amplitude of the sine output.

        Parameters
        ----------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        # cmd = f"SLVL {amplitude}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_sine_amplitude(self):
        """Get the amplitude of the sine output.

        Returns
        -------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        # cmd = f"SLVL?"
        # amplitude = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return amplitude
        return 0.0

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
        # cmd = f"ISRC {config}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()

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
        # cmd = f"ISRC?"
        # config = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return config
        # else:
        #     return self.input_configurations[config]
        return 0

    def set_input_shield_gnd(self, grounding):
        """Set input shield grounding.

        Parameters
        ----------
        grounding : {0, 1}
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        # cmd = f"IGND {grounding}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_input_shield_gnd(self):
        """Get input shield grounding.

        Returns
        -------
        grounding : {0, 1}
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        # cmd = f"IGND?"
        # grounding = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return grounding
        # else:
        #     return self.groundings[grounding]
        return 0

    def set_input_coupling(self, coupling):
        """Set input coupling.

        Parameters
        ----------
        coupling : {0, 1}
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        # cmd = f"ICPL {coupling}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_input_coupling(self):
        """Get input coupling.

        Returns
        -------
        coupling : {0, 1}
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        # cmd = f"ICPL?"
        # coupling = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return coupling
        # else:
        #     return self.input_couplings[coupling]
        return 0

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
        # cmd = f"ILIN {status}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_line_notch_status(self):
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
        # cmd = f"ILIN?"
        # status = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return status
        # else:
        #     return self.input_line_notch_filter_statuses[status]
        return 0

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
        # cmd = f"SENS {sensitivity}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"SENS?"
        # sensitivity = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return sensitivity
        # else:
        #     return self.sensitivities[sensitivity]
        return 1e-6

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
        # cmd = f"RMOD {mode}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"RMOD?"
        # mode = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return mode
        # else:
        #     self.reserve_modes[mode]
        return 0

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
        # cmd = f"OFLT {tc}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"OFLT?"
        # tc = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return tc
        # else:
        #     return self.time_constants[tc]
        return 0

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
        # cmd = f"OFSL {slope}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_low_pass_filter_slope(self):
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
        # cmd = f"OFSL?"
        # slope = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return slope
        # else:
        #     return self.low_pass_filter_slopes[slope]
        return 0

    def set_sync_status(self, status):
        """Set synchronous filter status.

        Parameters
        ----------
        status : {0, 1}
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        # cmd = f"SYNC {status}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_sync_status(self):
        """Get synchronous filter status.

        Returns
        -------
        status : {0, 1}
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        # cmd = f"SYNC?"
        # status = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return status
        # else:
        #     return self.synchronous_filter_statuses[status]
        return 0

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
                * 1 : Aux In 3
                * 2 : Aux In 4
        """
        # cmd = f"DDEF {channel}, {display}, {ratio}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"DDEF? {channel}"
        # resp = self.instr.write(cmd)
        # display, ratio = resp.split(",")
        # display = int(display)
        # ratio = int(ratio)

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return display, ratio
        # else:
        #     if channel == 1:
        #         return self.display_ch1[display], self.ratio_ch1[ratio]
        #     elif channel == 2:
        #         return self.display_ch2[display], self.ratio_ch2[ratio]
        #     else:
        #         raise ValueError(f"Invalid channel, {channel}")
        return 0, 0

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
        # cmd = f"FPOP {channel}, {output}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"FPOP? {channel}"
        # output = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return output
        # else:
        #     if channel == 1:
        #         return self.front_panel_output_sources_ch1[output]
        #     elif channel == 2:
        #         return self.front_panel_output_sources_ch2[output]
        #     else:
        #         raise ValueError(f"Invalid channel, {channel}")
        return 0

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
        # cmd = f"OEXP {parameter}, {offset}, {expand}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        return 0

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
        # cmd = f"OEXP? {parameter}"
        # resp = self.instr.query(cmd)
        # offset, expand = resp.split(",")
        # offset = float(offset)
        # expand = int(expand)

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return offset, expand
        # else:
        #     return offset, self.expands[expand]
        return 0

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
        # cmd = f"AOFF {parameter}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"OAUX? {aux_in}"
        # voltage = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return voltage
        return 0

    def set_aux_out(self, aux_out, voltage):
        """Set voltage of auxiliary output.

        Parameters
        ----------
        aux_out : {1, 2, 3, 4}
            Auxiliary output (1, 2, 3, or 4).
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        # cmd = f"AUXV {aux_out}, {voltage}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"AUXV? {aux_out}"
        # voltage = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return voltage
        return 0

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
        # cmd = f"OUTX {interface}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_output_interface(self):
        """Get the output communication interface.

        Returns
        -------
        interface : {0, 1}
            Output communication interface:

                * 0 : RS232
                * 1 : GPIB
        """
        # cmd = f"OUTX?"
        # interface = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return interface
        # else:
        #     return self.communication_interfaces[interface]
        return 0

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
        # cmd = f"OVRM {status}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def set_key_click_state(self, state):
        """Set key click state.

        Parameters
        ----------
        state : {0, 1}
            Key click state:

                * 0 : Off
                * 1 : On
        """
        # cmd = f"KCLK {state}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_key_click_state(self):
        """Get key click state.

        Returns
        -------
        state : {0, 1}
            Key click state:

                * 0 : Off
                * 1 : On
        """
        # cmd = f"KCLK?"
        # state = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return state
        # else:
        #     return self.key_click_states[state]
        return 0

    def set_alarm(self, status):
        """Set the alarm status.

        Parameters
        ----------
        status : {0, 1}
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        # cmd = f"ALRM {status}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()

    def get_alarm(self):
        """Get the alarm status.

        Returns
        -------
        status : {0, 1}
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        # cmd = f"ALRM?"
        # status = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return status
        # else:
        #     return self.alarm_statuses[status]
        return 0

    def save_setup(self, number):
        """Save the lock-in setup in a settings buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        # cmd = f"SSET {number}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def recall_setup(self, number):
        """Recall lock-in setup from setting buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        # cmd = f"RSET {number}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    # --- Auto functions ---

    def auto_gain(self):
        """Automatically set the gain.

        Does nothing if the time constant is greater than 1 second.
        """
        # cmd = f"AGAN"
        # self.instr.write(cmd)

        # # poll serial poll status byte to determine whether execution in progress
        # ifc = self.get_status_byte(status_byte="serial_poll", bit=1)
        # while ifc != 1:
        #     ifc = self.get_status_byte(status_byte="serial_poll", bit=1)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def auto_reserve(self):
        """Automatically set reserve."""
        # cmd = f"ARSV"
        # self.instr.write(cmd)

        # # poll serial poll status byte to determine whether execution in progress
        # ifc = self.get_status_byte(status_byte="serial_poll", bit=1)
        # while ifc != 1:
        #     ifc = self.get_status_byte(status_byte="serial_poll", bit=1)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def auto_phase(self):
        """Automatically set phase."""
        # cmd = f"APHS"
        # self.instr.write(cmd)

        # # poll serial poll status byte to determine whether execution in progress
        # ifc = self.get_status_byte(status_byte="serial_poll", bit=1)
        # while ifc != 1:
        #     ifc = self.get_status_byte(status_byte="serial_poll", bit=1)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"SRAT {rate}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"SRAT?"
        # rate = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return rate
        # else:
        #     return self.sample_rates[rate]
        return 0

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
        # cmd = f"SEND {mode}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_end_of_buffer_mode(self):
        """Get the end of buffer mode.

        Returns
        ----------
        mode : {0, 1} or str
            End of buffer mode:

                * 0 : 1 Shot
                * 1 : Loop
        """
        # cmd = f"SEND?"
        # mode = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return mode
        # else:
        #     return self.end_of_buffer_modes[mode]
        return 0

    def trigger(self):
        """Send software trigger."""
        # cmd = f"TRIG"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def set_trigger_start_mode(self, mode):
        """Set the trigger start mode.

        Parameters
        ----------
        mode : {0, 1}
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        # cmd = f"TSTR {mode}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_trigger_start_mode(self):
        """Get the trigger start mode.

        Returns
        -------
        mode : {0, 1} or str
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        # cmd = f"TSTR?"
        # mode = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return mode
        # else:
        #     return self.trigger_start_modes[mode]
        return 0

    def start(self):
        """Start or resume data storage.

        Ignored if storage already in progress.
        """
        # cmd = f"STRT"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def pause(self):
        """Pause data storage.

        Ignored if storage is already paused or reset.
        """
        # cmd = f"PAUS"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def reset_data_buffers(self):
        """Reset data buffers.

        This command will erase the data buffer.
        """
        # cmd = f"REST"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"OUTP? {parameter}"
        # value = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return value
        return 0.5e-6

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
        # cmd = f"OUTR? {channel}"
        # value = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return value
        return 0.0

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
        # parameters = ",".join([str(i) for i in parameters])
        # cmd = f"SNAP? {parameters}"
        # values = self.instr.query(cmd).split(",")

        # if self.check_errors is True:
        #     self.error_check()

        # return (float(i) for i in values)
        return (1.0 for i in parameters)

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
        # cmd = f"OAUX? {aux_in}"
        # voltage = float(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return voltage
        return 0.0

    def get_buffer_size(self):
        """Get the number of points stored in the buffer.

        Returns
        -------
        N : int
            Number of points in the buffer.
        """
        # cmd = f"SPTS?"
        # N = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return N
        return 0

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
        # cmd = f"TRCA? {channel},{start_bin},{bins}"

        # # pause storage if loop mode
        # buffer_mode = self.get_end_of_buffer_mode()
        # if buffer_mode == "Loop":
        #     self.pause()

        # buffer = self.instr.query_ascii_values(cmd, container=tuple())

        # if self.check_errors is True:
        #     self.error_check()

        # # restart loop storage if previously set
        # if buffer_mode == "Loop":
        #     self.set_end_of_buffer_mode(mode=1)

        # return buffer
        return (0.0 for i in range(bins))

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
        # cmd = f"TRCB? {channel},{start_bin},{bins}"

        # output_interface = self.get_output_interface()
        # if (output_interface == "RS232") or (output_interface == 0):
        #     expect_termination = False
        #     warnings.warn(
        #         f"SRS recommends not using binary transfers over serial interfaces."
        #     )
        # elif (output_interface == "GPIB") or (output_interface == 1):
        #     expect_termination = True

        # # pause storage if loop mode
        # buffer_mode = self.get_end_of_buffer_mode()
        # if buffer_mode == "Loop":
        #     self.pause()

        # buffer = self.instr.query_binary_values(
        #     cmd,
        #     datatype="f",
        #     container=tuple(),
        #     expect_termination=expect_termination,
        #     data_points=bins,
        # )

        # if self.check_errors is True:
        #     self.error_check()

        # # restart loop storage if previously set
        # if buffer_mode == "Loop":
        #     self.set_end_of_buffer_mode(mode=1)

        # return buffer
        return (0.0 for i in range(bins))

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
        # cmd = f"TRCL? {channel},{start_bin},{bins}"

        # output_interface = self.get_output_interface()
        # if (output_interface == "RS232") or (output_interface == 0):
        #     expect_termination = False
        #     warnings.warn(
        #         f"SRS recommends not using binary transfers over serial interfaces."
        #     )
        # elif (output_interface == "GPIB") or (output_interface == 1):
        #     expect_termination = True

        # # pause storage if loop mode
        # buffer_mode = self.get_end_of_buffer_mode()
        # if buffer_mode == "Loop":
        #     self.pause()

        # # Although each value requires 4 bytes to be represented, read bytes into array
        # # 2 at time for later formatting, i.e. datatype is 'h' (short). Also, therefore
        # # read twice as many 2-byte values as 4-byte bins.
        # buffer = self.instr.query_binary_values(
        #     cmd,
        #     datatype="h",
        #     is_big_endian=False,
        #     container=list(),
        #     expect_termination=expect_termination,
        #     data_points=2 * bins,
        # )

        # if self.check_errors is True:
        #     self.error_check()

        # # Convert raw byte array into array of floats using SR830 format
        # mantissa_buffer = buffer[::2]
        # exp_buffer = buffer[1::2]
        # buffer = [m * 2 ** (e - 124) for m, e in zip(mantissa_buffer, exp_buffer)]
        # buffer = tuple(buffer)

        # # restart loop storage if previously set
        # if buffer_mode == "Loop":
        #     self.set_end_of_buffer_mode(mode=1)

        # return buffer
        return (0.0 for i in range(bins))

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
        # cmd = f"FAST {mode}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = f"FAST?"
        # mode = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return mode
        # else:
        #     return self.data_transfer_modes[mode]
        return 0

    def start_scan(self):
        """Start scan.

        After turning on fast data transfer, this function starts
        the scan after a delay of 0.5 sec. Do not use the STRT command to start the
        scan with fast mode enabled.
        """
        # cmd = f"STRD"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    # --- Interface commands ---

    def reset(self):
        """Reset the instrument to the default configuration."""
        # cmd = f"*RST"
        # self.instr.write(cmd)

        # # poll serial poll status byte to determine whether execution in progress
        # # TODO: test if enable status byte registers are set by default. If not, this
        # # won't work
        # ifc = self.get_status_byte(status_byte="serial_poll", bit=1)
        # while ifc != 1:
        #     ifc = self.get_status_byte(status_byte="serial_poll", bit=1)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_id(self):
        """Get the device identification string.

        The string is in the format "Stanford_Research_Systems,SR830,s/n00111,ver1.000",
        where, for example, the serial number is 00111 and the firmware version is
        1.000.

        Returns
        -------
        idn : list
            List of identification strings consisting of manufacturer, model, serial
            number, and firmware version number in order.
        """
        # cmd = f"*IDN?"
        # idn = self.instr.query(cmd).split(",")

        # if self.check_errors is True:
        #     self.error_check()

        # return idn
        return ["Stanford_Research_Systems", "SR830", "Virtual", "ver0"]

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
        # cmd = f"LOCL {local}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

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
        # cmd = "LOCL?"
        # local = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return local
        # else:
        #     return self.local_modes[local]
        return 0

    def set_gpib_overide_remote(self, condition):
        """Set the GPIB overide remote condition.

        Parameters
        ----------
        condition : int
            GPIB overide remote condition:

                * 0 : No
                * 1 : Yes
        """
        # cmd = f"OVRM {condition}"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_gpib_overide_remote(self):
        """Get the GPIB overide remote condition.

        Returns
        -------
        condition : int
            GPIB overide remote condition:

                * 0 : No
                * 1 : Yes
        """
        # cmd = f"OVRM?"
        # condition = int(self.instr.write(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # if self.return_int is True:
        #     return condition
        # else:
        #     return self.gpib_overide_remote_conditions[condition]
        return 0

    # --- Status reporting commands ---

    def clear_status_registers(self):
        """Clear all status registers."""
        # cmd = "*CLS"
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def set_enable_register(self, register, value, decimal=True, bit=None):
        """Set an enable register.

        Parameters
        ----------
        register : {"standard_event", "serial_poll", "error", "lia_status"}
            Enable register to set.
        value : {0-255} or {0, 1}
            Value of standard event enable register. If decimal is true, value is in
            the range 0-255. Otherwise value is applied to a specific bit given by
            argument to 0 or 1.
        decimal : bool, optional
            If `value` is decimal or binary.
        bit : None or {0-7}, optional
            Specific bit to set with a binary value.
        """
        # if decimal is True:
        #     if (value >= 0) & (value <= 255):
        #         cmd = f"{self._enable_register_cmd_dict[register]} {value}"
        #     else:
        #         raise ValueError(
        #             f"Value: {value} is out of range. Must be in range 0-255 if decimal."
        #         )
        # else:
        #     if (bit >= 0) & (bit <= 7) & ((value == 0) or (value == 1)):
        #         cmd = f"{self._enable_register_cmd_dict[register]} {bit},{value}"
        #     else:
        #         raise ValueError(
        #             f"Bit: {bit}, or Value: {value} is out of range. Bit must in range 0-7 and value must be 0 or 1 if value is not decimal."
        #         )
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_enable_register(self, register, bit=None):
        """Get the standard event enable register value.

        Parameters
        ----------
        register : {"standard_event", "serial_poll", "error", "lia_status"}
            Enable register to get.
        bit : None or {0-7}, optional
            Specific bit to query. If `None`, query entire byte.

        Returns
        -------
        value : int
            Register value.
        """
        # if bit is None:
        #     cmd = f"{self._enable_register_cmd_dict[register]}?"
        # else:
        #     if (bit >= 0) & (bit <= 7):
        #         cmd = f"{self._enable_register_cmd_dict[register]}? {bit}"
        #     else:
        #         raise ValueError(
        #             f"{bit} is out of range. Bit must be in range 0-7 if specified."
        #         )
        # value = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return value
        return 0

    def get_status_byte(self, status_byte, bit=None):
        """Get a status byte.

        This function has no error check to avoid infinite recursion.

        Parameters
        ----------
        status_byte : {"standard_event", "serial_poll", "error", "lia"}
            Status byte to get.
        bit : None or {0-7}, optional
            Specific bit to get with a binary value. If `None` query entire byte.

        Returns
        -------
        value : int
            Status byte value.
        """
        # if bit is None:
        #     cmd = f"{self._status_byte_cmd_dict[status_byte]}"
        # else:
        #     if (bit >= 0) & (bit <= 7):
        #         cmd = f"{self._status_byte_cmd_dict[status_byte]} {bit}"
        #     else:
        #         raise ValueError(
        #             f"{bit} is out of range. Bit must be in range 0-7 if specified."
        #         )
        # return int(self.instr.query(cmd))
        return 0

    def set_power_on_status_clear_bit(self, value):
        """Set the power-on status clear bit.

        Parameters
        ----------
        value : {0, 1}
            Value of power-on status clear bit. Values:

                * 0 : Cleared, status enable registers maintain values at power down.
                * 1 : Set, all status and enable registers are cleared on power up.
        """
        # if (value == 0) or (value == 1):
        #     cmd = f"*PSC {value}"
        # else:
        #     raise ValueError(f'Invalid value "{value}". Value must be 0 or 1.')
        # self.instr.write(cmd)

        # if self.check_errors is True:
        #     self.error_check()
        pass

    def get_power_on_status_clear_bit(self):
        """Get the power-on status clear bit.

        Returns
        -------
        value : int
            Power-on status clear bit value.
        """
        # cmd = f"*PSC?"
        # value = int(self.instr.query(cmd))

        # if self.check_errors is True:
        #     self.error_check()

        # return value
        return 0
