#!/usr/bin/env python3

from xml.dom.minidom import parseString
import http.client as httplib
import urllib.parse as urllib
from zero_point import zpt
import pandas as pd
import numpy as np
import argparse
import warnings
import pathlib
import h5py
import time
import csv
import sys

class Findgaia():
    """
    This class contains tools to query the Gaia archive and retreive data from Gaia DR3 and 2MASS cross match.
    """
    
    def __init__(self, lvalue: float, bvalue: float, psize: float, path: str = None, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None, pi: int = 1) -> None:
        """
        Initialize the class

        Args:
            lvalue (float): 
                Square center value in Galactic longitude (in degree)
            bvalue (float): 
                Square center value in Galactic latitude (in degree)
            psize (float): 
                Pixel size (in arcmin)
            path (str): 
                Working directory
            proxy (tuple[str, int], optional):
                Proxy to use, if needed. Tuple containing the adresse of the proxy and the port to use. Default to None.
            verbose (int, optional): 
                Toggle verbose (1 or 0). Default to 0.
            name (str, optional):
                Name of the catalog. Default name is 'observations_gaia_{bvalue}_{lvalue}_{psize}.csv'
            pi (int, optional):
                Apply offset correction to the parallaxes. Default to 1, parallaxes are corrected.
        """

        self.host = "gea.esac.esa.int"
        self.port = 443
        self.pathinfo = "/tap-server/tap/async"
        self.query = "SELECT gaia.source_id, gaia.phot_bp_mean_mag, gaia.phot_bp_mean_flux_over_error, \
                gaia.phot_g_mean_mag, gaia.phot_g_mean_flux_over_error, gaia.phot_rp_mean_mag, \
                gaia.phot_rp_mean_flux_over_error, gaia.parallax, gaia.parallax_error, gaia.l, gaia.b, \
                gaia.nu_eff_used_in_astrometry, gaia.pseudocolour, gaia.ecl_lat, gaia.astrometric_params_solved, \
                tmass.j_m, tmass.j_msigcom, tmass.h_m, tmass.h_msigcom, tmass.ks_m , tmass.ks_msigcom \
                FROM gaiadr3.gaia_source AS gaia \
                JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xmatch USING (source_id) \
                JOIN gaiadr3.tmass_psc_xsc_join AS xjoin USING (clean_tmass_psc_xsc_oid) \
                JOIN gaiadr1.tmass_original_valid AS tmass ON \
                xjoin.original_psc_source_id = tmass.designation \
                WHERE \
                tmass.ext_key IS NULL AND "
        self.lvalue = lvalue
        self.bvalue = bvalue
        self.path = path
        self.psize = psize / 60
        self.proxy = proxy
        self.verbose = verbose
        self.filename = name
        self.pi = pi

        if not self.verbose:
            warnings.filterwarnings("ignore")

        if self.path == None:
            self.path = str(pathlib.Path().resolve())

    def query_obs(self, lmin: float, lmax: float) -> pd.DataFrame:
        """
        Make a query to gaia archive to retreive gaia flux in G, B and R bands
        and their uncertainty, as well as the longitude and lattitude of each
        source.
        The returned data correspond to a square of size psize centered on the 
        coordinates (lvalue, bvalue).

        Args:
            lmin (float): 
                Lowest value in longitude (in degree)
            lmax (float):
                Highest value in longitude (in degree)

        Returns:
            pd.DataFrame: Dataframe containing the data
        """

        zone = f"gaia.l BETWEEN {lmin} AND {lmax} \
                 AND gaia.b BETWEEN {self.bvalue - self.psize/2} AND {self.bvalue + self.psize/2}"
            
        query = self.query + zone

        # Encode the query
        params = urllib.urlencode({\
            "REQUEST": "doQuery", \
            "LANG":    "ADQL", \
            "FORMAT":  "csv", \
            "PHASE":  "RUN", \
            "JOBNAME":  "Any name (optional)", \
            "JOBDESCRIPTION":  "Any description (optional)", \
            "QUERY":   f"{query}"
            })

        headers = {\
            "Content-type": "application/x-www-form-urlencoded", \
            "Accept":       "text/plain" \
            }

        # Use proxy if needed
        if self.proxy != None:
            connection=httplib.HTTPSConnection(self.proxy[0], self.proxy[1])
            connection.set_tunnel(self.host, self.port)
        else:
            connection=httplib.HTTPSConnection(self.host, self.port)

        # Send the query
        connection.request("POST", self.pathinfo, params, headers)

        #Status
        response = connection.getresponse()
        if self.verbose:
            print ("Status: " +str(response.status), "Reason: " + str(response.reason))

        #Server job location (URL)
        location = response.getheader("location")
        if self.verbose:
            print ("Location: " + location)

        #Jobid
        jobid = location[location.rfind('/')+1:]
        if self.verbose:
            print ("Job id: " + jobid)

        connection.close()


        # Check job status, wait until finished
        while True:
            # Use proxy if needed
            if self.proxy != None:
                connection=httplib.HTTPSConnection(self.proxy[0], self.proxy[1])
                connection.set_tunnel(self.host, self.port)
            else:
                connection=httplib.HTTPSConnection(self.host, self.port)

            connection.request("GET", self.pathinfo + "/" + jobid)
            response = connection.getresponse()
            data = response.read()
            dom = parseString(data)
            phaseElement = dom.getElementsByTagName('uws:phase')[0]
            phaseValueElement = phaseElement.firstChild
            phase = phaseValueElement.toxml()
            if self.verbose:
                print ("Status: " + phase)
            #Check finished
            if phase == 'COMPLETED': break

            if phase == 'ERROR':
                print("Critical failure: Error during the query")
                print(data)
                exit()

            #wait and repeat
            time.sleep(0.2)

        connection.close()

        # Get results
        if self.verbose:
            print("Retrieving data...")

        # Use proxy if needed
        if self.proxy != None:
            connection=httplib.HTTPSConnection(self.proxy[0], self.proxy[1])
            connection.set_tunnel(self.host, self.port)
        else:
            connection=httplib.HTTPSConnection(self.host, self.port)

        connection.request("GET", self.pathinfo + "/" + jobid + "/results/result")
        response = connection.getresponse()

        data = response.read().decode('iso-8859-1')
        data = data.split()
        data = list((csv.reader(data, delimiter=',')))
        data = pd.DataFrame(data[1:], columns = data[0])
        data = data.replace(r'^\s*$', np.nan, regex=True)
        # data_temp = data['source_id'].astype(int)
        data = data.astype(float)
        # data['source_id'] = data_temp
        # del data_temp

        connection.close()

        return data
    
    def clean_obs(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Clean the observationnal data

        Args:
            data (pd.DataFrame): Data to clean

        Returns:
            pd.DataFrame: Cleaned data
        """

        if self.verbose:
            print('Cleaning data...')

        # Make maglimList bolean list
        # maglim_list = self.maglimList(data, 5, 90)

        # Convert job result in numpy array
        # data1 = np.transpose(np.array([data['phot_g_n_obs'][maglim_list], data['phot_g_mean_mag'][maglim_list], data['phot_g_mean_flux'][maglim_list], data['phot_g_mean_flux_error'][maglim_list], \
        #                 data['phot_bp_n_obs'][maglim_list], data['phot_bp_mean_mag'][maglim_list], data['phot_bp_mean_flux'][maglim_list], data['phot_bp_mean_flux_error'][maglim_list], \
        #                 data['phot_bp_n_obs'][maglim_list], data['phot_rp_mean_mag'][maglim_list], data['phot_rp_mean_flux'][maglim_list], data['phot_rp_mean_flux_error'][maglim_list], \
        #                 data['l'][maglim_list], data['b'][maglim_list], data['parallax'][maglim_list]]))


        # Remove rows containing at least one nan value
        data = data[data["phot_g_mean_mag"].notna() & data["phot_bp_mean_mag"].notna() & data["phot_rp_mean_mag"].notna() & data["parallax"].notna() & \
                    data["phot_bp_mean_flux_over_error"].notna() & data["phot_g_mean_flux_over_error"].notna() & data["phot_rp_mean_flux_over_error"].notna() & \
                    data["parallax_error"].notna() & \
                    data["ks_m"].notna() & data["j_m"].notna() & data["h_m"].notna() & data["ks_msigcom"].notna() & data["j_msigcom"].notna() & data["h_msigcom"].notna()]

        # data = data[(data['phot_g_mean_mag'] > 8) & (data['phot_g_mean_mag'] < 17) & (data['phot_bp_mean_mag'] > 8) & (data['phot_bp_mean_mag'] < 17) & (data['phot_rp_mean_mag'] > 8) & (data['phot_rp_mean_mag'] < 17)]

        return data

    def save_obs(self, data: pd.DataFrame) -> None:
        """
        Save the observationnal data

        Args:
            data (pd.DataFrame): Data to save
        """

        if self.filename == None:
            # Name of the output file
            self.filename = f"{self.path}/observations_gaia2mass_{self.bvalue:.6f}_{self.lvalue:.6f}_{self.psize:.6f}.hdf5"
        else:
            self.filename = f"{self.path}/{self.filename}"

        if self.filename.split('.')[-1] == 'hdf5':
            self.write_hdf5(data)
        else:
            data = data[['phot_bp_mean_mag', 'phot_bp_mean_mag_error', 'phot_g_mean_mag', 'phot_g_mean_mag_error', 'phot_rp_mean_mag', 'phot_rp_mean_mag_error', 'parallax', 'parallax_error',
                         'j_m', 'j_msigcom', 'h_m', 'h_msigcom', 'ks_m', 'ks_msigcom', 'l', 'b']]
            np.savetxt(self.filename, data, header="BP,BP_err,G,G_err,RP,RP_err,parallax,parallax_err,J,J_err,H,H_err,K,K_err,l,b", delimiter=',', comments='')

        if self.verbose:
            print('Done!')
            print(f"Nb sources: {len(data)}")
        
        print(f"Gaia obs saved in {self.filename}")

    def write_hdf5(self, data: pd.DataFrame) -> None:
        with h5py.File(self.filename, 'w') as f:
            f.create_dataset('BP', data=data['phot_bp_mean_mag'], dtype = float)
            f.create_dataset('BP_err', data=data['phot_bp_mean_mag_error'], dtype = float)
            f.create_dataset('G', data=data['phot_g_mean_mag'], dtype = float)
            f.create_dataset('G_err', data=data['phot_g_mean_mag_error'], dtype = float)
            f.create_dataset('RP', data=data['phot_rp_mean_mag'], dtype = float)
            f.create_dataset('RP_err', data=data['phot_rp_mean_mag_error'], dtype = float)
            f.create_dataset('parallax', data=data['parallax'], dtype = float)
            f.create_dataset('parallax_err', data=data['parallax_error'], dtype = float)
            f.create_dataset('J', data = data['j_m'], dtype = float)
            f.create_dataset('J_err', data = data['j_msigcom'], dtype = float)
            f.create_dataset('H', data = data['h_m'], dtype = float)
            f.create_dataset('H_err', data = data['h_msigcom'], dtype = float)
            f.create_dataset('K', data = data['ks_m'], dtype = float)
            f.create_dataset('K_err', data = data['ks_msigcom'])
            f.create_dataset('l', data=data['l'], dtype = float)
            f.create_dataset('b', data=data['b'], dtype = float)

    def maglimList(data: np.ndarray, level: int, percentile: float) -> np.ndarray:
        """
        Return a bolean list to remove source that do not satisfy the limit of
        magnitude define by the gaia collaboration for gaia rdr3.

        Args:
            data (np.ndarray):
                Array contaning at least several source id and their magnitude in the G band
            level (int):
                Healpix level
            percentile (float):
                Percentile of the limit magnitude

        Returns:
            output (np.ndarray):
                Bolean array to use to select the data to keep
        """

        maglim = np.loadtxt('maglim.dat.gz')
        source_id = data['source_id']
        healpix_idx = source_id // (2**35 * 4**(12-level))

        output = np.zeros(np.shape(source_id), dtype=np.float16)

        output = data['phot_g_mean_mag'] < maglim[healpix_idx, percentile + 1]

        return output
    
    def mag_uncertainty(self, flux_over_error: float) -> float:
        """
        Compute the uncertainty on the magnitude given the flux, its uncertainty and the zero point uncertainty.
        Args:
            flux_over_error (float): flux over its error

        Returns:
            float: uncertainty on the magnitude
        """

        # return np.sqrt((-2.5 / np.log(10) * flux_err / flux)**2 + zero_point_err**2)
        return (2.5/np.log(10)) * (1/flux_over_error)
    
    def attach_mag_uncertainty(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Attach the uncertainty on the magnitudes to the observationnal data

        Args:
            data (pd.DataFrame): Data to attach the uncertainty on the magnitudes for each band
        
        Returns:
            pd.DataFrame: Data with the uncertainty on the magnitudes for each band
        """

        if self.verbose:
            print("Attaching magnitude uncertainty to each band...")

        # Compute the uncertainty on the magnitude
        data['phot_bp_mean_flux_over_error'] = self.mag_uncertainty(data['phot_bp_mean_flux_over_error'])
        data['phot_g_mean_flux_over_error'] = self.mag_uncertainty(data['phot_g_mean_flux_over_error'])
        data['phot_rp_mean_flux_over_error'] = self.mag_uncertainty(data['phot_rp_mean_flux_over_error'])

        data.rename(columns={'phot_bp_mean_flux_over_error': 'phot_bp_mean_mag_error', \
                            'phot_g_mean_flux_over_error': 'phot_g_mean_mag_error', \
                            'phot_rp_mean_flux_over_error': 'phot_rp_mean_mag_error'}, inplace=True)

        return data
    
    def correct_parallaxes(self, data: pd.DataFrame) -> pd.DataFrame:

        zpt.load_tables()
        zero_point = zpt.get_zpt(data["phot_g_mean_mag"], data["nu_eff_used_in_astrometry"],
                   data["pseudocolour"],data["ecl_lat"],
                   data["astrometric_params_solved"], _warnings=True)

        data["parallax"] -= zero_point

        return data
        
    def get_obs(self) -> None:
        """
        Complete function to get the observationnal data
        """

        # If longitude zone definition contains negative and positive longitudes
        if self.lvalue - self.psize/2 < 0 and self.lvalue + self.psize/2 > 0:
            if self.verbose:
                print("Query split in two parts")

            data_part1 = self.query_obs(360 + self.lvalue - self.psize/2, 360)
            data_part2 = self.query_obs(0, self.lvalue + self.psize/2)

            data = pd.concat([data_part1, data_part2], ignore_index=True)
        
        # If longitude zone definition is entirely inferior to 0
        elif self.lvalue - self.psize/2 < 0 and self.lvalue + self.psize/2 <= 0:
            if self.verbose:
                print("Negative longitude range, aborting")
                exit()
        

        # If zone definition is in the range [0, 360]
        else:
            data = self.query_obs(self.lvalue - self.psize/2, self.lvalue + self.psize/2)

        # Clean observations
        data = self.clean_obs(data)

        # Attach magnitudes uncertainties
        data = self.attach_mag_uncertainty(data)

        if self.pi:
            # Correct parallaxes offset
            data = self.correct_parallaxes(data)

        # Save observations
        self.save_obs(data)
        

def main() -> int:
    """
    Main function used when the script is called from a command line
    """
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', type = float, required = True, help = "Square center value in Galactic longitude (deg)")
    parser.add_argument('-b', type = float, required = True, help = "Square center value in Galactic latitude (deg)")
    parser.add_argument('-p', type = float, required = False, help = "Pixel size (arcminute)", default = 5)
    parser.add_argument('-v', type = int, required = False, help = "Verbose", default = 0)
    parser.add_argument('-d', type = str, required = False, help = "Working directory", default = None)
    parser.add_argument('-n', type = str, required = False, help = "Name of the output file", default = None)
    parser.add_argument('-proxy', type = str, required = False, help = "Proxy to use host:port", default = None)
    parser.add_argument('-pi', type = int, required=False, help = "Apply offset correction to the parallaxes", default = 1)

    # Get arguments value
    args = parser.parse_args()
    long = args.l
    latt = args.b
    psize = args.p
    verbose = args.v
    path = args.d
    name = args.n
    pi = args.pi

    if args.proxy != None:
        proxy = (args.proxy.split(':')[0], int(args.proxy.split(':')[1]))
    else:
        proxy = None

    fgaia = Findgaia(lvalue = long, bvalue = latt, path = path, psize = psize, proxy = proxy, verbose = verbose, name = name, pi = pi)
    fgaia.get_obs()

    return 0

if __name__ == '__main__':
    sys.exit(main())
