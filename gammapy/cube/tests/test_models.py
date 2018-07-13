# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function, unicode_literals
import pytest
import numpy as np
from numpy.testing import assert_allclose
import astropy.units as u
from ...utils.testing import requires_dependency
from ...maps import MapAxis, WcsGeom, Map
from ...irf.energy_dispersion import EnergyDispersion
from ...image.models import SkyGaussian
from ...spectrum.models import PowerLaw
from ..models import (
    SkyModel,
    SkyModelMapEvaluator,
    SourceLibrary,
    CompoundSkyModel,
)


@pytest.fixture(scope='session')
def sky_model():
    spatial_model = SkyGaussian(
        lon_0='3 deg', lat_0='4 deg', sigma='3 deg',
    )
    spectral_model = PowerLaw(
        index=2, amplitude='1e-11 cm-2 s-1 TeV-1', reference='1 TeV',
    )
    return SkyModel(spatial_model, spectral_model)


@pytest.fixture(scope='session')
def geom():
    axis = MapAxis.from_edges(np.logspace(-1, 1, 3), unit=u.TeV)
    return WcsGeom.create(skydir=(0, 0), npix=(5, 4), coordsys='GAL', axes=[axis])


@pytest.fixture(scope='session')
def exposure(geom):
    m = Map.from_geom(geom)
    m.quantity = np.ones((2, 4, 5)) * u.Quantity('100 m2 s')
    return m


@pytest.fixture(scope='session')
def background(geom):
    m = Map.from_geom(geom)
    m.quantity = np.ones((2, 4, 5)) * 1e-7
    return m


@pytest.fixture(scope='session')
def edisp(geom):
    e_true = geom.get_axis_by_name('energy').edges
    return EnergyDispersion.from_diagonal_matrix(e_true=e_true)


@pytest.fixture()
def evaluator(sky_model, exposure, background):
    return SkyModelMapEvaluator(sky_model, exposure, background)


class TestSourceLibrary:
    def setup(self):
        self.source_library = SourceLibrary([sky_model(), sky_model()])

    def test_to_compound_model(self):
        compound = self.source_library.to_compound_model()
        assert isinstance(compound, CompoundSkyModel)


class TestSkyModel:
    @staticmethod
    def test_repr(sky_model):
        assert 'SkyModel' in repr(sky_model)

    @staticmethod
    def test_str(sky_model):
        assert 'SkyModel' in str(sky_model)

    @staticmethod
    def test_evaluate_scalar(sky_model):
        lon = 3 * u.deg
        lat = 4 * u.deg
        energy = 1 * u.TeV

        q = sky_model.evaluate(lon, lat, energy)

        assert q.unit == 'cm-2 s-1 TeV-1 deg-2'
        assert q.shape == (1, 1, 1)
        assert_allclose(q.value, 1.76838826e-13)

    @staticmethod
    def test_evaluate_array(sky_model):
        lon = 3 * u.deg * np.ones(shape=(3, 4))
        lat = 4 * u.deg * np.ones(shape=(3, 4))
        energy = [1, 1, 1, 1, 1] * u.TeV

        q = sky_model.evaluate(lon, lat, energy)

        assert q.shape == (5, 3, 4)
        assert_allclose(q.value, 1.76838826e-13)


class TestCompoundSkyModel:

    @staticmethod
    def test_add(sky_model):
        compound_model = sky_model + sky_model
        parnames = ['lon_0', 'lat_0', 'sigma', 'index', 'amplitude', 'reference'] * 2
        assert compound_model.parameters.names == parnames

        lon = 3 * u.deg * np.ones(shape=(3, 4))
        lat = 4 * u.deg * np.ones(shape=(3, 4))
        energy = [1, 1, 1, 1, 1] * u.TeV

        q = compound_model.evaluate(lon, lat, energy)

        assert q.shape == (5, 3, 4)
        assert_allclose(q.value, 3.536776513153229e-13)


@requires_dependency('scipy')
class TestSkyModelMapEvaluator:

    @staticmethod
    def test_energy_center(evaluator):
        val = evaluator.energy_center
        assert val.shape == (2,)
        assert val.unit == 'TeV'

    @staticmethod
    def test_energy_edges(evaluator):
        val = evaluator.energy_edges
        assert val.shape == (3,)
        assert val.unit == 'TeV'

    @staticmethod
    def test_energy_bin_width(evaluator):
        val = evaluator.energy_bin_width
        assert val.shape == (2,)
        assert val.unit == 'TeV'

    @staticmethod
    def test_lon_lat(evaluator):
        val = evaluator.lon
        assert val.shape == (4, 5)
        assert val.unit == 'deg'

        val = evaluator.lat
        assert val.shape == (4, 5)
        assert val.unit == 'deg'

    @staticmethod
    def test_solid_angle(evaluator):
        val = evaluator.solid_angle
        assert val.shape == (2, 4, 5)
        assert val.unit == 'sr'

    @staticmethod
    def test_bin_volume(evaluator):
        val = evaluator.bin_volume
        assert val.shape == (2, 4, 5)
        assert val.unit == 'TeV sr'

    @staticmethod
    def test_compute_dnde(evaluator):
        out = evaluator.compute_dnde()

        assert out.shape == (2, 4, 5)
        assert out.unit == 'cm-2 s-1 TeV-1 deg-2'
        assert_allclose(out.value.mean(), 7.460919e-14)

    @staticmethod
    def test_compute_flux(evaluator):
        out = evaluator.compute_flux()

        assert out.shape == (2, 4, 5)
        assert out.unit == 'cm-2 s-1'
        assert_allclose(out.value.mean(), 1.828206748668197e-14)

    @staticmethod
    def test_compute_npred(evaluator):
        out = evaluator.compute_npred()
        assert out.shape == (2, 4, 5)
        assert_allclose(out.sum(), 47.312826994672788e-07)
