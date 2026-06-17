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

def _compact_values(values: list) -> object:
    values = [value for value in values if pd.notna(value)]
    if len(values) == 0:
        return np.nan

    unique_values = list(dict.fromkeys(values))
    if len(unique_values) == 1:
        return unique_values[0]
    return unique_values

def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    return [value]

class FindSimbad():
    """
    This class contains tools to query Simbad and retreive some data given an object name.
    """
    
    def __init__(self, columns: str = "", mag: str = "", path: str = None, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None) -> None:
        """
        Initialize the class

        Args:
            columns (str): 
                Single column or list of columns to retreive. Columns must be defined as ["column1", "column2", ...]
            mag (str): 
                Magnitude column to retreive. Must be defined as ["bandname", "bandname2", ...]. Mag error are automatically retreived.
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
        extra_joins = ""

        if mag != "":
            # mag_column = mag.strip()
            extra_joins = """\n LEFT OUTER JOIN flux ON flux.oidref = basic.oid\n
                            LEFT OUTER JOIN filter on filter.filtername = flux.filter\n"""

            self.extra_query = f"""AND filter.filtername IN ({', '.join([f"'{band.strip()}'" for band in mag])})"""
            self.mag = mag #mag_column.split(',')
            mag_columns = ["filter.filtername", "flux.flux", "flux.flux_err"]
        else:
            self.extra_query = ""
            self.mag = []
            mag_columns = []

        if type(columns) == list:
            # user_columns = ', '.join(columns)
            columns = [col.strip() for col in columns]
            query_columns = ','.join(base_columns + columns + mag_columns)

            non_basic_columns = [col.split('.')[0] for col in columns if not col.startswith("basic.")]
            non_basic_columns = np.unique(non_basic_columns)

            if len(non_basic_columns) > 0:
                extra_joins += "\n ".join([f"LEFT OUTER JOIN {col} ON {col}.oidref = basic.oid" for col in non_basic_columns])

            self.query = f"""SELECT {query_columns} 
                            FROM basic 
                            LEFT OUTER JOIN ident ON ident.oidref = basic.oid 
                            LEFT OUTER JOIN ids ON ids.oidref = ident.oidref
                            {extra_joins}
                            WHERE """
        else:
            query_columns = ", ".join(base_columns) + (", " + columns) * (columns != "") + (", " + mag_columns) * (len(self.mag) > 0)
            self.query = f"""SELECT {query_columns} 
                            FROM basic 
                            LEFT OUTER JOIN ident ON ident.oidref = basic.oid 
                            LEFT OUTER JOIN ids ON ids.oidref = ident.oidref 
                            {extra_joins}
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
            identifier = [id.strip() for id in identifier]
            query = " OR ".join([f"(ident.id = '{id}' {self.extra_query})" for id in identifier])
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

        # Clean duplicates due to one row per magnitude for simbad query
        if "filtername" in cleaned_data.columns and len(self.mag) > 0:
            # Keep as grouping keys all columns except the magnitude triplet
            key_cols = [c for c in cleaned_data.columns if c not in ["filtername", "flux", "flux_err"]]

            pivot = cleaned_data.pivot_table(
                index=key_cols,
                columns="filtername",
                values=["flux", "flux_err"],
                aggfunc="first"
            )

            # Flatten MultiIndex columns: ('flux','J') -> 'J', ('flux_err','J') -> 'J_err'
            pivot.columns = [
                f"{band}" if val == "flux" else f"{band}_err"
                for val, band in pivot.columns
            ]

            new_cleaned_data = pivot.reset_index()

            # Order columns: keys then bands in the order given by self.mag (if present)
            band_cols = [c for band in self.mag for c in (band, f"{band}_err")]
            ordered = [c for c in key_cols + band_cols if c in new_cleaned_data.columns]
            new_cleaned_data = new_cleaned_data[ordered]
        else:
            new_cleaned_data = cleaned_data


        for col in new_cleaned_data.columns:
            if isinstance(new_cleaned_data[col].iloc[0], list):
                new_cleaned_data[col] = new_cleaned_data[col].apply(lambda x: _compact_values(x) if isinstance(x, list) else x)

        return new_cleaned_data
        
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

    def get_obs(self, identifier, return_data: bool = False) -> None:
        """
        Complete function to get the data from simbad

        Args:
            identifier (str): Object name to query, or list of object names to query. If list, object must be defined as ["object1", "object2", ...]
            return_data (bool): Whether to return the data or save it directly. Default is False.
        """

        # Get data
        data = self.query_obs(identifier)

        # Clean data
        data = self.clean_obs(data)

        if return_data:
            return data
        else:
            # Save observations
            self.save_obs(data)

    def convert_str_to_float(self, data: pd.DataFrame):
        """
        Convert columns in the DataFrame that are strings but represent numeric values to float.

        Args:
            data (pd.DataFrame): DataFrame to convert

        Returns:
            pd.DataFrame: DataFrame with converted columns
        """
        for column in data.columns:
            if pd.api.types.is_string_dtype(data[column]):
                try:
                    data[column] = pd.to_numeric(data[column], errors='raise')
                except ValueError:
                    # If conversion fails, keep the column as string
                    continue
        return data

    def get_obs_with_gaia(self, identifier, gaia_columns: list, gaia_condition: str = "", lite: bool = True, correct_parallax: bool = False,
                            get_mag_uncertainty: bool = True, return_data: bool = False) -> pd.DataFrame:
        """
        Complete function to get the data from simbad and gaia

        Args:
            identifier (str): Object name to query, or list of object names to query. If list, object must be defined as ["object1", "object2", ...]
            gaia_columns (list): List of columns to retreive from gaia, in addition to the source_id column which is necessary for the merge with simbad data.
            gaia_condition (str): Condition to apply to the gaia query, in addition to the condition on the gaia source_id. 
            lite (bool): Whether to use the lite version of the Gaia catalog. Default is True.
            correct_parallax (bool): Whether to correct the parallax values following the method described in Lindegren et al. (2021). Needed values for the 
                                     correction are automatically retreived, but not saved. Default is False.
            get_mag_uncertainty (bool): Whether to retreive the uncertainty on the magnitude values. If False, only the magnitude values are retreived. Default is True.
            return_data (bool): Whether to return the data or save it directly. Default if False.

        Returns:
            pd.DataFrame: DataFrame with one row per object. Columns with multiple values are stored as lists.
        """

        from .findgaia import FindGaiaQuery

        gaia_columns = [column.strip() for entry in gaia_columns for column in str(entry).split(",") if column.strip()]

        if correct_parallax and "parallax" in gaia_columns:
            if lite:
                lite = False
                if self.verbose:
                    print("Warning: Parallax correction requires querying the full Gaia DR3 catalog.")

        # Get data from simbad
        data_simbad = self.query_obs(identifier)

        # Clean data
        data_simbad = self.clean_obs(data_simbad)

        # Gaia Ids
        gaia_ids = data_simbad["GaiaDR3"].dropna().unique()
        gaia_ids = [r.replace("GaiaDR3", "") for r in gaia_ids]

        object_rows = []
        for obj_id, group in data_simbad.groupby("id", sort=False):
            row = {"id": obj_id}

            for column in group.columns:
                if column == "id":
                    continue

                values = group[column].dropna().unique().tolist()
                if len(values) > 0:
                    row[column] = _compact_values(values)

            object_rows.append(row)

        data_obs = pd.DataFrame(object_rows)

        if len(gaia_ids) == 0:
            return data_obs

        # Make gaia condition to get data only for those gaia ids
        gaia_condition = f"gaiadr3.gaia_source{'_lite' if lite else ''}.source_id IN ({', '.join(map(str, gaia_ids))})" + (f" AND {gaia_condition}" if gaia_condition != "" else "")

        gaia_columns = ["source_id"] + gaia_columns

        # Get data from gaia
        fgq = FindGaiaQuery(columns = gaia_columns, path = self.path, proxy = self.proxy, verbose = self.verbose, name = self.filename, lite = lite, correct_parallax = correct_parallax, get_mag_uncertainty = get_mag_uncertainty)
        data_gaia = fgq.query_obs(gaia_condition)

        if data_gaia.empty:
            return data_obs

        # Add the Gaia data to each object
        for gaia_obj_id in data_gaia["source_id"]:
            for obj_idx, row in data_obs.iterrows():
                gaia_ids_for_object = _as_list(row.get("GaiaDR3", []))
                if f"GaiaDR3{gaia_obj_id}" in gaia_ids_for_object:
                    for column in data_gaia.columns:
                        if column != "source_id":
                            gaia_values = data_gaia[data_gaia["source_id"] == gaia_obj_id][column].dropna().unique().tolist()
                            if len(gaia_values) > 0:
                                data_obs.at[obj_idx, column] = _compact_values(gaia_values)

        data_obs = self.convert_str_to_float(data_obs)

        if return_data:
            return data_obs
        else:
            self.save_obs(data_obs)


    def save_obs(self, data: pd.DataFrame, filename: str = None) -> None:
        """
        Save the data from get_obs_with_gaia to an HDF5 file with hierarchical structure.
        Creates one group per object, with datasets for each column.
        Numeric values (scalars or lists) are stored as float64. Strings stay as strings.

        Args:
            data (pd.DataFrame): DataFrame returned from get_obs_with_gaia
            filename (str, optional): Output file path. Uses self.filename if not provided.
        """

        # Merge duplicate rows for the same object id, if any
        if "id" in data.columns and data["id"].duplicated().any():
            object_rows = []
            for obj_id, group in data.groupby("id", sort=False):
                row = {"id": obj_id}
                for col in group.columns:
                    if col == "id":
                        continue
                    values = group[col].dropna().tolist()
                    if len(values) > 0:
                        row[col] = _compact_values(values)
                object_rows.append(row)
            data = pd.DataFrame(object_rows)

        if filename is None:
            if self.filename:
                filename = self.filename if self.filename.endswith('.hdf5') else f"{self.filename}.hdf5"
            else:
                filename = f"{self.path}/simbad_output.hdf5"
        elif not filename.endswith('.hdf5'):
            filename = f"{filename}.hdf5"

        if self.verbose:
            print(f'Saving data to {filename}...')

        with h5py.File(filename, 'w') as f:
            # Create a group for each object
            for _, row in data.iterrows():
                obj_id = row.get('id', 'unknown')
                obj_group = f.create_group(str(obj_id))
                
                # Store each column as a dataset
                for col in data.columns:
                    if col == 'id':
                        continue
                    
                    value = row[col]
                    
                    # Skip None, NaN, empty strings
                    if value is None or (isinstance(value, str) and value == ''):
                        continue
                    if isinstance(value, float) and np.isnan(value):
                        continue
                    
                    # Handle lists (convert strings to float if possible)
                    if isinstance(value, list):
                        try:
                            # Try to convert to float for numeric values
                            numeric_array = np.array(value, dtype=float)
                            obj_group.create_dataset(col, data=numeric_array)
                        except (ValueError, TypeError):
                            # Keep as string for non-numeric values
                            obj_group.create_dataset(
                                col, 
                                data=np.array(value, dtype=h5py.string_dtype(encoding='utf-8'))
                            )
                    # Handle scalars
                    else:
                        try:
                            # Try to convert string numbers to float
                            if isinstance(value, str):
                                float_val = float(value)
                                obj_group.create_dataset(col, data=float_val)
                            else:
                                # Store numbers as-is
                                obj_group.create_dataset(col, data=value)
                        except (ValueError, TypeError):
                            # Keep as string if conversion fails
                            obj_group.create_dataset(
                                col,
                                data=str(value),
                                dtype=h5py.string_dtype(encoding='utf-8')
                            )

        if self.verbose:
            print('Done!')
            print(f"Saved {len(data)} objects to {filename}")

    def load_obs_with_gaia(self, filename: str = None) -> pd.DataFrame:
        """
        Load data saved with save_obs from an HDF5 file.

        Args:
            filename (str, optional): Path to HDF5 file. Uses self.filename if not provided.

        Returns:
            pd.DataFrame: DataFrame with the loaded data (preserving types: lists as lists, scalars as scalars/floats)
        """
        if filename is None:
            if self.filename:
                filename = self.filename if self.filename.endswith('.hdf5') else f"{self.filename}.hdf5"
            else:
                raise ValueError("No filename provided and self.filename is not set")

        if self.verbose:
            print(f'Loading data from {filename}...')

        data = []
        with h5py.File(filename, 'r') as f:
            # Iterate through each object group
            for obj_id in f.keys():
                obj_group = f[obj_id]
                row = {'id': obj_id}
                
                # Extract all datasets from the group
                for col in obj_group.keys():
                    dataset = obj_group[col]
                    value = dataset[()]
                    
                    # If it's an array, convert to list (for multi-value columns)
                    if isinstance(value, np.ndarray):
                        if value.ndim == 0:
                            # Scalar stored as array - extract the value
                            row[col] = value.item()
                        else:
                            # Array - convert to list
                            row[col] = value.tolist()
                    # If it's bytes (string), decode it
                    elif isinstance(value, bytes):
                        row[col] = value.decode('utf-8')
                    else:
                        row[col] = value
                
                data.append(row)

        result = pd.DataFrame(data)
        
        if self.verbose:
            print('Done!')
            print(f"Loaded {len(result)} objects from {filename}")
        
        return result

def main() -> int:
    """
    Main function used when the script is called from a command line
    """
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('-id', required = True, help = "Simbad identifier of the object to query, or list of identifiers to query.")
    parser.add_argument('-col', type = str, required = False, help = "Columns to retreive from simbad, in addition to the default columns 'ident.id'. Columns must be defined as 'column1, column2, ...'", default = "")
    parser.add_argument('-mag', type = str, required = False, help = "Magnitude bands to retreive from simbad. Must be defined as 'band1, band2, ...'", default = "")
    parser.add_argument('-v', type = int, required = False, help = "Verbose", default = 0)
    parser.add_argument('-d', type = str, required = False, help = "Working directory", default = None)
    parser.add_argument('-n', type = str, required = False, help = "Name of the output file", default = None)
    parser.add_argument('-gaia', type = str, required = False, help = "Columns to retreive from gaia, Must be defined as 'column1, column2, ...'", default = "")
    parser.add_argument('-proxy', type = str, required = False, help = "Proxy to use host:port", default = None)

    # Get arguments value
    args = parser.parse_args()
    ident = args.id.split(',')
    columns = args.col.split(',') if args.col != "" else ""
    magnitudes = args.mag.split(',') if args.mag != "" else ""
    gaia = args.gaia.split(',') if args.gaia != "" else ""
    verbose = args.v
    path = args.d
    name = args.n

    if args.proxy != None:
        proxy = (args.proxy.split(':')[0], int(args.proxy.split(':')[1]))
    else:
        proxy = None

    fsimbad = FindSimbad(path = path, proxy = proxy, verbose = verbose, name = name, columns = columns, mag = magnitudes)
    if gaia != "":
        fsimbad.get_obs_with_gaia(ident, gaia_columns=gaia)
    else:
        fsimbad.get_obs(ident)

    return 0

if __name__ == '__main__':
    sys.exit(main())




"""
Example to get simbad and gaia data for two objects

python3 findsimbad.py -id "HD192660,HD229238" -col "mesFe_H.teff,mesFe_H.log_g" -mag "J,H,K" -gaia "phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, parallax, parallax_error"



"""