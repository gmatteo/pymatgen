from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose

from pymatgen.symmetry.settings import JonesFaithfulTransformation, Lattice, SymmOp

__author__ = "Matthew Horton"
__copyright__ = "Copyright 2017, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Matthew Horton"
__email__ = "mkhorton@lbl.gov"
__status__ = "Development"
__date__ = "Apr 2017"


class TestJonesFaithfulTransformation:
    def setup_method(self):
        self.test_strings = [
            "a,b,c;0,0,0",  # identity
            "a-b,a+b,2c;0,0,1/2",
            "a/4+b/4-c/2,a/4-b/4,-a/2-b/2;0,0,0",
            "a,b,c;1/4,1/2,3/4",
        ]  # pure translation
        self.test_Pps = [
            (np.eye(3), [0, 0, 0]),
            ([[1, 1, 0], [-1, 1, 0], [0, 0, 2]], [0, 0, 0.5]),
            ([[0.25, 0.25, -0.5], [0.25, -0.25, -0.5], [-0.5, 0, 0]], [0, 0, 0]),
            (np.eye(3), [0.25, 0.5, 0.75]),
        ]

    def test_init(self):
        for test_str, test_Pp in zip(self.test_strings, self.test_Pps, strict=True):
            jft = JonesFaithfulTransformation.from_transformation_str(test_str)
            jft2 = JonesFaithfulTransformation(test_Pp[0], test_Pp[1])
            assert_allclose(jft.P, jft2.P)
            assert_allclose(jft.p, jft2.p)
            assert test_str == jft.transformation_string
            assert test_str == jft2.transformation_string

    def test_inverse(self):
        for test_string in self.test_strings:
            jft = JonesFaithfulTransformation.from_transformation_str(test_string)
            assert jft == jft.inverse.inverse
            assert jft.transformation_string == jft.inverse.inverse.transformation_string

    def test_transform_lattice(self):
        lattice = Lattice.cubic(5)

        all_ref_lattices = [
            [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
            [[5.0, 5.0, 0.0], [-5.0, 5.0, 0.0], [0.0, 0.0, 10.0]],
            [[1.25, 1.25, -2.5], [1.25, -1.25, -2.5], [-2.5, 0.0, 0.0]],
            [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
        ]

        for ref_lattice, (P, p) in zip(all_ref_lattices, self.test_Pps, strict=True):
            jft = JonesFaithfulTransformation(P, p)
            assert_allclose(jft.transform_lattice(lattice).matrix, ref_lattice)

    def test_transform_coords(self):
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]

        all_ref_coords = [
            [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
            [[0.0, 0.0, -0.25], [0.0, 0.5, 0.0]],
            [[0.0, 0.0, 0.0], [-1.0, 0.0, -1.5]],
            [[-0.25, -0.5, -0.75], [0.25, 0.0, -0.25]],
        ]

        for ref_coords, (P, p) in zip(all_ref_coords, self.test_Pps, strict=True):
            jft = JonesFaithfulTransformation(P, p)
            transformed_coords = jft.transform_coords(coords)
            for coord, ref_coord in zip(transformed_coords, ref_coords, strict=True):
                assert_allclose(coord, ref_coord)

    def test_transform_symmops(self):
        # reference data for this test taken from GENPOS
        # https://cryst.ehu.es/cryst/get_gen.html

        # Fm-3m
        input_symm_ops = """x,y,z
-x,-y,z
-x,y,-z
x,-y,-z
z,x,y
z,-x,-y
-z,-x,y
-z,x,-y
y,z,x
-y,z,-x
y,-z,-x
-y,-z,x
y,x,-z
-y,-x,-z
y,-x,z
-y,x,z
x,z,-y
-x,z,y
-x,-z,-y
x,-z,y
z,y,-x
z,-y,x
-z,y,x
-z,-y,-x
-x,-y,-z
x,y,-z
x,-y,z
-x,y,z
-z,-x,-y
-z,x,y
z,x,-y
z,-x,y
-y,-z,-x
y,-z,x
-y,z,x
y,z,-x
-y,-x,z
y,x,z
-y,x,-z
y,-x,-z
-x,-z,y
x,-z,-y
x,z,y
-x,z,-y
-z,-y,x
-z,y,-x
z,-y,-x
z,y,x"""

        # Fm-3m transformed by (a-b,a+b,2c;0,0,1/2)
        ref_transformed_symm_ops = """x,y,z
-x,-y,z
-y,-x,-z+1/2
y,x,-z+1/2
-1/2x-1/2y+z+1/4,1/2x+1/2y+z+1/4,-1/2x+1/2y+3/4
1/2x+1/2y+z+1/4,-1/2x-1/2y+z+1/4,1/2x-1/2y+3/4
1/2x+1/2y-z+3/4,-1/2x-1/2y-z+3/4,-1/2x+1/2y+3/4
-1/2x-1/2y-z+3/4,1/2x+1/2y-z+3/4,1/2x-1/2y+3/4
-1/2x+1/2y-z+3/4,-1/2x+1/2y+z+1/4,1/2x+1/2y+3/4
1/2x-1/2y-z+3/4,1/2x-1/2y+z+1/4,-1/2x-1/2y+3/4
-1/2x+1/2y+z+1/4,-1/2x+1/2y-z+3/4,-1/2x-1/2y+3/4
1/2x-1/2y+z+1/4,1/2x-1/2y-z+3/4,1/2x+1/2y+3/4
-x,y,-z+1/2
x,-y,-z+1/2
y,-x,z
-y,x,z
1/2x+1/2y-z+3/4,1/2x+1/2y+z+1/4,1/2x-1/2y+3/4
-1/2x-1/2y-z+3/4,-1/2x-1/2y+z+1/4,-1/2x+1/2y+3/4
-1/2x-1/2y+z+1/4,-1/2x-1/2y-z+3/4,1/2x-1/2y+3/4
1/2x+1/2y+z+1/4,1/2x+1/2y-z+3/4,-1/2x+1/2y+3/4
1/2x-1/2y+z+1/4,-1/2x+1/2y+z+1/4,-1/2x-1/2y+3/4
-1/2x+1/2y+z+1/4,1/2x-1/2y+z+1/4,1/2x+1/2y+3/4
1/2x-1/2y-z+3/4,-1/2x+1/2y-z+3/4,1/2x+1/2y+3/4
-1/2x+1/2y-z+3/4,1/2x-1/2y-z+3/4,-1/2x-1/2y+3/4
-x,-y,-z+1/2
x,y,-z+1/2
y,x,z
-y,-x,z
1/2x+1/2y-z+3/4,-1/2x-1/2y-z+3/4,1/2x-1/2y+3/4
-1/2x-1/2y-z+3/4,1/2x+1/2y-z+3/4,-1/2x+1/2y+3/4
-1/2x-1/2y+z+1/4,1/2x+1/2y+z+1/4,1/2x-1/2y+3/4
1/2x+1/2y+z+1/4,-1/2x-1/2y+z+1/4,-1/2x+1/2y+3/4
1/2x-1/2y+z+1/4,1/2x-1/2y-z+3/4,-1/2x-1/2y+3/4
-1/2x+1/2y+z+1/4,-1/2x+1/2y-z+3/4,1/2x+1/2y+3/4
1/2x-1/2y-z+3/4,1/2x-1/2y+z+1/4,1/2x+1/2y+3/4
-1/2x+1/2y-z+3/4,-1/2x+1/2y+z+1/4,-1/2x-1/2y+3/4
x,-y,z
-x,y,z
-y,x,-z+1/2
y,-x,-z+1/2
-1/2x-1/2y+z+1/4,-1/2x-1/2y-z+3/4,-1/2x+1/2y+3/4
1/2x+1/2y+z+1/4,1/2x+1/2y-z+3/4,1/2x-1/2y+3/4
1/2x+1/2y-z+3/4,1/2x+1/2y+z+1/4,-1/2x+1/2y+3/4
-1/2x-1/2y-z+3/4,-1/2x-1/2y+z+1/4,1/2x-1/2y+3/4
-1/2x+1/2y-z+3/4,1/2x-1/2y-z+3/4,1/2x+1/2y+3/4
1/2x-1/2y-z+3/4,-1/2x+1/2y-z+3/4,-1/2x-1/2y+3/4
-1/2x+1/2y+z+1/4,1/2x-1/2y+z+1/4,-1/2x-1/2y+3/4
1/2x-1/2y+z+1/4,-1/2x+1/2y+z+1/4,1/2x+1/2y+3/4"""

        jft = JonesFaithfulTransformation.from_transformation_str(self.test_strings[1])

        input_symm_ops = [SymmOp.from_xyz_str(s) for s in input_symm_ops.split()]
        ref_transformed_symm_ops = [SymmOp.from_xyz_str(s) for s in ref_transformed_symm_ops.split()]

        transformed_symm_ops = [jft.transform_symmop(op) for op in input_symm_ops]

        for transformed_op, ref_transformed_op in zip(transformed_symm_ops, ref_transformed_symm_ops, strict=True):
            assert transformed_op == ref_transformed_op
