import setuptools

setuptools.setup(
        name='getnear',
        version='20020905',
        author='Edward Speyer',
        author_email='getnear@ed.wtf',
        install_requires=['requests'],
        packages=['getnear'],
        scripts=['scripts/getnear'])
