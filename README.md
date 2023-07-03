# adar

Network coding for automated distributed storage systems

## What is this?

This is my BAdvSci(Hons) research project


## What are the details?

Please see [SPEC.md](SPEC.md)

## Requirements

I assume you have a working Windows installation, with Python 3.10 (or thereabout), and the Projected File System feature enabled

Alternatively, it should also work on a GNU + Linux distribution that has the requirements for FUSE installed and working, along with Python 3.10 (or thereabout)

## Running (from source)

To run the project from source:

1. Clone from GitHub

```sh
~ $ git clone https://github.com/theonlytechnohead/adar.git
```

2. Install `simplenc`

```sh
~ $ cd adar
~/adar $ cd python/simple_nc-main
~/adar/python/simple_nc-main $ pip install .
```

3. Install requirements

```sh
~ $ cd adar
~/adar $ cd python
~/adar/python $ pip install -r requirements.txt
```

For Unix systems (GNU+Linux, macOS), ensure that FUSE is working, e.g. with the `libfuse` library

For Windows systems, enable `Windows Projected File System` in `Turn Windows features on or off`

4. Run the program

```sh
~ $ cd adar
~/adar $ cd python
~/adar/python $ python3 main.py
```

The `mount` directory will present itself for file storage

You can run `adar` on additional computers to pair and connect to them, which will allow the storage to be distributed


## Building

Follow the steps above for running from source, verify all is working as expected.

1. Install `pyinstaller`

```sh
pip install pyinstaller
```

2. Build

```sh
~ $ cd adar
~/adar $ pyinstaller --onefile python/main.py
```

The build output will be located in `~/adar/dist`
