from setuptools import setup, find_packages


setup(
    author='Marcin Kurczewski',
    author_email='rr-@sakuya.pl',
    name='ftpfs',
    long_description='FTP over FUSE',
    version='0.2',
    url='https://github.com/rr-/ftpfs',
    packages=find_packages(),

    entry_points={'console_scripts': ['ftpfs = ftpfs.__main__:main']},
    install_requires=['fusepy'],

    classifiers=[
        'Environment :: Console',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Filesystems',
        'Topic :: Internet :: File Transfer Protocol (FTP)',
    ])
