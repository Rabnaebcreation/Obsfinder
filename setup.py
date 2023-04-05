# from setuptools import setup
# setup(
#     name='findgaia',
#     version='0.5',
#     entry_points={
#         'console_scripts': [
#             'findgaia = findgaia:main',
#         ],
#     },
#     packages=['obsfinder']
# )cd 

# from distutils.core import setup

# setup(
#     name='Obsfinder',
#     version='0.1.0',
#     author='Barnabé Déforêt',
#     packages=['obsfinder', 'obsfinder.test'],
#     scripts=['obsfinder/findgaia.py', 'obsfinder/find2mass.py'],
#     description='Tool to query 2mass and Gaia observatins',
#     long_description=open('README.md').read(),
#     install_requires=[
#         "numpy>=1.20.3",
#         "pandas>=1.5.3",
#     ],
# )


import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='obsfinder',
    version='0.1.0',
    author='Barnabé Déforêt',
    author_email='babedef@orange.fr',
    description='Too to query 2mass and Gaia observatins',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/mike-huls/toolbox',
    project_urls = {
        "Bug Tracker": "https://github.com/mike-huls/toolbox/issues"
    },
    license='MIT',
    packages=['toolbox'],
    install_requires=['requests'],
)