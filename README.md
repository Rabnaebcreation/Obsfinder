# Here is Obsfinder
This is a repository containing tools to query observations catalogue from 2mass and Gaia.

## Available program
For the moment, only 2 program can be used:
- ```findgaia.py```: This program send a query to the Gaia archive (https://gea.esac.esa.int/archive/) to recover data from the Gaia DR3 point source catalogue in a zone define by its center and its size.
- ```findgaia.py```: This program send a query to the NASA/IPAC Infrared Science Archive (https://irsa.ipac.caltech.edu) to recover data from the 2MASS point source catalogue in a zone define by its center and its size.

## Usage
Both program work in the same way. Thay take as argments:
- REQUIRED: Zone center Galactic longitude (in degree). Should be contained between 0 and 360. Negative value are accepted, as soon as the pixel size allow to have a positive ending value. Argument: ```-l```. 
- REQUIRED: Zone center Galactic lattitude (in degree). Should be contained between -90 and 90. Argument: ```-b```.
- OPTIONAL: Directory on whish the data will be saved. Argument: ```-d```. Empty by default.
- OPTIONAL: Pixel size, i.e size of the zone of interest (in arcminute). Argument: ```-p```. Default to 5.
- OPTIONAL: Show information (verbose). Argument: ```-v```. Should be 1 or 0. Default to 0.
- OPTIONAL : Name of the catalog. Argument: ```-n```. Default to "observations_2mass_{bvalue}_{lvalue}.cat_{psize}"
- OPTIONAL : Toggle hdf5 output file format (1 or 0). Argument: ```-h5```. Default to 0 (ascii).

Arguments can be placed in any order. Here is an example to get Gaia DR3 data for a zone centered at longitude=45°, lattitude=1°, for a pixel zise of 5' and that save the data in the directory ```/home/user/data/```:
```python3 findgaia.py -l 45 -b 5 -p 5 -d /home/user/data/```

```findgaia.py``` can also be directly called within a terminal:
```findgaia -l 45 -b 5 -p 5 -d /home/user/data/```
The same stand for ```find2mass.py```:
```newfind2mass -l 45 -b 5 -p 5 -d /home/user/data/```

The name of the output file have the following form:
- ```observations_gaia_{latitude}_{longitude}_{size}.dat``` with ```findgaia.py```
- ```observations_2mass_{latitude}_{longitude}_{size}.dat``` with ```find2mass.py```

## Output file format
Both files are either ascii or hdf5 files. They contains the following columns/datasets:
- Gaia: BP, BP_err, G, G_err, RP, RP_err, l, b
- 2mass: J, J_err, H_m, H_err, J_m, J_err, l, b
 
 Sources with any empty column are automatically removed.

## Installation
This package can by installed via pip:
```pip install git+https://github.com/Rabnaebcreation/Obsfinder.git```
