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

class Find2mass():
    """
    This class contains tools to query caltech server and retreive 2mass data.
    """
    
    def __init__(self, lvalue: float, bvalue: float, path: str, psize: float, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None) -> None:
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
            name (str, optional):
                Name of the catalog. Default name is 'observations_2mass_{bvalue}_{lvalue}.cat_{psize}.csv'
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

    def query_obs(self, lmin: float, lmax: float) -> pd.DataFrame:
        """
        Make a query to caltech server to retreive 2mas J, H an K bands,
        their uncertainty, as well as the longitude and lattitude of each
        source.
        The returned data correspond to a square of size psize centered on the 
        coordinates (lvalue, bvalue).

        Args:
            lmin (float): 
                Square left value in longitude (in degree)
            lmax (float):
                Square right value in longitude (in degree)

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
            time.sleep(1.0)

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

        # Remove rows containing at least one nan value
        data = data[~np.isnan(data).any(axis=1)]

        # Remove row with a magnitude error greater than 5
        data = data[(data['j_msigcom'] < 5.) | (data['h_msigcom'] < 5.) | (data['k_msigcom'] < 5.)]

        return data

    def save_obs(self, data: pd.DataFrame) -> None:
        """
        Save the observationnal data

        Args:
            data (pd.DataFrame): Data to save
        """

        if self.filename == None:
            # Name of the output file
            self.filename = 'observations_2mass_{:.6f}_{:.6f}.cat_{:.6f}.csv' \
                    .format(self.bvalue, self.lvalue, self.psize)
            
        data.to_csv(f"{self.path}/{self.filename}", float_format = '%.4f', index=False)

        # Save data
        #np.savetxt(filename, data, fmt='%-10.4f')

        if self.verbose:
            print('Done!')
            print(f"Nb sources: {len(data)}")
            print(f"2mass obs saved in {self.path}{self.filename}")

    
    def get_obs(self) -> None:
        """
        Complete function to get the observationnal data
        """

        # If zone definition is not in [0, 360]
        if self.lvalue - (self.psize/2) < 0:
            if self.verbose:
                print("Query split in two parts")

            data_part1 = self.query_obs(360 + (self.lvalue - self.psize/2), 360)
            data_part2 = self.query_obs(0, self.lvalue + self.psize/2)

            data = pd.concat([data_part1, data_part2], ignore_index=True)

        # If zone definition is in the range [0, 360]
        else:
            data = self.query_obs(self.lvalue - self.psize/2, self.lvalue + self.psize/2)

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
    parser.add_argument('-n', type = str, required = False, help = "Name of the output file")

    # Get arguments value
    args = parser.parse_args()
    long = args.l
    latt = args.b
    psize = args.p
    verbose = args.v
    path = args.d
    name = args.n

    ftmass = Find2mass(long, latt, path, psize, proxy = ("11.0.0.254",3142), verbose = verbose, name = name)
    ftmass.get_obs()

    return 0

if __name__ == '__main__':
    sys.exit(main())
