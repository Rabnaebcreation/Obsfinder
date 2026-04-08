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

class FindSimbad():
    """
    This class contains tools to query Simbad and retreive some data given an object name.
    """
    
    def __init__(self, columns: str = "", path: str = None, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None) -> None:
        """
        Initialize the class

        Args:
            columns (str): 
                Single column or list of columns to retreive. Columns must be defined as ["column1", "column2", ...]
            path (str): 
                Working directory
            proxy (tuple[str, int], optional):
                Proxy to use, if needed. Tuple containing the adresse of the proxy and the port to use. Default to None.
            verbose (int, optional): 
                Toggle verbose (1 or 0). Default to 0.
            name (str, optional):
                Name of the catalog. Default name is 'observations_2mass_{bvalue}_{lvalue}_{psize}'
        """

        self.host = "simbad.u-strasbg.fr"
        self.port = 443
        self.pathinfo = "/simbad/sim-tap/async"

        base_columns = ["basic.OID", "ident.id", "ident.oidref", "ids.ids"]

        if type(columns) == list:
            # user_columns = ', '.join(columns)
            query_columns = ', '.join(base_columns + columns)
            self.query = f"""SELECT {query_columns} 
                            FROM basic 
                            LEFT OUTER JOIN ident ON ident.oidref = basic.oid 
                            LEFT OUTER JOIN ids ON ids.oidref = ident.oidref 
                            WHERE """
        else:
            query_columns = ", ".join(base_columns) + (", " + columns) * (columns != "")
            self.query = f"""SELECT {query_columns} 
                            FROM basic \
                            LEFT OUTER JOIN ident ON ident.oidref = basic.oid 
                            LEFT OUTER JOIN ids ON ids.oidref = ident.oidref 
                            WHERE """
    
        self.path = path
        self.proxy = proxy
        self.verbose = verbose
        self.filename = name

        if self.path == None:
            self.path = str(pathlib.Path().resolve())

    def query_obs(self, identifier: str) -> pd.DataFrame:
        """
        Make a query to simbad to retreive 2mas J, H an K bands,
        their uncertainty, as well as the longitude and lattitude of each
        source.
        The returned data correspond to a square of size psize centered on the 
        coordinates (lvalue, bvalue).

        Args:
            identifier (str): Object name to query, or list of object names to query. If list, object must be defined as ["object1", "object2", ...]

        Returns:
            pd.DataFrame: Dataframe containing the data
        """

        if type(identifier) == list:
            query = " OR ".join([f"ident.id = '{id}'" for id in identifier])
        else:
            query = f"ident.id = '{identifier}'"
            
        query = self.query + query

        # Encode the query
        params = urllib.urlencode({
        "QUERY":   f"{query}", \
        "LANG":   "ADQL", \
        "FORMAT":  "csv", \
        "PHASE":  "RUN", \
        "REQUEST": "doQuery"
        })

        # Use proxy if needed
        if self.proxy != None:
            connection=httplib.HTTPSConnection(self.proxy[0], self.proxy[1])
            connection.set_tunnel(self.host, self.port)
        else:
            connection=httplib.HTTPSConnection(self.host, self.port)

        headers = {\
            "Content-type": "application/x-www-form-urlencoded", \
            "Accept":       "text/plain" \
            }

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
            phaseElement = dom.getElementsByTagName('phase')[0]
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
            time.sleep(0.5)

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
        # data = data.astype(float)

        connection.close()

        return data
    
    def clean_obs(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Clean the be only keeping indent.id and Gaia DR3 source_id if it exists and user defined columns if set by the user and if they exists.

        Args:
            data (pd.DataFrame): Data to clean

        Returns:
            pd.DataFrame: Cleaned data
        """

        if self.verbose:
            print('Cleaning data...')

        # Keep only ident.id, ident.oidref and user defined columns if they exist
        columns_to_keep = [col for col in data.columns if col not in ["oid", "id", "oidref", "ids"]]
        id_data = data.get("id")

        
        cleaned_data = pd.DataFrame()
        cleaned_data['id'] = id_data
        
        # Extract Gaia DR3 IDs for all rows
        gaia_ids = data["ids"].apply(lambda x: next((item for item in str(x).split('|') if "GaiaDR3" in item), None))
        cleaned_data['GaiaDR3'] = gaia_ids
        
        # Add user-defined columns
        for col in columns_to_keep:
            if col in data.columns:
                cleaned_data[col] = data[col]

        return cleaned_data

    def save_obs(self, data: pd.DataFrame) -> None:
        """
        Save the observationnal data

        Args:
            data (pd.DataFrame): Data to save
        """

        if self.filename == None:
            # Name of the output file
            self.filename = f"{self.path}/simbad_output.hdf5"
        else:
            self.filename = f"{self.path}/{self.filename}"

        if self.filename.split('.')[-1] == 'hdf5':
            self.write_hdf5(data)
            # data.to_hdf(self.filename, key = 'data', mode = 'w')
        else:
            # np.savetxt(self.filename, data, header="J,J_err,H,H_err,K,K_err,l,b", delimiter=',', comments='')
            data.to_csv(self.filename, index = False)

        # print(data.columns)

        if self.verbose:
            print('Done!')
            print(f"Nb sources: {len(data)}")
        
    def write_hdf5(self, data: pd.DataFrame) -> None:
        """
        Write the data in an hdf5 file, with one dataset per column.

        Args:
            data (pd.DataFrame): Data to write
        """

        with h5py.File(self.filename, 'w') as f:
            for column in data.columns:
                series = data[column]

                if pd.api.types.is_string_dtype(series.dtype) or pd.api.types.is_object_dtype(series.dtype):
                    values = series.fillna("").astype(str).to_numpy()
                    f.create_dataset(column, data=values, dtype=h5py.string_dtype(encoding='utf-8'))
                else:
                    f.create_dataset(column, data=series.to_numpy())

    def get_obs(self, identifier) -> None:
        """
        Complete function to get the data from simbad

        Args:
            identifier (str): Object name to query, or list of object names to query. If list, object must be defined as ["object1", "object2", ...]
        """

        # Get data
        data = self.query_obs(identifier)

        # Clean data
        data = self.clean_obs(data)

        # Save observations
        self.save_obs(data)

    def get_obs_with_gaia(self, identifier, gaia_columns: list, gaia_condition: str = "", lite: bool = True) -> None:
        """
        Complete function to get the data from simbad and gaia

        Args:
            identifier (str): Object name to query, or list of object names to query. If list, object must be defined as ["object1", "object2", ...]
            gaia_columns (list): List of columns to retreive from gaia, in addition to the source_id column which is necessary for the merge with simbad data.
            gaia_condition (str): Condition to apply to the gaia query, in addition to the condition on the gaia source_id. 
        """

        from .findgaia import FindGaiaQuery

        # Get data from simbad
        data_simbad = self.query_obs(identifier)

        # Clean data
        data_simbad = self.clean_obs(data_simbad)

        # Gaia Ids
        gaia_ids = data_simbad["GaiaDR3"].dropna().unique()
        gaia_ids = [r.replace("GaiaDR3", "") for r in gaia_ids]
        data_simbad["GaiaDR3"] = gaia_ids

        # Make gaia condition to get data only for those gaia ids
        gaia_condition = f"gaiadr3.gaia_source{'_lite' if lite else ''}.source_id IN ({', '.join(map(str, gaia_ids))})" + (f" AND {gaia_condition}" if gaia_condition != "" else "")

        gaia_columns = ["source_id"] + gaia_columns

        # Get data from gaia
        fgq = FindGaiaQuery(columns = gaia_columns, path = self.path, proxy = self.proxy, verbose = self.verbose, name = self.filename, lite = lite)
        data_gaia = fgq.query_obs(gaia_condition)

        # Merge data (every simbad columns on the left, every gaia columns on the right, which already correspond to simbad 'GaiaDR3')
        data = pd.merge(data_simbad, data_gaia, left_on='GaiaDR3', right_on='source_id')

        # Drop "source_id" column as it is the same as "GaiaDR3"
        data = data.drop(columns=['source_id'])

        # Save observations
        self.save_obs(data)

def main() -> int:
    """
    Main function used when the script is called from a command line
    """
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('-id', required = True, help = "Simbad identifier of the object to query, or list of identifiers to query.")
    parser.add_argument('-col', type = str, required = False, help = "Columns to retreive from simbad, in addition to the default columns 'ident.id'. Columns must be defined as 'column1, column2, ...'", default = "")
    parser.add_argument('-v', type = int, required = False, help = "Verbose", default = 0)
    parser.add_argument('-d', type = str, required = False, help = "Working directory", default = None)
    parser.add_argument('-n', type = str, required = False, help = "Name of the output file", default = None)
    parser.add_argument('-proxy', type = str, required = False, help = "Proxy to use host:port", default = None)

    # Get arguments value
    args = parser.parse_args()
    ident = args.id.split(',')
    columns = args.col.split(',') if args.col != "" else ""
    verbose = args.v
    path = args.d
    name = args.n

    if args.proxy != None:
        proxy = (args.proxy.split(':')[0], int(args.proxy.split(':')[1]))
    else:
        proxy = None

    fsimbad = FindSimbad(path = path, proxy = proxy, verbose = verbose, name = name, columns = columns)
    test = fsimbad.get_obs(ident)

    return 0

if __name__ == '__main__':
    sys.exit(main())
