# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 15:31:22 2017

@author: nooteboom
"""
import itertools

from parcels import (FieldSet, JITParticle, AdvectionRK4_3D,
                     Field, ErrorCode, ParticleFile, Variable)
# from parcels import ParticleSet
# from parcels.particleset_vectorized_benchmark import ParticleSet_Benchmark
from parcels.particleset_node_benchmark import ParticleSet_Benchmark

from argparse import ArgumentParser
from datetime import timedelta as delta
from datetime import datetime
import numpy as np
import math
from glob import glob
import sys
import pandas as pd

import os
import time as ostime
import matplotlib.pyplot as plt
import fnmatch

# import dask
import gc

try:
    from mpi4py import MPI
except:
    MPI = None

import warnings
import xarray as xr
warnings.simplefilter("ignore", category=xr.SerializationWarning)

global_t_0 = 0
odir = ""

def plot(total_times = None, compute_times = None, io_times = None, memory_used = None, nparticles = None, imageFilePath = ""):
    if total_times is None:
        total_times = []
    if compute_times is None:
        compute_times = []
    if io_times is None:
        io_times = []
    if memory_used is None:
        memory_used = []
    if nparticles is None:
        nparticles = []
    plot_t = []
    plot_ct = []
    plot_iot = []
    plot_npart = []
    cum_t = 0
    cum_ct = 0
    cum_iot = 0
    t_scaler = 1. * 10./1.0
    npart_scaler = 1.0 / 1000.0
    for i in range(len(total_times)):
        #if i==0:
        #    plot_t.append( (total_times[i]-global_t_0)*t_scaler )
        #    cum_t += (total_times[i]-global_t_0)
        #else:
        #    plot_t.append( (total_times[i]-total_times[i-1])*t_scaler )
        #    cum_t += (total_times[i]-total_times[i-1])
        plot_t.append( total_times[i]*t_scaler )
        cum_t += (total_times[i])

    for i in range(len(compute_times)):
        plot_ct.append(compute_times[i] * t_scaler)
        cum_ct += compute_times[i]
    for i in range(len(io_times)):
        plot_iot.append(io_times[i] * t_scaler)
        cum_iot += io_times[i]
    for i in range(len(nparticles)):
        plot_npart.append(nparticles[i] * npart_scaler)

    plot_mem = []
    if memory_used is not None:
        #mem_scaler = (1*10)/(1024*1024*1024)
        mem_scaler = 1 / (1024 * 1024 * 1024)
        for i in range(len(memory_used)):
            plot_mem.append(memory_used[i] * mem_scaler)

    # do_ct_plot = True
    do_iot_plot = True
    do_mem_plot = True
    do_npart_plot = True
    assert (len(plot_t) == len(plot_ct))
    # assert (len(plot_t) == len(plot_iot))
    if len(plot_t) != len(plot_iot):
        print("plot_t and plot_iot have different lengths ({} vs {})".format(len(plot_t), len(plot_iot)))
        do_iot_plot = False
    # assert (len(plot_t) == len(plot_mem))
    if len(plot_t) != len(plot_mem):
        print("plot_t and plot_mem have different lengths ({} vs {})".format(len(plot_t), len(plot_mem)))
        do_mem_plot = False
    # assert (len(plot_t) == len(plot_npart))
    if len(plot_t) != len(plot_npart):
        print("plot_t and plot_npart have different lengths ({} vs {})".format(len(plot_t), len(plot_npart)))
        do_npart_plot = False
    x = []
    for i in range(len(plot_t)):
        x.append(i)

    fig, ax = plt.subplots(1, 1, figsize=(21, 12))
    ax.plot(x, plot_t, 'o-', label="total time_spent [100ms]")
    ax.plot(x, plot_ct, 'o-', label="compute time_spent [100ms]")
    # == this is still the part that breaks - as they are on different time scales, possibly leave them out ? == #
    if do_iot_plot:
        ax.plot(x, plot_iot, 'o-', label="io time_spent [100ms]")
    if (memory_used is not None) and do_mem_plot:
        #ax.plot(x, plot_mem, 'x-', label="memory_used (cumulative) [100 MB]")
        ax.plot(x, plot_mem, 'x-', label="memory_used (cumulative) [1 GB]")
    if do_npart_plot:
        ax.plot(x, plot_npart, '-', label="sim. particles [# 1000]")
    plt.xlim([0, 730])
    plt.ylim([0, 120])
    plt.legend()
    ax.set_xlabel('iteration')
    plt.savefig(os.path.join(odir, imageFilePath), dpi=600, format='png')

    sys.stdout.write("cumulative total runtime: {}".format(cum_t))
    sys.stdout.write("cumulative compute time: {}".format(cum_ct))
    sys.stdout.write("cumulative I/O time: {}".format(cum_iot))


def set_nemo_fieldset(ufiles, vfiles, wfiles, tfiles, pfiles, dfiles, ifiles, bfile, mesh_mask='/scratch/ckehl/experiments/palaeo-parcels/NEMOdata/domain/coordinates.nc'):
    filenames = { 'U': {'lon': mesh_mask,
                        'lat': mesh_mask,
                        'depth': [ufiles[0]],
                        'data':ufiles},
                'V' : {'lon': mesh_mask,
                        'lat': mesh_mask,
                        'depth': [ufiles[0]],
                        'data':vfiles},
                'W' : {'lon': mesh_mask,
                        'lat': mesh_mask,
                        'depth': [ufiles[0]],
                        'data':wfiles},  
                'S' : {'lon': mesh_mask,
                        'lat': mesh_mask,
                        'depth': [tfiles[0]],
                        'data':tfiles},   
                'T' : {'lon': mesh_mask,
                        'lat': mesh_mask,
                        'depth': [tfiles[0]],
                        'data':tfiles},
                'NO3':{'lon': mesh_mask,
                       'lat': mesh_mask,
                       'depth': [pfiles[0]],
                       'data':pfiles},
                'PP':{'lon': mesh_mask,
                       'lat': mesh_mask,
                       'depth': [dfiles[0]],
                       'data':dfiles},
                'ICE':{'lon': mesh_mask,
                       'lat': mesh_mask,
                       'depth': [ifiles[0]],
                       'data':ifiles},
                'ICEPRES':{'lon': mesh_mask,
                       'lat': mesh_mask,
                       'depth': [ifiles[0]],
                       'data':ifiles},
                'CO2':{'lon': mesh_mask,
                       'lat': mesh_mask,
                       'depth': [dfiles[0]],
                       'data':dfiles},
                }
    if mesh_mask:
        filenames['mesh_mask'] = mesh_mask
    variables = {'U': 'uo',
                 'V': 'vo',
                 'W': 'wo',
                 'T': 'sst',
                 'S': 'sss',
                 'NO3': 'DIN',                 
                 'PP': 'TPP3',                
                 'ICE': 'sit',
                 'ICEPRES': 'ice_pres',
                 'CO2': 'TCO2' }

    dimensions = {'U': {'lon': 'glamf', 'lat': 'gphif', 'depth': 'depthu', 'time': 'time_counter'},  #
                  'V': {'lon': 'glamf', 'lat': 'gphif', 'depth': 'depthu', 'time': 'time_counter'},  #
                  'W': {'lon': 'glamf', 'lat': 'gphif', 'depth': 'depthu', 'time': 'time_counter'},  #
                  'T': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'S': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'NO3': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'PP': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'ICE': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'ICEPRES': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'},
                  'CO2': {'lon': 'glamf', 'lat': 'gphif', 'time': 'time_counter'} } #,
    bfiles = {'lon': mesh_mask, 'lat': mesh_mask, 'data': [bfile, ]}
    bvariables = ('B', 'Bathymetry')
    bdimensions = {'lon': 'glamf', 'lat': 'gphif'}
    bchs = False

    chs = {'time_counter': 1, 'depthu': 75, 'depthv': 75, 'depthw': 75, 'deptht': 75, 'y': 200, 'x': 200}
    #
    #chs = (1, 75, 200, 200)
    #
    #dask.config.set({'array.chunk-size': '6MiB'})
    #chs = 'auto'

    if mesh_mask: # and isinstance(bfile, list) and len(bfile) > 0:
        # fieldset = FieldSet.from_nemo(filenames, variables, dimensions, allow_time_extrapolation=False, field_chunksize='auto')
        fieldset = FieldSet.from_nemo(filenames, variables, dimensions, allow_time_extrapolation=True, field_chunksize=chs)
        Bfield = Field.from_netcdf(bfiles, bvariables, bdimensions, allow_time_extrapolation=True, interp_method='cgrid_tracer', field_chunksize=bchs)
        fieldset.add_field(Bfield, 'B')
        fieldset.U.vmax = 10
        fieldset.V.vmax = 10
        fieldset.W.vmax = 10
        return fieldset
    else:
        filenames.pop('B')
        variables.pop('B')
        dimensions.pop('B')
        # fieldset = FieldSet.from_netcdf(filenames, variables, dimensions, allow_time_extrapolation=False, field_chunksize=chs)
        fieldset = FieldSet.from_netcdf(filenames, variables, dimensions, allow_time_extrapolation=True, field_chunksize=chs)
        fieldset.U.vmax = 10
        fieldset.V.vmax = 10
        fieldset.W.vmax = 10
        return fieldset
        

def periodicBC(particle, fieldSet, time):
    if particle.lon > 180:
        particle.lon -= 360
    if particle.lon < -180:
        particle.lon += 360

def Sink(particle, fieldset, time):
    if(particle.depth>fieldset.dwellingdepth):
        particle.depth = particle.depth + fieldset.sinkspeed * particle.dt
    elif(particle.depth<=fieldset.dwellingdepth and particle.depth>1):
        particle.depth = fieldset.surface
        particle.temp = fieldset.T[time+particle.dt, fieldset.surface, particle.lat, particle.lon]
        particle.salin = fieldset.S[time+particle.dt, fieldset.surface, particle.lat, particle.lon]
        particle.PP = fieldset.PP[time+particle.dt, fieldset.surface, particle.lat, particle.lon]
        particle.NO3 = fieldset.NO3[time+particle.dt, fieldset.surface, particle.lat, particle.lon]
        particle.ICE = fieldset.ICE[time+particle.dt, fieldset.surface, particle.lat, particle.lon]
        particle.ICEPRES = fieldset.ICEPRES[time+particle.dt, fieldset.surface, particle.lat, particle.lon] 
        particle.CO2 = fieldset.CO2[time+particle.dt, fieldset.surface, particle.lat, particle.lon]  
        particle.delete()

def Age(particle, fieldset, time):
    if particle.state == ErrorCode.Evaluate:
        particle.age = particle.age + math.fabs(particle.dt)

def DeleteParticle(particle, fieldset, time):
    particle.delete()

def perIterGC():
    gc.collect()

def initials(particle, fieldset, time):
    if particle.age==0.:
        particle.depth = fieldset.B[time, fieldset.surface, particle.lat, particle.lon]
        if(particle.depth  > 5800.):
            particle.age = (particle.depth - 5799.)*fieldset.sinkspeed
            particle.depth = 5799.        
        particle.lon0 = particle.lon
        particle.lat0 = particle.lat
        particle.depth0 = particle.depth


if __name__ == "__main__":
    parser = ArgumentParser(description="Example of particle advection using in-memory stommel test case")
    parser.add_argument("-i", "--imageFileName", dest="imageFileName", type=str, default="mpiChunking_plot_MPI.png", help="image file name of the plot")
    parser.add_argument("-p", "--periodic", dest="periodic", action='store_true', default=False, help="enable/disable periodic wrapping (else: extrapolation)")
    parser.add_argument("-sp", "--sinking_speed", dest="sp", type=float, default=11.0, help="set the simulation sinking speed in [m/day] (default: 11.0)")
    parser.add_argument("-dd", "--dwelling_depth", dest="dd", type=float, default=10.0, help="set the dwelling depth (i.e. ocean surface depth) in [m] (default: 10.0)")
    # parser.add_argument("-t", "--time_in_days", dest="time_in_days", type=int, default=365, help="runtime in days (default: 365)")
    parser.add_argument("-t", "--time_in_days", dest="time_in_days", type=str, default="1*365", help="runtime in days (default: 1*365)")
    parser.add_argument("-G", "--GC", dest="useGC", action='store_true', default=False, help="using a garbage collector (default: false)")
    args = parser.parse_args()

    sp = args.sp # The sinkspeed m/day
    dd = args.dd  # The dwelling depth
    imageFileName=args.imageFileName
    periodicFlag=args.periodic
    time_in_days = int(float(eval(args.time_in_days)))
    with_GC = args.useGC

    headdir = ""
    odir = ""
    dirread_pal = ""
    datahead = ""
    dirread_top = ""
    dirread_top_bgc = ""
    if os.uname()[1] in ['science-bs35', 'science-bs36']:  # Gemini
        # headdir = "/scratch/{}/experiments/palaeo-parcels".format(os.environ['USER'])
        headdir = "/scratch/{}/experiments/palaeo-parcels".format("ckehl")
        odir = os.path.join(headdir,"BENCHres")
        dirread_pal = os.path.join(headdir,'NEMOdata')
        datahead = "/data/oceanparcels/input_data"
        dirread_top = os.path.join(datahead, 'NEMO-MEDUSA/ORCA0083-N006/')
        dirread_top_bgc = os.path.join(datahead, 'NEMO-MEDUSA/ORCA0083-N006/')
    elif fnmatch.fnmatchcase(os.uname()[1], "int?.*"):  # Cartesius
        CARTESIUS_SCRATCH_USERNAME = 'ckehl'
        headdir = "/scratch/shared/{}/experiments/palaeo-parcels".format(CARTESIUS_SCRATCH_USERNAME)
        odir = os.path.join(headdir, "/BENCHres")
        dirread_pal = os.path.join(headdir,'NEMOdata')
        datahead = "/projects/0/topios/hydrodynamic_data"
        dirread_top = os.path.join(datahead, 'NEMO-MEDUSA/ORCA0083-N006/')
        dirread_top_bgc = os.path.join(datahead, 'NEMO-MEDUSA_BGC/ORCA0083-N006/')
    else:
        headdir = "/var/scratch/nooteboom"
        odir = os.path.join(headdir, "BENCHres")
        dirread_pal = headdir
        datahead = "/data"
        dirread_top = os.path.join(datahead, 'NEMO-MEDUSA/ORCA0083-N006/')
        dirread_top_bgc = os.path.join(datahead, 'NEMO-MEDUSA/ORCA0083-N006/')


    # dirread_pal = '/projects/0/palaeo-parcels/NEMOdata/'

    outfile = 'grid_dd' + str(int(dd)) + '_sp' + str(int(sp))
    dirwrite = os.path.join(odir, "sp%d_dd%d" % (int(sp),int(dd)))
    if not os.path.exists(dirwrite):
        os.mkdir(dirwrite)

    latsz = np.array(pd.read_csv(os.path.join(headdir,"TF_locationsSurfaceSamples_forPeter.csv")).Latitude.tolist())
    lonsz = np.array(pd.read_csv(os.path.join(headdir,"TF_locationsSurfaceSamples_forPeter.csv")).Longitude.tolist())
    numlocs = np.logical_and(latsz<1000, lonsz<1000)
    latsz = latsz[numlocs]
    lonsz = lonsz[numlocs]

    assert ~(np.isnan(latsz)).any(), 'locations should not contain any NaN values'
    dep = dd * np.ones(latsz.shape)

    times = np.array([datetime(2000, 12, 25) - delta(days=x) for x in range(0,int(365),3)])
    time = np.empty(shape=(0))
    depths = np.empty(shape=(0))
    lons = np.empty(shape=(0))
    lats = np.empty(shape=(0))
    for i in range(len(times)):
        lons = np.append(lons,lonsz)
        lats = np.append(lats, latsz)
        depths = np.append(depths, np.zeros(len(lonsz), dtype=np.float32))
        time = np.append(time, np.full(len(lonsz),times[i]))


    if MPI:
        mpi_comm = MPI.COMM_WORLD
        mpi_rank = mpi_comm.Get_rank()
        if mpi_rank==0:
            # global_t_0 = ostime.time()
            # global_t_0 = MPI.Wtime()
            global_t_0 = ostime.process_time()
    else:
        # global_t_0 = ostime.time()
        global_t_0 = ostime.process_time()

    ufiles = sorted(glob(dirread_top + 'means/ORCA0083-N06_2000????d05U.nc'))
    vfiles = sorted(glob(dirread_top + 'means/ORCA0083-N06_2000????d05V.nc'))
    wfiles = sorted(glob(dirread_top + 'means/ORCA0083-N06_2000????d05W.nc'))
    tfiles = sorted(glob(dirread_top + 'means/ORCA0083-N06_2000????d05T.nc'))
    pfiles = sorted(glob(dirread_top_bgc + 'means/ORCA0083-N06_2000????d05P.nc'))
    dfiles = sorted(glob(dirread_top_bgc + 'means/ORCA0083-N06_2000????d05D.nc'))
    ifiles = sorted(glob(dirread_top + 'means/ORCA0083-N06_2000????d05I.nc'))
    bfile = dirread_top + 'domain/bathymetry_ORCA12_V3.3.nc'

    fieldset = set_nemo_fieldset(ufiles, vfiles, wfiles, tfiles, pfiles, dfiles, ifiles, bfile, os.path.join(dirread_pal, "domain/coordinates.nc"))
    fieldset.add_periodic_halo(zonal=True) 
    fieldset.add_constant('dwellingdepth', np.float(dd))
    fieldset.add_constant('sinkspeed', sp/86400.)
    fieldset.add_constant('maxage', 300000.*86400)
    fieldset.add_constant('surface', 2.5)

    class DinoParticle(JITParticle):
        temp = Variable('temp', dtype=np.float32, initial=np.nan)
        age = Variable('age', dtype=np.float32, initial=0.)
        salin = Variable('salin', dtype=np.float32, initial=np.nan)
        lon0 = Variable('lon0', dtype=np.float32, initial=0.)
        lat0 = Variable('lat0', dtype=np.float32, initial=0.)
        depth0 = Variable('depth0',dtype=np.float32, initial=0.) 
        PP = Variable('PP',dtype=np.float32, initial=np.nan)
        NO3 = Variable('NO3',dtype=np.float32, initial=np.nan)
        ICE = Variable('ICE',dtype=np.float32, initial=np.nan)
        ICEPRES = Variable('ICEPRES',dtype=np.float32, initial=np.nan)
        CO2 = Variable('CO2',dtype=np.float32, initial=np.nan)

    pset = ParticleSet_Benchmark.from_list(fieldset=fieldset, pclass=DinoParticle, lon=lons.tolist(), lat=lats.tolist(), depth=depths.tolist(), time = time)

    # perflog = PerformanceLog()
    # perflog.pset = pset
    # postProcessFuncs = [perflog.advance,]

    """ Kernal + Execution"""
    postProcessFuncs = []
    if with_GC:
        postProcessFuncs.append(perIterGC)
    pfile = pset.ParticleFile(os.path.join(dirwrite, outfile), convert_at_end=True, write_ondelete=True)
    kernels = pset.Kernel(initials) + Sink + Age  + pset.Kernel(AdvectionRK4_3D) + Age

    starttime = 0
    endtime = 0
    if MPI:
        mpi_comm = MPI.COMM_WORLD
        mpi_rank = mpi_comm.Get_rank()
        if mpi_rank==0:
            # starttime = ostime.time()
            # starttime = MPI.Wtime()
            starttime = ostime.process_time()
    else:
        # starttime = ostime.time()
        starttime = ostime.process_time()

    # pset.execute(kernels, runtime=delta(days=365*9), dt=delta(minutes=-20), output_file=pfile, verbose_progress=False,
    # recovery={ErrorCode.ErrorOutOfBounds: DeleteParticle}, postIterationCallbacks=postProcessFuncs)
    # postIterationCallbacks=postProcessFuncs, callbackdt=delta(hours=12)
    pset.execute(kernels, runtime=delta(days=time_in_days), dt=delta(hours=-12), output_file=pfile, verbose_progress=False, recovery={ErrorCode.ErrorOutOfBounds: DeleteParticle}, postIterationCallbacks=postProcessFuncs, callbackdt=np.infty)

    if MPI:
        mpi_comm = MPI.COMM_WORLD
        mpi_rank = mpi_comm.Get_rank()
        if mpi_rank==0:
            # endtime = ostime.time()
            # endtime = MPI.Wtime()
            endtime = ostime.process_time()
    else:
        #endtime = ostime.time()
        endtime = ostime.process_time()

    size_Npart = len(pset.nparticle_log)
    Npart = pset.nparticle_log.get_param(size_Npart-1)
    if MPI:
        mpi_comm = MPI.COMM_WORLD
        Npart = mpi_comm.reduce(Npart, op=MPI.SUM, root=0)
        if mpi_comm.Get_rank() == 0:
            if size_Npart>0:
                sys.stdout.write("final # particles: {}\n".format( Npart ))
            sys.stdout.write("Time of pset.execute(): {} sec.\n".format(endtime-starttime))
            avg_time = np.mean(np.array(pset.total_log.get_values(), dtype=np.float64))
            sys.stdout.write("Avg. kernel update time: {} msec.\n".format(avg_time*1000.0))
    else:
        if size_Npart > 0:
            sys.stdout.write("final # particles: {}\n".format( Npart ))
        sys.stdout.write("Time of pset.execute(): {} sec.\n".format(endtime - starttime))
        avg_time = np.mean(np.array(pset.total_log.get_values(), dtype=np.float64))
        sys.stdout.write("Avg. kernel update time: {} msec.\n".format(avg_time * 1000.0))

    pfile.close()


    if MPI:
        mpi_comm = MPI.COMM_WORLD
        Nparticles = mpi_comm.reduce(np.array(pset.nparticle_log.get_params()), op=MPI.SUM, root=0)
        Nmem = mpi_comm.reduce(np.array(pset.mem_log.get_params()), op=MPI.SUM, root=0)
        # mpi_comm.Barrier()
        if mpi_comm.Get_rank() == 0:
            # plot(perflog.samples, perflog.times_steps, perflog.memory_steps, pset.compute_log.times_steps, pset.io_log.times_steps, os.path.join(odir, args.imageFileName))
            # plot_internal(pset.total_log.get_values(), pset.compute_log.get_values(), pset.io_log.get_values(), pset.mem_log.get_params(), pset.nparticle_log.get_params(), imageFileName)
            plot(pset.total_log.get_values(), pset.compute_log.get_values(), pset.io_log.get_values(), Nmem, Nparticles, os.path.join(odir, args.imageFileName))
    else:
        # plot(perflog.samples, perflog.times_steps, perflog.memory_steps, pset.compute_log.times_steps, pset.io_log.times_steps, os.path.join(odir, args.imageFileName))
        plot(pset.total_log.get_values(), pset.compute_log.get_values(), pset.io_log.get_values(), pset.mem_log.get_params(), pset.nparticle_log.get_params(), os.path.join(odir, args.imageFileName))

    print('Execution finished')
    exit(0)




