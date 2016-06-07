from parcels import Grid, Particle, JITParticle, AdvectionRK4
import numpy as np
import pytest
import math
from datetime import timedelta as delta


ptype = {'scipy': Particle, 'jit': JITParticle}

# Some constants
f = 1.e-4
u_0 = 0.3
u_g = 0.04
gamma = 1/(86400. * 2.89)
gamma_g = 1/(86400. * 28.9)


@pytest.fixture
def lon(xdim=200):
    return np.linspace(-170, 170, xdim, dtype=np.float32)


@pytest.fixture
def lat(ydim=100):
    return np.linspace(-80, 80, ydim, dtype=np.float32)


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_zonal(lon, lat, mode, npart=10):
    """ Particles at high latitude move geographically faster due to
        the pole correction in `GeographicPolar`.
    """
    U = np.ones((lon.size, lat.size), dtype=np.float32)
    V = np.zeros((lon.size, lat.size), dtype=np.float32)
    grid = Grid.from_data(U, lon, lat, V, lon, lat, mesh='spherical')

    pset = grid.ParticleSet(npart, pclass=ptype[mode],
                            lon=np.zeros(npart, dtype=np.float32) + 20.,
                            lat=np.linspace(0, 80, npart, dtype=np.float32))
    pset.execute(AdvectionRK4, endtime=delta(hours=2), dt=delta(seconds=30))
    assert (np.diff(np.array([p.lon for p in pset])) > 1.e-4).all()


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_meridional(lon, lat, mode, npart=10):
    """ Particles at high latitude move geographically faster due to
        the pole correction in `GeographicPolar`.
    """
    U = np.zeros((lon.size, lat.size), dtype=np.float32)
    V = np.ones((lon.size, lat.size), dtype=np.float32)
    grid = Grid.from_data(U, lon, lat, V, lon, lat, mesh='spherical')

    pset = grid.ParticleSet(npart, pclass=ptype[mode],
                            lon=np.linspace(-60, 60, npart, dtype=np.float32),
                            lat=np.linspace(0, 30, npart, dtype=np.float32))
    delta_lat = np.diff(np.array([p.lat for p in pset]))
    pset.execute(AdvectionRK4, endtime=delta(hours=2), dt=delta(seconds=30))
    assert np.allclose(np.diff(np.array([p.lat for p in pset])), delta_lat, rtol=1.e-4)


def truth_stationary(x_0, y_0, t):
    lat = y_0 - u_0 / f * (1 - math.cos(f * t))
    lon = x_0 + u_0 / f * math.sin(f * t)
    return lon, lat


@pytest.fixture
def grid_stationary(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a stationary eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_0 * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -u_0 * np.sin(f * time)
    return Grid.from_data(U, lon, lat, V, lon, lat, time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_stationary_eddy(grid_stationary, mode, npart=1):
    grid = grid_stationary
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = grid.ParticleSet(size=npart, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(AdvectionRK4, dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_stationary(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_stationary(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=1e-5)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=1e-5)


def truth_moving(x_0, y_0, t):
    lat = y_0 - (u_0 - u_g) / f * (1 - math.cos(f * t))
    lon = x_0 + u_g * t + (u_0 - u_g) / f * math.sin(f * t)
    return lon, lat


@pytest.fixture
def grid_moving(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a moving eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_g + (u_0 - u_g) * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -(u_0 - u_g) * np.sin(f * time)
    return Grid.from_data(U, lon, lat, V, lon, lat, time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_moving_eddy(grid_moving, mode, npart=1):
    grid = grid_moving
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = grid.ParticleSet(size=npart, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(AdvectionRK4, dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_moving(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_moving(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=1e-5)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=1e-5)


def truth_decaying(x_0, y_0, t):
    lat = y_0 - ((u_0 - u_g) * f / (f ** 2 + gamma ** 2) *
                 (1 - np.exp(-gamma * t) * (np.cos(f * t) + gamma / f * np.sin(f * t))))
    lon = x_0 + (u_g / gamma_g * (1 - np.exp(-gamma_g * t)) +
                 (u_0 - u_g) * f / (f ** 2 + gamma ** 2) *
                 (gamma / f + np.exp(-gamma * t) *
                  (math.sin(f * t) - gamma / f * math.cos(f * t))))
    return lon, lat


@pytest.fixture
def grid_decaying(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a decaying eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_g *\
        np.exp(-gamma_g * time) + (u_0 - u_g) * np.exp(-gamma * time) * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -(u_0 - u_g) *\
        np.exp(-gamma * time) * np.sin(f * time)
    return Grid.from_data(U, lon, lat, V, lon, lat, time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_decaying_eddy(grid_decaying, mode, npart=1):
    grid = grid_decaying
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = grid.ParticleSet(size=npart, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(AdvectionRK4, dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_decaying(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_decaying(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=1e-5)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=1e-5)
