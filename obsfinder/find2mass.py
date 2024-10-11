#!/usr/bin/env python3

from xml.dom.minidom import parseString
import http.client as httplib
import urllib.parse as urllib
import pandas as pd
import numpy as np
import argparse
import pathlib
import h5py
import time
import csv
import sys

class Find2mass():
    """
    This class contains tools to query caltech server and retreive 2mass data.
    """
    
    def __init__(self, lvalue: float, bvalue: float, psize: float, path: str = None, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None) -> None:
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
                Name of the catalog. Default name is 'observations_2mass_{bvalue}_{lvalue}_{psize}'
        """

        self.host = "irsa.ipac.caltech.edu"
        self.port = 443
        self.pathinfo = "/TAP/async"
        self.query = "SELECT j_m, j_msigcom, h_m, h_msigcom, k_m , k_msigcom, glon, glat \
             FROM fp_psc \
             WHERE "
        self.lvalue = lvalue
        self.bvalue = bvalue
        self.path = path
        self.psize = psize / 60
        self.proxy = proxy
        self.verbose = verbose
        self.filename = name

        if self.path == None:
            self.path = str(pathlib.Path().resolve())

    def query_obs(self, lmin: float, lmax: float) -> pd.DataFrame:
        """
        Make a query to caltech server to retreive 2mas J, H an K bands,
        their uncertainty, as well as the longitude and lattitude of each
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

        zone = f"glon BETWEEN {lmin} AND {lmax} \
                 AND glat BETWEEN {self.bvalue - self.psize/2} AND {self.bvalue + self.psize/2}"
            
        query = self.query + zone

        # Encode the query
        params = urllib.urlencode({
        "QUERY":   f"{query}", \
        "FORMAT":  "csv", \
        "PHASE":  "RUN", \
        })

        # Use proxy if needed
        if self.proxy != None:
            connection=httplib.HTTPSConnection(self.proxy[0], self.proxy[1])
            connection.set_tunnel(self.host, self.port)
        else:
            connection=httplib.HTTPSConnection(self.host, self.port)

        # Send the query
        connection.request("POST", self.pathinfo + "?", params)

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
        data = data.astype(float)

        connection.close()

        return data

    def save_obs(self, data: pd.DataFrame) -> None:
        """
        Save the observationnal data

        Args:
            data (pd.DataFrame): Data to save
        """

        if self.filename == None:
            # Name of the output file
            self.filename = f"{self.path}/observations_2mass_{self.bvalue:.6f}_{self.lvalue:.6f}_{self.psize:.6f}.hdf5"
        else:
            self.filename = f"{self.path}/{self.filename}"

        if self.filename.split('.')[-1] == 'hdf5':
            self.write_hdf5(data)
        else:
            np.savetxt(self.filename, data, header="J,J_err,H,H_err,K,K_err,l,b", delimiter=',', comments='')

        if self.verbose:
            print('Done!')
            print(f"Nb sources: {len(data)}")

        print(f"2mass obs saved in {self.filename}")

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

        # Save observations
        self.save_obs(data)
        
    def write_hdf5(self, data: pd.DataFrame) -> None:
        with h5py.File(self.filename, 'w') as f:
            f.create_dataset('J', data = data['j_m'], dtype = float)
            f.create_dataset('J_err', data = data['j_msigcom'], dtype = float)
            f.create_dataset('H', data = data['h_m'], dtype = float)
            f.create_dataset('H_err', data = data['h_msigcom'], dtype = float)
            f.create_dataset('K', data = data['k_m'], dtype = float)
            f.create_dataset('K_err', data = data['k_msigcom'])
            f.create_dataset('l', data = data['glon'], dtype = float)
            f.create_dataset('b', data = data['glat'], dtype = float)

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

    # Get arguments value
    args = parser.parse_args()
    long = args.l
    latt = args.b
    psize = args.p
    verbose = args.v
    path = args.d
    name = args.n

    if args.proxy != None:
        proxy = (args.proxy.split(':')[0], int(args.proxy.split(':')[1]))
    else:
        proxy = None

    ftmass = Find2mass(lvalue = long, bvalue = latt, path = path, psize = psize, proxy = proxy, verbose = verbose, name = name)
    ftmass.get_obs()

    return 0

if __name__ == '__main__':
    sys.exit(main())
