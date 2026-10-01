from importlib.metadata import PackageNotFoundError, version

# get version if package has been installed
try:
    __version__ = version("srs_sr830")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .sr830 import *

from .settings import (
    ReferenceSource as ReferenceSource,
    ReferenceTrigger as ReferenceTrigger,
    InputConfiguration as InputConfiguration,
    InputShieldGrounding as InputShieldGrounding,
    InputCoupling as InputCoupling,
    LineNotchFilter as LineNotchFilter,
    ReserveMode as ReserveMode,
    SynchronousFilter as SynchronousFilter,
    Channel1Display as Channel1Display,
    Channel2Display as Channel2Display,
    Channel1Ratio as Channel1Ratio,
    Channel2Ratio as Channel2Ratio,
    FrontPanelOutputSource as FrontPanelOutputSource,
    OutputInterface as OutputInterface,
    SwitchState as SwitchState,
    EndOfBufferMode as EndOfBufferMode,
    TriggerStartMode as TriggerStartMode,
    DataTransferMode as DataTransferMode,
    LocalMode as LocalMode,
    GpibOverrideRemote as GpibOverrideRemote,
    Sensitivity as Sensitivity,
    TimeConstant as TimeConstant,
    LowPassFilterSlope as LowPassFilterSlope,
    OutputExpansion as OutputExpansion,
    SampleRate as SampleRate,
    Channel as Channel,
    AuxiliaryChannel as AuxiliaryChannel,
    OutputParameter as OutputParameter,
    MeasurementParameter as MeasurementParameter,
    StatusRegister as StatusRegister,
    StandardEventBit as StandardEventBit,
    StandardEventFlag as StandardEventFlag,
    SerialPollBit as SerialPollBit,
    SerialPollFlag as SerialPollFlag,
    ErrorBit as ErrorBit,
    ErrorFlag as ErrorFlag,
    LiaStatusBit as LiaStatusBit,
    LiaStatusFlag as LiaStatusFlag,
)
