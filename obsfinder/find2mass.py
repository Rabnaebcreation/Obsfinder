#!/usr/bin/env python3

"""
Warning !
This script cannot do query for zones where longitude is negative !
Example:
for find2mass.py -l 0 -b 0 -p 60 -p path, le longitude range will be between 0 and 1 instead of 359 and 0
"""
from xml.dom.minidom import parseString
import http.client as httplib
import urllib.parse as urllib
import pandas as pd
import numpy as np
import argparse
import time
import csv

def get_obs(lvalue: float, bvalue: float, psize: float, path: str, proxy: tuple[str, int] = None, verbose: int = 1):
    """
    Make a query to gaia archive to retreive 2MASS flux in J, H and K bands
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
            Working directory and output file name
        proxy (tuple[str, int], optional):
            Proxy to use, if needed. Tuple containing the adresse of the proxy and the port to use. Default to None.
        verbose (int, optional): 
            Toggle verbose (1 or 0). Default to 1.
    """

    # Connection informations
    host = "irsa.ipac.caltech.edu"
    port = 443
    pathinfo = "/TAP/async"

    # Define the query
    query = f"SELECT j_m, j_msigcom, h_m, h_msigcom, k_m , k_msigcom, glon, glat \
             FROM fp_psc \
             WHERE \
             glon BETWEEN {lvalue - psize} AND {lvalue + psize} \
             AND glat BETWEEN {bvalue - psize} AND {bvalue + psize}"

    # Encode the query  
    params = urllib.urlencode({
        "QUERY":   f"{query}", \
        "FORMAT":  "csv", \
        "PHASE":  "RUN", \
        })

    # Use proxy if needed
    if proxy != None:
        connection=httplib.HTTPSConnection(proxy[0], proxy[1])
        connection.set_tunnel(host, port)
    else:
        connection=httplib.HTTPSConnection(host, port)

    # Send the query
    connection.request("POST",pathinfo+"?",params)

    # Get status
    response = connection.getresponse()

    if verbose:
        print ("Status: " +str(response.status), "Reason: " + str(response.reason))

    # Get server job location (URL)
    location = response.getheader("location")
    if verbose:
        print ("Location: " + location)

    # Get Jobid
    jobid = location[location.rfind('/')+1:]
    if verbose:
        print ("Job id: " + jobid)

    connection.close()


    # Check job status, wait until finished
    while True:
        # Use proxy if needed
        if proxy != None:
            connection=httplib.HTTPSConnection(proxy[0], proxy[1])
            connection.set_tunnel(host, port)
        else:
            connection=httplib.HTTPSConnection(host, port)

        connection.request("GET",pathinfo+"/"+jobid)
        response = connection.getresponse()
        data = response.read()
        dom = parseString(data)
        phaseElement = dom.getElementsByTagName('uws:phase')[0]
        phaseValueElement = phaseElement.firstChild
        phase = phaseValueElement.toxml()
        if verbose:
            print ("Status: " + phase)
        # Check finished
        if phase == 'COMPLETED': break

        if phase == 'ERROR':
            print("Critical failure: Error during the query")
            exit()

        # Wait and repeat
        time.sleep(0.2)

    connection.close()

    # Get results
    if verbose:
        print("Retrieving data...")

    # Use proxy if needed
    if proxy != None:
        connection=httplib.HTTPSConnection(proxy[0], proxy[1])
        connection.set_tunnel(host, port)
    else:
        connection=httplib.HTTPSConnection(host, port)
        
    connection.request("GET",pathinfo+"/"+jobid+"/results/result")
    response = connection.getresponse()

    data = response.read().decode('iso-8859-1')
    data = data.split()
    data = list((csv.reader(data, delimiter=',')))
    data = pd.DataFrame(data[1:], columns = data[0])
    data = data.replace(r'^\s*$', np.nan, regex=True)
    data = data.astype(float)

    connection.close()

    # Remove rows containing at least one nan value
    data = data[~np.isnan(data).any(axis=1)]

    # Remove row with a magnitude error greater than 5
    data = data[(data['j_msigcom'] < 5.) | (data['h_msigcom'] < 5.) | (data['k_msigcom'] < 5.)]

    # Name of the output file
    # filename = '{}/observations_2mass_{:.6f}_{:.6f}.cat_{:.6f}.bz2' \
    #         .format(path, bvalue, lvalue, psize)
    
    # Save data
    #np.savetxt(path, data, fmt='%-10.4f')
    data.to_csv(path, float_format = '%.4f', index=False)
    if verbose:
        print('Done!')
        print(f"Nb sources: {len(data)}")
        print(f"2MASS obs saved in {path}")


if __name__ == '__main__':
    
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', type = float, required = True, help = "Square center value in Galactic longitude (deg)")
    parser.add_argument('-b', type = float, required = True, help = "Square center value in Galactic lattitude (deg)")
    parser.add_argument('-p', type = float, required = False, help = "Pixel size (arcminute)", default = 5)
    parser.add_argument('-v', type = int, required = False, help = "Verbose", default = 1)
    parser.add_argument('-d', type = str, required = True, help = "Working directory and output file name")

    # Get arguments value
    args = parser.parse_args()
    long = args.l
    latt = args.b
    psize = args.p
    verbose = args.v
    path = args.d

    # Arcminute to degree
    psize /= 60   

    get_obs(long, latt, psize, path, proxy = ("11.0.0.254",3142), verbose = verbose)
