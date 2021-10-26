import setuptools

setuptools.setup(
        name='getnear',
        version='20020908',
        author='Edward Speyer',
        author_email='getnear@ed.wtf',
        install_requires=['requests', 'tabulate'],
        packages=['getnear'],
        scripts=['scripts/getnear'])
