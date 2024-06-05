from setuptools import setup
import os

if os.name == 'nt':
    OPTIONS = {}
    EXTRAS = []
else:
    OPTIONS = {'py2app': {
        'resources': './resources',
        'iconfile': f'./resources/QFIcon.icns'
    }}
    EXTRAS = ['py2app']


setup(
    app=['QuantiFish.py'],
    options=OPTIONS,
    setup_requires=EXTRAS,
    install_requires=["scikit-image", "scipy", "pillow", "numpy"],
)
