from .findgaia import Findgaia
from .find2mass import Find2mass
from .findgaia2mass import Findgaia2mass
import argparse
import sys

class Finder():
    """
    This class contains tools to query the Gaia archive and retreive data from Gaia DR3.
    """
    def __init__(self):
        pass
    
    def get_obs(self, type: str, lvalue: float, bvalue: float, psize: float, path: str = None, proxy: tuple[str, int] = None, verbose: int = 0, name: str = None, pi: int = 1) -> None:
        """
        Initialize the class

        Args:
            type (str):
                Type of query to perform. Can be 'gaia', '2mass' or 'gaia2mass'.
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

        # Define case according to the type of query
        if type == 'gaia':
            self.query = Findgaia(lvalue, bvalue, psize, path, proxy, verbose, name, pi)
        elif type == '2mass':
            self.query = Find2mass(lvalue, bvalue, psize, path, proxy, verbose, name)
        elif type == 'gaia2mass':
            self.query = Findgaia2mass(lvalue, bvalue, psize, path, proxy, verbose, name, pi)
        else:
            raise ValueError(f"Unknown type of query: {type}")
        
def main() -> int:
    """
    Main function used when the script is called from a command line
    """
    # Arguments definition
    parser = argparse.ArgumentParser()
    parser.add_argument('type', type = str, help = "Type of query to perform. Can be 'gaia', '2mass' or 'gaia2mass'")
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

    ftmass = Finder(type=args.type ,lvalue = args.l, bvalue = args.b, path = args.path, psize = args.p, proxy = args.proxy, verbose = args.v, name = args.n)
    ftmass.get_obs()

    return 0

if __name__ == '__main__':
    sys.exit(main())