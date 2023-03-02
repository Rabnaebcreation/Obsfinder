# Here is RedlineUtils
This is a repository containing scripts that can be used with or without the REDLINE program (D.J Marshall).

## Available program
For the moment, only 2 program can be used:
- ```findgaia.py```: This program send a query to the Gaia archive (https://gea.esac.esa.int/archive/) to recover data from the Gaia DR3 point source catalogue in a zone define by its center and its size.
- ```findgaia.py```: This program send a query to the NASA/IPAC Infrared Science Archive (https://irsa.ipac.caltech.edu) to recover data from the 2MASS point source catalogue in a zone define by its center and its size.

## Usage
Both program works in the same way. Thay take as argments:
- $${\color{red} REQUIRED}$$: Zone center Galactic longitude (in degree). Should be contained between 0 and 360. Arguments: ```-l```.
- $${\color{red} REQUIRED}$$: Zone center Galactic lattitude (in degree). Should be contained between -90 and 90. Arguments: ```-b```.
- $${\color{orange} OPTIONAL}$$: Pixel size, i.e size of the zone of interest (in arcminute). Arguments: ```-p```. Default to 5.
- $${\color{orange} OPTIONAL}$$: Show information (verbose). Arguments: ```-v```. Should be 1 or 0. Default to 1.
- $${\color{red} REQUIRED}$$: Directory on whish the data will be saved. Arguments: ```-d```.

Arguments can be placed in any order. Here is an example to get Gaia DR3 data for a zone center in longitude=45°, lattitude=1°, for a pixel zise of 5" and save in the directory ```/home/user/data/```:
<p align="center">
```python3 findgaia.py -l 45 -b 5 -p 5 -d /home/user/data/```
</p>