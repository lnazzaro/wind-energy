#!/usr/bin/env python

"""
Author: Lori Garzio on 10/26/2021
Last modified: 10/27/2021
Plot Hovmoller diagram of hourly-averaged wind speed divergence at specified cross-section
"""

import datetime as dt
import os
import xarray as xr
import numpy as np
import pandas as pd
from geographiclib.geodesic import Geodesic
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import functions.common as cf
import functions.plotting as pf
import metpy.calc as mc
from wrf import interpline, CoordPair, WrfProj
plt.rcParams.update({'font.size': 12})  # all font sizes are 12 unless otherwise specified


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    geod = Geodesic.WGS84
    g = geod.Inverse(lat1, lon1, lat2, lon2)
    return np.round(g['s12'])


def plot_divergence_hovmoller(ds_sub, save_dir, interval_name, t0=None, sb_t0str=None, sb_t1str=None):
    t0 = t0 or None
    sb_t0str = sb_t0str or None
    sb_t1str = sb_t1str or None
    heights = [250, 200, 160, 10]

    la_polygon, pa_polygon = cf.extract_lease_area_outlines()

    # grab data along the line perpendicular to the coast in southern NJ
    point_start = CoordPair(lat=39.64, lon=-74.745)
    point_end = CoordPair(lat=39.1, lon=-74.15)

    for height in heights:
        if height == 10:
            u = ds_sub['U10']
            v = ds_sub['V10']
        else:
            u = ds_sub.sel(height=height)['U']
            v = ds_sub.sel(height=height)['V']

        hours = np.arange(1, 24)

        divergence = np.empty(shape=(len(hours), 27))
        divergence[:] = np.nan

        for hour in hours:
            if hour < 5:
                u_hour = u[u.time.dt.hour == hour]
                v_hour = v[v.time.dt.hour == hour]

                # calculate hourly average
                uhm = u_hour.mean('time')
                vhm = v_hour.mean('time')

                # calculate divergence
                div = mc.divergence(uhm, vhm) * 10**4  # surface divergence, *10^-4 1/s

                # get values along specified line
                wrf_projection = WrfProj(map_proj=1, dx=3000, dy=3000, truelat1=38.8, truelat2=38.8,
                                         moad_cen_lat=38.75293, stand_lon=-74.5)
                ll_point = CoordPair(lat=34.321144, lon=-79.763733)
                div_line = interpline(div, start_point=point_start, end_point=point_end, projection=wrf_projection,
                                      ll_point=ll_point, latlon=True)

                # get the coordinates for the line that is returned
                if hour == 1:
                    lats_interp = np.array([])
                    lons_interp = np.array([])
                    for i, value in enumerate(div_line.xy_loc.values):
                        lats_interp = np.append(lats_interp, value.lat)
                        lons_interp = np.append(lons_interp, value.lon)

                divergence[hour - 1] = div_line

            # # set up map
            # lccproj = ccrs.LambertConformal(central_longitude=-74.5, central_latitude=38.8)
            # fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection=lccproj))
            # pf.add_map_features(ax, [-75, -73.6, 38.7, 39.9])
            # la_polygon, pa_polygon = cf.extract_lease_area_outlines()
            # pf.add_lease_area_polygon(ax, la_polygon, '#737373')  # lease areas
            # ax.plot(lons_interp, lats_interp, transform=ccrs.PlateCarree())
            #
            # sname = f'hovmoller_map.png'
            # plt.savefig(os.path.join(save_dir, sname), dpi=200)
            # plt.close()

        fig, ax = plt.subplots(figsize=(8, 8))

        # initialize keyword arguments for plotting
        kwargs = dict()
        # kwargs['levels'] = [-.0004, -.00035, -.0003, -.00025, -.0002, -.00015, -.0001, -.00005, .00005,
        #                    .0001, .00015, .0002, .00025, .0003, .00035, .0004]
        # kwargs['cbar_ticks'] = [-.0004, -.0003, -.0002, -.0001, .0001, .0002, .0003, .0004]
        kwargs['levels'] = [-2.5, -2.25, -2, -1.75, -1.5, -1.25, -1, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75,
                            1, 1.25, 1.5, 1.75, 2, 2.25, 2.5]
        kwargs['cbar_ticks'] = [-2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5]
        kwargs['extend'] = 'both'

        kwargs['ttl'] = 'Hourly Averaged Seabreeze Days\nDivergence Along Cross-Section: {}m\n{} to {}'.format(height, sb_t0str, sb_t1str)
        kwargs['clab'] = 'Divergence x $10^{-4}$ (1/s)'
        kwargs['shift_subplot_right'] = 0.85
        kwargs['xlab'] = 'Longitude'
        kwargs['ylab'] = 'Hour'
        kwargs['yticks'] = [5, 10, 15, 20]
        pf.plot_contourf(fig, ax, lons_interp, hours, divergence, plt.get_cmap('RdBu_r'), **kwargs)

        sname = 'divergence_hovmoller_{}.png'.format(height)
        plt.savefig(os.path.join(save_dir, sname), dpi=200)
        plt.close()


def main(sDir, sdate, edate, intvl):
    wrf = 'http://tds.marine.rutgers.edu/thredds/dodsC/cool/ruwrf/wrf_4_1_3km_processed/WRF_4.1_3km_Processed_Dataset_Best'

    savedir = os.path.join(sDir, '{}_{}-{}'.format(intvl, sdate.strftime('%Y%m%d'), edate.strftime('%Y%m%d')))
    os.makedirs(savedir, exist_ok=True)

    ds = xr.open_dataset(wrf)
    ds = ds.sel(time=slice(sdate, edate))
    dst0 = pd.to_datetime(ds.time.values[0]).strftime('%Y-%m-%d')
    dst1 = pd.to_datetime(ds.time.values[-1]).strftime('%Y-%m-%d')
    df = pd.read_csv(os.path.join(sDir, 'radar_seabreezes_2020.csv'))
    df = df[df['Seabreeze'] == 'y']
    sb_dates = np.array(pd.to_datetime(df['Date']))
    sb_datetimes = [pd.date_range(pd.to_datetime(x), pd.to_datetime(x) + dt.timedelta(hours=23), freq='H') for x in sb_dates]
    sb_datetimes = pd.to_datetime(sorted([inner for outer in sb_datetimes for inner in outer]))

    # grab the WRF data for the seabreeze dates
    ds = ds.sel(time=sb_datetimes)
    # ds = ds.sel(time=slice(dt.datetime(2020, 6, 1, 0, 0), dt.datetime(2020, 6, 1, 5, 0)))  # for debugging

    # define arguments for plotting function
    kwargs = dict()
    kwargs['sb_t0str'] = dst0
    kwargs['sb_t1str'] = dst1

    plot_divergence_hovmoller(ds, savedir, intvl, **kwargs)


if __name__ == '__main__':
    # save_directory = '/Users/garzio/Documents/rucool/bpu/wrf/windspeed_averages'
    save_directory = '/www/home/lgarzio/public_html/bpu/windspeed_averages'  # on server
    start_date = dt.datetime(2020, 6, 1, 0, 0)  # dt.datetime(2019, 9, 1, 0, 0)
    end_date = dt.datetime(2020, 7, 31, 23, 0)  # dt.datetime(2020, 9, 1, 0, 0)
    interval = 'divergence_hourly_avg_hovmoller'
    main(save_directory, start_date, end_date, interval)