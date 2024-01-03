# adar

Network coding for automated distributed storage system: adar

## What is this?

This is my BAdvSci(Hons) research project

Please see [DEFINITIONS.md](DEFINITIONS.md) and/or [SPEC.md](SPEC.md) for further details and descriptions

## I want to implement this myself

Please see [SPEC.md](SPEC.md)

## Requirements

[Python 3.10 or later](https://www.python.org/downloads/)

| For Windows | For Unix (GNU+Linux, macOS) |
| --- | --- |
| [Windows Projected File System](https://learn.microsoft.com/en-us/windows/win32/projfs/projected-file-system) | [Filsystem in Userspace](https://www.kernel.org/doc/html/next/filesystems/fuse.html) (FUSE) as required by [fusepy](https://github.com/fusepy/fusepy) |

## Running (from source)

### 1. Clone from GitHub

```sh
~ $ git clone https://github.com/theonlytechnohead/adar.git
```

### 2. Install `simplenc`

```sh
~ $ cd adar/python/simple_nc-main
~/adar/python/simple_nc-main $ pip install .
```

### 3. Install requirements

```sh
~ $ cd adar/python
~/adar/python $ pip install -r requirements.txt
```

| For Windows systems | For Unix systems (GNU+Linux, macOS) |
| --- | --- |
| enable `Windows Projected File System` in `Turn Windows features on or off`   | ensure that FUSE is working, e.g. with the `libfuse` library |

Alternatively for Windows, in an elevated Powershell prompt (Run as Administrator):

```powershell
PS > Enable-WindowsOptionalFeature -Online -FeatureName Client-ProjFS -NoRestart
```

### 4. Run the program

```sh
~ $ cd adar/python
~/adar/python $ python3 main.py
```

The `mount` directory will present itself for file storage

You can run `adar` on additional computers to pair and connect to them, which will allow the storage to be distributed

## Building (from source)

Follow the steps above for running from source, verify all is working as expected.

### 1. Install `pyinstaller`

```sh
pip install pyinstaller
```

### 2. Build

```sh
~ $ cd adar
~/adar $ pyinstaller --onefile python/main.py
```

The build output will be located in `~/adar/dist`
