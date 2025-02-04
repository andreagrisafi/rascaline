from .ase import HAVE_ASE, AseSystem
from .base import SystemBase
from .chemfiles import HAVE_CHEMFILES, ChemfilesSystem


class IntoSystem:
    """
    Possible types that can be used as a rascaline System.
    """

    def __init__(self):
        raise ValueError(
            "this class is for documentation purposes only and should not "
            "be instantiated"
        )


if HAVE_ASE:
    IntoSystem.__doc__ += """
    - `ase.Atoms`_: the Atomistic Simulation Environment (ASE) Atoms class. The
      ASE neighbor list is used to find neighbors.

    .. _ase.Atoms: https://wiki.fysik.dtu.dk/ase/ase/atoms.html
    """

if HAVE_CHEMFILES:
    IntoSystem.__doc__ += """
    - `chemfiles.Frame`_: chemfiles' Frame type. There is no associated neighbor
      list implementation, the system will only be usable with
      ``use_native_system=True``

    .. _chemfiles.Frame: http://chemfiles.org/chemfiles.py/latest/reference/frame.html
    """


def wrap_system(system: IntoSystem) -> SystemBase:
    """Wrap different systems implementation into the right class.

    This function is automatically called on all systems passed to
    :py:func:`rascaline.calculators.CalculatorBase.compute`. This function makes
    different systems compatible with rascaline.

    The supported system types are documented in the
    py:class:`rascaline.IntoSystem` class. If ``system`` is already a subclass
    of :py:class:`rascaline.SystemBase`, it is returned as-is.

    :param system: external system to wrap

    :returns: a specialized instance of :py:class:`rascaline.SystemBase`
    """
    if isinstance(system, SystemBase):
        return system

    if HAVE_ASE and AseSystem.can_wrap(system):
        return AseSystem(system)

    if HAVE_CHEMFILES and ChemfilesSystem.can_wrap(system):
        return ChemfilesSystem(system)

    raise TypeError(f"unknown system type: {type(system)}")
