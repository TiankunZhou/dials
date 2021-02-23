import os

import procrunner
import pytest

from dxtbx.model.experiment_list import ExperimentListFactory


def plot_beam_centre_error(ideal_bc, obs_bc):
    import matplotlib.pyplot as plt

    ideal_x, ideal_y = zip(*ideal_bc)
    obs_x, obs_y = zip(*obs_bc)
    del_x = [a - b for a, b in zip(obs_x, ideal_x)]
    del_y = [a - b for a, b in zip(obs_y, ideal_y)]
    scan_points = range(len(ideal_x))
    plt.plot(scan_points, del_x, scan_points, del_y)
    plt.xlabel("Scan point")
    plt.ylabel("Beam centre residual (obs - ideal) (pixels)")
    plt.show()


def test_refinement_and_compare_with_known_truth(dials_regression, run_in_tmpdir):
    # use data generated by simulation for this test
    data_dir = os.path.join(
        dials_regression, "refinement_test_data", "varying_beam_direction"
    )
    experiments_path = os.path.join(data_dir, "refined_static.json")
    pickle_path = os.path.join(data_dir, "refined_static.pickle")

    for pth in (experiments_path, pickle_path):
        assert os.path.exists(pth)

    # Run refinement and load models
    result = procrunner.run(
        [
            "dials.refine",
            experiments_path,
            pickle_path,
            "scan_varying=True",
            "crystal.orientation.force_static=True",
            "crystal.unit_cell.force_static=True",
            "beam.force_static=False",
            "beam.fix=wavelength",
        ]
    )
    assert not result.returncode and not result.stderr
    exp = ExperimentListFactory.from_json_file("refined.expt", check_format=False)[0]
    beam, detector = exp.beam, exp.detector

    # Beam centre at every scan-point
    s0_scan_points = [beam.get_s0_at_scan_point(i) for i in range(beam.num_scan_points)]
    bc_scan_points = [detector[0].get_beam_centre_px(s0) for s0 in s0_scan_points]

    # Set up the nanoBragg object as used in the simulation
    from .sim_images import Simulation

    sim = Simulation()
    sim.set_varying_beam(along="both")

    # Simulation beam centre at every scan-point
    sim_s0_scan_points = [
        sim.beam.get_s0_at_scan_point(i) for i in range(sim.beam.num_scan_points)
    ]
    sim_bc_scan_points = [
        sim.detector[0].get_beam_centre_px(s0) for s0 in sim_s0_scan_points
    ]

    assert beam.num_scan_points == sim.beam.num_scan_points

    # Generate a plot. This shows that the beam centre is worse at the edges of
    # the scan. This is what we expect as the centroids at the scan edges are
    # least well determined because of the truncation of found spots. At these
    # edges the error approaches 0.15 pixels, whilst in the central region of
    # the scan it is within 0.05 pixels.
    #
    # plot_beam_centre_error(sim_bc_scan_points, bc_scan_points)

    # Compare the results.
    for bc1, bc2 in zip(sim_bc_scan_points, bc_scan_points):
        assert bc2 == pytest.approx(bc1, abs=0.15)
