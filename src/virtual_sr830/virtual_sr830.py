"""Virtual Stanford Research Systems SR830 lock-in amplifier (LIA) control library.

The full instrument manual, including the programming guide, can be found at
https://www.thinksrs.com/downloads/pdfs/manuals/SR830m.pdf.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from types import TracebackType
from typing import Any

import pyvisa
from pyvisa.constants import InterfaceType
from sr830._connection import connection_kwargs, resolve_output_interface
from sr830.settings import (
    AuxiliaryChannel,
    Channel,
    Channel1Display,
    Channel1Ratio,
    Channel2Display,
    Channel2Ratio,
    DataTransferMode,
    EndOfBufferMode,
    ErrorBit,
    ErrorFlag,
    FrontPanelOutputSource,
    GpibOverrideRemote,
    InputConfiguration,
    InputCoupling,
    InputShieldGrounding,
    LiaStatusBit,
    LiaStatusFlag,
    LineNotchFilter,
    LocalMode,
    LowPassFilterSlope,
    MeasurementParameter,
    OutputExpansion,
    OutputInterface,
    OutputParameter,
    ReferenceSource,
    ReferenceTrigger,
    ReserveMode,
    SampleRate,
    Sensitivity,
    SerialPollBit,
    SerialPollFlag,
    StandardEventBit,
    StandardEventFlag,
    StatusRegister,
    SwitchState,
    SynchronousFilter,
    TimeConstant,
    TriggerStartMode,
    _ENABLE_REGISTER_COMMANDS,
    _STATUS_REGISTER_COMMANDS,
    _validate_enum,
    _validate_register_bit,
    _validate_register_value,
)

import warnings


class VirtualSR830:
    """Virtual Stanford Research Systems SR830 LIA instrument."""

    def __init__(self) -> None:
        """Initialise dummy properties."""
        self._connected = False
        self._set_dummy_properties()

    def __enter__(self) -> VirtualSR830:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object."""
        self.disconnect()

    def _set_dummy_properties(self) -> None:
        """Initialise dummy properties."""
        self._errors: list[str] = []
        self._reference_phase_shift: float = 0
        self._reference_source = 0
        self._reference_frequency: float = 1000
        self._reference_trigger = 0
        self._harmonic = 1
        self._sine_amplitude: float = 1
        self._input_configuration = 0
        self._input_shield_grounding = 0
        self._input_coupling = 0
        self._line_notch_filter_status = 0
        self._sensitivity = 26
        self._reserve_mode = 1
        self._time_constant = 8
        self._lowpass_filter_slope = 1
        self._sync_filter_status = 0
        self._output_interface = 0
        self._ch1_display = 0
        self._ch1_ratio = 0
        self._ch2_display = 0
        self._ch2_ratio = 0
        self._ch1_output = 0
        self._ch2_output = 0
        self._X_offset: float = 0
        self._X_expand = 0
        self._Y_offset: float = 0
        self._Y_expand = 0
        self._R_offset: float = 0
        self._R_expand = 0
        self._aux_out_1: float = 0
        self._aux_out_2: float = 0
        self._aux_out_3: float = 0
        self._aux_out_4: float = 0
        self._key_click_state = 0
        self._alarm_status = 0
        self._sample_rate = 13
        self._end_of_buffer_mode = 0
        self._trigger_start_mode = 0
        self._buffer_size = 0
        self._data_transfer_mode = 0
        self._idn = "Dummy_Stanford_Research_Systems,SR830,s/n00000,ver0.000"
        self._local_mode = 0
        self._gpib_override_remote = 0
        self._power_on_status_clear_bit = 0

    def connect(
        self,
        resource_name: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        output_interface: OutputInterface | int | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Select the virtual response interface without opening a VISA resource.

        Infer ASRL/GPIB resource names, or use an explicit output_interface for
        adapters. A supplied manager is only used to resolve names or aliases;
        it remains caller-owned. Validate framing just like the hardware driver.
        Reconnecting requires disconnect first. Reset is an explicit operation.
        Local mode is preserved; set local_mode explicitly to change it.
        """
        if self._connected:
            raise RuntimeError("Instrument is already connected; disconnect first.")
        if resource_manager is not None:
            interface_type = resource_manager.resource_info(resource_name).interface_type
        else:
            name = pyvisa.rname.parse_resource_name(resource_name)
            interface_type = InterfaceType[name.interface_type.lower()]
        interface = resolve_output_interface(interface_type, output_interface)
        connection_kwargs(interface, resource_kwargs, interface_type=interface_type)
        self.output_interface = interface
        self._connected = True

    def disconnect(self) -> None:
        """Return to virtual local mode; repeated calls are harmless."""
        if self._connected:
            self.local_mode = 0
            self._connected = False

    def enable_all_status_bytes(self) -> None:
        """Enable all status bytes."""
        pass

    @property
    def errors(self) -> list[str]:
        """Check for errors.

        Returns
        -------
        errors : list
            List of errors.
        """
        return self._errors

    # --- Reference and phase commands ---
    @property
    def reference_phase_shift(self) -> float:
        """Get the reference phase shift.

        Returns
        -------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        return self._reference_phase_shift

    @reference_phase_shift.setter
    def reference_phase_shift(self, phase_shift: float) -> None:
        """Set the reference phase shift.

        Parameters
        ----------
        phase_shift : float
            Phase shift in degrees, -360 =< phase_shift =< 720.
        """
        if (phase_shift >= -360) and (phase_shift <= 720):
            self._reference_phase_shift = phase_shift
        else:
            raise ValueError(
                f"Invalid phase shift: {phase_shift}. Must be in range -360 - 720 "
                + "degrees."
            )

    @property
    def reference_source(self) -> int:
        """Get the reference source.

        Returns an integer code; use ReferenceSource(code) for its named setting.

        Returns
        -------
        source : {0, 1}
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        return self._reference_source

    @reference_source.setter
    def reference_source(self, source: ReferenceSource | int) -> None:
        """Set the reference source.

        Parameters
        ----------
        source : ReferenceSource or int
            Refernce source:

                * 0 : external
                * 1 : internal
        """
        _validate_enum(source, ReferenceSource)
        if source in [0, 1]:
            self._reference_source = int(source)
        else:
            raise ValueError(
                f"Invalid reference source: {source}. Must be 0 (external) or 1 "
                + "(internal)."
            )

    @property
    def reference_frequency(self) -> float:
        """Get the reference frequency.

        Returns
        -------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        return self._reference_frequency

    @reference_frequency.setter
    def reference_frequency(self, freq: float) -> None:
        """Set the frequency of the internal oscillator.

        Parameters
        ----------
        freq : float
            Frequency in Hz, 0.001 =< freq =< 102000.
        """
        if (freq >= 0.001) and (freq <= 102000):
            self._reference_frequency = freq
        else:
            raise ValueError(
                f"Invalid reference frequency: {freq}. Must be in range 0.001 - 102000 "
                + "Hz."
            )

    @property
    def reference_trigger(self) -> int:
        """Get the reference trigger type when using external ref.

        Returns an integer code; use ReferenceTrigger(code) for its named setting.

        Returns
        -------
        trigger : {0, 1, 2}
            Trigger type:

                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        return self._reference_trigger

    @reference_trigger.setter
    def reference_trigger(self, trigger: ReferenceTrigger | int) -> None:
        """Set the reference trigger type when using external ref.

        Parameters
        ----------
        trigger : ReferenceTrigger or int
            Trigger type:

                * 0: zero crossing
                * 1: TTL rising egde
                * 2: TTL falling edge
        """
        _validate_enum(trigger, ReferenceTrigger)
        if trigger in [0, 1, 2]:
            self._reference_trigger = int(trigger)
        else:
            raise ValueError(
                f"Invalid trigger type: {trigger}. Must be 0 (zero crossing), 1 "
                + "(rising edge), or 2 (falling edge)."
            )

    @property
    def harmonic(self) -> int:
        """Get detection harmonic.

        Returns
        -------
        harmonic : int
            detection harmonic, 1 =< harmonic =< 19999
        """
        return self._harmonic

    @harmonic.setter
    def harmonic(self, harmonic: int) -> None:
        """Set detection harmonic.

        Parameters
        ----------
        harmonic : int
            Detection harmonic, 1 =< harmonic =< 19999.
        """
        if (harmonic >= 1) and (harmonic <= 19999):
            self._harmonic = harmonic
        else:
            raise ValueError(
                f"Invalid detection harmonic: {harmonic}. Must be in range 1 - 19999."
            )

    @property
    def sine_amplitude(self) -> float:
        """Get the amplitude of the sine output.

        Returns
        -------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        return self._sine_amplitude

    @sine_amplitude.setter
    def sine_amplitude(self, amplitude: float) -> None:
        """Set the amplitude of the sine output.

        Parameters
        ----------
        amplitude : float
            sine amplitude in volts, 0.004 =< amplitude =< 5.000
        """
        if (amplitude >= 0.004) and (amplitude <= 5):
            self._sine_amplitude = amplitude
        else:
            raise ValueError(
                f"Invalid sine output amplitude: {amplitude}. Must be in range 0.004 -"
                + " 5 volts."
            )

    @property
    def input_configuration(self) -> int:
        """Set the input configuration.

        Returns an integer code; use InputConfiguration(code) for its named setting.

        Returns
        -------
        config : {0, 1, 2, 3}
            Input configuration:

                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        return self._input_configuration

    @input_configuration.setter
    def input_configuration(self, config: InputConfiguration | int) -> None:
        """Set the input configuration.

        Parameters
        ----------
        config : InputConfiguration or int
            Input configuration:

                * 0 : A
                * 1 : A-B
                * 2 : I (1 MOhm)
                * 3 : I (100 MOhm)
        """
        _validate_enum(config, InputConfiguration)
        if config in range(4):
            self._input_configuration = int(config)
        else:
            raise ValueError(
                f"Invalid input configuration: {config}. Must be 0 (A), 1 (A-B), 2 "
                + "(I 1MOhm), or 3 (I 100MOhm)."
            )

    @property
    def input_shield_grounding(self) -> int:
        """Get input shield grounding.

        Returns an integer code; use InputShieldGrounding(code) for its named setting.

        Returns
        -------
        grounding : {0, 1}
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        return self._input_shield_grounding

    @input_shield_grounding.setter
    def input_shield_grounding(self, grounding: InputShieldGrounding | int) -> None:
        """Set input shield grounding.

        Parameters
        ----------
        grounding : InputShieldGrounding or int
            Input shield grounding:

                * 0 : Float
                * 1 : Ground
        """
        _validate_enum(grounding, InputShieldGrounding)
        if grounding in [0, 1]:
            self._input_shield_grounding = int(grounding)
        else:
            raise ValueError(
                f"Invalid input shield grounding: {grounding}. Must be 0 (float) or 1"
                + " (ground)."
            )

    @property
    def input_coupling(self) -> int:
        """Get input coupling.

        Returns an integer code; use InputCoupling(code) for its named setting.

        Returns
        -------
        coupling : {0, 1}
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        return self._input_coupling

    @input_coupling.setter
    def input_coupling(self, coupling: InputCoupling | int) -> None:
        """Set input coupling.

        Parameters
        ----------
        coupling : InputCoupling or int
            Input coupling:

                * 0 : AC
                * 1 : DC
        """
        _validate_enum(coupling, InputCoupling)
        if coupling in [0, 1]:
            self._input_coupling = int(coupling)
        else:
            raise ValueError(
                f"Invalid input coupling: {coupling}. Must be 0 (AC) or 1 (DC)."
            )

    @property
    def line_notch_filter_status(self) -> int:
        """Get input line notch filter status.

        Returns an integer code; use LineNotchFilter(code) for its named setting.

        Returns
        -------
        status : {0, 1, 2, 3}
            Input line notch filter status:

                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        return self._line_notch_filter_status

    @line_notch_filter_status.setter
    def line_notch_filter_status(self, status: LineNotchFilter | int) -> None:
        """Set input line notch filter status.

        Parameters
        ----------
        status : LineNotchFilter or int
            Input line notch filter status:

                * 0 : no filters
                * 1 : Line notch in
                * 2 : 2 x Line notch in
                * 3 : Both notch filters in
        """
        _validate_enum(status, LineNotchFilter)
        if status in range(4):
            self._line_notch_filter_status = int(status)
        else:
            raise ValueError(
                f"Invalid line notch filter status: {status}. Must be 0 (no filters), "
                + "1 (line notch in), 2 (2 x line notch in), or 3 (both line notch in)"
                + "."
            )

    # --- Gain and time constant commands ---

    @property
    def sensitivity(self) -> int:
        """Get sensitivity.

        Returns an integer code; use Sensitivity(code) for its named setting.

        Returns
        -------
        sensitivity : {0 - 26}
            RMS full-scale amplitude, in V for voltage inputs or microamps
            for current inputs (not gain):

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
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, sensitivity: Sensitivity | int) -> None:
        """Set sensitivity.

        Parameters
        ----------
        sensitivity : Sensitivity or int
            RMS full-scale amplitude (not gain), in V for voltage inputs or
            microamps for current inputs. Names use x<number><SI prefix>,
            with u for micro (x1u) and x1 for the unity multiplier:

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
        _validate_enum(sensitivity, Sensitivity)
        if sensitivity in range(27):
            self._sensitivity = int(sensitivity)
        else:
            raise ValueError(
                f"Invalid sensitivity: {sensitivity}. Must be an integer in range 0 - "
                + "26."
            )

    @property
    def reserve_mode(self) -> int:
        """Get reserve mode.

        Returns an integer code; use ReserveMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1, 2}
            Reserve mode:

                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        return self._reserve_mode

    @reserve_mode.setter
    def reserve_mode(self, mode: ReserveMode | int) -> None:
        """Set reserve mode.

        Parameters
        ----------
        mode : ReserveMode or int
            Reserve mode:

                * 0 : High reserve
                * 1 : Normal
                * 2 : Low noise
        """
        _validate_enum(mode, ReserveMode)
        if mode in range(3):
            self._reserve_mode = int(mode)
        else:
            raise ValueError(
                f"Invalid reserve mode: {mode}. Must be 0 (high), 1 (normal), or 2 "
                + "(low)."
            )

    @property
    def time_constant(self) -> int:
        """Get time constant.

        Returns an integer code; use TimeConstant(code) for its named setting.

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
        return self._time_constant

    @time_constant.setter
    def time_constant(self, tc: TimeConstant | int) -> None:
        """Set time constant.

        Parameters
        ----------
        tc : TimeConstant or int
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
        _validate_enum(tc, TimeConstant)
        if tc in range(20):
            self._time_constant = int(tc)
        else:
            raise ValueError(
                f"Invalid time constant: {tc}. Must be an integer in range 0 - 19."
            )

    @property
    def lowpass_filter_slope(self) -> int:
        """Get the low pass filter slope.

        Returns an integer code; use LowPassFilterSlope(code) for its named setting.

        Returns
        -------
        slope : {0, 1, 2, 3}
            Low pass filter slope in dB/oct:

                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        return self._lowpass_filter_slope

    @lowpass_filter_slope.setter
    def lowpass_filter_slope(self, slope: LowPassFilterSlope | int) -> None:
        """Set the low pass filter slope.

        Parameters
        ----------
        slope : LowPassFilterSlope or int
            Low pass filter slope in dB/oct:

                * 0 : 6
                * 1 : 12
                * 2 : 18
                * 3 : 24
        """
        _validate_enum(slope, LowPassFilterSlope)
        if slope in range(4):
            self._lowpass_filter_slope = int(slope)
        else:
            raise ValueError(
                f"Invalid low-pass filter slope: {slope}. Must be 0 (6 dB/oct), 1 "
                + "(12 dB/oct), 2 (18 dB/oct), or 3 (24 dB/oct)."
            )

    @property
    def sync_filter_status(self) -> int:
        """Get synchronous filter status.

        Returns an integer code; use SynchronousFilter(code) for its named setting.

        Returns
        -------
        status : {0, 1}
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        return self._sync_filter_status

    @sync_filter_status.setter
    def sync_filter_status(self, status: SynchronousFilter | int) -> None:
        """Set synchronous filter status.

        Parameters
        ----------
        status : SynchronousFilter or int
            Synchronous filter status:

                * 0 : Off
                * 1 : below 200 Hz
        """
        _validate_enum(status, SynchronousFilter)
        if status in [0, 1]:
            self._sync_filter_status = int(status)
        else:
            raise ValueError(
                f"Invalid synchronous filter status: {status}. Must be 0 (off) or 1 "
                + "(below 200 Hz)."
            )

    # --- Display and output commands ---

    @property
    def output_interface(self) -> int:
        """Get the output communication interface.

        Returns an integer code; use OutputInterface(code) for its named setting.

        Returns
        -------
        interface : {0, 1}
            Output communication interface:

                * 0 : RS232
                * 1 : GPIB
        """
        return self._output_interface

    @output_interface.setter
    def output_interface(self, interface: OutputInterface | int) -> None:
        """Set the output communication interface.

        This command should be sent before any query commands to direct the
        responses to the interface in use.

        Parameters
        ----------
        interface : OutputInterface or int
            Output communication interface:

                * 0 : RS232
                * 1 : GPIB
        """
        _validate_enum(interface, OutputInterface)
        if interface in [0, 1]:
            self._output_interface = int(interface)
        else:
            raise ValueError(
                f"Invalid output interface: {interface}. Must be 0 (RS232) or 1 "
                + "(GPIB)."
            )

    def set_display(
        self,
        channel: Channel | int,
        display: Channel1Display | Channel2Display | int = 1,
        ratio: Channel1Ratio | Channel2Ratio | int = 0,
    ) -> None:
        """Set a channel display configuration.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        display : Channel1Display | Channel2Display or int
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

        ratio : Channel1Ratio | Channel2Ratio or int
            Channel1Ratio for CH1 and Channel2Ratio for CH2.
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2

            Ratio type for CH2:

                * 0 : none
                * 1 : Aux In 3
                * 2 : Aux In 4
        """
        _validate_enum(channel, Channel)
        _validate_enum(display, Channel1Display if channel == 1 else Channel2Display)
        _validate_enum(ratio, Channel1Ratio if channel == 1 else Channel2Ratio)
        if (channel in [1, 2]) and (display in range(5)) and (ratio in range(3)):
            if channel == 1:
                self._ch1_display = int(display)
                self._ch1_ratio = int(ratio)
            elif channel == 2:
                self._ch2_display = int(display)
                self._ch2_ratio = int(ratio)
        else:
            raise ValueError(
                f"Invalid channel, display, or ratio: {channel}, {display}, or {ratio}"
                + ". Channel must be 1 (Ch1) or 2 (Ch2); display must be an integer in"
                + " range 0 - 4; and ratio must be an integer in the range 0 - 2."
            )

    def get_display(self, channel: Channel | int) -> tuple[int, int]:
        """Get a channel display configuration.

        Parameters
        ----------
        channel : Channel or int
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
            Channel1Ratio for CH1 and Channel2Ratio for CH2.
            Ratio type for CH1:

                * 0 : none
                * 1 : Aux In 1
                * 2 : Aux In 2

            Ratio type for CH2:

                * 0 : none
                * 1 : Aux In 2
                * 2 : Aux In 4
        """
        _validate_enum(channel, Channel)
        if channel == 1:
            return self._ch1_display, self._ch1_ratio
        elif channel == 2:
            return self._ch2_display, self._ch2_ratio
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def set_front_output(
        self,
        channel: Channel | int,
        output: FrontPanelOutputSource | int = 0,
    ) -> None:
        """Set front panel output sources.

        Parameters
        ----------
        channel : Channel or int
            Channel:

                * 1 : CH1
                * 2 : CH2

        output : FrontPanelOutputSource or int
            Output quantity for CH1:

                * 0 : CH1 display
                * 1 : X

            Output quantity for CH2:

                * 0 : CH2 display
                * 1 : Y
        """
        _validate_enum(channel, Channel)
        _validate_enum(output, FrontPanelOutputSource)
        if (channel in [1, 2]) and (output in [0, 1]):
            if channel == 1:
                self._ch1_output = int(output)
            elif channel == 2:
                self._ch2_output = int(output)
        else:
            raise ValueError(
                f"Invalid channel or output: {channel} or {output}. Channel must be 0 "
                + "(Ch1) or 1 (Ch2); and output must be 0 or 1."
            )

    def get_front_output(self, channel: Channel | int) -> int:
        """Get front panel output sources.

        Parameters
        ----------
        channel : Channel or int
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
        _validate_enum(channel, Channel)
        if channel == 1:
            return self._ch1_output
        elif channel == 2:
            return self._ch2_output
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def set_output_offset_expand(
        self,
        parameter: OutputParameter | int,
        offset: float,
        expand: OutputExpansion | int,
    ) -> None:
        """Set the output offsets and expands.

        Setting an offset to zero turns the offset off.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R

        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : OutputExpansion or int
            Expansion factor; OutputExpansion.x1 has code 0:

                * 0 : 1 (no expansion)
                * 1 : 10
                * 2 : 100
        """
        _validate_enum(parameter, OutputParameter)
        _validate_enum(expand, OutputExpansion)
        if (
            (parameter in [1, 2, 3])
            and (offset >= -105)
            and (offset <= 105)
            and (expand in range(3))
        ):
            if parameter == 1:
                self._X_offset = offset
                self._X_expand = int(expand)
            elif parameter == 2:
                self._Y_offset = offset
                self._Y_expand = int(expand)
            elif parameter == 3:
                self._R_offset = offset
                self._R_expand = int(expand)
        else:
            raise ValueError(
                f"Invalid parameter, offset, or expand: {parameter}, {offset}, or "
                + f"{expand}. Parameter must be 1 (X), 2 (Y), or 3 (R); offset must "
                + "be in the range -105 - 105 percent; and expand must be 0 (1), 1 "
                + "(10), or 2 (100)."
            )

    def get_output_offset_expand(self, parameter: OutputParameter | int) -> tuple[float, int]:
        """Get the output offsets and expands.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R

        Returns
        -------
        offset : float
            Offset in %, -105.00 =< offset =< 105.00.
        expand : {0, 1, 2}
            Expansion factor; OutputExpansion.x1 has code 0:

                * 0 : 1 (no expansion)
                * 1 : 10
                * 2 : 100
        """
        _validate_enum(parameter, OutputParameter)
        if parameter == 1:
            return self._X_offset, self._X_expand
        elif parameter == 2:
            return self._Y_offset, self._Y_expand
        elif parameter == 3:
            return self._R_offset, self._R_expand
        else:
            raise ValueError(
                f"Invalid paramter: {parameter}. Must be 1 (X), 2 (Y), or 3 (R)."
            )

    def auto_offset(self, parameter: OutputParameter | int) -> None:
        """Set parameter offset to zero.

        Parameters
        ----------
        parameter : OutputParameter or int
            Measurement parameter:

                * 1 : X
                * 2 : Y
                * 3 : R
        """
        _validate_enum(parameter, OutputParameter)
        if parameter == 1:
            self._X_offset = 0
        elif parameter == 2:
            self._Y_offset = 0
        elif parameter == 3:
            self._R_offset = 0
        else:
            raise ValueError(
                f"Invalid paramter: {parameter}. Must be 1 (X), 2 (Y), or 3 (R)."
            )

    # --- Aux input and output commands ---

    def get_aux_in(self, aux_in: AuxiliaryChannel | int) -> float:
        """Get voltage of auxiliary input.

        The resolution is 1/3 mV.

        Parameter
        ---------
        aux_in : AuxiliaryChannel or int
            Auxiliary input (1, 2, 3, or 4).

        Returns
        -------
        voltage : float
            Auxiliary input voltage.
        """
        _validate_enum(aux_in, AuxiliaryChannel)
        if aux_in in [1, 2, 3, 4]:
            return 1
        else:
            raise ValueError(
                f"Invalid auxilliary input: {aux_in}. Must be an integer in range "
                + "1 - 4."
            )

    def set_aux_out(self, aux_out: AuxiliaryChannel | int, voltage: float) -> None:
        """Set voltage of auxiliary output.

        Parameters
        ----------
        aux_out : AuxiliaryChannel or int
            Auxiliary output (1, 2, 3, or 4).
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        _validate_enum(aux_out, AuxiliaryChannel)
        if (aux_out in [1, 2, 3, 4]) and (voltage >= -10.5) and (voltage <= 10.5):
            if aux_out == 1:
                self._aux_out_1 = voltage
            elif aux_out == 2:
                self._aux_out_2 = voltage
            elif aux_out == 3:
                self._aux_out_3 = voltage
            elif aux_out == 4:
                self._aux_out_4 = voltage
        else:
            raise ValueError(
                f"Invalid auxilliary output or voltage: {aux_out} or {voltage}. Aux "
                + "out must be an integer in range 1 - 4, and voltage must be in "
                + "range -10.5 - 10.5 volts."
            )

    def get_aux_out(self, aux_out: AuxiliaryChannel | int) -> float:
        """Get voltage of auxiliary output.

        Parameters
        ----------
        aux_out : AuxiliaryChannel or int
            Auxiliary output (1, 2, 3, or 4).

        Returns
        -------
        voltage : float
            Output voltage, -10.500 =< voltage =< 10.500
        """
        _validate_enum(aux_out, AuxiliaryChannel)
        if aux_out == 1:
            return self._aux_out_1
        elif aux_out == 2:
            return self._aux_out_2
        elif aux_out == 3:
            return self._aux_out_3
        elif aux_out == 4:
            return self._aux_out_4
        else:
            raise ValueError(
                f"Invalid auxilliary output: {aux_out}. Must be an integer in range "
                + "1 - 4."
            )

    # --- Setup commands ---

    @property
    def key_click_state(self) -> int:
        """Get key click state.

        Returns an integer code; use SwitchState(code) for its named setting.

        Returns
        -------
        state : {0, 1}
            Key click state:

                * 0 : Off
                * 1 : On
        """
        return self._key_click_state

    @key_click_state.setter
    def key_click_state(self, state: SwitchState | int) -> None:
        """Set key click state.

        Parameters
        ----------
        state : SwitchState or int
            Key click state:

                * 0 : Off
                * 1 : On
        """
        _validate_enum(state, SwitchState)
        if state in [0, 1]:
            self._key_click_state = int(state)
        else:
            raise ValueError(
                f"Invalid key click state: {state}. Must be 0 (off) or 1 (on)."
            )

    @property
    def alarm_status(self) -> int:
        """Get the alarm status.

        Returns an integer code; use SwitchState(code) for its named setting.

        The 'alarm' refers to all sounds emitted by the instrument.

        Returns
        -------
        status : {0, 1}
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        return self._alarm_status

    @alarm_status.setter
    def alarm_status(self, status: SwitchState | int) -> None:
        """Set the alarm status.

        The 'alarm' refers to all sounds emitted by the instrument.

        Parameters
        ----------
        status : SwitchState or int
            Alarm status:

                * 0 : Off
                * 1 : On
        """
        _validate_enum(status, SwitchState)
        if status in [0, 1]:
            self._alarm_status = int(status)
        else:
            raise ValueError(
                f"Invalid alarm status: {status}. Must be 0 (off) or 1 (on)."
            )

    def save_setup(self, number: int) -> None:
        """Save the lock-in setup in a settings buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        if number in range(1, 10):
            pass
        else:
            raise ValueError(
                f"Invalid save buffer number: {number}. Must be an integer in range "
                + "1 - 9."
            )

    def recall_setup(self, number: int) -> None:
        """Recall lock-in setup from setting buffer.

        Parameters
        ----------
        number : {1 - 9}
            Buffer number, 1 =< number =< 9.
        """
        if number in range(1, 10):
            pass
        else:
            raise ValueError(
                f"Invalid save buffer number: {number}. Must be an integer in range "
                + "1 - 9."
            )

    # --- Auto functions ---

    def auto_gain(self) -> None:
        """Automatically set the gain.

        Does nothing if the time constant is greater than 1 second.
        """
        pass

    def auto_reserve(self) -> None:
        """Automatically set reserve."""
        pass

    def auto_phase(self) -> None:
        """Automatically set phase."""
        pass

    # --- Data storage commands ---

    @property
    def sample_rate(self) -> int:
        """Get the data sample rate.

        Returns an integer code; use SampleRate(code) for its named setting.

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
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, rate: SampleRate | int) -> None:
        """Set the data sample rate.

        Paramters
        ---------
        rate : SampleRate or int
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
        _validate_enum(rate, SampleRate)
        if rate in range(15):
            self._sample_rate = int(rate)
        else:
            raise ValueError(
                f"Invalid sample rate: {rate}. Must be an integer in range 0 - 14."
            )

    @property
    def end_of_buffer_mode(self) -> int:
        """Get the end of buffer mode.

        Returns an integer code; use EndOfBufferMode(code) for its named setting.

        Returns
        ----------
        mode : {0, 1} or str
            End of buffer mode:

                * 0 : 1 Shot
                * 1 : Loop
        """
        return self._end_of_buffer_mode

    @end_of_buffer_mode.setter
    def end_of_buffer_mode(self, mode: EndOfBufferMode | int) -> None:
        """Set the end of buffer mode.

        If Loop mode is used, make sure to pause data storage before reading the
        data to avoid confusion about which point is the most recent.

        Parameters
        ----------
        mode : EndOfBufferMode or int
            End of buffer mode:

                * 0 : 1 Shot
                * 1 : Loop
        """
        _validate_enum(mode, EndOfBufferMode)
        if mode in [0, 1]:
            self._end_of_buffer_mode = int(mode)
        else:
            raise ValueError(
                f"Invalid end of buffer mode: {mode}. Must be 0 (1 shot) or 1 (loop)."
            )

    def trigger(self) -> None:
        """Send software trigger."""
        pass

    @property
    def trigger_start_mode(self) -> int:
        """Get the trigger start mode.

        Returns an integer code; use TriggerStartMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1} or str
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        return self._trigger_start_mode

    @trigger_start_mode.setter
    def trigger_start_mode(self, mode: TriggerStartMode | int) -> None:
        """Set the trigger start mode.

        Parameters
        ----------
        mode : TriggerStartMode or int
            Trigger start mode:

                * 0 : Off
                * 1 : Start scan
        """
        _validate_enum(mode, TriggerStartMode)
        if mode in [0, 1]:
            self._trigger_start_mode = int(mode)
        else:
            raise ValueError(
                f"Invalid trigger start mode: {mode}. Must be 0 (off) or 1 "
                + "(start scan)."
            )

    def start(self) -> None:
        """Start or resume data storage.

        Ignored if storage already in progress.

        After turning on fast data transfer, this function starts the scan after a
        delay of 0.5 sec.
        """
        # TODO: implement dummy store in buffer
        pass

    def pause(self) -> None:
        """Pause data storage.

        Ignored if storage is already paused or reset.
        """
        # TODO: implement dummy store in buffer
        pass

    def reset_data_buffers(self) -> None:
        """Reset data buffers.

        This command will erase the data buffer.
        """
        # TODO: implement dummy store in buffer
        pass

    # --- Data transfer commands ---

    def measure(self, parameter: MeasurementParameter | int) -> float:
        """Read the value of X, Y, R, or phase.

        Parameters
        ----------
        parameter : MeasurementParameter or int
            Measured parameter; only X, Y, R, and PHASE are accepted:

                * 1 : X
                * 2 : Y
                * 3 : R
                * 4 : Phase

        Returns
        -------
        value : float
            Value of measured parameter in volts or degrees.
        """
        _validate_enum(parameter, MeasurementParameter)
        if parameter in range(1, 5):
            return 1.0
        else:
            raise ValueError(
                f"Invalid parameter: {parameter}. Must be 1 (X), 2 (Y), 3 (R), or 4 "
                + "(phase)."
            )

    def read_display(self, channel: Channel | int) -> float:
        """Read the value of a channel display.

        Parameters
        ----------
        channel : Channel or int
            Channel display to read:

                * 1 : CH1
                * 2 : CH2

        Returns
        -------
        value : float
            Displayed value in display units.
        """
        _validate_enum(channel, Channel)
        if channel in [1, 2]:
            return 1.0
        else:
            raise ValueError(f"Invalid channel: {channel}. Must be 0 (Ch1) or 1 (Ch2).")

    def measure_multiple(
        self,
        parameters: Sequence[MeasurementParameter | int],
    ) -> Iterator[float]:
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

        Parameters
        ----------
        parameters : Sequence[MeasurementParameter | int]
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
        values : iterator of float
            Values of measured parameters.
        """
        for parameter in parameters:
            _validate_enum(parameter, MeasurementParameter)
        if all(p in range(1, 12) for p in parameters) and (
            len(parameters) in range(2, 7)
        ):
            return (1.0 for i in parameters)
        else:
            raise ValueError(
                f"Invalid parameter list: {parameters}. All paramters must be integers"
                + " in the range 1 - 11 and the list length must be in the range 2 - 6"
                + "."
            )

    @property
    def buffer_size(self) -> int:
        """Get the number of points stored in the buffer.

        Returns
        -------
        N : int
            Number of points in the buffer.
        """
        return self._buffer_size

    def get_ascii_buffer_data(
        self,
        channel: Channel | int,
        start_bin: int,
        bins: int,
    ) -> tuple[float, ...]:
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
        channel : Channel or int
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest. Must be in range 0 - 16382.
        bins : int
            Number of bins to read. Must be in range 1 - 16383.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        _validate_enum(channel, Channel)
        if (
            (channel in (1, 2))
            and (start_bin in range(16383))
            and (bins in range(1, 16384))
        ):
            return tuple([1.0 for x in range(bins)])
        else:
            raise ValueError(
                f"Invalid channel, start bin or bins: {channel}, {start_bin}, or "
                + f"{bins}. Channel must be 1 (Ch1) or 2 (Ch2); start bin must in "
                + "range 0 - 16382; and bins must be in range 1 - 16383."
            )

    def get_binary_buffer_data(
        self,
        channel: Channel | int,
        start_bin: int,
        bins: int,
    ) -> tuple[float, ...]:
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
        channel : Channel or int
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest. Must be in range 0 - 16382.
        bins : int
            Number of bins to read. Must be in range 1 - 16383.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        _validate_enum(channel, Channel)
        if (
            (channel in [1, 2])
            and (start_bin >= 0)
            and (start_bin <= 16382)
            and (bins >= 1)
            and (bins <= 16383)
        ):
            return tuple([1.0 for x in range(bins)])
        else:
            raise ValueError(
                f"Invalid channel, start bin or bins: {channel}, {start_bin}, or "
                + f"{bins}. Channel must be 1 (Ch1) or 2 (Ch2); start bin must in "
                + "range 0 - 16382; and bins must be in range 1 - 16383."
            )

    def get_non_norm_buffer_data(
        self,
        channel: Channel | int,
        start_bin: int,
        bins: int,
    ) -> tuple[float, ...]:
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
        channel : Channel or int
            Channel 1 or 2.
        start_bin : int
            Starting bin to read where 0 is oldest. Must be in range 0 - 16382.
        bins : int
            Number of bins to read. Must be in range 1 - 16383.

        Returns
        -------
        buffer : tuple of float
            Data stored in buffer range.
        """
        _validate_enum(channel, Channel)
        if (
            (channel in [1, 2])
            and (start_bin >= 0)
            and (start_bin <= 16382)
            and (bins >= 1)
            and (bins <= 16383)
        ):
            return tuple([1.0 for x in range(bins)])
        else:
            raise ValueError(
                f"Invalid channel, start bin or bins: {channel}, {start_bin}, or "
                + f"{bins}. Channel must be 1 (Ch1) or 2 (Ch2); start bin must in "
                + "range 0 - 16382; and bins must be in range 1 - 16383."
            )

    @property
    def data_transfer_mode(self) -> int:
        """Get the data transfer mode.

        Returns an integer code; use DataTransferMode(code) for its named setting.

        Returns
        -------
        mode : {0, 1, 2}
            Data transfer mode:

                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        return self._data_transfer_mode

    @data_transfer_mode.setter
    def data_transfer_mode(self, mode: DataTransferMode | int) -> None:
        """Set the data transfer mode.

        GPIB only.

        Parameters
        ----------
        mode : DataTransferMode or int
            Data transfer mode:

                * 0 : Off
                * 1 : On (DOS)
                * 2 : On (Windows)
        """
        _validate_enum(mode, DataTransferMode)
        if mode in range(3):
            self._data_transfer_mode = int(mode)
        else:
            raise ValueError(
                f"Invalid data transfer mode: {mode}. Must be 0 (off), 1 (on [DOS]), "
                + "or 2 (on [Windows])."
            )

    # --- Interface commands ---

    def reset(self) -> None:
        """Reset the instrument to the default configuration."""
        self._set_dummy_properties()

    @property
    def idn(self) -> str:
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
        return self._idn

    @property
    def local_mode(self) -> int:
        """Get the local/remote function.

        Returns an integer code; use LocalMode(code) for its named setting.

        Returns
        -------
        local : {0, 1, 2}
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        return self._local_mode

    @local_mode.setter
    def local_mode(self, mode: LocalMode | int) -> None:
        """Set the local/remote function.

        Parameters
        ----------
        mode : LocalMode or int
            Local/remote function:

                * 0 : LOCAL
                * 1 : REMOTE
                * 2 : LOCAL LOCKOUT
        """
        _validate_enum(mode, LocalMode)
        if mode in range(3):
            self._local_mode = int(mode)
        else:
            raise ValueError(
                f"Invalid local mode: {mode}. Must be 0 (local), 1 (remote), or 2 "
                + "(local lockout)."
            )

    @property
    def gpib_override_remote(self) -> int:
        """Get the GPIB override remote condition.

        Returns an integer code; use GpibOverrideRemote(code) for its named setting.

        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Returns
        -------
        condition : int
            GPIB override remote condition:

                * 0 : No
                * 1 : Yes
        """
        return self._gpib_override_remote

    @gpib_override_remote.setter
    def gpib_override_remote(self, condition: GpibOverrideRemote | int) -> None:
        """Set the GPIB override remote condition.

        Under normal operation every GPIB command puts the instrument in the remote
        state with the front panel deactivated.

        Parameters
        ----------
        condition : GpibOverrideRemote or int
            GPIB override remote condition:

                * 0 : No
                * 1 : Yes
        """
        _validate_enum(condition, GpibOverrideRemote)
        if condition in [0, 1]:
            self._gpib_override_remote = int(condition)
        else:
            raise ValueError(
                f"Invalid GPIB override remote condition: {condition}. Must be 0 (no) "
                + "or 1 (yes)."
            )

    # --- Status reporting commands ---

    def clear_status_registers(self) -> None:
        """Clear all status registers."""
        pass

    def set_enable_register(
        self,
        register: StatusRegister | str,
        value: StandardEventFlag | SerialPollFlag | ErrorFlag | LiaStatusFlag | SwitchState | int,
        decimal: bool = True,
        bit: StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit | int | None = None,
    ) -> None:
        """Set an enable register.

        Parameters
        ----------
        register : StatusRegister or str
            Enable register to set.
        value : StandardEventFlag | SerialPollFlag | ErrorFlag | LiaStatusFlag | SwitchState or int
            Whole-byte mask (0-255) when decimal=True; use the flag type
            matching the register and combine flags with |. When decimal=False,
            use SwitchState or 0/1 for the bit specified by bit.
        decimal : bool, optional
            True writes a whole-byte mask; False writes a single bit state.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask. Use the bit enum matching the register
            or an integer from 0 to 7; required when decimal=False.
        """
        _validate_register_bit(register, bit)
        _validate_register_value(register, value, decimal)
        if register in (registers := _ENABLE_REGISTER_COMMANDS.keys()):
            # TODO: make dummy variables
            pass
        else:
            raise ValueError(
                f"Invalid register: {register}. Must be one of "
                + f"{', '.join(list(registers))}."
            )

    def get_enable_register(
        self,
        register: StatusRegister | str,
        bit: StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit | int | None = None,
    ) -> None:
        """Get the standard event enable register value.

        Parameters
        ----------
        register : StatusRegister or str
            Enable register to get.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask; the enum must match the register.
            If None, query the entire byte (an integer mask).

        Returns
        -------
        value : None
            Status-register simulation is not implemented.
        """
        _validate_register_bit(register, bit)
        if register in (registers := _ENABLE_REGISTER_COMMANDS.keys()):
            # TODO: make dummy variables
            pass
        else:
            raise ValueError(
                f"Invalid register: {register}. Must be one of "
                + f"{', '.join(list(registers))}."
            )

    def get_status_byte(
        self,
        status_byte: StatusRegister | str,
        bit: StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit | int | None = None,
    ) -> None:
        """Get a status byte.

        This function has no error check to avoid infinite recursion.

        Parameters
        ----------
        status_byte : StatusRegister or str
            Status byte to get.
        bit : StandardEventBit | SerialPollBit | ErrorBit | LiaStatusBit or int, optional
            Bit position, not a mask; the enum must match the register.
            If None, query the entire byte (an integer mask).

        Returns
        -------
        value : int
            Status byte value.
        """
        _validate_register_bit(status_byte, bit)
        if status_byte in (status_bytes := _STATUS_REGISTER_COMMANDS.keys()):
            # TODO: make dummy variables
            pass
        else:
            raise ValueError(
                f"Invalid status byte: {status_byte}. Must be one of "
                + f"{', '.join(list(status_bytes))}."
            )

    @property
    def power_on_status_clear_bit(self) -> int:
        """Get the power-on status clear bit.

        Returns an integer code; use SwitchState(code) for its named setting.

        Returns
        -------
        value : int
            Power-on status clear bit value.
        """
        return self._power_on_status_clear_bit

    @power_on_status_clear_bit.setter
    def power_on_status_clear_bit(self, value: SwitchState | int) -> None:
        """Set the power-on status clear bit.

        Parameters
        ----------
        value : SwitchState or int
            Value of power-on status clear bit. Values:

                * 0 : Cleared, status enable registers maintain values at power down.
                * 1 : Set, all status and enable registers are cleared on power up.
        """
        _validate_enum(value, SwitchState)
        if value in [0, 1]:
            self._power_on_status_clear_bit = int(value)
        else:
            raise ValueError(
                f"Invalid power on status clear bit: {value}. Must be 0 (cleared) or 1"
                + " (set)."
            )
