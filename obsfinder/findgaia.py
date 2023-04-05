#!/usr/bin/env python3

from xml.dom.minidom import parseString
import http.client as httplib
import urllib.parse as urllib
import pandas as pd
import numpy as np
import argparse
import time
import csv
import sys

class Findgaia():
    """
    This class contains tools to query the Gaia archive and retreive data from Gaia DR3.
    """
    
    def __init__(self, lvalue: float, bvalue: float, path: str, psize: float, proxy: tuple[str, int] = None, verbose: int = 0) -> None:
        """
        Initialize the class

        Args:
            lvalue (float): 
                Square center value in longitude (in degree)
            bvalue (float): 
                Square center value in lattitude (in degree)
            psize (float): 
                Pixel size (in degree)
            path (str): 
                Working directory
            proxy (tuple[str, int], optional):
                Proxy to use, if needed. Tuple containing the adresse of the proxy and the port to use. Default to None.
            verbose (int, optional): 
                Toggle verbose (1 or 0). Default to 0.
        """

        self.host = "gea.esac.esa.int"
        self.port = 443
        self.pathinfo = "/tap-server/tap/async"
        self.query = "SELECT source_id, phot_g_n_obs, phot_g_mean_mag, phot_g_mean_flux, phot_g_mean_flux_error,\
            phot_bp_n_obs, phot_bp_mean_mag, phot_bp_mean_flux, phot_bp_mean_flux_error, \
            phot_rp_n_obs, phot_rp_mean_mag, phot_rp_mean_flux, phot_rp_mean_flux_error, \
            l, b, parallax, parallax_error \
            FROM gaiadr3.gaia_source \
            WHERE "
        self.lvalue = lvalue
        self.bvalue = bvalue
        self.path = path
        self.psize = psize / 60
        self.proxy = proxy
        self.verbose = verbose

        self.catalog = ""

    def query_obs(self, lmin, lmax) -> pd.DataFrame:
        """
        Make a query to gaia archive to retreive gaia flux in G, B and R bands
        and their uncertainty, as well as the longitude and lattitude of each
        source.
        The returned data correspond to a square of size psize centered on the 
        coordinates (lvalue, bvalue).

        Args:
            lvalue (float): 
                Square center value in longitude (in degree)
            bvalue (float): 
                Square center value in lattitude (in degree)
            psize (float): 
                Pixel size (in degree)
            path (str): 
                Working directory
            proxy (tuple[str, int], optional):
                Proxy to use, if needed. Tuple containing the adresse of the proxy and the port to use. Default to None.
            verbose (int, optional): 
                Toggle verbose (1 or 0). Default to 0.

        Returns:
            pd.DataFrame: Dataframe containing the data
        """

        zone = f"gaiadr3.gaia_source.l BETWEEN {lmin} AND {lmax} AND \
                 gaiadr3.gaia_source.b BETWEEN {self.bvalue - self.psize} AND {self.bvalue + self.psize}"
            
        query = self.query + zone

        print(query)

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
        data_temp = data['source_id'].astype(int)
        data = data.astype(float)
        data['source_id'] = data_temp
        del data_temp

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
        data = data[~np.isnan(data).any(axis=1)]

        return data

    def save_obs(self, data: pd.DataFrame) -> None:
        """
        Save the observationnal data

        Args:
            data (pd.DataFrame): Data to save
        """

        # Name of the output file
        filename = '{}/observations_gaia_{:.6f}_{:.6f}.cat_{:.6f}.csv' \
                .format(self.path, self.bvalue, self.lvalue, self.psize)
        # Name of the output file
        
        data.drop(columns=['source_id'], inplace=True,)
        data.to_csv(filename, float_format = '%.4f', index=False)

        # Save data
        #np.savetxt(filename, data, fmt='%-10.4f')

        if self.verbose:
            print('Done!')
            print(f"Nb sources: {len(data)}")
            print(f"Gaia obs saved in {filename}")

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
    
    def get_obs(self) -> None:
        """
        Complete function to get the observationnal data
        """

        # If zone definition is not in [0, 360]
        if self.lvalue - self.psize < 0:
            if self.verbose:
                print("Query split in two parts")

            data_part1 = self.query_obs(360 + (self.lvalue - self.psize), 360)
            data_part2 = self.query_obs(0, self.lvalue + self.psize)

            data = pd.concat([data_part1, data_part2], ignore_index=True)

        # If zone definition is in the range [0, 360]
        else:
            data = self.query_obs(self.lvalue - self.psize, self.lvalue + self.psize)

        # Clean observations
        data = self.clean_obs(data)

        # Save observations
        self.save_obs(data)
        

def main() -> int:
    """
    Main function used when the script is called from a command line
    """
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', type = float, required = True, help = "Square center value in Galactic longitude (deg)")
    parser.add_argument('-b', type = float, required = True, help = "Square center value in Galactic lattitude (deg)")
    parser.add_argument('-p', type = float, required = False, help = "Pixel size (arcminute)", default = 5)
    parser.add_argument('-v', type = int, required = False, help = "Verbose", default = 1)
    parser.add_argument('-d', type = str, required = True, help = "Working directory")

    # Get arguments value
    args = parser.parse_args()
    long = args.l
    latt = args.b
    psize = args.p
    verbose = args.v
    path = args.d

    fgaia = Findgaia(long, latt, path, psize, proxy = ("11.0.0.254",3142), verbose = verbose)
    fgaia.get_obs()

    return 0

if __name__ == '__main__':
    sys.exit(main())
