import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='obsfinder',
    version='1.5.0',
    author='Barnabé Déforêt',
    author_email='babedef@orange.fr',
    description='Tools to query 2mass and Gaia observations',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/Rabnaebcreation/Obsfinder',
    entry_points={
        'console_scripts': [
            'pyfindgaia = obsfinder.findgaia:main',
            'pyfind2mass = obsfinder.find2mass:main',
            'pyfindgaia2mass = obsfinder.findgaia2mass:main',
            'pyfinder = obsfinder.finder:main',
        ],
    },
    packages=['obsfinder'],
    license='MIT',
    install_requires=[
        "numpy>=1.20.3",
        "pandas>=1.5.3",
        "pathlib>=1.0.1",
        "h5py>=3.8.0",
        "tables>=3.8.0",
        "gaiadr3-zeropoint>=0.0.5"
    ],
)
