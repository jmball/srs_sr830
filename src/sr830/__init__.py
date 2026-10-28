from importlib.metadata import PackageNotFoundError, version

# get version if package has been installed
try:
    __version__ = version("srs_sr830")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .settings import (
    AuxiliaryChannel as AuxiliaryChannel,
    Channel as Channel,
    Channel1Display as Channel1Display,
    Channel1Ratio as Channel1Ratio,
    Channel2Display as Channel2Display,
    Channel2Ratio as Channel2Ratio,
    DataTransferMode as DataTransferMode,
    EndOfBufferMode as EndOfBufferMode,
    ErrorBit as ErrorBit,
    ErrorFlag as ErrorFlag,
    FrontPanelOutputSource as FrontPanelOutputSource,
    GpibOverrideRemote as GpibOverrideRemote,
    InputConfiguration as InputConfiguration,
    InputCoupling as InputCoupling,
    InputShieldGrounding as InputShieldGrounding,
    LiaStatusBit as LiaStatusBit,
    LiaStatusFlag as LiaStatusFlag,
    LineNotchFilter as LineNotchFilter,
    LocalMode as LocalMode,
    LowPassFilterSlope as LowPassFilterSlope,
    MeasurementParameter as MeasurementParameter,
    OutputExpansion as OutputExpansion,
    OutputInterface as OutputInterface,
    OutputParameter as OutputParameter,
    ReferenceSource as ReferenceSource,
    ReferenceTrigger as ReferenceTrigger,
    ReserveMode as ReserveMode,
    SampleRate as SampleRate,
    Sensitivity as Sensitivity,
    SerialPollBit as SerialPollBit,
    SerialPollFlag as SerialPollFlag,
    StandardEventBit as StandardEventBit,
    StandardEventFlag as StandardEventFlag,
    StatusRegister as StatusRegister,
    SwitchState as SwitchState,
    SynchronousFilter as SynchronousFilter,
    TimeConstant as TimeConstant,
    TriggerStartMode as TriggerStartMode,
)
from .sr830 import SR830 as SR830, InstrumentError as InstrumentError
