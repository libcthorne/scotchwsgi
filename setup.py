from distutils.core import setup

setup(
    name='scotchwsgi',
    version='0.2.0',
    author='Christopher Thorne',
    author_email='libcthorne@gmail.com',
    url='https://cthorne.me',
    install_requires=[
        'gevent',
    ],
    packages=['scotchwsgi'],
    scripts=[
        'bin/scotchwsgi',
    ],
)
