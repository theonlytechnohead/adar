# Specifications

Here follows the specifications for *adar*, an automated distributed storage system utilising network coding

## Definitions

## adar

"The system"

## network coding

A form of error correction that allows the reconstruction of data from several distinct pieces by utilising the mathematical properties of linear equations

## distributed storage

A system that distributes data over several distinct hardware nodes, but presents itself as a single storage device via an interface, typically a network connection

## automated

Automation includes, but is not limited to: the configuration of system parameters and variables during setup, and the management of system parameters and variables during operation

## Discovery

*adar* is discovered by utilising mDNS or DNS-SD or Bonjour or avahi to allow for a robust, user-friendly mechanism utilising industry standards

The service nane is the device hostname

The service type is `_adar`

The service protocol is `_tcp`

The service server is the FQDN of the device

The service port is `6780`

The service TXT records shall include the following:

| Field | Value |
| ----- | ----- |
| `Description` | `Network coding for automated distributed storage systems` |
| `uuid` | The integer representation of the machine's hardware MAC address |

The service IP addresses must include at least one IPv4 address

The service IP addresses should include at least one IPv6 address

## Pairing

TODO: follow Bluetooth's process probably
