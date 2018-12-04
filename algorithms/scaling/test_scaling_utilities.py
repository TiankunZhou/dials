'''
Tests for scaling utilities module.
'''
from math import sqrt, pi
import pytest
import numpy as np
from mock import Mock
from dxtbx.model import Experiment, Crystal
from libtbx.test_utils import approx_equal
from dials.array_family import flex
from dials.algorithms.scaling.scaling_utilities import \
  calc_crystal_frame_vectors, calc_theta_phi, create_sph_harm_table,\
  sph_harm_table, align_rotation_axis_along_z, set_wilson_outliers,\
  quasi_normalisation, combine_intensities, calculate_prescaling_correction, Reasons

@pytest.fixture(scope='module')
def mock_exp():
  """Create a mock experiments object."""
  exp = Mock()
  exp.beam.get_s0.return_value = (1.0, 0.0, 0.0)
  exp.goniometer.get_rotation_axis.return_value = (0.0, 0.0, 1.0)
  return exp

@pytest.fixture(scope='module')
def test_exp_E2():
  """Create a mock experiments object."""
  exp = Experiment()
  exp_dict = {"__id__" : "crystal", "real_space_a": [1.0, 0.0, 0.0],
              "real_space_b": [0.0, 1.0, 0.0], "real_space_c": [0.0, 0.0, 2.0],
              "space_group_hall_symbol": " P 1"}
  crystal = Crystal.from_dict(exp_dict)
  exp.crystal = crystal
  return exp

@pytest.fixture(scope='module')
def test_exp_P1():
  """Create a mock experiments object."""
  exp = Experiment()
  exp_dict = {"__id__" : "crystal", "real_space_a": [1.0, 0.0, 0.0],
              "real_space_b": [0.0, 1.0, 0.0], "real_space_c": [0.0, 0.0, 1.0],
              "space_group_hall_symbol": " P 1"}
  crystal = Crystal.from_dict(exp_dict)
  exp.crystal = crystal
  return exp

@pytest.fixture(scope='module')
def test_reflection_table():
  """Return a test reflection table."""
  return generate_reflection_table()

@pytest.fixture(scope='module')
def wilson_test_reflection_table():
  """Return a test reflection table."""
  rt = flex.reflection_table()
  rt['centric_flag'] = flex.bool([True, True, False, False])
  rt['Esq'] = flex.double([50.0, 10.0, 50.0, 10.0])
  return rt

def generate_reflection_table():
  """Create a reflection table with s1 and phi."""
  rt = flex.reflection_table()
  s1_vec = (1.0/sqrt(2.0), 0.0, 1.0/sqrt(2.0))
  rt['s1'] = flex.vec3_double([s1_vec, s1_vec, s1_vec])
  rt['phi'] = flex.double([0.0, 45.0, 90.0])
  return rt

@pytest.fixture
def simple_reflection_table():
  """Create a small reflection table"""
  refl = flex.reflection_table()
  refl['intensity'] = flex.double([1.0, 2.0, 3.0])
  refl['d'] = flex.double([1.0, 2.0, 3.0])
  refl['miller_index'] = flex.miller_index([(0, 0, 3), (0, 0, 2), (0, 0, 1)])
  refl.set_flags(flex.bool(refl.size(), False), refl.flags.bad_for_scaling)
  return refl

def refl_for_norm():
  """Create 11000 refelctions in 10 groups of 1100 approx equally spaced in
  resolution."""
  intensity_array = flex.double([])
  miller_indices = flex.miller_index([])
  # a set of miller indices with h2 + k2 + l2 = [2,3,4,5,6,8,9,10,11,12],
  # which should split nicely into 10 resolution groups.
  miller_array_list = [(1, 1, 0), (1, 1, 1), (2, 0, 0), (2, 1, 0), (2, 1, 1),
    (2, 2, 0), (2, 2, 1), (3, 0, 1), (3, 1, 1), (2, 2, 2)]
  for i in range(1, 11):
    miller_indices.extend(flex.miller_index(1100, miller_array_list[i-1]))
    intensity_array.extend(flex.double(np.linspace(90, 110, num=1100,
    endpoint=True)))
  rt = flex.reflection_table()
  rt['intensity'] = intensity_array
  rt['miller_index'] = miller_indices
  rt.set_flags(flex.bool(11000, False), rt.flags.bad_for_scaling)
  return rt

def test_quasi_normalisation(simple_reflection_table, test_exp_E2, test_exp_P1):
  """Test the quasi_normalisation function."""
  # Test that for small datasets, all Esq values are set to one.
  refl = quasi_normalisation(simple_reflection_table, test_exp_E2)
  assert list(refl['Esq']) == [1.0, 1.0, 1.0]

  rt = refl_for_norm()
  new_rt = quasi_normalisation(rt, test_exp_P1)
  for i in range(0, 9):
    assert list(new_rt['Esq'][i*1100:(i+1)*1100]) == pytest.approx(list(
      np.linspace(0.9, 1.1, num=1100, endpoint=True)))
  # FIXME Note, this test should actually be for i in range(0, 10):, however
  # the binner appears to create an extra bin above the highest data,
  # and then the call to interpolate causes the last values to be incorrect.

def test_calc_crystal_frame_vectors(test_reflection_table, mock_exp):
  """Test the namesake function, to check that the vectors are correctly rotated
  into the crystal frame."""
  rt, exp = test_reflection_table, mock_exp
  s0_vec = (1.0, 0.0, 0.0)
  s1_vec = (1.0/sqrt(2.0), 0.0, 1.0/sqrt(2.0))
  reflection_table = calc_crystal_frame_vectors(rt, exp)
  assert list(reflection_table['s0']) == list(flex.vec3_double(
    [s0_vec, s0_vec, s0_vec]))
  assert approx_equal(list(reflection_table['s0c']), list(flex.vec3_double([
    s0_vec, (1.0/sqrt(2.0), -1.0/sqrt(2.0), 0.0), (0.0, -1.0, 0.0)])))
  assert approx_equal(list(reflection_table['s1c']), list(flex.vec3_double([
    s1_vec, (1.0/2.0, -1.0/2.0, 1.0/sqrt(2.0)),
    (0.0, -1.0/sqrt(2.0), 1.0/sqrt(2.0))])))

def test_align_rotation_axis_along_z():
  """Test the function to rotate the coordinate system such that the rotation
  axis is along z. In the test, the rotation axis is x, so we expect the
  transformation to be: x > z, y > y, z > -x, x+z > -x+z."""
  rot_axis = flex.vec3_double([(1.0, 0.0, 0.0)])
  vectors = flex.vec3_double([(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
    (1.0, 0.0, 1.0)])
  rotated_vectors = align_rotation_axis_along_z(rot_axis, vectors)
  assert approx_equal(list(rotated_vectors), list(flex.vec3_double([
    (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (-1.0, 0.0, 1.0)])))

def test_sph_harm_table(test_reflection_table, mock_exp):
  """Simple test for the spherical harmonic table, constructing the table step
  by step, and verifying the values of a few easy-to-calculate entries.
  This also acts as a test for the calc_theta_phi function as well."""
  from scitbx import sparse # Needed to be able to assign to sph_h_t
  rt, exp = test_reflection_table, mock_exp
  reflection_table = calc_crystal_frame_vectors(rt, exp)
  theta_phi = calc_theta_phi(reflection_table['s0c'])
  assert approx_equal(list(theta_phi),
    [(pi/2.0, 0.0), (pi/2.0, -1.0*pi/4.0), (pi/2.0, -1.0*pi/2.0)])
  theta_phi_2 = calc_theta_phi(reflection_table['s1c'])
  assert approx_equal(list(theta_phi_2),
    [(pi/4.0, 0.0), (pi/4.0, -1.0*pi/4.0), (pi/4.0, -1.0*pi/2.0)])
  sph_h_t = create_sph_harm_table(theta_phi, theta_phi_2, 2)
  Y10 = ((3.0/(8.0*pi))**0.5)/2.0
  Y20 = -1.0*((5.0/(256.0*pi))**0.5)
  assert approx_equal(sph_h_t[1, 0], Y10)
  assert approx_equal(sph_h_t[1, 1], Y10)
  assert approx_equal(sph_h_t[1, 2], Y10)
  assert approx_equal(sph_h_t[5, 0], Y20)
  assert approx_equal(sph_h_t[5, 1], Y20)
  assert approx_equal(sph_h_t[5, 2], Y20)
  # Now test that you get the same by just calling the function.
  sht = sph_harm_table(rt, exp, 2)
  assert approx_equal(sht[1, 0], Y10)
  assert approx_equal(sht[1, 1], Y10)
  assert approx_equal(sht[1, 2], Y10)
  assert approx_equal(sht[5, 0], Y20)
  assert approx_equal(sht[5, 1], Y20)
  assert approx_equal(sht[5, 2], Y20)

def test_calculate_wilson_outliers(wilson_test_reflection_table):
  """Test the set wilson outliers function."""
  reflection_table = set_wilson_outliers(wilson_test_reflection_table)

  assert list(reflection_table.get_flags(
    reflection_table.flags.outlier_in_scaling)) == [True, False, True, False]

def generate_simple_table(prf=True):
  """Generate a reflection table for testing intensity combination.
  The numbers are contrived to make sum intensities agree well at high
  intensity but terribly at low and vice versa for profile intensities."""
  reflections = flex.reflection_table()
  reflections['miller_index'] = flex.miller_index([
    (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1),
    (0, 0, 2), (0, 0, 2), (0, 0, 2), (0, 0, 2), (0, 0, 2),
    (0, 0, 3), (0, 0, 3), (0, 0, 3), (0, 0, 3), (0, 0, 3),
    (0, 0, 4), (0, 0, 4), (0, 0, 4), (0, 0, 4), (0, 0, 4),
    (0, 0, 5), (0, 0, 5), (0, 0, 5), (0, 0, 5), (0, 0, 5)])
  reflections['inverse_scale_factor'] = flex.double(25, 1.0)
  #Contrive an example that should give the best cc12 when combined.
  #make sum intensities agree well at high intensity but terribly at low
  # and vice versa for profile intensities.
  #profile less consistent at high intensity here

  #sumless consistent at low intensity here
  reflections['intensity.sum.value'] = flex.double([
    10000.0, 11000.0, 9000.0, 8000.0, 12000.0,
    500.0, 5600.0, 5500.0, 2000.0, 6000.0,
    100.0, 50.0, 150.0, 75.0, 125.0,
    30.0, 10.0, 2.0, 35.0, 79.0,
    1.0, 10.0, 20.0, 10.0, 5.0])
  reflections['intensity.sum.variance'] = flex.double(
    [10000]*5 + [5000]*5 + [100]*5 + [30]*5 + [10]*5)
  reflections.set_flags(flex.bool(25, False), reflections.flags.outlier_in_scaling)
  if prf:
    reflections['intensity.prf.value'] = flex.double([
      10000.0, 16000.0, 12000.0, 6000.0, 9000.0,
      5000.0, 2000.0, 1500.0, 1300.0, 9000.0,
      100.0, 80.0, 120.0, 90.0, 100.0,
      30.0, 40.0, 50.0, 30.0, 30.0,
      10.0, 12.0, 9.0, 8.0, 10.0])
    reflections['intensity.prf.variance'] = flex.double(
      [10000]*5 + [5000]*5 + [100]*5 + [30]*5 + [10]*5)
  return reflections

def test_combine_intensities(test_exp_P1):
  """Test the combine intensities function for a single dataset"""
  reflections = generate_simple_table()
  reflections_list, results = combine_intensities([reflections], test_exp_P1)
  reflections = reflections_list[0]
  # Imid being 1200.0 should be best for this contrived example
  assert pytest.approx(min(results, key=results.get)) == 1200.0

  #Due to nature of crossover, just require 2% tolerance for this example
  assert list(reflections['intensity'][0:5]) == pytest.approx(list(
    reflections['intensity.sum.value'][0:5]), rel=2e-2)
  assert list(reflections['intensity'][20:25]) == pytest.approx(list(
    reflections['intensity.prf.value'][20:25]), rel=2e-2)

def test_combine_intensities_multi_dataset(test_exp_P1):
  """Test the combine intensities function for multiple datasets"""
  r1 = generate_simple_table()
  r1['partiality'] = flex.double(25, 1.0)
  r2 = generate_simple_table(prf=False)
  rlist, results = combine_intensities([r1, r2], test_exp_P1)
  assert pytest.approx(min(results, key=results.get)) == 1200.0

  r1 = generate_simple_table()
  r1['partiality'] = flex.double(25, 1.0)
  r2 = generate_simple_table(prf=False)
  rlist, res = combine_intensities([r1, r2], test_exp_P1, Imids=[0])
  assert list(rlist[0]['intensity']) == list(rlist[0]['intensity.prf.value'])
  assert list(rlist[1]['intensity']) == list(rlist[1]['intensity.sum.value'])

  r1 = generate_simple_table()
  r1['partiality'] = flex.double(25, 1.0)
  r2 = generate_simple_table(prf=False)
  r2['partiality'] = flex.double(25, 1.0)
  rlist, res = combine_intensities([r1, r2], test_exp_P1, Imids=[1])
  assert list(rlist[0]['intensity']) == list(rlist[0]['intensity.sum.value'])
  assert list(rlist[1]['intensity']) == list(rlist[1]['intensity.sum.value'])

  r1 = generate_simple_table(prf=False)
  r2 = generate_simple_table(prf=False)
  rlist, res = combine_intensities([r1, r2], test_exp_P1)
  assert res is None
  assert list(rlist[0]['intensity']) == list(rlist[0]['intensity.sum.value'])
  assert list(rlist[1]['intensity']) == list(rlist[1]['intensity.sum.value'])


def test_calculate_prescaling_correction():
  """Test the helper function that applies the lp, dqe and partiality corr."""
  reflection_table = flex.reflection_table()
  reflection_table['lp'] = flex.double([1.0, 0.9, 0.8])
  reflection_table['qe'] = flex.double([0.6, 0.5, 0.4])

  cor = calculate_prescaling_correction(reflection_table)
  assert list(cor) == [1.0 / 0.6, 0.9 / 0.5, 0.8 / 0.4]

  # Test compatibilty for old datasets
  del reflection_table['qe']
  reflection_table['dqe'] = flex.double([0.6, 0.5, 0.4])
  cor = calculate_prescaling_correction(reflection_table)
  assert list(cor) == [1.0 / 0.6, 0.9 / 0.5, 0.8 / 0.4]

def test_reasons():
  """Test the reasons class, which is basically a dictionary with a nice
    printed output"""
  reasons = Reasons()
  reasons.add_reason('test reason', 100)
  assert reasons.reasons['test reason'] == 100
  print(reasons)
  expected_output = """Reflections passing individual criteria:
criterion: test reason, reflections: 100
"""
  assert reasons.__repr__() == expected_output
