# adar

Network coding for automated distributed storage systems

## What is this?

This is my BAdvSci(Hons) research project


## What are the details?

Please see [SPEC.md](SPEC.md)

## Requirements

I assume you have a working Windows installation, with Python 3.10 (or thereabout), and the Projected File System feature enabled

Alternatively, it should also work on a GNU + Linux distribution that has the requirements for FUSE installed and working, along with Python 3.10 (or thereabout)

## Running

To build/run the project:

1. Install `simplenc`

```sh
~/adar $ cd python/simple_nc-main
~/adar/python/simple_nc-main $ pip install .
```

2. Install requirements

```sh
~/adar $ cd python
~/adar/python $ pip install -r requirements.txt
```

For Unix systems (GNU+Linux, macOS), ensure that FUSE is working, e.g. with the `libfuse` library

For Windows systems, enable `Windows Projected File System` in `Turn Windows features on or off`

3. Run the program

```sh
~/adar $ cd python
~/adar/python $ python3 main.py
```

The `mount` directory will present itself for file storage

You can run `adar` on additional computers to pair and connect to them, which will allow the storage to be distributed
