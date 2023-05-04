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
~/adar $ cd python
~/adar/python $ cd simplenc
~/adar/python/simple_nc-main $ pip install .
```

2. Install requirements

```sh
~/adar $ cd python
~/adar/python $ pip install -r requirements.txt
```

Enable `Windows Projected File System` in `Turn Windows features on or off`

3. Run the program

```sh
~/adar $ cd python
~/adar/python $ python main.py
```

4. Test with the client

```sh
~/adar $ cd python
~/adar/python $ python client.py Hello, world!
```
