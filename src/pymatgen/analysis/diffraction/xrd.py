"""This module implements an XRD pattern calculator."""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING

import numpy as np
import orjson

from pymatgen.analysis.diffraction.core import (
    AbstractDiffractionPatternCalculator,
    DiffractionPattern,
    get_unique_families,
)
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

if TYPE_CHECKING:
    from pymatgen.core import Structure

# XRD wavelengths in angstroms
WAVELENGTHS = {
    "CuKa": 1.54184,
    "CuKa2": 1.54439,
    "CuKa1": 1.54056,
    "CuKb1": 1.39222,
    "MoKa": 0.71073,
    "MoKa2": 0.71359,
    "MoKa1": 0.70930,
    "MoKb1": 0.63229,
    "CrKa": 2.29100,
    "CrKa2": 2.29361,
    "CrKa1": 2.28970,
    "CrKb1": 2.08487,
    "FeKa": 1.93735,
    "FeKa2": 1.93998,
    "FeKa1": 1.93604,
    "FeKb1": 1.75661,
    "CoKa": 1.79026,
    "CoKa2": 1.79285,
    "CoKa1": 1.78896,
    "CoKb1": 1.63079,
    "AgKa": 0.560885,
    "AgKa2": 0.563813,
    "AgKa1": 0.559421,
    "AgKb1": 0.497082,
}

with open(
    os.path.join(os.path.dirname(__file__), "atomic_scattering_params.json"),
    "rb",
) as file:
    ATOMIC_SCATTERING_PARAMS = orjson.loads(file.read())


class XRDCalculator(AbstractDiffractionPatternCalculator):
    r"""
    Computes the XRD pattern of a crystal structure.

    This code is implemented by Shyue Ping Ong as part of UCSD's NANO106 -
    Crystallography of Materials. The formalism for this code is based on
    that given in Chapters 11 and 12 of Structure of Materials by Marc De
    Graef and Michael E. McHenry. This takes into account the atomic
    scattering factors and the Lorentz polarization factor, but not
    the Debye-Waller (temperature) factor (for which data is typically not
    available). Note that the multiplicity correction is not needed since
    this code simply goes through all reciprocal points within the limiting
    sphere, which includes all symmetrically equivalent facets. The algorithm
    is as follows

    1. Calculate reciprocal lattice of structure. Find all reciprocal points
       within the limiting sphere given by \frac{2}{\lambda}.

    2. For each reciprocal point \mathbf{g_{hkl}} corresponding to
       lattice plane (hkl), compute the Bragg condition
       \sin(\theta) = \frac{ \lambda}{2d_{hkl}}

    3. Compute the structure factor as the sum of the atomic scattering
       factors. The atomic scattering factors are given by

           f(s) = Z - 41.78214 \times s^2 \times \sum \limits_{i=1}^n a_i \exp(-b_is^2)

       where s = \ frac{\ sin(\ theta)}{\ lambda} and a_i
       and b_i are the fitted parameters for each element. The
       structure factor is then given by

           F_{hkl} = \sum \limits_{j=1}^N f_j  \exp(2 \pi i  \mathbf{g_{hkl}} \cdot  \mathbf{r})

    4. The intensity is then given by the modulus square of the structure factor.

           I_{hkl} = F_{hkl}F_{hkl}^*

    5. Finally, the Lorentz polarization correction factor is applied. This
       factor is given by:

           P(\theta) = \frac{1 + \cos^2(2 \theta)}{\sin^2(\theta) \cos(\theta)}
    """

    # Tuple of available radiation keywords.
    AVAILABLE_RADIATION = tuple(WAVELENGTHS)

    def __init__(self, wavelength="CuKa", symprec: float = 0, debye_waller_factors=None):
        """Initialize the XRD calculator with a given radiation.

        Args:
            wavelength (str | float): The wavelength can be specified as either a
                float or a string. If it is a string, it must be one of the
                supported definitions in the AVAILABLE_RADIATION class
                variable, which provides useful commonly used wavelengths.
                If it is a float, it is interpreted as a wavelength in
                angstroms. Defaults to "CuKa", i.e, Cu K_alpha radiation.
            symprec (float): Symmetry precision for structure refinement. If
                set to 0, no refinement is done. Otherwise, refinement is
                performed using spglib with provided precision.
            debye_waller_factors ({element symbol: float}): Allows the
                specification of Debye-Waller factors. Note that these
                factors are temperature dependent.
        """
        if isinstance(wavelength, float | int):
            self.wavelength = wavelength
        elif isinstance(wavelength, str):
            self.radiation = wavelength
            self.wavelength = WAVELENGTHS[wavelength]
        else:
            wavelength_type = type(wavelength).__name__
            raise TypeError(f"{wavelength_type=} must be either float, int or str")
        self.symprec = symprec
        self.debye_waller_factors = debye_waller_factors or {}

    def get_pattern(self, structure: Structure, scaled=True, two_theta_range=(0, 90)):
        """
        Calculates the diffraction pattern for a structure.

        Args:
            structure (Structure): Input structure
            scaled (bool): Whether to return scaled intensities. The maximum
                peak is set to a value of 100. Defaults to True. Use False if
                you need the absolute values to combine XRD plots.
            two_theta_range ([float of length 2]): Tuple for range of
                two_thetas to calculate in degrees. Defaults to (0, 90). Set to
                None if you want all diffracted beams within the limiting
                sphere of radius 2 / wavelength.

        Returns:
            DiffractionPattern: XRD pattern
        """
        if self.symprec:
            finder = SpacegroupAnalyzer(structure, symprec=self.symprec)
            structure = finder.get_refined_structure()

        wavelength = self.wavelength
        lattice = structure.lattice
        is_hex = lattice.is_hexagonal()

        # Obtained from Bragg condition. Note that reciprocal lattice
        # vector length is 1 / d_hkl.
        min_r, max_r = (
            (0, 2 / wavelength)
            if two_theta_range is None
            else [2 * math.sin(math.radians(t / 2)) / wavelength for t in two_theta_range]
        )

        # Obtain crystallographic reciprocal lattice points within range
        recip_lattice = lattice.reciprocal_lattice_crystallographic
        recip_pts = recip_lattice.get_points_in_sphere([[0, 0, 0]], [0, 0, 0], max_r)
        if min_r:
            recip_pts = [pt for pt in recip_pts if pt[1] >= min_r]

        # Create a flattened array of zs, coeffs, frac_coords and occus. This is used to perform
        # vectorized computation of atomic scattering factors later. Note that these are not
        # necessarily the same size as the structure as each partially occupied specie occupies its
        # own position in the flattened array.
        _zs = []
        _coeffs = []
        _frac_coords = []
        _occus = []
        _dw_factors = []

        for site in structure:
            for sp, occu in site.species.items():
                _zs.append(sp.Z)
                try:
                    c = ATOMIC_SCATTERING_PARAMS[sp.symbol]
                except KeyError:
                    raise ValueError(
                        f"Unable to calculate XRD pattern as there is no scattering coefficients for {sp.symbol}."
                    )
                _coeffs.append(c)
                _dw_factors.append(self.debye_waller_factors.get(sp.symbol, 0))
                _frac_coords.append(site.frac_coords)
                _occus.append(occu)

        zs = np.array(_zs)
        coeffs = np.array(_coeffs)
        frac_coords = np.array(_frac_coords)
        occus = np.array(_occus)
        dw_factors = np.array(_dw_factors)
        peaks: dict[float, list[float | list[tuple[int, ...]]]] = {}
        two_thetas: list[float] = []

        for hkl, g_hkl, ind, _ in sorted(recip_pts, key=lambda i: (i[1], -i[0][0], -i[0][1], -i[0][2])):
            # Force miller indices to be integers
            hkl = [round(i) for i in hkl]
            if g_hkl != 0:
                # Bragg condition
                theta = math.asin(wavelength * g_hkl / 2)

                # s = sin(theta) / wavelength = 1 / 2d = |ghkl| / 2 (d =
                # 1/|ghkl|)
                s = g_hkl / 2

                # Store s^2 since we are using it a few times
                s2 = s**2

                # Vectorized computation of g.r for all fractional coords and
                # hkl
                g_dot_r = np.dot(frac_coords, np.transpose([hkl])).T[0]

                # Highly vectorized computation of atomic scattering factors.
                # Equivalent non-vectorized code is:
                #
                #   for site in structure:
                #      el = site.specie
                #      coeff = ATOMIC_SCATTERING_PARAMS[el.symbol]
                #      fs = el.Z - 41.78214 * s2 * sum(
                #          [d[0] * exp(-d[1] * s2) for d in coeff])
                fs = zs - 41.78214 * s2 * np.sum(
                    coeffs[:, :, 0] * np.exp(-coeffs[:, :, 1] * s2),
                    axis=1,
                )

                dw_correction = np.exp(-dw_factors * s2)

                # Structure factor = sum of atomic scattering factors (with
                # position factor exp(2j * pi * g.r and occupancies).
                # Vectorized computation.
                f_hkl = np.sum(fs * occus * np.exp(2j * np.pi * g_dot_r) * dw_correction)

                # Lorentz polarization correction for hkl
                lorentz_factor = (1 + math.cos(2 * theta) ** 2) / (math.sin(theta) ** 2 * math.cos(theta))

                # Intensity for hkl is modulus square of structure factor
                i_hkl = (f_hkl * f_hkl.conjugate()).real

                two_theta = math.degrees(2 * theta)

                if is_hex:
                    # Use Miller-Bravais indices for hexagonal lattices
                    hkl = (hkl[0], hkl[1], -hkl[0] - hkl[1], hkl[2])
                # Deal with floating point precision issues
                ind = np.where(
                    np.abs(np.subtract(two_thetas, two_theta)) < AbstractDiffractionPatternCalculator.TWO_THETA_TOL
                )
                if len(ind[0]) > 0:
                    peaks[two_thetas[ind[0][0]]][0] += i_hkl * lorentz_factor
                    peaks[two_thetas[ind[0][0]]][1].append(tuple(hkl))  # type: ignore[union-attr]
                else:
                    d_hkl = 1 / g_hkl
                    peaks[two_theta] = [i_hkl * lorentz_factor, [tuple(hkl)], d_hkl]
                    two_thetas.append(two_theta)

        # Scale intensities so that the max intensity is 100
        max_intensity = max(v[0] for v in peaks.values())
        x = []
        y = []
        hkls = []
        d_hkls = []
        for k in sorted(peaks):
            v = peaks[k]
            fam = get_unique_families(v[1])
            if v[0] / max_intensity * 100 > AbstractDiffractionPatternCalculator.SCALED_INTENSITY_TOL:  # type: ignore[operator]
                x.append(k)
                y.append(v[0])
                hkls.append([{"hkl": hkl, "multiplicity": mult} for hkl, mult in fam.items()])
                d_hkls.append(v[2])
        xrd = DiffractionPattern(x, y, hkls, d_hkls)
        if scaled:
            xrd.normalize(mode="max", value=100)
        return xrd
