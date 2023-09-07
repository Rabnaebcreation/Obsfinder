import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='obsfinder',
    version='0.7.1',
    author='Barnabé Déforêt',
    author_email='babedef@orange.fr',
    description='Tools to query 2mass and Gaia observatins',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/Rabnaebcreation/Obsfinder',
    entry_points={
        'console_scripts': [
            'findgaia = obsfinder.findgaia:main',
            'newfind2mass = obsfinder.find2mass:main',
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
    ],
)
