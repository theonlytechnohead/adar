from simplenc import BinaryCoder


class ReadCoded:
	data: bytes | bytearray = None
	decoder: BinaryCoder = None