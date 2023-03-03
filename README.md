# Here is RedlineUtils
This is a repository containing scripts that can be used with or without the REDLINE program (D.J Marshall).

## Available program
For the moment, only 2 program can be used:
- ```findgaia.py```: This program send a query to the Gaia archive (https://gea.esac.esa.int/archive/) to recover data from the Gaia DR3 point source catalogue in a zone define by its center and its size.
- ```findgaia.py```: This program send a query to the NASA/IPAC Infrared Science Archive (https://irsa.ipac.caltech.edu) to recover data from the 2MASS point source catalogue in a zone define by its center and its size.

## Usage
Both program work in the same way. Thay take as argments:
- REQUIRED: Zone center Galactic longitude (in degree). Should be contained between 0 and 360. Arguments: ```-l```.
- REQUIRED: Zone center Galactic lattitude (in degree). Should be contained between -90 and 90. Arguments: ```-b```.
- OPTIONAL: Pixel size, i.e size of the zone of interest (in arcminute). Arguments: ```-p```. Default to 5.
- OPTIONAL: Show information (verbose). Arguments: ```-v```. Should be 1 or 0. Default to 1.
- REQUIRED: Directory on whish the data will be saved. Arguments: ```-d```.

Arguments can be placed in any order. Here is an example to get Gaia DR3 data for a zone center in longitude=45°, lattitude=1°, for a pixel zise of 5" and that save the data in the directory ```/home/user/data/```:
```python3 findgaia.py -l 45 -b 5 -p 5 -d /home/user/data/```

The name of the output file have the following form:
- ```observations_gaia_{lattitude}_{longitude}_lim.cat_{size}.bz2``` with ```findgaia.py```
- ```observations_2mass_{lattitude}_{longitude}_lim.cat_{size}.bz2``` with ```find2mass.py```

## Output file format
Both files are ASCII compressed file. They contains the following columns:
- phot_g_n_obs, phot_g_mean_mag, phot_g_mean_flux, phot_g_mean_flux_error, ...
- j_m, j_msigcom, h_m, h_mdiscom, j_m, j_msigcom, glon, glat
 
 Sources with empty columns are automatically removed.

> **Note** 
> While ```find2mass.py``` is almost done, ```findgaia.py``` is not and will be updated frequently.