"""Representative wire contracts from the SR830 manual, chapter 5.

https://www.thinksrs.com/downloads/PDFs/Manuals/SR830m.pdf
Expected commands are literals, independent of the enum values under test.
One example per property protects command routing without enumerating every code.
"""

from sr830 import settings

SETTING_CASES = (
    ("reference_source", settings.ReferenceSource.INTERNAL, "FMOD 1"),
    ("reference_trigger", settings.ReferenceTrigger.TTL_FALLING_EDGE, "RSLP 2"),
    ("input_configuration", settings.InputConfiguration.CURRENT_100_MOHM, "ISRC 3"),
    ("input_shield_grounding", settings.InputShieldGrounding.GROUND, "IGND 1"),
    ("input_coupling", settings.InputCoupling.DC, "ICPL 1"),
    ("line_notch_filter_status", settings.LineNotchFilter.BOTH, "ILIN 3"),
    ("reserve_mode", settings.ReserveMode.LOW_NOISE, "RMOD 2"),
    ("sync_filter_status", settings.SynchronousFilter.BELOW_200_HZ, "SYNC 1"),
    ("output_interface", settings.OutputInterface.GPIB, "OUTX 1"),
    ("key_click_state", settings.SwitchState.ON, "KCLK 1"),
    ("alarm_status", settings.SwitchState.ON, "ALRM 1"),
    ("end_of_buffer_mode", settings.EndOfBufferMode.LOOP, "SEND 1"),
    ("trigger_start_mode", settings.TriggerStartMode.START_SCAN, "TSTR 1"),
    ("data_transfer_mode", settings.DataTransferMode.WINDOWS, "FAST 2"),
    ("local_mode", settings.LocalMode.LOCAL_LOCKOUT, "LOCL 2"),
    ("gpib_override_remote", settings.GpibOverrideRemote.ENABLED, "OVRM 1"),
    ("power_on_status_clear_bit", settings.SwitchState.ON, "*PSC 1"),
    ("sensitivity", settings.Sensitivity.x1u, "SENS 8"),
    ("time_constant", settings.TimeConstant.ms_100, "OFLT 8"),
    ("lowpass_filter_slope", settings.LowPassFilterSlope.dB_12, "OFSL 1"),
    ("sample_rate", settings.SampleRate.Hz_512, "SRAT 13"),
)
