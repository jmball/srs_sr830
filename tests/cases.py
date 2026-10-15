"""Shared setting/command cases for unit tests."""

import sr830.settings as settings

PROPERTY_CODES = (
    ("reference_source", settings.ReferenceSource.INTERNAL, "FMOD"),
    ("reference_trigger", settings.ReferenceTrigger.TTL_FALLING_EDGE, "RSLP"),
    ("input_configuration", settings.InputConfiguration.CURRENT_100_MOHM, "ISRC"),
    ("input_shield_grounding", settings.InputShieldGrounding.GROUND, "IGND"),
    ("input_coupling", settings.InputCoupling.DC, "ICPL"),
    ("line_notch_filter_status", settings.LineNotchFilter.BOTH, "ILIN"),
    ("reserve_mode", settings.ReserveMode.LOW_NOISE, "RMOD"),
    ("sync_filter_status", settings.SynchronousFilter.BELOW_200_HZ, "SYNC"),
    ("output_interface", settings.OutputInterface.GPIB, "OUTX"),
    ("key_click_state", settings.SwitchState.ON, "KCLK"),
    ("alarm_status", settings.SwitchState.ON, "ALRM"),
    ("end_of_buffer_mode", settings.EndOfBufferMode.LOOP, "SEND"),
    ("trigger_start_mode", settings.TriggerStartMode.START_SCAN, "TSTR"),
    ("data_transfer_mode", settings.DataTransferMode.WINDOWS, "FAST"),
    ("local_mode", settings.LocalMode.LOCAL_LOCKOUT, "LOCL"),
    ("gpib_override_remote", settings.GpibOverrideRemote.ENABLED, "OVRM"),
    ("power_on_status_clear_bit", settings.SwitchState.ON, "*PSC"),
)

NUMERIC_PROPERTIES = (
    ("sensitivity", settings.Sensitivity, "SENS"),
    ("time_constant", settings.TimeConstant, "OFLT"),
    ("lowpass_filter_slope", settings.LowPassFilterSlope, "OFSL"),
    ("sample_rate", settings.SampleRate, "SRAT"),
)

SETTING_COMMANDS = (
    *((name, type(member), command) for name, member, command in PROPERTY_CODES),
    *NUMERIC_PROPERTIES,
)
