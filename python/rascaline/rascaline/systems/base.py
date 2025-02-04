import ctypes
from ctypes import POINTER, c_double, c_void_p, pointer

import numpy as np

from .._c_api import c_uintptr_t, rascal_pair_t, rascal_system_t
from ..status import _save_exception


def catch_exceptions(function):
    """Decorate a function catching any exception."""

    def inner(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except Exception as e:
            _save_exception(e)
            return -1
        return 0

    return inner


class SystemBase:
    """Base class implementing the ``System`` trait in rascaline.

    Developers should implement this class to add new kinds of system that work with
    rascaline.

    Most users should use one of the already provided implementation, such as
    :py:class:`rascaline.systems.AseSystem` or
    :py:class:`rascaline.systems.ChemfilesSystem` instead of using this class directly.

    A very simple implementation of the interface is given below as starting point. The
    example does not implement a neighbor list, and it can only be used by setting
    ``use_native_system=True`` in
    :py:meth:`rascaline.calculators.CalculatorBase.compute`, to transfer the data to the
    native code and compute the neighbors list there.

    >>> import rascaline
    >>> import numpy as np
    >>>
    >>> class SimpleSystem(rascaline.systems.SystemBase):
    ...     def __init__(self, species, positions, cell):
    ...         super().__init__()
    ...
    ...         # species should be a 1D array of integers
    ...         species = np.asarray(species)
    ...         assert len(species.shape) == 1
    ...         assert species.dtype == np.int32
    ...         self._species = species
    ...
    ...         # positions should be a 2D array of float
    ...         positions = np.asarray(positions)
    ...         assert len(positions.shape) == 2
    ...         assert positions.shape[0] == species.shape[0]
    ...         assert positions.shape[1] == 3
    ...         assert positions.dtype == np.float64
    ...         self._positions = positions
    ...
    ...         # cell should be a 3x3 array of float
    ...         cell = np.asarray(cell)
    ...         assert len(cell.shape) == 2
    ...         assert cell.shape[0] == 3
    ...         assert cell.shape[1] == 3
    ...         assert cell.dtype == np.float64
    ...         self._cell = cell
    ...
    ...     def size(self):
    ...         return len(self._species)
    ...
    ...     def species(self):
    ...         return self._species
    ...
    ...     def positions(self):
    ...         return self._positions
    ...
    ...     def cell(self):
    ...         return self._cell
    ...
    ...     def compute_neighbors(self, cutoff):
    ...         raise NotImplementedError("this system does not have a neighbors list")
    ...
    ...     def pairs(self):
    ...         raise NotImplementedError("this system does not have a neighbors list")
    ...
    ...     def pairs_containing(self, center):
    ...         raise NotImplementedError("this system does not have a neighbors list")
    ...
    >>> system = SimpleSystem(
    ...     species=np.random.randint(2, size=25, dtype=np.int32),
    ...     positions=6 * np.random.uniform(size=(25, 3)),
    ...     cell=6 * np.eye(3),
    ... )
    >>>
    >>> calculator = rascaline.SortedDistances(
    ...     cutoff=3.3,
    ...     max_neighbors=4,
    ...     separate_neighbor_species=True,
    ... )
    >>>
    >>> # this works, and uses our new system
    >>> calculator.compute(system)
    TensorMap with 4 blocks
    keys: species_center  species_neighbor
                0                0
                0                1
                1                0
                1                1
    >>> # this does not work, since the code is trying to get a neighbors list
    >>> try:
    ...     calculator.compute(system, use_native_system=False)
    ... except rascaline.RascalError as e:
    ...     raise e.__cause__
    ...
    Traceback (most recent call last):
        ...
    NotImplementedError: this system does not have a neighbors list
    """

    def __init__(self):
        # keep reference to some data to prevent garbage collection while Rust
        # might be using the data
        self._keepalive = {}

    def _as_rascal_system_t(self):
        """Convert a child instance of :py:class:`SystemBase`.

        Instances are converted to a C compatible ``rascal_system_t``.
        """
        struct = rascal_system_t()
        self._keepalive["c_struct"] = struct

        # user_data is a pointer to the PyObject `self`
        struct.user_data = ctypes.cast(pointer(ctypes.py_object(self)), c_void_p)

        def get_self(ptr):
            """Extract ``self`` from a pointer to the PyObject."""
            self = ctypes.cast(ptr, POINTER(ctypes.py_object)).contents.value
            assert isinstance(self, SystemBase)
            return self

        @catch_exceptions
        def rascal_system_size(user_data, size):
            """
            Implementation of ``rascal_system_t::size`` using
            :py:func:`SystemBase.size`.
            """
            size[0] = c_uintptr_t(get_self(user_data).size())

        # use struct.XXX.__class__ to get the right type for all functions
        struct.size = struct.size.__class__(rascal_system_size)

        @catch_exceptions
        def rascal_system_species(user_data, data):
            """
            Implementation of ``rascal_system_t::species`` using
            :py:func:`SystemBase.species`.
            """
            self = get_self(user_data)

            species = np.asarray(self.species(), order="C", dtype=np.int32)
            data[0] = species.ctypes.data
            self._keepalive["species"] = species

        struct.species = struct.species.__class__(rascal_system_species)

        @catch_exceptions
        def rascal_system_positions(user_data, data):
            """
            Implementation of ``rascal_system_t::positions`` using
            :py:func:`SystemBase.positions`.
            """
            self = get_self(user_data)
            positions = np.asarray(self.positions(), order="C", dtype=c_double)

            assert len(positions.shape) == 2
            assert positions.shape[1] == 3

            data[0] = positions.ctypes.data
            self._keepalive["positions"] = positions

        struct.positions = struct.positions.__class__(rascal_system_positions)

        @catch_exceptions
        def rascal_system_cell(user_data, data):
            """
            Implementation of ``rascal_system_t::cell`` using
            :py:func:`SystemBase.cell`.
            """
            self = get_self(user_data)
            cell = np.asarray(self.cell(), order="C", dtype=c_double)
            assert cell.shape == (3, 3)

            data[0] = cell[0][0]
            data[1] = cell[0][1]
            data[2] = cell[0][2]
            data[3] = cell[1][0]
            data[4] = cell[1][1]
            data[5] = cell[1][2]
            data[6] = cell[2][0]
            data[7] = cell[2][1]
            data[8] = cell[2][2]

        struct.cell = struct.cell.__class__(rascal_system_cell)

        @catch_exceptions
        def rascal_system_compute_neighbors(user_data, cutoff):
            """
            Implementation of ``rascal_system_t::compute_neighbors`` using
            :py:func:`SystemBase.compute_neighbors`.
            """
            self = get_self(user_data)
            self.compute_neighbors(cutoff)

        struct.compute_neighbors = struct.compute_neighbors.__class__(
            rascal_system_compute_neighbors
        )

        @catch_exceptions
        def rascal_system_pairs(user_data, data, count):
            """
            Implementation of ``rascal_system_t::pairs`` using
            :py:func:`SystemBase.pairs`.
            """
            self = get_self(user_data)

            pairs = np.asarray(
                self.pairs(),
                order="C",
                dtype=rascal_pair_t,
            )

            count[0] = c_uintptr_t(len(pairs))
            data[0] = pairs.ctypes.data
            self._keepalive["pairs"] = pairs

        struct.pairs = struct.pairs.__class__(rascal_system_pairs)

        @catch_exceptions
        def rascal_system_pairs_containing(user_data, center, data, count):
            """
            Implementation of ``rascal_system_t::pairs_containing`` using
            :py:func:`SystemBase.pairs_containing`.
            """
            self = get_self(user_data)

            pairs = np.asarray(
                self.pairs_containing(center),
                order="C",
                dtype=rascal_pair_t,
            )

            count[0] = c_uintptr_t(len(pairs))
            data[0] = pairs.ctypes.data
            self._keepalive["pairs_containing"] = pairs

        struct.pairs_containing = struct.pairs_containing.__class__(
            rascal_system_pairs_containing
        )

        return struct

    def size(self):
        """Get the number of atoms in this system as an integer."""

        raise NotImplementedError("System.size method is not implemented")

    def species(self):
        """Get the atomic species of all atoms in the system.

        Get a list of integers or a 1D numpy array of integers (ideally 32-bit
        integers, otherwise they will be converted on the fly) containing the
        atomic species for each atom in the system. Different atomic species
        should be identified with a different value. These values are usually
        the atomic number, but don't have to be.
        """

        raise NotImplementedError("System.species method is not implemented")

    def positions(self):
        """Get the cartesian position of all atoms in this system.

        The returned positions must be convertible to a numpy array of
        shape ``(self.size(), 3)``, with a dtype of `np.float64`.
        """

        raise NotImplementedError("System.positions method is not implemented")

    def cell(self):
        """Get the 3x3 matrix representing unit cell of the system.

        The cell should be written in row major order, i.e. `[[ax, ay, az], [bx,
        by, bz], [cx, cy, cz]]`, where a/b/c are the unit cell vectors.

        If the cell is returned as a numpy array, it should have a dtype of
        `np.float64`.
        """

        raise NotImplementedError("System.cell method is not implemented")

    def compute_neighbors(self, cutoff):
        """Compute the neighbor list with the given ``cutoff``.

        Store it for later access using :py:func:`rascaline.SystemBase.pairs` or
        :py:func:`rascaline.SystemBase.pairs_containing`.
        """

        raise NotImplementedError("System.compute_neighbors method is not implemented")

    def pairs(self):
        """Atoms pairs in this system.

        The pairs are those which were computed by the last call
        :py:func:`SystemBase.compute_neighbors`

        Get all neighbor pairs in this system as a list of tuples ``(int, int, float,
        (float, float, float), (int, int, int))`` containing the indexes of the first
        and second atom in the pair, the distance between the atoms, the vector between
        them, and the cell shift. The vector should be ``position[first] -
        position[second] * + H * cell_shift`` where ``H`` is the cell matrix.
        Alternatively, this function can return a 1D numpy array with
        ``dtype=rascal_pair_t``.

        The list of pair should only contain each pair once (and not twice as ``i-j``
        and ``j-i``), should not contain self pairs (``i-i``); and should only contains
        pairs where the distance between atoms is actually bellow the cutoff passed in
        the last call to :py:func:`rascaline.SystemBase.compute_neighbors`.

        This function is only valid to call after a call to
        :py:func:`rascaline.SystemBase.compute_neighbors` to set the cutoff.
        """

        raise NotImplementedError("System.pairs method is not implemented")

    def pairs_containing(self, center):
        """
        Get all neighbor pairs in this system containing the atom with index
        ``center``.

        The return type of this function should be the same as
        :py:func:`rascaline.SystemBase.pairs`. The same restrictions on the list
        of pairs also applies, with the additional condition that the pair
        ``i-j`` should be included both in the list returned by
        ``pairs_containing(i)`` and ``pairs_containing(j)``.
        """

        raise NotImplementedError("System.pairs_containing method is not implemented")
